"""Unit tests for `cloudless cost`."""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from cloudless.cli import cost as cost_cmd


def test_record_to_cost_from_token_record():
    record = {
        "model": "us.amazon.nova-micro-v1:0",
        "input_tokens": 1_000_000,
        "output_tokens": 0,
        "team": "payments",
    }
    model, team, usd = cost_cmd._record_to_cost(record)
    assert model == "us.amazon.nova-micro-v1:0"
    assert team == "payments"
    assert usd > 0


def test_record_to_cost_from_cassette_estimates_tokens():
    record = {
        "model": "us.amazon.nova-micro-v1:0",
        "prompt": "a" * 4000,   # ~1000 tokens
        "text": "b" * 4000,
    }
    _, _, usd = cost_cmd._record_to_cost(record)
    # ~1000 tokens in + ~1000 tokens out for Nova micro is < 1 cent.
    assert 0 < usd < 0.01


def test_rollup_by_model_groups_records():
    records = [
        {"model": "us.amazon.nova-micro-v1:0", "input_tokens": 1000, "output_tokens": 500},
        {"model": "us.amazon.nova-micro-v1:0", "input_tokens": 2000, "output_tokens": 100},
        {"model": "us.amazon.nova-pro-v1:0", "input_tokens": 500, "output_tokens": 50},
    ]
    totals = cost_cmd._rollup(records, by="model")
    assert "us.amazon.nova-micro-v1:0" in totals
    assert totals["us.amazon.nova-micro-v1:0"]["calls"] == 2
    assert totals["us.amazon.nova-pro-v1:0"]["calls"] == 1


def test_rollup_by_team_groups_records():
    records = [
        {"model": "us.amazon.nova-micro-v1:0", "input_tokens": 1000, "output_tokens": 0, "team": "payments"},
        {"model": "us.amazon.nova-micro-v1:0", "input_tokens": 2000, "output_tokens": 0, "team": "fraud"},
        {"model": "us.amazon.nova-micro-v1:0", "input_tokens": 100,  "output_tokens": 0, "team": "payments"},
    ]
    totals = cost_cmd._rollup(records, by="team")
    assert totals["payments"]["calls"] == 2
    assert totals["fraud"]["calls"] == 1


def test_rollup_invalid_by_raises():
    with pytest.raises(ValueError, match="--by"):
        cost_cmd._rollup([], by="bogus")


def test_run_with_no_input_returns_1(monkeypatch):
    # Simulate TTY stdin (no piped data); no --cassette glob
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cost_cmd.run()
    assert rc == 1


def test_run_from_stdin_table(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    fake_in = io.StringIO(
        json.dumps({"model": "us.amazon.nova-micro-v1:0",
                    "input_tokens": 1000, "output_tokens": 500}) + "\n"
        + json.dumps({"model": "us.amazon.nova-pro-v1:0",
                      "input_tokens": 100, "output_tokens": 100}) + "\n"
    )
    monkeypatch.setattr(sys, "stdin", fake_in)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cost_cmd.run()
    assert rc == 0
    out = buf.getvalue()
    assert "TOTAL" in out
    assert "us.amazon.nova-micro-v1:0" in out


def test_run_from_cassette_glob(tmp_path: Path):
    cassette = tmp_path / "demo.cassette.jsonl"
    cassette.write_text(
        json.dumps({"model": "us.amazon.nova-micro-v1:0",
                    "prompt": "p" * 400, "text": "r" * 100}) + "\n"
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cost_cmd.run(cassette_globs=[str(cassette)])
    assert rc == 0
    assert "us.amazon.nova-micro-v1:0" in buf.getvalue()


def test_run_json_format(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    fake_in = io.StringIO(
        json.dumps({"model": "us.amazon.nova-micro-v1:0",
                    "input_tokens": 1000, "output_tokens": 100}) + "\n"
    )
    monkeypatch.setattr(sys, "stdin", fake_in)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cost_cmd.run(output_format="json")
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert "us.amazon.nova-micro-v1:0" in payload
    assert payload["us.amazon.nova-micro-v1:0"]["calls"] == 1
