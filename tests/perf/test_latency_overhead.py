"""Latency-overhead benchmarks for the cloudless runtime.

These DO NOT exercise the cloud — they measure pure-Python overhead so
performance regressions in the framework itself are visible without
spending real LLM tokens.

Run with:
    pytest tests/perf -m perf -s

The `-s` flag prevents pytest from capturing stdout so the results print.
"""
from __future__ import annotations

import pytest
from tests.perf.bench import bench_async, bench_sync

import cloudless
from cloudless.chunks import TextChunk
from cloudless.runtime.audit import reset_sinks, set_sinks
from cloudless.runtime.policy import get_registry
from cloudless.runtime.tasks import pause, reset_store, resume


@pytest.fixture(autouse=True)
def _silence_audit():
    """Replace audit sink chain with empty list so perf measurements don't include
    structlog overhead from the default StructlogSink."""
    set_sinks([])
    yield
    reset_sinks()


pytestmark = [pytest.mark.perf, pytest.mark.asyncio]


# ----------------------------- Chunk construction --------------------- #


def test_perf_chunk_construction(capsys):
    def make():
        return TextChunk(text="hello")
    r = bench_sync("TextChunk()", make, iterations=10_000, warmup=500)
    with capsys.disabled():
        print(f"\n{r}")
    # Pydantic v2 frozen model — should be sub-100µs
    assert r.p95_ms < 0.5, f"TextChunk() got too slow: {r}"


def test_perf_chunk_dump(capsys):
    chunk = TextChunk(text="hello")
    def dump():
        return chunk.model_dump()
    r = bench_sync("TextChunk.model_dump()", dump, iterations=10_000, warmup=500)
    with capsys.disabled():
        print(f"\n{r}")
    assert r.p95_ms < 0.5


# ----------------------------- Policy overhead ------------------------ #


async def test_perf_policy_dispatch_empty(capsys):
    """Empty policy registry should add ~no overhead."""
    get_registry().clear()
    async def run():
        get_registry().run("before_llm", prompt="x", model="m", ctx=None)
    r = await bench_async("policy.run(empty)", run, iterations=5_000, warmup=500)
    with capsys.disabled():
        print(f"\n{r}")
    assert r.p95_ms < 1.0


async def test_perf_policy_dispatch_with_one_policy(capsys):
    """One policy that transforms should still be <1ms p95."""
    get_registry().clear()

    @cloudless.policy(stages=["before_llm"])
    def _noop(stage, prompt, **kw):
        return prompt.upper()

    async def run():
        get_registry().run("before_llm", prompt="x", model="m", ctx=None)
    r = await bench_async("policy.run(1 policy)", run, iterations=5_000, warmup=500)
    with capsys.disabled():
        print(f"\n{r}")
    assert r.p95_ms < 1.0
    get_registry().clear()


# ----------------------------- Context overhead ----------------------- #


async def test_perf_session_total_usd(capsys):
    """Cost computation on a session with 100 calls should be <5ms."""
    ctx = cloudless.InMemoryContext()
    for _ in range(100):
        ctx.cost.record_llm_call(
            model="us.amazon.nova-micro-v1:0",
            input_tokens=200, output_tokens=50,
        )
    async def run():
        await ctx.cost.session_total_usd()
    r = await bench_async("ctx.cost.session_total_usd (100 calls)", run,
                          iterations=2_000, warmup=200)
    with capsys.disabled():
        print(f"\n{r}")
    assert r.p95_ms < 5.0


# ----------------------------- HITL store overhead -------------------- #


def test_perf_task_pause_resume_roundtrip(capsys):
    """pause()+resume() should both be sub-millisecond."""
    reset_store()

    def roundtrip():
        rec = pause(agent_name="x", session_id="s")
        resume(rec.resume_token, {"approved": True})
    r = bench_sync("pause+resume roundtrip", roundtrip,
                   iterations=2_000, warmup=200)
    with capsys.disabled():
        print(f"\n{r}")
    assert r.p95_ms < 1.0
    reset_store()
