"""Unit tests for cloudless.cli.doctor."""
from __future__ import annotations

import io
from contextlib import redirect_stdout

from cloudless.cli import doctor


def test_individual_check_returns_result():
    r = doctor.check_python_version()
    assert r.name == "python-version"
    assert r.level in ("PASS", "WARN", "FAIL")


def test_bedrock_inference_profile_check_passes():
    """F1 mitigation must be PASS in the default install."""
    r = doctor.check_bedrock_inference_profile()
    assert r.level == "PASS", r
    assert "us." in r.message


def test_anthropic_streaming_check_warns():
    """F15: Anthropic models should still surface a streaming WARN."""
    r = doctor.check_anthropic_streaming()
    assert r.level == "WARN"


def test_run_returns_zero_when_no_fails(monkeypatch):
    """A run with only PASS/WARN results should exit 0."""
    fake_checks = [
        lambda: doctor.CheckResult("a", "PASS", "ok"),
        lambda: doctor.CheckResult("b", "WARN", "meh"),
    ]
    monkeypatch.setattr(doctor, "ALL_CHECKS", fake_checks)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = doctor.run()
    assert rc == 0
    out = buf.getvalue()
    assert "1 pass" in out
    assert "1 warn" in out
    assert "0 fail" in out


def test_run_returns_one_on_any_fail(monkeypatch):
    fake_checks = [
        lambda: doctor.CheckResult("a", "PASS", "ok"),
        lambda: doctor.CheckResult("bad", "FAIL", "broken"),
    ]
    monkeypatch.setattr(doctor, "ALL_CHECKS", fake_checks)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = doctor.run()
    assert rc == 1
    assert "1 fail" in buf.getvalue()
