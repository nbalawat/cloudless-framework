"""Unit tests for cloudless.runtime.cost_sinks."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cloudless.runtime.context import InMemoryContext
from cloudless.runtime.cost_sinks import (
    CostRecord,
    InMemoryCostSink,
    JsonlCostSink,
    emit_cost,
    reset_cost_sinks,
    set_cost_sinks,
)


@pytest.fixture(autouse=True)
def _clean():
    sink = InMemoryCostSink()
    set_cost_sinks([sink])
    yield sink
    reset_cost_sinks()


def test_emit_cost_writes_record(_clean):
    record = emit_cost(kind="llm", model="us.amazon.nova-micro-v1:0",
                       input_tokens=100, output_tokens=50)
    assert isinstance(record, CostRecord)
    assert len(_clean.records) == 1
    assert _clean.records[0].kind == "llm"


def test_record_llm_call_fires_emit_cost(_clean):
    ctx = InMemoryContext()
    ctx.cost.attribute(team="payments")
    ctx.cost.record_llm_call(
        model="us.amazon.nova-micro-v1:0",
        input_tokens=1000, output_tokens=200,
    )
    assert len(_clean.records) == 1
    rec = _clean.records[0]
    assert rec.team == "payments"
    assert rec.input_tokens == 1000
    assert rec.usd > 0  # priced via pricing table


def test_jsonl_sink_appends_lines(tmp_path: Path):
    p = tmp_path / "costs.jsonl"
    sink = JsonlCostSink(str(p))
    set_cost_sinks([sink])

    emit_cost(kind="llm", model="m1", input_tokens=10, output_tokens=5)
    emit_cost(kind="peer", model="orders", usd=0.01)
    lines = p.read_text().strip().split("\n")
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    rec1 = json.loads(lines[1])
    assert rec0["model"] == "m1"
    assert rec1["kind"] == "peer"
    reset_cost_sinks()


def test_broken_sink_does_not_crash(_clean):
    class Broken:
        def write(self, r):
            raise RuntimeError("nope")

    good = InMemoryCostSink()
    set_cost_sinks([Broken(), good])
    emit_cost(kind="llm", model="x")
    assert len(good.records) == 1


def test_empty_sink_chain_is_silent(monkeypatch):
    reset_cost_sinks()
    # No sinks; should not raise
    rec = emit_cost(kind="llm", model="x")
    assert isinstance(rec, CostRecord)
