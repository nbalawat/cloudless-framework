"""Unit tests for cloudless.MAFAgent event-translation logic.

Exercises `_translate()` and `_capture_state()` against synthetic
Microsoft Agent Framework `AgentResponseUpdate` objects — no Azure /
OpenAI / Bedrock calls. The matching real-cloud test lives at
tests/integration/test_maf_adapter_real_bedrock.py.
"""
from __future__ import annotations

import agent_framework as af

import cloudless
from cloudless.adapters.frameworks.maf import MAFAgent


def test_translate_text_content() -> None:
    update = af.AgentResponseUpdate(contents=[af.Content.from_text("hello")])
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert chunks[0].text == "hello"


def test_translate_reasoning_content() -> None:
    update = af.AgentResponseUpdate(
        contents=[af.Content.from_text_reasoning(text="thinking step by step")]
    )
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ReasoningChunk)
    assert chunks[0].text == "thinking step by step"


def test_translate_function_call_with_dict_args() -> None:
    update = af.AgentResponseUpdate(
        contents=[
            af.Content.from_function_call(
                call_id="c1", name="lookup_order", arguments={"order_id": "42"}
            )
        ]
    )
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolCallChunk)
    assert chunks[0].name == "lookup_order"
    assert chunks[0].args == {"order_id": "42"}
    assert chunks[0].call_id == "c1"


def test_translate_function_call_with_json_string_args() -> None:
    update = af.AgentResponseUpdate(
        contents=[
            af.Content.from_function_call(
                call_id="c2", name="search", arguments='{"query": "claude"}'
            )
        ]
    )
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolCallChunk)
    assert chunks[0].args == {"query": "claude"}


def test_translate_function_result() -> None:
    # MAF JSON-encodes dict results into the wire `result` field — the
    # adapter passes that through faithfully so downstream consumers see
    # exactly what MAF emitted on the wire.
    update = af.AgentResponseUpdate(
        contents=[
            af.Content.from_function_result(
                call_id="c1", result={"status": "shipped"}
            )
        ]
    )
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolResultChunk)
    assert chunks[0].result == '{"status": "shipped"}'
    assert chunks[0].call_id == "c1"
    assert chunks[0].is_error is False


def test_translate_function_result_exception_marks_error() -> None:
    update = af.AgentResponseUpdate(
        contents=[
            af.Content.from_function_result(
                call_id="c2", exception="ConnectionRefusedError(...)",
            )
        ]
    )
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolResultChunk)
    assert chunks[0].is_error is True
    assert "ConnectionRefusedError" in str(chunks[0].result)


def test_translate_skips_empty_contents() -> None:
    update = af.AgentResponseUpdate(contents=[])
    chunks = MAFAgent._translate(update)
    assert chunks == []


def test_translate_falls_back_to_text_attr_when_no_contents() -> None:
    class FakeUpdate:
        contents = None
        text = "fallback text"

    chunks = MAFAgent._translate(FakeUpdate())
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert chunks[0].text == "fallback text"


def test_translate_multiple_contents_in_one_update() -> None:
    update = af.AgentResponseUpdate(
        contents=[
            af.Content.from_text("I will search."),
            af.Content.from_function_call(
                call_id="c3", name="web_search", arguments={"q": "x"}
            ),
        ]
    )
    chunks = MAFAgent._translate(update)
    assert len(chunks) == 2
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert isinstance(chunks[1], cloudless.ToolCallChunk)


def test_capture_state_no_terminal_data() -> None:
    update = af.AgentResponseUpdate(contents=[af.Content.from_text("hi")])
    assert MAFAgent._capture_state(update) is None


def test_capture_state_picks_up_finish_reason() -> None:
    update = af.AgentResponseUpdate(
        contents=[af.Content.from_text("done")],
        finish_reason="stop",
    )
    state = MAFAgent._capture_state(update)
    assert state == {"finish_reason": "stop"}
