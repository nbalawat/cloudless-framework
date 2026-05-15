"""Verify _CloudlessGCPAgent exposes stream_query() and register_operations()."""
from __future__ import annotations

import pytest


def test_stream_query_exists_on_wrapper():
    from cloudless.adapters.gcp.agent_runtime import _CloudlessGCPAgent
    assert hasattr(_CloudlessGCPAgent, "stream_query")
    assert hasattr(_CloudlessGCPAgent, "query")


def test_register_operations_includes_stream():
    """Agent Engine introspects register_operations() to know which methods
    are streamable. Our wrapper must declare stream_query under 'stream'."""
    from cloudless.adapters.gcp.agent_runtime import _CloudlessGCPAgent
    # _CloudlessGCPAgent.__init__ needs an agent_class — pass a minimal stub
    class _MinAgent:
        async def query(self, ctx, prompt):
            yield None

    wrapper = _CloudlessGCPAgent.__new__(_CloudlessGCPAgent)
    wrapper.agent_class = _MinAgent
    ops = wrapper.register_operations()
    assert "" in ops
    assert "query" in ops[""]
    assert "stream" in ops
    assert "stream_query" in ops["stream"]
