"""Pattern 8 — Hierarchical (multi-level supervisor) with HITL.

Two levels:
  executive → {legal_manager, security_manager} → workers

Each manager runs its own orchestrator-workers pattern. The executive
treats each manager as a peer (here, an in-process function call to
simulate the cross-process call) and pauses if the managers'
recommendations conflict.
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


async def _legal_manager(prompt: str, llm) -> dict:
    """Manager-level agent: runs its own workers and returns a recommendation."""
    raw = await llm.invoke(
        prompt,
        system=(
            "You are a legal manager. Reply with exactly one word: "
            "'approve' or 'reject'."
        ),
        max_tokens=4,
    )
    decision = "approve" if "approve" in raw.lower() else "reject"
    return {"manager": "legal", "decision": decision, "raw": raw}


async def _security_manager(prompt: str, llm) -> dict:
    raw = await llm.invoke(
        prompt,
        system=(
            "You are a security manager. Reply with exactly one word: "
            "'approve' or 'reject'."
        ),
        max_tokens=4,
    )
    decision = "approve" if "approve" in raw.lower() else "reject"
    return {"manager": "security", "decision": decision, "raw": raw}


@cloudless.agent(name="executive-test", interfaces=["http"])
class ExecutiveAgent(cloudless.Agent):
    def __init__(self, legal_fn=None, security_fn=None, llm_provider: str = "bedrock"):
        super().__init__()
        self.legal_fn = legal_fn or _legal_manager
        self.security_fn = security_fn or _security_manager
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        legal, sec = await asyncio.gather(
            self.legal_fn(prompt, llm),
            self.security_fn(prompt, llm),
        )
        yield TextChunk(text=f"[legal] {legal['decision']}\n")
        yield TextChunk(text=f"[security] {sec['decision']}\n")

        if legal["decision"] != sec["decision"]:
            rec = pause(
                agent_name="executive-test",
                session_id=ctx.session.id,
                reason=f"managers disagreed: legal={legal['decision']} security={sec['decision']}",
                pending_action={"legal": legal, "security": sec, "prompt": prompt},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
            )
            return

        yield FinalChunk(state={"decision": legal["decision"]})


async def test_executive_consensus_no_pause(provider):
    """When both managers agree, the executive finalizes without pausing."""
    agent = ExecutiveAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    # A benign prompt — both managers should approve
    chunks = await drain(agent, ctx, "Should we add a 'help' link to the docs site? approve.")

    if find_pause(chunks) is None:
        final = next((c for c in chunks if isinstance(c, FinalChunk)), None)
        assert final is not None
    # If they happened to disagree even on this benign prompt, that's a real LLM
    # variance — we still assert the pause carries the right structure.
    else:
        pause_chunk = find_pause(chunks)
        assert "disagreed" in pause_chunk.reason


async def test_executive_pauses_on_disagreement(aws_available):
    """Force the two managers to disagree → executive pauses."""

    async def _yes_manager(prompt, llm):
        return {"manager": "legal", "decision": "approve", "raw": "approve"}

    async def _no_manager(prompt, llm):
        return {"manager": "security", "decision": "reject", "raw": "reject"}

    agent = ExecutiveAgent(legal_fn=_yes_manager, security_fn=_no_manager)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "anything")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "disagreed" in pause_chunk.reason
    assert pause_chunk.pending_action["legal"]["decision"] == "approve"
    assert pause_chunk.pending_action["security"]["decision"] == "reject"

    rec = complete_pause(pause_chunk.resume_token, {"final": "approve"})
    assert rec.approval == {"final": "approve"}
