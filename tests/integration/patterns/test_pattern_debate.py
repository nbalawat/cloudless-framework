"""Pattern 10 — Debate / consensus with HITL.

Three debater agents with conflicting perspectives argue across N rounds.
A judge agent reads the transcript and decides. If the judge's confidence
is low, the agent pauses for human override.

To keep the test fast and deterministic-ish, debaters return one-line
positions; the judge sees the joined transcript.
"""
from __future__ import annotations

import asyncio
import json
import re
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


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


DEBATERS = [
    ("pro-cost",  "Argue that cost is the primary factor. Be brief."),
    ("pro-speed", "Argue that speed is the primary factor. Be brief."),
    ("pro-quality", "Argue that quality is the primary factor. Be brief."),
]

CONFIDENCE_THRESHOLD = 0.6


@cloudless.agent(name="debate-test", interfaces=["http"])
class DebateAgent(cloudless.Agent):
    def __init__(self, judge_confidence: float | None = None,
                 llm_provider: str = "bedrock"):
        super().__init__()
        self.fixed_judge_confidence = judge_confidence
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        # Run debaters in parallel (one round only for test speed)
        async def _argue(name: str, system: str) -> dict:
            text = await llm.invoke(
                prompt,
                system=system,
                max_tokens=80,
                ctx=ctx,
            )
            return {"name": name, "text": text.strip()}

        args = await asyncio.gather(
            *[_argue(name, system) for name, system in DEBATERS]
        )
        transcript = "\n".join(f"{a['name']}: {a['text']}" for a in args)
        yield TextChunk(text=f"[debate transcript]\n{transcript}\n")

        # Judge synthesizes
        if self.fixed_judge_confidence is not None:
            confidence = self.fixed_judge_confidence
            verdict = "pro-cost"
        else:
            judge_raw = await llm.invoke(
                f"Transcript:\n{transcript}\n\nPick the winner ('pro-cost', 'pro-speed', "
                f"or 'pro-quality') and confidence (0.0-1.0). "
                f"Reply with ONLY JSON: {{\"winner\": \"...\", \"confidence\": 0.X}}",
                max_tokens=80,
                ctx=ctx,
            )
            try:
                match = re.search(r"\{.*?\}", judge_raw, re.DOTALL)
                data = json.loads(match.group(0)) if match else {}
                confidence = float(data.get("confidence", 0.0))
                verdict = data.get("winner", "unknown")
            except Exception:
                confidence = 0.0
                verdict = "unparseable"

        yield TextChunk(text=f"[judge] verdict={verdict} confidence={confidence:.2f}\n")

        if confidence < CONFIDENCE_THRESHOLD:
            rec = pause(
                agent_name="debate-test",
                session_id=ctx.session.id,
                reason=f"judge confidence {confidence:.2f} below threshold",
                pending_action={"transcript": transcript, "judge_verdict": verdict,
                                 "judge_confidence": confidence},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
            )
            return

        yield FinalChunk(state={"winner": verdict, "confidence": confidence})


async def test_debate_high_confidence_finalizes(provider):
    """Pin judge confidence high → no pause, finalize."""
    agent = DebateAgent(judge_confidence=0.95, llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "What matters most when shipping software?")

    assert find_pause(chunks) is None
    final = next((c for c in chunks if isinstance(c, FinalChunk)), None)
    assert final is not None
    assert final.state["confidence"] == 0.95


async def test_debate_low_confidence_pauses(provider):
    """Pin judge confidence low → pause for human override."""
    agent = DebateAgent(judge_confidence=0.3, llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "What matters most?")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "below threshold" in pause_chunk.reason
    assert "transcript" in pause_chunk.pending_action
    assert "pro-cost:" in pause_chunk.pending_action["transcript"]

    rec = complete_pause(
        pause_chunk.resume_token,
        {"human_verdict": "pro-quality", "reason": "long-term ROI"},
    )
    assert rec.approval["human_verdict"] == "pro-quality"


async def test_debate_three_perspectives_in_transcript(provider):
    """Verify all three debaters contribute."""
    agent = DebateAgent(judge_confidence=0.9, llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Should we ship Friday?")
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "pro-cost:" in text
    assert "pro-speed:" in text
    assert "pro-quality:" in text
