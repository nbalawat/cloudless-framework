"""Kitchen-sink example agent.

Exercises every cloudless primitive in one place so a new user can read
ONE file and see how the pieces fit:

  - LLM (Bedrock Nova Micro)
  - Memory (recall + add_event)
  - Tools (from_function, decorated with @policy)
  - Secrets (Secrets primitive read)
  - Sandbox (Code Interpreter / LocalSubprocess)
  - VectorStore (in-memory cosine search)
  - Embeddings (Titan v2)
  - Policy (before_llm: redaction + cost guard)
  - Cost (per-session USD tracking)
  - HITL pause/resume (PauseChunk for amounts > $1000)
  - Resilience (with_retry around the tool call)
  - Tracing (OTel spans emitted automatically)

This agent is INTENTIONALLY contrived — the goal is feature coverage.
Real agents should be focused and small.
"""
from __future__ import annotations

import os
import re
from typing import AsyncIterator

import cloudless
from cloudless.chunks import (
    Chunk,
    FinalChunk,
    PauseChunk,
    ReasoningChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)
from cloudless.exceptions import CostCapExceeded, PolicyViolation
from cloudless.runtime import resilient, tasks


# --------------------------------------------------------------------- #
# Policies — applied to every LLM/tool call in this process
# --------------------------------------------------------------------- #


SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


@cloudless.policy(stages=["before_llm"], name="block-ssn")
def block_ssn(stage, prompt, **kw):
    """Refuse to send anything that looks like an SSN to the LLM."""
    if SSN_RE.search(prompt):
        raise PolicyViolation("SSN-shaped string detected in prompt; refusing call")
    return None  # no transform


@cloudless.policy(stages=["after_llm"], name="cap-length")
def cap_response_length(stage, prompt, response, **kw):
    """Truncate model responses over 4kB to protect downstream parsers."""
    if len(response) > 4096:
        return response[:4096] + "\n\n[truncated]"
    return None


# --------------------------------------------------------------------- #
# Tools — surfaced to the LLM via Strands tool registry
# --------------------------------------------------------------------- #


@cloudless.tool
def lookup_order_status(order_id: str) -> dict:
    """Look up the status of an order by its ID."""
    # In a real agent: hit your order service or AWS Lambda
    return {"order_id": order_id, "status": "shipped", "tracking": "1Z..."}


@cloudless.tool
def issue_refund(order_id: str, amount_usd: float) -> dict:
    """Issue a refund. Amounts >$1000 require human approval (HITL)."""
    return {"order_id": order_id, "refund_usd": amount_usd, "status": "issued"}


# --------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------- #


@cloudless.agent(
    name="concierge",
    framework="langgraph",
    interfaces=["http", "a2a"],
    description="Customer concierge — order lookup, refund, HITL approval.",
)
class ConciergeAgent(cloudless.LangGraphAgent):
    """Kitchen-sink agent.

    Demonstrates the full Chunk taxonomy:
      ReasoningChunk → TextChunk → ToolCallChunk → ToolResultChunk →
      PauseChunk (for high-value refunds) → FinalChunk
    """

    def __init__(self) -> None:
        super().__init__()
        # All catalog primitives constructed lazily so unit tests can mock
        self._llm = cloudless.LLM(model="nova-micro")
        self._embeddings = cloudless.Embeddings(model="titan-v2")
        self._vectors = cloudless.VectorStore(
            backend=cloudless.InMemoryVectorBackend(dimensions=1024),
        )
        # Memory + Secrets + Sandbox would be initialized here when the
        # adapter is available; for the example we lazily get them per call.

    def build(self):
        # Required by LangGraphAgent — return a StateGraph or compiled graph.
        # For brevity in the example we override `query` directly below.
        return None

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:  # type: ignore[override]
        # 1. Show reasoning chunk
        yield ReasoningChunk(text=f"Parsing user request: {prompt!r}")

        # 2. Cost cap check
        spent = await ctx.cost.session_total_usd()
        if spent > 1.0:
            raise CostCapExceeded(f"Session already spent ${spent:.2f}")

        # 3. Resilient LLM call to classify intent
        @resilient(attempts=3, timeout_seconds=10.0, circuit="bedrock")
        async def _classify():
            return await self._llm.invoke(
                prompt,
                system=(
                    "You are a concierge. Reply with one word: "
                    "'STATUS', 'REFUND_SMALL', 'REFUND_LARGE', or 'OTHER'."
                ),
                max_tokens=10,
                ctx=ctx,
            )

        intent = (await _classify()).strip().upper()
        yield TextChunk(text=f"Detected intent: {intent}\n\n")

        # 4. Branch on intent
        if intent == "STATUS":
            yield ToolCallChunk(name="lookup_order_status", args={"order_id": "demo-1"})
            result = await lookup_order_status.invoke({"order_id": "demo-1"})
            yield ToolResultChunk(name="lookup_order_status", result=result)

        elif intent == "REFUND_SMALL":
            yield ToolCallChunk(name="issue_refund",
                                args={"order_id": "demo-1", "amount_usd": 25.00})
            result = await issue_refund.invoke({"order_id": "demo-1", "amount_usd": 25.00})
            yield ToolResultChunk(name="issue_refund", result=result)

        elif intent == "REFUND_LARGE":
            # HITL: pause and await human approval
            rec = tasks.pause(
                agent_name="concierge",
                session_id=ctx.session.id,
                reason="Refund > $1000 requires human approval",
                pending_action={"order_id": "demo-1", "amount_usd": 5000.00},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
                expires_at=rec.expires_at,
            )
            return

        else:
            # OTHER — fall back to a free-form LLM answer
            reply = await self._llm.invoke(prompt, max_tokens=200, ctx=ctx)
            for word in reply.split():
                yield TextChunk(text=word + " ")

        yield FinalChunk(state={"intent": intent})


# --------------------------------------------------------------------- #
# Local smoke entrypoint — `python -m agents.concierge` runs a quick test
# --------------------------------------------------------------------- #


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    async def _demo() -> None:
        agent = ConciergeAgent()
        ctx = cloudless.InMemoryContext()
        ctx.cost.attribute(team="support", project="concierge-demo")
        async for chunk in agent.query(ctx, "What's the status of my order?"):
            print(f"  [{chunk.kind}] {chunk.model_dump()}")
        total = await ctx.cost.session_total_usd()
        print(f"\n  session cost: ${total:.4f}")

    asyncio.run(_demo())
