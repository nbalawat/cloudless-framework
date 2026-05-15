"""Pattern 4 — Parallel / fan-out with HITL.

Three reviewer LLM calls run concurrently via asyncio.gather. Each scores
the prompt yes/no. If consensus is unanimous, the agent proceeds. If
reviewers disagree, the agent pauses for a human tiebreaker.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

import cloudless
from cloudless.chunks import Chunk, FinalChunk, PauseChunk, TextChunk
from cloudless.runtime.tasks import pause, reset_store

from tests.integration.patterns._harness import (
    aws_available,
    complete_pause,
    drain,
    fast_llm,
    find_pause,
    gcp_available,
    provider,
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


@cloudless.agent(name="parallel-test", interfaces=["http"])
class ParallelReviewAgent(cloudless.Agent):
    def __init__(self, llm_provider: str = "bedrock"):
        super().__init__()
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        async def _review(perspective: str) -> str:
            return await llm.invoke(
                prompt,
                system=(
                    f"You are a {perspective} reviewer. Answer the user's "
                    "yes/no question with ONLY 'yes' or 'no', lowercase."
                ),
                max_tokens=4,
                ctx=ctx,
            )

        # Fan out
        results = await asyncio.gather(
            _review("legal"),
            _review("security"),
            _review("product"),
        )
        yield TextChunk(text=f"[reviewers] {results}\n")

        # Normalize
        yeses = sum(1 for r in results if "yes" in r.lower())
        nos = sum(1 for r in results if "no" in r.lower())

        if yeses >= 2 and nos == 0:
            yield TextChunk(text="[consensus] approve\n")
            yield FinalChunk(state={"decision": "approve"})
            return
        if nos >= 2 and yeses == 0:
            yield TextChunk(text="[consensus] reject\n")
            yield FinalChunk(state={"decision": "reject"})
            return

        # Disagreement → HITL
        rec = pause(
            agent_name="parallel-test",
            session_id=ctx.session.id,
            reason=f"reviewers disagreed: yes={yeses} no={nos}",
            pending_action={"raw_reviews": results},
        )
        yield PauseChunk(
            resume_token=rec.resume_token,
            reason=rec.reason,
            pending_action=rec.pending_action,
        )


async def test_parallel_unanimous_yes_does_not_pause(provider):
    """A clear-yes question gets three yeses → no pause."""
    agent = ParallelReviewAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Is 2 + 2 equal to 4? Answer yes or no.")
    assert find_pause(chunks) is None
    # Final decision should be approve
    final = next((c for c in chunks if isinstance(c, FinalChunk)), None)
    assert final is not None
    assert final.state["decision"] == "approve"


async def test_parallel_pauses_when_reviewers_disagree(aws_available, monkeypatch):
    """Stub the LLM so reviewers split 2/1 → pause."""

    class _SplitLLM:
        def __init__(self):
            self._n = 0
        async def invoke(self, prompt, **kw):
            self._n += 1
            return "yes" if self._n <= 2 else "no"  # 2 yes, 1 no

    import cloudless as _cl
    monkeypatch.setattr(_cl, "LLM", lambda *a, **kw: _SplitLLM())

    agent = ParallelReviewAgent()
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "ambiguous question")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "disagreed" in pause_chunk.reason
    rec = complete_pause(pause_chunk.resume_token, {"override": "approve"})
    assert rec.approval == {"override": "approve"}


async def test_parallel_fans_out_concurrently(provider):
    """Verify parallel reviews actually overlap — relative speedup vs. serial.

    Both Bedrock (boto3) and Vertex (google-genai) sync clients are now
    off-loaded via asyncio.to_thread, so asyncio.gather yields real
    wall-clock speedup.
    """
    import asyncio
    import time

    llm = fast_llm(provider)

    async def _one_review():
        return await llm.invoke(
            "Is the sky blue? Answer yes or no.",
            system="Reply with exactly 'yes' or 'no'.",
            max_tokens=4,
        )

    N = 4
    t0 = time.perf_counter()
    for _ in range(N):
        await _one_review()
    serial_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    await asyncio.gather(*[_one_review() for _ in range(N)])
    parallel_elapsed = time.perf_counter() - t0

    speedup = serial_elapsed / max(parallel_elapsed, 0.001)
    assert speedup > 1.3, (
        f"no concurrency speedup: serial={serial_elapsed:.2f}s "
        f"parallel={parallel_elapsed:.2f}s (speedup={speedup:.2f}x)"
    )
