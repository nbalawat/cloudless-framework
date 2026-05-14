"""Unit tests for A2A protocol mode artifact generation."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import cloudless
from cloudless.adapters.aws.agentcore import AgentCoreDeployer


@cloudless.agent(name="strands-a2a", framework="strands", interfaces=["a2a"])
class _StrandsA2AAgent(cloudless.Agent):
    async def query(self, ctx, prompt):
        yield cloudless.TextChunk(text="x")


@cloudless.agent(name="lg-http", framework="langgraph", interfaces=["http"])
class _LangGraphHttpAgent(cloudless.Agent):
    async def query(self, ctx, prompt):
        yield cloudless.TextChunk(text="x")


@cloudless.agent(name="lg-a2a-invalid", framework="langgraph", interfaces=["a2a"])
class _LangGraphA2AInvalid(cloudless.Agent):
    async def query(self, ctx, prompt):
        yield cloudless.TextChunk(text="x")


@pytest.fixture
def tmp_build():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


class TestProtocolResolution:
    def test_a2a_interface_picks_a2a_protocol(self, tmp_build):
        d = AgentCoreDeployer()
        d.materialize_artifact(_StrandsA2AAgent, tmp_build,
                               extra_user_files={"user_agent.py": "# stub"})
        assert (tmp_build / ".cloudless_protocol").read_text().strip() == "A2A"

    def test_a2a_dockerfile_exposes_9000(self, tmp_build):
        d = AgentCoreDeployer()
        d.materialize_artifact(_StrandsA2AAgent, tmp_build,
                               extra_user_files={"user_agent.py": "# stub"})
        df = (tmp_build / "Dockerfile").read_text()
        assert "EXPOSE 9000" in df

    def test_a2a_entrypoint_uses_serve_a2a(self, tmp_build):
        d = AgentCoreDeployer()
        d.materialize_artifact(_StrandsA2AAgent, tmp_build,
                               extra_user_files={"user_agent.py": "# stub"})
        ep = (tmp_build / "entrypoint.py").read_text()
        assert "serve_a2a" in ep
        assert "StrandsA2AExecutor" in ep
        assert "BedrockAgentCoreApp" not in ep

    def test_http_interface_picks_http_protocol(self, tmp_build):
        d = AgentCoreDeployer()
        d.materialize_artifact(_LangGraphHttpAgent, tmp_build,
                               extra_user_files={"user_agent.py": "# stub"})
        assert (tmp_build / ".cloudless_protocol").read_text().strip() == "HTTP"
        df = (tmp_build / "Dockerfile").read_text()
        assert "EXPOSE 8080" in df

    def test_a2a_without_strands_is_rejected(self, tmp_build):
        """Per F3 + Q5: A2A requires framework=strands at v0.x."""
        d = AgentCoreDeployer()
        with pytest.raises(ValueError, match="A2A protocol mode requires"):
            d.materialize_artifact(_LangGraphA2AInvalid, tmp_build,
                                   extra_user_files={"user_agent.py": "# stub"})

    def test_explicit_protocol_overrides_metadata(self, tmp_build):
        d = AgentCoreDeployer()
        # HTTP agent forced to deploy as A2A would fail (langgraph != strands)
        # but a Strands HTTP agent forced HTTP should work cleanly.
        @cloudless.agent(name="strands-http-explicit", framework="strands",
                          interfaces=["a2a"])
        class StrandsForcedHttp(cloudless.Agent):
            async def query(self, ctx, prompt):
                yield cloudless.TextChunk(text="x")
        d.materialize_artifact(StrandsForcedHttp, tmp_build,
                               extra_user_files={"user_agent.py": "# stub"},
                               protocol="HTTP")
        assert (tmp_build / ".cloudless_protocol").read_text().strip() == "HTTP"
