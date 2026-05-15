"""Pattern 11 — Tool-as-agent with HITL.

A specialist sub-agent is wrapped as a `@cloudless.tool` so the supervising
LLM can decide when to call it. A `@cloudless.policy(stages=["before_tool"])`
hook gates calls to that tool when the args look high-impact.

This verifies:
  - Tool factory wraps an async callable correctly
  - The policy hook intercepts before the inner agent runs
  - Audit emission fires on block
  - HITL pause flows when the policy hands off to a human
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from tests.integration.patterns._harness import (
    complete_pause,
    drain,
    find_pause,
)

import cloudless
from cloudless.chunks import Chunk, FinalChunk, PauseChunk, TextChunk
from cloudless.exceptions import PolicyViolation
from cloudless.runtime.audit import InMemorySink, reset_sinks, set_sinks
from cloudless.runtime.policy import get_registry
from cloudless.runtime.tasks import pause, reset_store

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean():
    sink = InMemorySink()
    set_sinks([sink])
    get_registry().clear()
    reset_store()
    yield sink
    reset_sinks()
    get_registry().clear()
    reset_store()


# A sub-agent that handles "legal opinion" queries
class _LegalAgent(cloudless.Agent):
    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        # In a real system this would be a peer call; here we just synthesize
        yield TextChunk(text=f"[legal opinion] reviewed: {prompt[:60]}")
        yield FinalChunk()


async def _consult_legal_impl(args: dict) -> dict:
    """Tool body: invokes the legal sub-agent and collects its reply."""
    legal = _LegalAgent()
    ctx = cloudless.InMemoryContext(session_id="legal-tool-call")
    text_parts: list[str] = []
    async for chunk in legal.query(ctx, args.get("question", "")):
        if hasattr(chunk, "text"):
            text_parts.append(chunk.text)
    return {"answer": "".join(text_parts).strip()}


def _make_legal_tool() -> cloudless.Tool:
    return cloudless.Tool(
        name="consult_legal",
        description="Ask the legal agent for an opinion.",
        parameters={
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
        _invoker=_consult_legal_impl,
    )


async def test_tool_as_agent_basic_invocation(aws_available):
    """Calling the wrapped legal-as-tool returns the inner agent's output."""
    tool = _make_legal_tool()
    result = await tool.invoke({"question": "Is this NDA enforceable?"})
    assert "[legal opinion]" in result["answer"]


async def test_policy_blocks_tool_for_sensitive_query(aws_available, _clean):
    """A before_tool policy raises PolicyViolation → call is blocked + audited."""

    @cloudless.policy(stages=["before_tool"], name="block-pii-in-legal")
    def block_pii(stage, tool_name, args, **kw):
        if tool_name == "consult_legal" and "SSN" in args.get("question", ""):
            raise PolicyViolation("legal queries must not include raw PII")
        return None

    tool = _make_legal_tool()
    with pytest.raises(PolicyViolation, match="PII"):
        await tool.invoke({"question": "Is SSN 123-45-6789 ok in this contract?"})

    # Audit record was emitted
    assert any(r.policy_name == "block-pii-in-legal" and r.decision == "block"
               for r in _clean.records)


@cloudless.agent(name="tool-supervisor-test", interfaces=["http"])
class SupervisorWithToolAgent(cloudless.Agent):
    """Top-level agent that uses the legal sub-agent via the tool wrapper.

    On a sensitive question, the policy on the tool blocks; the supervisor
    catches the PolicyViolation and pauses for human handoff.
    """

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        tool = _make_legal_tool()
        try:
            result = await tool.invoke({"question": prompt})
            yield TextChunk(text=f"[result] {result['answer']}\n")
            yield FinalChunk(state={"status": "ok"})
        except PolicyViolation as e:
            rec = pause(
                agent_name="tool-supervisor-test",
                session_id=ctx.session.id,
                reason=f"tool blocked by policy: {e}",
                pending_action={"prompt": prompt, "policy_reason": str(e)},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
            )


async def test_supervisor_pauses_when_inner_tool_blocked(aws_available, _clean):
    """End-to-end: supervisor uses tool, tool's before-policy blocks, supervisor pauses."""

    @cloudless.policy(stages=["before_tool"], name="block-pii-in-legal")
    def block_pii(stage, tool_name, args, **kw):
        if "SSN" in args.get("question", ""):
            raise PolicyViolation("PII detected")
        return None

    agent = SupervisorWithToolAgent()
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Is SSN 999-00-0000 valid for this NDA?")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "blocked by policy" in pause_chunk.reason
    rec = complete_pause(pause_chunk.resume_token, {"redacted": True})
    assert rec.approval == {"redacted": True}
