"""Real-cloud integration test for cloudless.VectorStore.

InMemoryVectorBackend backed by REAL Bedrock Titan embeddings — validates
the full embed → cosine-rank → search loop without any KB infrastructure.
"""
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
    except Exception:  # noqa: BLE001
        return False


async def test_in_memory_vector_store_with_real_embeddings(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")
    embed = cloudless.Embeddings(model="titan-v2", region="us-east-1")
    store = cloudless.VectorStore(embeddings=embed)

    n = await store.upsert([
        {"id": "1", "text": "Paris is the capital of France."},
        {"id": "2", "text": "Tokyo is the capital of Japan."},
        {"id": "3", "text": "Brasília is the capital of Brazil."},
        {"id": "4", "text": "The Pacific Ocean is the largest ocean."},
    ])
    assert n == 4
    assert await store.count() == 4

    # Query semantically; the Japan-related doc should rank first.
    matches = await store.search(query="what is the capital city of Japan", top_k=3)
    assert len(matches) == 3
    assert "Tokyo" in matches[0].text
    # All scores should be in [-1, 1] cosine range
    for m in matches:
        assert -1.0 <= m.score <= 1.0

    # Delete a doc and reconfirm
    deleted = await store.delete(ids=["2"])
    assert deleted == 1
    assert await store.count() == 3
    matches = await store.search(query="Tokyo capital Japan", top_k=3)
    assert all("Tokyo" not in m.text for m in matches)
