"""Tests for cloudless.agent — Agent base class + @cloudless.agent decorator (Q10)."""
from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

import cloudless
from cloudless.agent import Agent, AgentMetadata, agent


class _NoopAgent(Agent):
    """Concrete subclass used for decorator tests."""

    async def query(self, ctx: Any, prompt: str) -> AsyncIterator[cloudless.Chunk]:
        yield cloudless.TextChunk(text="pong")


class TestDecoratorBasics:
    def test_decorator_attaches_metadata(self):
        @agent(name="example")
        class Example(_NoopAgent):
            pass

        assert hasattr(Example, "__cloudless_metadata__")
        m = Example.__cloudless_metadata__
        assert isinstance(m, AgentMetadata)
        assert m.name == "example"
        assert m.interfaces == ("http",)
        assert m.framework is None

    def test_decorator_accepts_all_fields(self):
        @agent(
            name="support",
            framework="langgraph",
            interfaces=["http", "a2a"],
            description="Customer support agent.",
            version="2.1.3",
            tags=["public", "tier-1"],
        )
        class Support(_NoopAgent):
            pass

        m = Support.__cloudless_metadata__
        assert m.name == "support"
        assert m.framework == "langgraph"
        assert m.interfaces == ("http", "a2a")
        assert m.description == "Customer support agent."
        assert m.version == "2.1.3"
        assert m.tags == ("public", "tier-1")

    def test_metadata_is_frozen(self):
        @agent(name="frozen-test")
        class FrozenAgent(_NoopAgent):
            pass

        m = FrozenAgent.__cloudless_metadata__
        with pytest.raises(Exception):
            # frozen dataclass — mutation raises FrozenInstanceError
            m.name = "renamed"  # type: ignore[misc]


class TestDecoratorValidation:
    """The decorator validates eagerly so typos fail at import time, not deploy time."""

    def test_rejects_unknown_interface(self):
        with pytest.raises(ValueError, match="unknown interface"):
            @agent(name="bad", interfaces=["graphql"])  # type: ignore[list-item]
            class Bad(_NoopAgent):
                pass

    def test_rejects_empty_interfaces(self):
        with pytest.raises(ValueError, match="at least one protocol"):
            @agent(name="empty", interfaces=[])
            class Empty(_NoopAgent):
                pass

    def test_rejects_unknown_framework(self):
        with pytest.raises(ValueError, match="unknown framework"):
            @agent(name="bad-fw", framework="autogen")  # type: ignore[arg-type]
            class BadFramework(_NoopAgent):
                pass

    def test_rejects_non_Agent_class(self):
        with pytest.raises(TypeError, match="must inherit from"):
            @agent(name="not-agent")
            class NotAnAgent:  # not subclass of Agent
                pass

    @pytest.mark.parametrize("framework", ["langgraph", "strands", "adk", "maf", None])
    def test_accepts_all_valid_frameworks(self, framework):
        @agent(name="ok", framework=framework)
        class OK(_NoopAgent):
            pass
        assert OK.__cloudless_metadata__.framework == framework


class TestInterfaceCombinations:
    """Q6: declarative interfaces; deploy planner reads these to enumerate runtimes."""

    def test_http_only(self):
        @agent(name="x", interfaces=["http"])
        class X(_NoopAgent):
            pass
        assert X.__cloudless_metadata__.interfaces == ("http",)

    def test_a2a_only(self):
        @agent(name="x", interfaces=["a2a"])
        class X(_NoopAgent):
            pass
        assert X.__cloudless_metadata__.interfaces == ("a2a",)

    def test_http_plus_a2a(self):
        # On AWS this becomes 2 runtimes from one source; on GCP, 1 runtime
        @agent(name="x", interfaces=["http", "a2a"])
        class X(_NoopAgent):
            pass
        assert set(X.__cloudless_metadata__.interfaces) == {"http", "a2a"}

    def test_all_four_protocols(self):
        @agent(name="x", interfaces=["http", "a2a", "mcp", "ag-ui"])
        class X(_NoopAgent):
            pass
        assert len(X.__cloudless_metadata__.interfaces) == 4


@pytest.mark.asyncio
async def test_concrete_agent_can_be_subclassed_and_queried():
    """Smoke test that a decorated agent actually runs through `query()`."""

    @agent(name="hello")
    class Hello(_NoopAgent):
        pass

    instance = Hello()
    chunks = [c async for c in instance.query(ctx=None, prompt="hi")]
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert chunks[0].text == "pong"


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.Agent is Agent
        assert cloudless.AgentMetadata is AgentMetadata
        assert cloudless.agent is agent
