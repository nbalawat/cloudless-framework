"""Tests for cloudless.runtime.context — the per-invocation Context Protocol."""
from __future__ import annotations

import cloudless
from cloudless.runtime import (
    Context,
    InMemoryContext,
)


class TestInMemoryContext:
    def test_satisfies_context_protocol(self):
        ctx = InMemoryContext(session_id="x")
        assert isinstance(ctx, Context)  # runtime_checkable Protocol

    def test_session_id(self):
        ctx = InMemoryContext(session_id="my-session")
        assert ctx.session.id == "my-session"

    def test_default_user_is_None(self):
        assert InMemoryContext().user is None

    def test_cost_tracker_default_zero(self):
        ctx = InMemoryContext()
        # session_total_usd is async
        assert ctx.cost is not None

    async def test_session_total_usd_returns_zero(self):
        ctx = InMemoryContext()
        assert await ctx.cost.session_total_usd() == 0.0

    def test_cost_attribute(self):
        ctx = InMemoryContext()
        ctx.cost.attribute(team="customer-success", project="onboarding")
        # InMemoryCostTracker records on the underlying object
        assert ctx.cost.attribution == {  # type: ignore[attr-defined]
            "team": "customer-success",
            "project": "onboarding",
        }

    def test_cost_record_llm_call(self):
        ctx = InMemoryContext()
        ctx.cost.record_llm_call(
            model="us.amazon.nova-micro-v1:0",
            input_tokens=10,
            output_tokens=5,
        )
        calls = ctx.cost.llm_calls  # type: ignore[attr-defined]
        assert len(calls) == 1
        assert calls[0]["model"] == "us.amazon.nova-micro-v1:0"
        assert calls[0]["input_tokens"] == 10

    async def test_peer_returns_stub_with_canned_response(self):
        ctx = InMemoryContext(peer_responses={"orders": "shipped"})
        peer = ctx.peer("orders")
        result = await peer.call("status of order #1")
        assert result == "shipped"
        # Each call is recorded for assertion
        assert len(peer.calls) == 1  # type: ignore[attr-defined]
        assert peer.calls[0]["prompt"] == "status of order #1"  # type: ignore[attr-defined]

    async def test_peer_with_no_canned_response_returns_stub_string(self):
        ctx = InMemoryContext()
        peer = ctx.peer("anything")
        result = await peer.call("hi")
        assert "stub peer anything" in str(result)

    def test_peer_same_name_returns_same_client(self):
        ctx = InMemoryContext()
        a = ctx.peer("orders")
        b = ctx.peer("orders")
        assert a is b


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.Context is Context
        assert cloudless.InMemoryContext is InMemoryContext

    def test_module_imports(self):
        # The Protocols are importable for type-narrowing
        for name in ("Context", "Session", "User", "CostTracker", "PeerClient"):
            assert name in dir(cloudless.runtime)
