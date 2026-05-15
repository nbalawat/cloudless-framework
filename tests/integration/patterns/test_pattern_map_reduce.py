"""Pattern 9 — Map-reduce with HITL.

Map: classify each item in a list (parallel sub-agent calls).
Reduce: summarize the classifications into a single output.
HITL: pause for approval of the reduced summary before downstream
action.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from tests.integration.patterns._harness import (
    complete_pause,
    drain,
    fast_llm,
    find_pause,
)

import cloudless
from cloudless.chunks import Chunk, PauseChunk, TextChunk
from cloudless.runtime.tasks import pause, reset_store

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


@cloudless.agent(name="map-reduce-test", interfaces=["http"])
class MapReduceAgent(cloudless.Agent):
    def __init__(self, items: list[str] | None = None, llm_provider: str = "bedrock"):
        super().__init__()
        self.items = items or []
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        # Map: classify each item
        async def _classify(item: str) -> dict:
            label = await llm.invoke(
                item,
                system=(
                    "Classify the input as 'positive' or 'negative'. "
                    "Reply with ONLY that one word, lowercase."
                ),
                max_tokens=4,
                ctx=ctx,
            )
            return {
                "item": item,
                "label": "positive" if "positive" in label.lower() else "negative",
            }

        mapped = await asyncio.gather(*[_classify(it) for it in self.items])
        yield TextChunk(text=f"[mapped] {len(mapped)} items\n")

        # Reduce: summary counts
        pos = sum(1 for m in mapped if m["label"] == "positive")
        neg = len(mapped) - pos
        summary = {"positive": pos, "negative": neg, "total": len(mapped)}
        yield TextChunk(text=f"[reduced] {summary}\n")

        # HITL: approve the summary before publishing
        rec = pause(
            agent_name="map-reduce-test",
            session_id=ctx.session.id,
            reason="approve aggregated report",
            pending_action={"mapped": mapped, "summary": summary},
        )
        yield PauseChunk(
            resume_token=rec.resume_token,
            reason=rec.reason,
            pending_action=rec.pending_action,
        )


async def test_map_reduce_with_three_items(provider):
    items = [
        "I love this product, it's amazing!",
        "Terrible experience, would not recommend.",
        "Great quality and fast shipping.",
    ]
    agent = MapReduceAgent(items=items, llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    summary = pause_chunk.pending_action["summary"]
    assert summary["total"] == 3
    # 2 positive items + 1 negative — assert at least the totals add up
    assert summary["positive"] + summary["negative"] == 3
    assert len(pause_chunk.pending_action["mapped"]) == 3


async def test_map_reduce_resume_carries_summary(provider):
    items = ["good", "bad"]
    agent = MapReduceAgent(items=items, llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "")
    pause_chunk = find_pause(chunks)

    rec = complete_pause(
        pause_chunk.resume_token,
        {"approved": True, "publish_to": "slack"},
    )
    assert rec.approval == {"approved": True, "publish_to": "slack"}
    assert rec.pending_action["summary"]["total"] == 2


async def test_map_reduce_concurrent_map_step(provider):
    """Verify the map step runs in parallel via relative speedup vs. serial."""
    import asyncio
    import time

    llm = fast_llm(provider)

    async def _classify(item: str) -> str:
        return await llm.invoke(
            item,
            system="Classify as 'positive' or 'negative'. One word only.",
            max_tokens=4,
        )

    items = ["good a", "bad b", "good c", "bad d"]

    t0 = time.perf_counter()
    for it in items:
        await _classify(it)
    serial_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    await asyncio.gather(*[_classify(it) for it in items])
    parallel_elapsed = time.perf_counter() - t0

    speedup = serial_elapsed / max(parallel_elapsed, 0.001)
    assert speedup > 1.3, (
        f"no concurrency speedup: serial={serial_elapsed:.2f}s "
        f"parallel={parallel_elapsed:.2f}s (speedup={speedup:.2f}x)"
    )
