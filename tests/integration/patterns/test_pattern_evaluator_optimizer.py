"""Pattern 6 — Evaluator-optimizer (critic loop) with HITL.

A generator agent produces a draft. A critic agent scores it. If the
score is below threshold, the generator revises using the critique. The
loop runs up to MAX_ITERATIONS; if no convergence, pause for human.

To keep the test deterministic-ish, we use real Bedrock for the generator
but a stubbed critic that approves after exactly N iterations. The
production pattern is the same shape with real critic LLM calls.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from tests.integration.patterns._harness import (
    complete_pause,
    drain,
    fast_llm,
    find_pause,
)

import cloudless
from cloudless.chunks import Chunk, FinalChunk, PauseChunk, TextChunk
from cloudless.runtime.tasks import pause, reset_store

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


MAX_ITERATIONS = 3


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


class _DeterministicCritic:
    """Stub critic. Approves at the configured iteration; otherwise rejects."""

    def __init__(self, approve_at_iteration: int = 2):
        self.approve_at = approve_at_iteration
        self.iter = 0

    async def critique(self, draft: str) -> dict:
        self.iter += 1
        if self.iter >= self.approve_at:
            return {"approved": True, "score": 0.95, "feedback": "good enough"}
        return {
            "approved": False,
            "score": 0.4,
            "feedback": f"iteration {self.iter}: needs more specificity",
        }


@cloudless.agent(name="evaloop-test", interfaces=["http"])
class EvaluatorOptimizerAgent(cloudless.Agent):
    """Inject a critic in __init__ for testability; default to deterministic stub."""

    def __init__(self, critic=None, llm_provider: str = "bedrock"):
        super().__init__()
        self.critic = critic or _DeterministicCritic(approve_at_iteration=2)
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)
        last_feedback = ""
        draft = ""

        for i in range(MAX_ITERATIONS):
            generator_prompt = (
                f"{prompt}\n\n"
                + (f"Prior critique: {last_feedback}\nRevise accordingly." if last_feedback else "")
            )
            draft = await llm.invoke(
                generator_prompt,
                system="Be terse. One short sentence.",
                max_tokens=60,
                ctx=ctx,
            )
            yield TextChunk(text=f"[iter {i + 1}] draft: {draft[:80]}\n")

            critique = await self.critic.critique(draft)
            yield TextChunk(
                text=f"[iter {i + 1}] critique: approved={critique['approved']} "
                f"score={critique['score']:.2f}\n"
            )
            if critique["approved"]:
                yield FinalChunk(state={"draft": draft, "iterations": i + 1})
                return
            last_feedback = critique["feedback"]

        # Loop didn't converge — HITL
        rec = pause(
            agent_name="evaloop-test",
            session_id=ctx.session.id,
            reason=f"critic loop didn't converge in {MAX_ITERATIONS} iterations",
            pending_action={"last_draft": draft, "last_feedback": last_feedback},
        )
        yield PauseChunk(
            resume_token=rec.resume_token,
            reason=rec.reason,
            pending_action=rec.pending_action,
        )


async def test_evaloop_converges_within_max_iterations(provider):
    agent = EvaluatorOptimizerAgent(
        _DeterministicCritic(approve_at_iteration=2),
        llm_provider=provider,
    )
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Write a single-sentence tagline for a CLI tool.")

    assert find_pause(chunks) is None
    final = next((c for c in chunks if isinstance(c, FinalChunk)), None)
    assert final is not None
    assert final.state["iterations"] == 2
    assert final.state["draft"]


async def test_evaloop_pauses_when_no_convergence(provider):
    """Critic that never approves → exhaust iterations → pause."""
    never_approves = _DeterministicCritic(approve_at_iteration=999)
    agent = EvaluatorOptimizerAgent(never_approves, llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Write a tagline.")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "didn't converge" in pause_chunk.reason
    assert "last_draft" in pause_chunk.pending_action
    assert "last_feedback" in pause_chunk.pending_action

    # Human supplies the final draft
    rec = complete_pause(pause_chunk.resume_token, {"final_draft": "Ship it."})
    assert rec.approval["final_draft"] == "Ship it."
