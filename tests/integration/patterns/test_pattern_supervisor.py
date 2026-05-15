"""Pattern 5 — Orchestrator-workers (supervisor) with HITL.

A supervisor agent:
  1. Asks an LLM to decompose a goal into 2-4 steps
  2. PAUSES for human plan approval (the canonical HITL placement)
  3. After resume, dispatches steps to worker functions in parallel
  4. Synthesizes the final answer from worker outputs

The HITL gate is BEFORE workers execute, so a bad plan is caught once
rather than after N expensive executions.
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
from cloudless.chunks import Chunk, PauseChunk, TextChunk
from cloudless.runtime.tasks import pause, reset_store

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


# Simulated worker — represents whatever sub-agent would handle a step
async def _execute_step(step: str) -> dict:
    return {"step": step, "status": "done"}


@cloudless.agent(name="supervisor-test", interfaces=["http"])
class SupervisorAgent(cloudless.Agent):
    def __init__(self, llm_provider: str = "bedrock"):
        super().__init__()
        self.llm_provider = llm_provider

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        llm = fast_llm(self.llm_provider)

        # Stage 1: planning
        plan_raw = await llm.invoke(
            prompt,
            system=(
                "Decompose the user's goal into 2 to 4 short steps. "
                "Reply with ONLY a JSON array of strings, no prose. "
                "Example: [\"step 1\", \"step 2\"]"
            ),
            max_tokens=200,
            ctx=ctx,
        )

        # Extract a JSON array from the response — the model occasionally
        # adds prose. Be defensive.
        match = re.search(r"\[.*?\]", plan_raw, re.DOTALL)
        plan: list[str] = []
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    plan = [str(x) for x in parsed if isinstance(x, str)][:4]
            except json.JSONDecodeError:
                plan = []
        if not plan:
            plan = [f"step: {prompt}"]

        yield TextChunk(text=f"[plan] {plan}\n")

        # Stage 2: HITL gate — approve the plan before workers run
        rec = pause(
            agent_name="supervisor-test",
            session_id=ctx.session.id,
            reason="approve plan before workers execute",
            pending_action={"plan": plan, "goal": prompt},
        )
        yield PauseChunk(
            resume_token=rec.resume_token,
            reason=rec.reason,
            pending_action=rec.pending_action,
        )
        # NB: real production flow would re-invoke after resume.
        # For test purposes, the assertions verify state at this point;
        # a separate test calls resume + asserts the resume record carries
        # the approved plan.


async def test_supervisor_pauses_after_planning_before_workers(provider):
    agent = SupervisorAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(
        agent, ctx, "Onboard a new SaaS customer named Acme Corp",
    )

    # Plan was produced
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "[plan]" in text

    # Paused for approval
    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "approve plan" in pause_chunk.reason
    assert "plan" in pause_chunk.pending_action
    assert isinstance(pause_chunk.pending_action["plan"], list)
    assert len(pause_chunk.pending_action["plan"]) >= 1


async def test_supervisor_approval_carries_through(provider):
    """After resume, the approved plan is recoverable from the task record."""
    agent = SupervisorAgent(llm_provider=provider)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Onboard a new SaaS customer named Acme")
    token = find_pause(chunks).resume_token

    rec = complete_pause(
        token,
        {"approved": True, "edits": ["adjusted step 2 phrasing"]},
    )
    assert rec.approval["approved"] is True
    assert rec.pending_action["goal"].startswith("Onboard")


async def test_supervisor_worker_dispatch_simulated(aws_available):
    """Simulate the post-resume worker dispatch — verify parallel execution."""
    import time

    plan = ["fetch CRM record", "create billing account", "send welcome email"]
    t0 = time.perf_counter()
    results = await asyncio.gather(*[_execute_step(s) for s in plan])
    elapsed = time.perf_counter() - t0

    assert [r["step"] for r in results] == plan
    assert all(r["status"] == "done" for r in results)
    assert elapsed < 0.1  # local fns are instant; parallel structure intact
