"""`cloudless dev <agent>` — local runner.

Q13: run the user's agent on 127.0.0.1:<port> with the same HTTP contract
the deployed AgentCore Runtime uses. Real LLM calls (Bedrock) so prompt
iteration feels real; in-memory context for sessions/cost/peer-mocks;
no cloud deploy in the loop.

Implementation: wraps the same `BedrockAgentCoreApp` entrypoint we
generate for deploy, but binds locally and serves from the in-process
user agent class (no Docker, no CodeBuild).

Hot reload, --record/--replay cassettes, multi-agent local topology
defer to later milestones — this is the M1 minimum: one agent, real
Bedrock, real HTTP.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console

import cloudless


_console = Console()


def _discover_agent_class(agent_name: str, agents_dir: Path) -> type:
    """Walk src/agents/*.py for a class with __cloudless_metadata__.name == agent_name.

    Mirrors the logic in `cloudless.cli.deploy` so dev/deploy share discovery semantics.
    """
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
                if obj.__cloudless_metadata__.name == agent_name:
                    candidates.append(obj)
    if not candidates:
        raise LookupError(
            f"No @cloudless.agent class named {agent_name!r} in {agents_dir}/*.py"
        )
    if len(candidates) > 1:
        names = [f"{c.__module__}.{c.__name__}" for c in candidates]
        raise LookupError(f"Multiple agents named {agent_name!r}: {names}")
    return candidates[0]


def _build_local_app(agent_class: type, *, session_id: str = "dev-session"):
    """Wrap the user's agent class in a BedrockAgentCoreApp for local serving.

    Returns the app object (.run() to start uvicorn).
    """
    # Defer the import so `cloudless dev --help` works without the AWS extra.
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    instance = agent_class()
    app = BedrockAgentCoreApp()

    @app.entrypoint
    async def invocations(payload: dict, context):  # noqa: ANN001
        prompt = payload.get("prompt", "")
        # Local dev always uses InMemoryContext — Q13. Cloud deploy uses
        # the real Context bridged from AgentCore's RequestContext.
        ctx = cloudless.InMemoryContext(session_id=session_id)
        chunks: list[dict] = []
        async for chunk in instance.query(ctx, prompt):
            chunks.append(chunk.model_dump())
        final_text = "".join(c["text"] for c in chunks if c.get("kind") == "text")
        return {"chunks": chunks, "final_text": final_text,
                "agent": agent_class.__cloudless_metadata__.name}

    return app


def run(
    *,
    agent_name: str,
    host: str = "127.0.0.1",
    port: int = 8080,
    project_root: Optional[Path] = None,
    block: bool = True,
) -> int:
    """Entry point for `cloudless dev <agent>`."""
    project_root = (project_root or Path.cwd()).resolve()

    cfg_path = project_root / "cloudless.yaml"
    if cfg_path.is_file():
        cfg = yaml.safe_load(cfg_path.read_text()) or {}
        if agent_name not in (cfg.get("agents") or {}):
            _console.print(
                f"[yellow]![/] Agent {agent_name!r} not declared in cloudless.yaml. "
                f"Running anyway."
            )

    src_agents = project_root / "src" / "agents"
    src_dir = project_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    try:
        agent_class = _discover_agent_class(agent_name, src_agents)
    except (FileNotFoundError, LookupError) as e:
        _console.print(f"[red]✗[/] {e}")
        return 1

    meta = agent_class.__cloudless_metadata__
    _console.print(f"[bold]cloudless dev[/]  agent=[cyan]{meta.name}[/]  "
                   f"framework=[cyan]{meta.framework or 'custom'}[/]")
    _console.print(f"  serving on  http://{host}:{port}/invocations")
    _console.print(f"  health      http://{host}:{port}/ping")
    _console.print(f"  Ctrl-C to stop")

    app = _build_local_app(agent_class)

    if not block:
        # Used by integration tests that spawn this in a thread.
        return 0

    # `BedrockAgentCoreApp.run()` binds to 0.0.0.0 in containers and
    # 127.0.0.1 locally. We want explicit 127.0.0.1 + custom port.
    import uvicorn
    # The BedrockAgentCoreApp wraps a Starlette app on .app
    starlette_app = getattr(app, "app", None) or app
    uvicorn.run(starlette_app, host=host, port=port, log_level="info")
    return 0
