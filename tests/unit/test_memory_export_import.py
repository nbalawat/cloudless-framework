"""Unit tests for Memory.export_facts + import_facts."""
from __future__ import annotations

import pytest

import cloudless

pytestmark = [pytest.mark.asyncio]


async def test_export_then_import_round_trips_in_memory():
    """Round-trip: write events to one Memory, export, import to another."""
    src = cloudless.Memory()
    dst = cloudless.Memory()
    scope = "user:1"

    await src.add_event(scope=scope, role="user", content="hello")
    await src.add_event(scope=scope, role="assistant", content="hi back")
    await src.add_event(scope=scope, role="user", content="bye")

    exported = await src.export_facts(scope=scope, limit=100)
    assert len(exported) == 3
    assert exported[0]["role"] == "user"
    assert exported[0]["content"] == "hello"
    assert "timestamp" in exported[0]
    assert "id" in exported[0]

    n_imported = await dst.import_facts(records=exported)
    assert n_imported == 3
    events = await dst.list_events(scope=scope)
    contents = sorted(e.content for e in events)
    assert contents == sorted(["hello", "hi back", "bye"])


async def test_export_facts_respects_limit():
    src = cloudless.Memory()
    for i in range(5):
        await src.add_event(scope="user:1", role="user", content=f"msg-{i}")
    exported = await src.export_facts(scope="user:1", limit=3)
    assert len(exported) <= 3


async def test_import_facts_requires_scope():
    """Records without scope and no default_scope should error."""
    dst = cloudless.Memory()
    with pytest.raises(ValueError, match="scope"):
        await dst.import_facts(
            records=[{"role": "user", "content": "x"}],
        )


async def test_import_facts_default_scope_fallback():
    """default_scope is used when records omit scope."""
    dst = cloudless.Memory()
    n = await dst.import_facts(
        records=[{"role": "user", "content": "x"}],
        default_scope="user:fallback",
    )
    assert n == 1
    events = await dst.list_events(scope="user:fallback")
    assert events[0].content == "x"
