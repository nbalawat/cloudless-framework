"""Unit tests for `cloudless dev` — no cloud calls."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

import cloudless
from cloudless.cli import dev as dev_cmd


@cloudless.agent(name="testbed-agent")
class _TestbedAgent(cloudless.Agent):
    async def query(self, ctx, prompt: str) -> AsyncIterator[cloudless.Chunk]:
        yield cloudless.TextChunk(text=f"echo:{prompt}")


def _scaffold_project(tmp: Path, agent_file: str) -> Path:
    """Create a minimal valid cloudless-project layout for discovery tests."""
    base = tmp / "demo"
    (base / "src" / "agents").mkdir(parents=True)
    (base / "src" / "agents" / "hello.py").write_text(agent_file)
    (base / "cloudless.yaml").write_text(
        "project: demo\nagents:\n  testbed-agent:\n    cloud: aws\n"
    )
    return base


_AGENT_FILE = '''\
import cloudless

@cloudless.agent(name="testbed-agent")
class TestbedAgent(cloudless.Agent):
    async def query(self, ctx, prompt):
        yield cloudless.TextChunk(text=f"echo:{prompt}")
'''


@pytest.fixture
def project(tmp_path):
    return _scaffold_project(tmp_path, _AGENT_FILE)


class TestDiscovery:
    def test_finds_agent_by_name(self, project):
        cls = dev_cmd._discover_agent_class("testbed-agent", project / "src" / "agents")
        assert cls.__cloudless_metadata__.name == "testbed-agent"

    def test_raises_on_missing(self, project):
        with pytest.raises(LookupError, match="No @cloudless.agent class"):
            dev_cmd._discover_agent_class("does-not-exist", project / "src" / "agents")

    def test_raises_on_missing_dir(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            dev_cmd._discover_agent_class("x", tmp_path / "nope")


class TestBuildLocalApp:
    def test_returns_app_with_entrypoint(self):
        app = dev_cmd._build_local_app(_TestbedAgent)
        # BedrockAgentCoreApp exposes the underlying Starlette app via .app
        # OR is callable as ASGI itself; both indicate a usable web app.
        assert hasattr(app, "run") or hasattr(app, "app") or callable(app)


class TestRunSmoke:
    """`run(block=False)` returns 0 after wiring; doesn't start uvicorn."""

    def test_run_non_blocking_returns_zero(self, project):
        rc = dev_cmd.run(
            agent_name="testbed-agent",
            project_root=project,
            block=False,
        )
        assert rc == 0

    def test_run_unknown_agent_returns_1(self, project):
        rc = dev_cmd.run(
            agent_name="not-there",
            project_root=project,
            block=False,
        )
        assert rc == 1
