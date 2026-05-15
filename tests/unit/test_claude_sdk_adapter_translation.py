"""Unit tests for cloudless.ClaudeAgentSDKAgent event-translation logic.

Exercises `_translate()`, `_is_result()`, and `_capture_state()` against
synthetic Claude Agent SDK messages — no Anthropic API calls. The
matching real-cloud test lives at
tests/integration/test_claude_sdk_adapter_real_anthropic.py.
"""
from __future__ import annotations

import claude_agent_sdk as cas

import cloudless
from cloudless.adapters.frameworks.claude_sdk import ClaudeAgentSDKAgent, ClaudeSDKAgent


def test_alias_is_same_class() -> None:
    assert ClaudeSDKAgent is ClaudeAgentSDKAgent


def test_translate_assistant_text_block() -> None:
    msg = cas.AssistantMessage(
        content=[cas.TextBlock(text="hello world")],
        model="claude-opus-4-7",
    )
    chunks = ClaudeAgentSDKAgent._translate(msg)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert chunks[0].text == "hello world"


def test_translate_thinking_block_yields_reasoning() -> None:
    msg = cas.AssistantMessage(
        content=[cas.ThinkingBlock(thinking="step-by-step reasoning", signature="sig")],
        model="claude-opus-4-7",
    )
    chunks = ClaudeAgentSDKAgent._translate(msg)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ReasoningChunk)
    assert chunks[0].text == "step-by-step reasoning"


def test_translate_tool_use_block() -> None:
    msg = cas.AssistantMessage(
        content=[
            cas.ToolUseBlock(id="toolu_01", name="Read", input={"file_path": "/tmp/x"})
        ],
        model="claude-opus-4-7",
    )
    chunks = ClaudeAgentSDKAgent._translate(msg)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolCallChunk)
    assert chunks[0].name == "Read"
    assert chunks[0].args == {"file_path": "/tmp/x"}
    assert chunks[0].call_id == "toolu_01"


def test_translate_tool_result_block_in_user_message() -> None:
    msg = cas.UserMessage(
        content=[
            cas.ToolResultBlock(tool_use_id="toolu_01", content="file contents", is_error=False)
        ],
    )
    chunks = ClaudeAgentSDKAgent._translate(msg)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolResultChunk)
    assert chunks[0].call_id == "toolu_01"
    assert chunks[0].result == "file contents"
    assert chunks[0].is_error is False


def test_translate_tool_result_block_error_flag_propagates() -> None:
    msg = cas.UserMessage(
        content=[
            cas.ToolResultBlock(tool_use_id="toolu_02", content="permission denied", is_error=True)
        ],
    )
    chunks = ClaudeAgentSDKAgent._translate(msg)
    assert len(chunks) == 1
    assert isinstance(chunks[0], cloudless.ToolResultChunk)
    assert chunks[0].is_error is True


def test_translate_mixed_blocks_in_one_assistant_message() -> None:
    msg = cas.AssistantMessage(
        content=[
            cas.TextBlock(text="I'll look that up."),
            cas.ToolUseBlock(id="toolu_03", name="Grep", input={"pattern": "TODO"}),
        ],
        model="claude-opus-4-7",
    )
    chunks = ClaudeAgentSDKAgent._translate(msg)
    assert len(chunks) == 2
    assert isinstance(chunks[0], cloudless.TextChunk)
    assert isinstance(chunks[1], cloudless.ToolCallChunk)


def test_is_result_recognises_result_message() -> None:
    rm = cas.ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=80,
        is_error=False,
        num_turns=2,
        session_id="sess-1",
        total_cost_usd=0.001,
    )
    assert ClaudeAgentSDKAgent._is_result(rm) is True


def test_is_result_rejects_other_messages() -> None:
    msg = cas.AssistantMessage(content=[cas.TextBlock(text="hi")], model="claude-x")
    assert ClaudeAgentSDKAgent._is_result(msg) is False


def test_capture_state_extracts_cost_session_turns() -> None:
    rm = cas.ResultMessage(
        subtype="success",
        duration_ms=200,
        duration_api_ms=150,
        is_error=False,
        num_turns=3,
        session_id="sess-2",
        total_cost_usd=0.0042,
        result="done",
    )
    state = ClaudeAgentSDKAgent._capture_state(rm)
    assert state is not None
    assert state["session_id"] == "sess-2"
    assert state["num_turns"] == 3
    assert state["total_cost_usd"] == 0.0042
    assert state["result"] == "done"
