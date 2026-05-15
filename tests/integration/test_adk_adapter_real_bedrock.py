"""Real-cloud integration test for cloudless.ADKAgent + AWS Bedrock.

Google ADK ships only `Gemini` (and `LiteLlm`) model classes natively.
cloudless ships `BedrockADKLlm` — an ADK `BaseLlm` subclass that talks
to AWS Bedrock via `boto3.client('bedrock-runtime').converse` — so ADK
users can deploy to AWS without LiteLLM.

Cost: ~$0.0001 (one Nova Micro turn).
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


async def test_adk_agent_runs_against_real_bedrock_nova_micro(aws_available) -> None:
    """End-to-end: ADK + BedrockADKLlm → real Bedrock Nova Micro."""
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    from google.adk.agents import Agent as NativeADKAgent

    from cloudless.adapters.frameworks._bridges import BedrockADKLlm

    @cloudless.agent(name="adk-bedrock-test", framework="adk")
    class ADKBedrockTestAgent(cloudless.ADKAgent):
        def build(self):
            return NativeADKAgent(
                name="adk_bedrock_test",
                model=BedrockADKLlm(
                    model="us.amazon.nova-micro-v1:0", region="us-east-1"
                ),
                instruction="Reply with exactly the single word 'pong'.",
            )

    agent_instance = ADKBedrockTestAgent()
    ctx = InMemoryContext(session_id="adk-bedrock-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Say pong."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from ADK+Bedrock; got: {chunks!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk)
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
