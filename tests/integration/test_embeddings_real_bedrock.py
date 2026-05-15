"""Real-cloud integration test for cloudless.Embeddings + Bedrock Titan."""
from __future__ import annotations

import pytest

import cloudless

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


async def test_titan_v2_embeddings_dimensions(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")
    embed = cloudless.Embeddings(model="titan-v2", region="us-east-1")
    vectors = await embed.embed(["hello world", "second sentence"])
    assert len(vectors) == 2
    # Titan v2 is 1024-dim by default
    assert len(vectors[0]) == 1024
    assert len(vectors[1]) == 1024
    # Vectors should be different for different inputs
    assert vectors[0] != vectors[1]
