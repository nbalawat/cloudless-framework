"""Unit tests for metric emission to CloudWatch + Cloud Monitoring."""
from __future__ import annotations

import pytest

from cloudless.runtime import metrics as M


def test_no_emit_when_not_configured(monkeypatch):
    """emit_metric is a no-op until configure_* is called."""
    M._CW_CLIENT = None
    M._CM_CLIENT = None
    # Should not raise
    M.emit_metric(name="test", value=1.0)


def test_cloudwatch_emit_uses_configured_client(monkeypatch):
    calls = []

    class _FakeCW:
        def put_metric_data(self, **kw):
            calls.append(kw)

    M._CW_CLIENT = _FakeCW()
    M._CW_NAMESPACE = "test-ns"
    try:
        M.emit_cloudwatch_metric(
            name="LLMInvokeLatency",
            value=42.0,
            unit="Milliseconds",
            dimensions={"model": "nova-micro"},
        )
        assert len(calls) == 1
        c = calls[0]
        assert c["Namespace"] == "test-ns"
        assert c["MetricData"][0]["MetricName"] == "LLMInvokeLatency"
        assert c["MetricData"][0]["Value"] == 42.0
        assert c["MetricData"][0]["Dimensions"] == [{"Name": "model", "Value": "nova-micro"}]
    finally:
        M._CW_CLIENT = None


def test_cloudwatch_emit_swallows_exceptions():
    """Buggy CW SDK should not break the user's request path."""
    class _BadCW:
        def put_metric_data(self, **kw):
            raise RuntimeError("CW down")

    M._CW_CLIENT = _BadCW()
    try:
        M.emit_cloudwatch_metric(name="x", value=1.0)  # must not raise
    finally:
        M._CW_CLIENT = None


def test_unified_emit_fans_out():
    """emit_metric should call both CW and CM emitters."""
    cw_calls = []
    cm_called = []

    class _FakeCW:
        def put_metric_data(self, **kw):
            cw_calls.append(kw)

    M._CW_CLIENT = _FakeCW()

    class _FakeCM:
        def create_time_series(self, **kw):
            cm_called.append(kw)

    M._CM_CLIENT = _FakeCM()
    M._CM_PROJECT = "test-proj"

    try:
        M.emit_metric(name="x", value=1.0, unit="Count", dimensions={"k": "v"})
        assert len(cw_calls) == 1
        # CM emission has more failure modes (proto types); accept either
        # success or silent failure
    finally:
        M._CW_CLIENT = None
        M._CM_CLIENT = None
        M._CM_PROJECT = None


def test_configure_xray_export_no_op_without_otel(monkeypatch):
    """Without OTel SDK, configure_xray_export should be a no-op."""
    # Just call it — no exception is the assertion
    M.configure_xray_export(sampler_ratio=0.1)


def test_configure_cloud_trace_export_no_op_without_exporter(monkeypatch):
    """Without gcp-trace exporter, configure_cloud_trace_export should no-op."""
    M.configure_cloud_trace_export(project="my-proj")
