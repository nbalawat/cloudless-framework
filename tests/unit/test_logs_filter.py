"""Unit tests for `cloudless logs` filter / JSON behavior."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from cloudless.cli.ops import _emit_event


def _ev(ts_ms: int, payload: dict | str) -> dict:
    return {"timestamp": ts_ms,
            "message": json.dumps(payload) if isinstance(payload, dict) else payload}


def _capture(ev, **kw) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        _emit_event(ev, **{"trace_id": None, "session_id": None, "level": None,
                            "output": "text", **kw})
    return buf.getvalue()


def test_text_output_prints_iso_timestamp_and_message():
    out = _capture(_ev(1700000000000, "hello world"))
    assert "hello world" in out
    assert "2023-11-14" in out  # ISO timestamp


def test_json_output_passes_parsed_structlog_through():
    payload = {"level": "info", "msg": "hello", "trace.id": "abc"}
    out = _capture(_ev(1700000000000, payload), output="json")
    parsed = json.loads(out.strip())
    assert parsed["msg"] == "hello"
    assert parsed["__timestamp_ms"] == 1700000000000


def test_json_output_wraps_non_json_line():
    out = _capture(_ev(1700000000000, "plain line"), output="json")
    parsed = json.loads(out.strip())
    assert parsed["message"] == "plain line"


def test_trace_id_filter_drops_non_matching():
    matching = _ev(1, {"trace.id": "abc", "msg": "yes"})
    other = _ev(2, {"trace.id": "xyz", "msg": "no"})
    assert "yes" in _capture(matching, trace_id="abc")
    assert _capture(other, trace_id="abc") == ""


def test_session_id_filter_drops_non_matching():
    matching = _ev(1, {"session.id": "s1", "msg": "yes"})
    other = _ev(2, {"session.id": "s2", "msg": "no"})
    assert "yes" in _capture(matching, session_id="s1")
    assert _capture(other, session_id="s1") == ""


def test_level_filter_drops_below_threshold():
    warn = _ev(1, {"level": "warning", "msg": "warn-msg"})
    info = _ev(2, {"level": "info", "msg": "info-msg"})
    err = _ev(3, {"level": "error", "msg": "err-msg"})
    assert "warn-msg" in _capture(warn, level="WARNING")
    assert _capture(info, level="WARNING") == ""
    assert "err-msg" in _capture(err, level="WARNING")


def test_trace_id_filter_skips_non_json_lines():
    """Plain-text lines without trace.id should be dropped when filter set."""
    plain = _ev(1, "plain text — not structlog")
    assert _capture(plain, trace_id="abc") == ""


def test_combined_filters():
    """trace_id + level: both must match."""
    ev = _ev(1, {"trace.id": "abc", "level": "error", "msg": "kept"})
    assert "kept" in _capture(ev, trace_id="abc", level="WARNING")
    assert _capture(ev, trace_id="other", level="WARNING") == ""
