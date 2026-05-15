"""Unit tests for Q19 policy audit log."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import cloudless
from cloudless.exceptions import PolicyViolation
from cloudless.runtime.audit import (
    AuditRecord,
    FileSink,
    InMemorySink,
    emit_audit,
    hash_payload,
    reset_sinks,
    set_sinks,
)
from cloudless.runtime.policy import get_registry


@pytest.fixture(autouse=True)
def _clean_state():
    """Each test gets clean policy + audit state."""
    sink = InMemorySink()
    set_sinks([sink])
    get_registry().clear()
    yield sink
    reset_sinks()
    get_registry().clear()


def test_hash_payload_str():
    assert hash_payload("hello") == hash_payload("hello")
    assert hash_payload("hello") != hash_payload("world")
    assert len(hash_payload("x")) == 16


def test_hash_payload_dict():
    a = hash_payload({"k": "v"})
    b = hash_payload({"k": "v"})
    assert a == b


def test_emit_audit_writes_to_sinks(_clean_state):
    record = emit_audit(
        stage="before_llm",
        decision="block",
        policy_name="block-ssn",
        reason="SSN detected",
        payload="my ssn is 123",
    )
    assert isinstance(record, AuditRecord)
    assert _clean_state.records[0].policy_name == "block-ssn"
    assert _clean_state.records[0].decision == "block"
    assert _clean_state.records[0].payload_hash  # non-empty


def test_policy_block_emits_audit_record(_clean_state):
    @cloudless.policy(stages=["before_llm"])
    def block_ssn(stage, prompt, **kw):
        if "ssn" in prompt.lower():
            raise PolicyViolation("PII blocked")
        return None

    with pytest.raises(PolicyViolation):
        get_registry().run("before_llm", prompt="my ssn is 123", ctx=None, model="m")

    assert len(_clean_state.records) == 1
    r = _clean_state.records[0]
    assert r.stage == "before_llm"
    assert r.decision == "block"
    assert r.policy_name == "block_ssn"
    assert "PII blocked" in r.reason
    assert r.payload_hash  # should be set


def test_policy_transform_emits_audit_record(_clean_state):
    @cloudless.policy(stages=["before_llm"])
    def upper(stage, prompt, **kw):
        return prompt.upper()

    get_registry().run("before_llm", prompt="hello", ctx=None, model="m")
    assert len(_clean_state.records) == 1
    assert _clean_state.records[0].decision == "transform"


def test_no_audit_on_passthrough(_clean_state):
    """A policy returning None (no transform, no raise) emits no audit."""
    @cloudless.policy(stages=["before_llm"])
    def noop(stage, prompt, **kw):
        return None

    get_registry().run("before_llm", prompt="ok", ctx=None, model="m")
    assert len(_clean_state.records) == 0


def test_file_sink_appends_json_lines(tmp_path: Path):
    sink_path = tmp_path / "audit.jsonl"
    sink = FileSink(str(sink_path))
    set_sinks([sink])

    emit_audit(stage="before_llm", decision="block", policy_name="a", reason="r1", payload="p1")
    emit_audit(stage="after_llm", decision="block", policy_name="b", reason="r2", payload="p2")

    lines = sink_path.read_text().strip().split("\n")
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    rec1 = json.loads(lines[1])
    assert rec0["policy_name"] == "a"
    assert rec1["policy_name"] == "b"
    reset_sinks()


def test_broken_sink_does_not_crash(_clean_state):
    """A misbehaving sink must not interrupt the audit chain."""
    class BrokenSink:
        def write(self, record):
            raise RuntimeError("disk full")

    good_sink = InMemorySink()
    set_sinks([BrokenSink(), good_sink])

    emit_audit(stage="before_llm", decision="block", policy_name="x", payload="p")
    # Good sink still got the record
    assert len(good_sink.records) == 1
