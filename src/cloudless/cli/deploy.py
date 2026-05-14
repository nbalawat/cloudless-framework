"""`cloudless deploy <agent>` — read cloudless.yaml, find the agent, deploy."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

import cloudless
from cloudless.adapters.aws.agentcore import AgentCoreDeployer

_console = Console()


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        _console.print(f"[red]✗[/] No cloudless.yaml in {path.parent} — run `cloudless init` first.")
        raise SystemExit(1)
    with path.open() as f:
        return yaml.safe_load(f)


def _discover_agent_class(agent_name: str, agents_dir: Path) -> type:
    """Walk src/agents/*.py for a class with __cloudless_metadata__.name == agent_name."""
    if not agents_dir.is_dir():
        raise FileNotFoundError(f"agents dir not found: {agents_dir}")

    candidates: list[type] = []
    for py_file in agents_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and hasattr(obj, "__cloudless_metadata__"):
                meta = obj.__cloudless_metadata__
                if meta.name == agent_name:
                    candidates.append(obj)

    if not candidates:
        raise LookupError(
            f"No @cloudless.agent class with name={agent_name!r} found in {agents_dir}/*.py"
        )
    if len(candidates) > 1:
        names = [f"{c.__module__}.{c.__name__}" for c in candidates]
        raise LookupError(
            f"Multiple @cloudless.agent classes with name={agent_name!r}: {names}"
        )
    return candidates[0]


def run(
    *,
    agent_name: str,
    region: str = "us-east-1",
    build_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> int:
    """`cloudless deploy <agent>` entrypoint."""
    project_root = (project_root or Path.cwd()).resolve()
    cfg = _load_yaml(project_root / "cloudless.yaml")

    agents_cfg = cfg.get("agents") or {}
    if agent_name not in agents_cfg:
        _console.print(
            f"[red]✗[/] Agent {agent_name!r} not declared in cloudless.yaml agents block. "
            f"Available: {list(agents_cfg)}"
        )
        return 1

    # Per-agent region override
    region = agents_cfg[agent_name].get("region", region)

    # Load the agent class from src/agents/*.py
    src_agents = project_root / "src" / "agents"
    sys.path.insert(0, str(project_root / "src"))
    try:
        agent_class = _discover_agent_class(agent_name, src_agents)
    except (FileNotFoundError, LookupError) as e:
        _console.print(f"[red]✗[/] {e}")
        return 1

    _console.print(f"[bold]Deploying[/] {agent_class.__module__}.{agent_class.__name__}")
    _console.print(f"  region: {region}")
    _console.print(f"  build_dir: {build_dir or '.cloudless/build/' + agent_name.replace('-', '_')}")

    deployer = AgentCoreDeployer(region=region)

    # Read the user's agent source file and pass it as user_agent.py to the build
    agent_module_path = src_agents / f"{agent_class.__module__.split('.')[-1]}.py"
    if agent_module_path.is_file():
        extra_files = {"user_agent.py": agent_module_path.read_text()}
    else:
        extra_files = None

    try:
        result = deployer.deploy(
            agent_class,
            build_dir=(build_dir.resolve() if build_dir else None),
            extra_user_files=extra_files,
        )
    except (FileNotFoundError, RuntimeError) as e:
        _console.print(f"[red]✗ deploy failed:[/] {e}")
        return 2

    _console.print()
    _console.print("[green]✓ deployed[/]")
    _console.print(f"  runtime ARN:   {result.runtime_arn}")
    _console.print(f"  endpoint ARN:  {result.endpoint_arn}")
    _console.print(f"  ECR URI:       {result.ecr_uri}")
    _console.print(f"  protocol:      {result.protocol}")
    _console.print(f"  build dir:     {result.build_dir}")
    return 0
