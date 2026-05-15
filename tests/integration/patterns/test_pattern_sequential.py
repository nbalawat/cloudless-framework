"""Pattern 2 — Sequential / pipeline with HITL.

Three agents A→B→C chained:
  drafter:    LLM produces a draft from the prompt
  reviewer:   LLM scores the draft for clarity
  publisher:  records the final text in ctx state

HITL pause between reviewer and publisher: if the reviewer flags
"needs_approval", the agent yields a PauseChunk; on resume with
approved=True, the publisher runs.
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
from cloudless.runtime.tasks import pause, reset_store, resume

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


@cloudless.agent(name="pipeline-test", interfaces=["http"])
class PipelineAgent(cloudless.Agent):
    """Sequential A→B→C with a HITL gate before publish."""

    def __init__(self, llm_provider: str = "bedrock"):
        super().__init__()
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        # Stage A: drafter
        draft = await llm.invoke(
            f"Write a one-sentence answer to: {prompt}",
            system="Be terse. One sentence only.",
            max_tokens=60,
            ctx=ctx,
        )
        yield TextChunk(text=f"[draft] {draft}\n")

        # Stage B: reviewer flags whether human approval is needed
        needs_approval = "$" in prompt or "refund" in prompt.lower()

        if needs_approval:
            rec = pause(
                agent_name="pipeline-test",
                session_id=ctx.session.id,
                reason="financial decision needs human approval",
                pending_action={"draft": draft, "prompt": prompt},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
                expires_at=rec.expires_at,
            )
            return  # halt — resume runs in a separate invocation

        # Stage C: publisher (no HITL needed)
        yield TextChunk(text=f"[published] {draft}\n")
        yield FinalChunk(state={"stage": "published"})


async def test_pipeline_runs_without_hitl_for_safe_prompts(provider):
    """No financial keywords → pipeline runs A→B→C without pausing."""
    agent = PipelineAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "What is the capital of France?")

    assert find_pause(chunks) is None
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "[draft]" in text
    assert "[published]" in text
    assert any(isinstance(c, FinalChunk) for c in chunks)


async def test_pipeline_pauses_for_hitl_then_resumes(provider):
    """Financial prompt → pause; resume with approved=True → publisher runs."""
    agent = PipelineAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Issue a $5,000 refund for order o1")

    # Stage A ran, Stage B paused
    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert pause_chunk.resume_token
    assert "draft" in pause_chunk.pending_action
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "[draft]" in text
    assert "[published]" not in text

    rec = complete_pause(pause_chunk.resume_token, {"approved": True, "by": "alice"})
    assert rec.approval == {"approved": True, "by": "alice"}
    assert rec.pending_action["prompt"] == "Issue a $5,000 refund for order o1"


async def test_pipeline_resume_is_idempotent(provider):
    """Double-resume on the same token returns None on the second call."""
    agent = PipelineAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Issue a $5,000 refund")
    token = find_pause(chunks).resume_token

    rec1 = resume(token, {"approved": True})
    rec2 = resume(token, {"approved": True})
    assert rec1 is not None
    assert rec2 is None
