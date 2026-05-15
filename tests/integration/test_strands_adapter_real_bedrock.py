"""Real-cloud integration test for cloudless.StrandsAgent.

Builds a minimal Strands agent backed by real Bedrock (Nova Micro — per F15),
runs it through cloudless.StrandsAgent.query(), asserts that text chunks
come back.
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


async def test_strands_agent_runs_against_real_bedrock_nova_micro(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured in this environment")

    from strands import Agent as StrandsCoreAgent

    @cloudless.agent(name="strands-bedrock-test", framework="strands")
    class StrandsBedrockTestAgent(cloudless.StrandsAgent):
        def build(self):
            return StrandsCoreAgent(
                name="strands-bedrock-test",
                model="us.amazon.nova-micro-v1:0",  # F15: streaming-safe
                system_prompt="Always reply with exactly the single word 'pong'.",
            )

    agent_instance = StrandsBedrockTestAgent()
    ctx = InMemoryContext(session_id="strands-bedrock-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "say pong"):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), \
        "expected at least one TextChunk from Strands"
    assert isinstance(chunks[-1], cloudless.FinalChunk), \
        "stream must terminate with a FinalChunk"

    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
