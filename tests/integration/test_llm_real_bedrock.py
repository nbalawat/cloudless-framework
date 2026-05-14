"""Real-cloud integration test for cloudless.LLM.

Cost: ~$0.0002 per run. Validates:
  - invoke() returns expected text
  - stream() yields TextChunks
  - Cost tracker is updated on the ctx
  - Inference-profile IDs resolve correctly (F1)
"""
from __future__ import annotations

import pytest

import cloudless
from cloudless.runtime import InMemoryContext


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        return False


async def test_llm_invoke_returns_pong(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")
    llm = cloudless.LLM(model="nova-micro")
    ctx = InMemoryContext()
    text = await llm.invoke(
        "Output exactly this single word with no punctuation: pong",
        system="Always output exactly what the user asks for, no more.",
        max_tokens=50,
        ctx=ctx,
    )
    assert "pong" in text.lower(), f"unexpected response: {text!r}"
    # Cost tracker recorded the call
    calls = ctx.cost.llm_calls  # type: ignore[attr-defined]
    assert len(calls) == 1
    assert calls[0]["model"] == "us.amazon.nova-micro-v1:0"
    assert calls[0]["input_tokens"] > 0
    assert calls[0]["output_tokens"] > 0


async def test_llm_stream_yields_text_chunks(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")
    llm = cloudless.LLM(model="nova-micro")
    ctx = InMemoryContext()
    chunks: list[cloudless.TextChunk] = []
    async for chunk in llm.stream(
        "Output exactly this single word with no punctuation: pong",
        system="Always output exactly what the user asks for, no more.",
        max_tokens=50,
        ctx=ctx,
    ):
        chunks.append(chunk)
    assert len(chunks) >= 1
    assert all(isinstance(c, cloudless.TextChunk) for c in chunks)
    full = "".join(c.text for c in chunks)
    assert "pong" in full.lower(), f"streamed text: {full!r}"
    # Streaming usage records once at the end
    calls = ctx.cost.llm_calls  # type: ignore[attr-defined]
    assert len(calls) == 1
    assert calls[0]["output_tokens"] > 0


async def test_llm_resolves_inference_profile_id(aws_available):
    """F1: cloudless.LLM must transparently use the us.* inference profile prefix."""
    if not aws_available:
        pytest.skip("AWS credentials not configured")
    # If we passed the raw model ID without prefix, Bedrock would 400.
    # cloudless.LLM with alias "nova-micro" must resolve to inference-profile form.
    llm = cloudless.LLM(model="nova-micro")
    assert llm.alias.model_id == "us.amazon.nova-micro-v1:0"
    # And we can actually call it
    text = await llm.invoke("hi", max_tokens=10)
    assert isinstance(text, str) and text
