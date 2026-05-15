"""Real-cloud integration test for cloudless.MAFAgent.

Builds a Microsoft Agent Framework `Agent` backed by
`agent_framework_bedrock.BedrockChatClient` against real Bedrock
(Nova Micro), runs it through `cloudless.MAFAgent.query()`, asserts
TextChunks come back and the stream terminates with a FinalChunk.

This exercises the full vertical: MAF → BedrockChatClient → boto3
→ AWS Bedrock Runtime. Cost: ~$0.0001 (Nova Micro inference).
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
    except Exception:
        return False


async def test_maf_agent_runs_against_real_bedrock_nova_micro(aws_available) -> None:
    """End-to-end: real Bedrock invocation through cloudless.MAFAgent."""
    if not aws_available:
        pytest.skip("AWS credentials not configured in this environment")

    from agent_framework import Agent as NativeMAFAgent
    from agent_framework_bedrock import BedrockChatClient

    @cloudless.agent(name="maf-bedrock-test", framework="maf")
    class MAFBedrockTestAgent(cloudless.MAFAgent):
        def build(self):
            client = BedrockChatClient(
                model="us.amazon.nova-micro-v1:0",
                region="us-east-1",
            )
            return NativeMAFAgent(
                client,
                instructions="Reply with exactly the single word 'pong'.",
                name="maf_bedrock_test",
            )

    agent_instance = MAFBedrockTestAgent()
    ctx = InMemoryContext(session_id="maf-bedrock-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Say pong."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from Bedrock via MAF; got: {[type(c).__name__ for c in chunks]!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk), (
        "stream must terminate with a FinalChunk"
    )

    full_text = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full_text.lower(), f"model didn't say pong; got: {full_text!r}"

    # In-memory cost tracker is always 0.0 — real cost lives in the deployed
    # runtime's CostTracker.
    assert await ctx.cost.session_total_usd() == 0.0
