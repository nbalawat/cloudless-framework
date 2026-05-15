"""Unit tests for cloudless.runtime.tracing (Q39 OTel propagation)."""
from __future__ import annotations

import pytest

from cloudless.runtime import tracing


@pytest.fixture(scope="module")
def otel_exporter():
    """OTel only allows one global TracerProvider per process. If something
    else has already set it, attach our exporter to that provider; otherwise
    install our own SDK provider."""
    pytest.importorskip("opentelemetry.trace")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    current = trace.get_tracer_provider()
    if not hasattr(current, "add_span_processor"):
        # ProxyTracerProvider or similar — install a real SDK provider.
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    else:
        # SDK provider already installed; just add our processor to it.
        current.add_span_processor(SimpleSpanProcessor(exporter))

    tracing._INITIALIZED = True
    tracing._TRACER = trace.get_tracer("cloudless")
    yield exporter


@pytest.fixture(autouse=True)
def _clear_spans(otel_exporter):
    otel_exporter.clear()
    yield


def test_span_context_manager_yields_no_op_when_otel_missing(monkeypatch):
    """If OTel can't be imported, span() must not crash and yields None."""
    monkeypatch.setattr(tracing, "_has_otel", lambda: False)
    saved = tracing._TRACER
    tracing._TRACER = None
    try:
        with tracing.span("llm.invoke", **{"gen_ai.system": "bedrock"}) as sp:
            assert sp is None
    finally:
        tracing._TRACER = saved


def test_configure_idempotent():
    """Calling configure twice should not raise."""
    tracing.configure()
    tracing.configure()


def test_span_records_attributes_when_otel_present(otel_exporter):
    with tracing.span("test.op", custom_attr="value"):
        tracing.set_attr("late.attr", 42)

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.op"
    assert spans[0].attributes.get("custom_attr") == "value"
    assert spans[0].attributes.get("late.attr") == 42


def test_record_exception_marks_span_error(otel_exporter):
    from opentelemetry.trace import StatusCode

    try:
        with tracing.span("test.error"):
            try:
                raise ValueError("kaboom")
            except ValueError as e:
                tracing.record_exception(e)
                raise
    except ValueError:
        pass

    spans = otel_exporter.get_finished_spans()
    err_spans = [s for s in spans if s.name == "test.error"]
    assert err_spans, "no test.error span recorded"
    assert err_spans[0].status.status_code == StatusCode.ERROR


def test_set_attr_when_no_active_span_is_safe():
    """Calling set_attr outside any span context should not raise."""
    tracing.set_attr("x", 1)


def test_none_attributes_are_skipped(otel_exporter):
    """None attribute values should not be set on the span."""
    with tracing.span("test.none", real="value", missing=None):
        pass
    spans = otel_exporter.get_finished_spans()
    sp = next(s for s in spans if s.name == "test.none")
    assert "real" in sp.attributes
    assert "missing" not in sp.attributes
