"""Unit tests for cloudless.ADKAgent event-translation logic.

These exercise the static `_translate()` and `_is_final()` helpers using
synthetic ADK events — no Google Cloud calls. The matching real-cloud
test lives at tests/integration/test_adk_adapter_real_gemini.py.
"""
from __future__ import annotations

import cloudless
from cloudless.adapters.frameworks.adk import ADKAgent


def _make_event(parts, final: bool = False):
    """Build a synthetic ADK Event using real google.genai.types."""
    from google.genai.types import Content

    class _Event:
        def __init__(self, content, final):
            self.content = content
            self._final = final

        def is_final_response(self) -> bool:
            return self._final

    return _Event(Content(role="model", parts=parts), final)


def test_translate_text_part_yields_text_chunk() -> None:
    from google.genai.types import Part

    event = _make_event([Part(text="hello")])
    chunks = ADKAgent._translate(event)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert chunks[0].text == "hello"


def test_translate_thought_part_yields_reasoning_chunk() -> None:
    from google.genai.types import Part

    part = Part(text="thinking through this")
    # ADK marks chain-of-thought parts with thought=True
    object.__setattr__(part, "thought", True)
    event = _make_event([part])
    chunks = ADKAgent._translate(event)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ReasoningChunk)
    assert chunks[0].text == "thinking through this"


def test_translate_function_call_yields_tool_call_chunk() -> None:
    from google.genai.types import FunctionCall, Part

    fc = FunctionCall(name="lookup_order", args={"order_id": "42"})
    object.__setattr__(fc, "id", "fc-001")
    part = Part(function_call=fc)
    event = _make_event([part])
    chunks = ADKAgent._translate(event)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolCallChunk)
    assert chunks[0].name == "lookup_order"
    assert chunks[0].args == {"order_id": "42"}
    assert chunks[0].call_id == "fc-001"


def test_translate_function_response_unwraps_result_dict() -> None:
    from google.genai.types import FunctionResponse, Part

    fr = FunctionResponse(name="lookup_order", response={"result": {"status": "shipped"}})
    object.__setattr__(fr, "id", "fc-001")
    part = Part(function_response=fr)
    event = _make_event([part])
    chunks = ADKAgent._translate(event)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolResultChunk)
    assert chunks[0].name == "lookup_order"
    # ADK wraps simple results in {"result": ...} — adapter unwraps that.
    assert chunks[0].result == {"status": "shipped"}
    assert chunks[0].call_id == "fc-001"


def test_translate_unknown_event_yields_no_chunks() -> None:
    chunks = ADKAgent._translate(object())  # no .content attr
    assert chunks == []


def test_is_final_handles_missing_method() -> None:
    assert ADKAgent._is_final(object()) is False


def test_capture_state_concatenates_final_texts() -> None:
    from google.genai.types import Part

    event = _make_event([Part(text="part one. "), Part(text="part two.")], final=True)
    state = ADKAgent._capture_state(event)
    assert state == {"final_text": "part one. part two."}


def test_capture_state_no_text_returns_none() -> None:
    event = _make_event([])
    assert ADKAgent._capture_state(event) is None
