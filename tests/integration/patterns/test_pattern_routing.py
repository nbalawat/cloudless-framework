"""Pattern 3 — Routing / handoff with HITL.

A router agent classifies the prompt and dispatches to one of three
specialists (billing, technical, legal). If the classifier confidence
is below threshold, the agent pauses for a human to pick the specialist.

Specialists are simulated as inline functions (no peer calls) to keep
the test in-process. The routing decision and HITL behavior are what's
under test.
"""
from __future__ import annotations

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


SPECIALISTS = ("billing", "technical", "legal")


def _specialist_response(name: str, prompt: str) -> str:
    return f"[{name}-specialist] handled: {prompt[:40]}"


@cloudless.agent(name="router-test", interfaces=["http"])
class RouterAgent(cloudless.Agent):
    def __init__(self, llm_provider: str = "bedrock"):
        super().__init__()
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        # Classify intent — model returns one of the specialist names
        raw = await llm.invoke(
            prompt,
            system=(
                "Classify the user's request into exactly one category: "
                "'billing', 'technical', or 'legal'. "
                "Reply with ONLY the category word, lowercase, no punctuation."
            ),
            max_tokens=8,
            ctx=ctx,
        )
        # Robust extraction in case the model adds punctuation
        match = re.search(r"\b(billing|technical|legal)\b", raw.lower())
        if not match:
            # Low confidence — pause for human
            rec = pause(
                agent_name="router-test",
                session_id=ctx.session.id,
                reason=f"router could not classify; raw={raw!r}",
                pending_action={"prompt": prompt, "raw": raw},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
            )
            return

        specialist = match.group(1)
        yield TextChunk(text=f"[router] → {specialist}\n")
        yield TextChunk(text=_specialist_response(specialist, prompt) + "\n")
        yield FinalChunk(state={"routed_to": specialist})


async def test_router_dispatches_to_billing_for_invoice_prompt(provider):
    agent = RouterAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "I have a question about my invoice for last month")
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "→ billing" in text
    assert "billing-specialist" in text
    assert find_pause(chunks) is None
    final = next((c for c in chunks if isinstance(c, FinalChunk)), None)
    assert final.state["routed_to"] == "billing"


async def test_router_dispatches_to_technical_for_bug_prompt(provider):
    agent = RouterAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "My API keeps returning 500 errors when I call /search")
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "→ technical" in text


async def test_router_pauses_when_classifier_uncertain(aws_available, monkeypatch):
    """Inject a deliberately ambiguous classifier response → pause."""

    class _AmbiguousLLM:
        async def invoke(self, prompt, **kw):
            return "i'm not sure"  # no specialist keyword

    # Monkeypatch cloudless.LLM so the agent's `fast_llm()` call returns our stub
    import cloudless as _cl
    monkeypatch.setattr(_cl, "LLM", lambda *a, **kw: _AmbiguousLLM())

    agent = RouterAgent()
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "literally anything")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "could not classify" in pause_chunk.reason
    assert "raw" in pause_chunk.pending_action

    # Human picks the specialist
    rec = complete_pause(pause_chunk.resume_token, {"specialist": "technical"})
    assert rec.approval == {"specialist": "technical"}
