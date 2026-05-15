"""Unit tests for Memory.recall_facts_cross_actor + CUSTOM strategy provisioning."""
from __future__ import annotations

import pytest

from cloudless.adapters.aws.memory_provision import ensure_memory_resource


pytestmark = [pytest.mark.asyncio]


# ----------------------------- cross-actor recall ----------------------- #


class _StubBackend:
    """Recall returns canned results per scope."""
    def __init__(self, results: dict):
        self._results = results

    async def recall_facts(self, *, scope, query, top_k=5):
        from cloudless.catalog.memory import MemoryRecord
        out = []
        for text, score in self._results.get(scope, []):
            out.append(MemoryRecord(
                id=f"r-{text}", text=text, scope=scope, score=score,
            ))
        return out


async def test_cross_actor_recall_aggregates_and_ranks():
    import cloudless
    backend = _StubBackend({
        "user:1": [("user 1 fact", 0.7)],
        "user:2": [("user 2 fact", 0.9)],
        "user:3": [],
    })
    m = cloudless.Memory(backend=backend)
    results = await m.recall_facts_cross_actor(
        scopes=["user:1", "user:2", "user:3"],
        query="anything",
        top_k=5,
    )
    # Both results returned, ranked by score desc
    assert len(results) == 2
    assert results[0].text == "user 2 fact"
    assert results[1].text == "user 1 fact"


async def test_cross_actor_recall_resilient_to_one_scope_failure():
    """If one scope raises, the others still produce results."""
    import cloudless

    class _FlakyBackend:
        async def recall_facts(self, *, scope, query, top_k=5):
            from cloudless.catalog.memory import MemoryRecord
            if scope == "user:bad":
                raise RuntimeError("network blip")
            return [MemoryRecord(id="r", text=f"{scope} result", scope=scope, score=0.5)]

    m = cloudless.Memory(backend=_FlakyBackend())
    results = await m.recall_facts_cross_actor(
        scopes=["user:good", "user:bad", "user:other"],
        query="x",
    )
    texts = [r.text for r in results]
    assert "user:good result" in texts
    assert "user:other result" in texts
    assert len(results) == 2


# ----------------------------- CUSTOM strategy ----------------------- #


class _FakeAWSClient:
    def __init__(self):
        self.created = []

    def list_memories(self):
        return {"memories": []}

    def create_memory(self, **kw):
        self.created.append(kw)
        return {"memoryId": "mem-custom-1"}

    def get_memory(self, *, memoryId):
        return {"memory": {"status": "ACTIVE"}}


def test_custom_strategy_provisioning_uses_correct_config():
    client = _FakeAWSClient()
    ensure_memory_resource(
        project="demo", strategy="custom", client=client,
    )
    assert len(client.created) == 1
    strategies = client.created[0]["memoryStrategies"]
    assert "customMemoryStrategy" in strategies[0]
    cfg = strategies[0]["customMemoryStrategy"]
    assert cfg["name"] == "default_custom"
    assert "configuration" in cfg
    assert "semanticOverride" in cfg["configuration"]


def test_semantic_strategy_unchanged():
    """Regression — non-CUSTOM strategies still produce the simple config."""
    client = _FakeAWSClient()
    ensure_memory_resource(project="demo", strategy="semantic", client=client)
    strategies = client.created[0]["memoryStrategies"]
    assert "semanticMemoryStrategy" in strategies[0]
    cfg = strategies[0]["semanticMemoryStrategy"]
    assert cfg == {"name": "default_semantic"}  # simple, no extra fields
