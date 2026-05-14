"""Operational CLI commands: logs, versions, rollback (Q30, Q18).

All target deployed AgentCore runtimes. Discovery: cloudless.yaml gives
the agent name; we look up the runtime ARN by matching that name (after
the same kebab→snake conversion the deploy adapter does) in the AWS account.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from rich.console import Console
from rich.table import Table

_console = Console()


def _to_runtime_name(agent_name: str) -> str:
    """Mirror the deploy adapter's name normalization."""
    return agent_name.replace("-", "_")


def _find_runtime(client, agent_name: str) -> Optional[dict]:
    """Look up the AgentCore runtime metadata for an agent name."""
    runtime_name = _to_runtime_name(agent_name)
    for r in client.list_agent_runtimes()["agentRuntimes"]:
        if r["agentRuntimeName"] == runtime_name:
            return r
    return None


# --------------------------------------------------------------------- #
# versions
# --------------------------------------------------------------------- #


def versions_command(*, agent_name: str, region: str = "us-east-1") -> int:
    """`cloudless versions <agent>` — list versions + endpoints + which version
    each endpoint points at (Q18)."""
    import boto3
    control = boto3.client("bedrock-agentcore-control", region_name=region)

    rt = _find_runtime(control, agent_name)
    if rt is None:
        _console.print(f"[red]✗[/] No deployed AgentCore runtime for agent {agent_name!r} "
                       f"in {region} (looked for runtime named {_to_runtime_name(agent_name)!r}).")
        return 1

    rid = rt["agentRuntimeId"]
    _console.print(f"[bold]{rt['agentRuntimeName']}[/]  id=[cyan]{rid}[/]  "
                   f"arn=[dim]{rt['agentRuntimeArn']}[/]")

    versions_table = Table(title="Versions")
    versions_table.add_column("version", style="cyan")
    versions_table.add_column("created", style="dim")
    versions_table.add_column("description")
    try:
        ver_resp = control.list_agent_runtime_versions(agentRuntimeId=rid)
        for v in ver_resp.get("agentRuntimes", ver_resp.get("agentRuntimeVersions", [])):
            versions_table.add_row(
                str(v.get("agentRuntimeVersion", "?")),
                str(v.get("createdAt", "?"))[:19],
                (v.get("description") or "")[:60],
            )
    except Exception as e:  # noqa: BLE001
        versions_table.add_row("[red]error[/]", "", str(e)[:80])

    endpoints_table = Table(title="Endpoints (aliases)")
    endpoints_table.add_column("name", style="green")
    endpoints_table.add_column("→ version", style="cyan")
    endpoints_table.add_column("status")
    try:
        ep_resp = control.list_agent_runtime_endpoints(agentRuntimeId=rid)
        for ep in ep_resp.get("runtimeEndpoints", []):
            endpoints_table.add_row(
                ep.get("name", "?"),
                str(ep.get("agentRuntimeVersion") or ep.get("liveVersion") or "?"),
                ep.get("status", "?"),
            )
    except Exception as e:  # noqa: BLE001
        endpoints_table.add_row("[red]error[/]", "", str(e)[:80])

    _console.print(versions_table)
    _console.print(endpoints_table)
    return 0


# --------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------- #


def rollback_command(
    *, agent_name: str, to_version: Optional[str] = None,
    endpoint: str = "DEFAULT", region: str = "us-east-1",
) -> int:
    """`cloudless rollback <agent> [--to vN]` — swap endpoint alias to a prior version.

    If --to is omitted, swap to the second-most-recent version (Q18: "revert
    to the previous default version").
    """
    import boto3
    control = boto3.client("bedrock-agentcore-control", region_name=region)

    rt = _find_runtime(control, agent_name)
    if rt is None:
        _console.print(f"[red]✗[/] No AgentCore runtime for {agent_name!r}.")
        return 1

    rid = rt["agentRuntimeId"]

    target = to_version
    if target is None:
        # Find the 2nd-newest version
        ver_resp = control.list_agent_runtime_versions(agentRuntimeId=rid)
        versions = ver_resp.get("agentRuntimes", ver_resp.get("agentRuntimeVersions", []))
        if len(versions) < 2:
            _console.print(f"[red]✗[/] {agent_name!r} has only {len(versions)} version(s); "
                           f"nothing to roll back to.")
            return 1
        # Sort newest-first; pick index 1 (2nd-newest)
        versions.sort(key=lambda v: v.get("createdAt", ""), reverse=True)
        target = str(versions[1].get("agentRuntimeVersion", ""))
        _console.print(f"[dim]No --to given; rolling back to previous version: {target}[/]")

    _console.print(f"[bold]Rolling back[/]  agent={agent_name}  "
                   f"endpoint={endpoint}  → version={target}")
    try:
        control.update_agent_runtime_endpoint(
            agentRuntimeId=rid,
            endpointName=endpoint,
            agentRuntimeVersion=target,
        )
    except Exception as e:  # noqa: BLE001
        _console.print(f"[red]✗ rollback failed:[/] {e}")
        return 2

    _console.print(f"[green]✓[/] {agent_name} {endpoint} now points at v{target}")
    return 0


# --------------------------------------------------------------------- #
# logs
# --------------------------------------------------------------------- #


def logs_command(
    *, agent_name: str, region: str = "us-east-1",
    since: str = "10m", follow: bool = False, endpoint: str = "DEFAULT",
) -> int:
    """`cloudless logs <agent> [--follow] [--since 1h]` — stream runtime logs."""
    import boto3
    control = boto3.client("bedrock-agentcore-control", region_name=region)
    logs = boto3.client("logs", region_name=region)

    rt = _find_runtime(control, agent_name)
    if rt is None:
        _console.print(f"[red]✗[/] No AgentCore runtime for {agent_name!r}.")
        return 1
    rid = rt["agentRuntimeId"]

    # Per Spike 1 finding, the log group is named:
    #   /aws/bedrock-agentcore/runtimes/<runtime-id>-<endpoint>
    log_group = f"/aws/bedrock-agentcore/runtimes/{rid}-{endpoint}"

    start_ts_ms = int((datetime.now(timezone.utc) - _parse_since(since)).timestamp() * 1000)

    _console.print(f"[bold]cloudless logs[/]  {log_group}  since={since}  "
                   f"follow={follow}")

    while True:
        try:
            resp = logs.filter_log_events(
                logGroupName=log_group, startTime=start_ts_ms, limit=200,
            )
        except logs.exceptions.ResourceNotFoundException:
            _console.print(f"[yellow]![/] log group {log_group} not found — "
                           f"may not have received any logs yet.")
            if not follow:
                return 0
            time.sleep(3)
            continue
        except Exception as e:  # noqa: BLE001
            _console.print(f"[red]✗ logs error:[/] {e}")
            return 2

        new_events = resp.get("events", [])
        for e in new_events:
            ts = datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc)
            print(f"{ts.isoformat()}  {e['message'].rstrip()}")
            start_ts_ms = max(start_ts_ms, e["timestamp"] + 1)

        if not follow:
            return 0
        time.sleep(2)


def _parse_since(s: str) -> timedelta:
    """Parse '10m', '1h', '24h', '7d' into a timedelta."""
    if s.endswith("m"):
        return timedelta(minutes=int(s[:-1]))
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    raise ValueError(f"Unknown --since format: {s!r}. Use e.g. 10m, 1h, 24h, 7d.")
