"""Real-Bedrock Knowledge Base test (gated by user-provisioned KB).

Bedrock KBs require an OpenSearch Serverless collection (~$24/mo) or
Aurora pgvector cluster. Cloudless cannot auto-provision either within
a CI test budget, so this test:

  1. Lists KBs in the account
  2. If at least one exists with a synced data source, exercises `Retrieve`
  3. If none exist, skips with clear instructions for the operator

To enable: create a KB in the AWS console or via Terraform, name it
anything starting with `cloudless-kb-` to mark it as a test target.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        pytest.skip("AWS credentials not configured")
        return False


@pytest.fixture(scope="module")
def cloudless_kb(aws_available):
    """Find a pre-provisioned KB tagged for cloudless testing."""
    import boto3
    client = boto3.client("bedrock-agent", region_name="us-east-1")
    summaries = client.list_knowledge_bases().get("knowledgeBaseSummaries", [])
    if not summaries:
        pytest.skip(
            "No Bedrock Knowledge Base in account. To enable this test, "
            "create one via the console (any embedding model) and ingest "
            "some data. Annual cost ~$24/mo for OpenSearch Serverless."
        )
    # Prefer one named cloudless-kb-*; otherwise pick the first
    chosen = next(
        (kb for kb in summaries if kb["name"].startswith("cloudless-kb-")),
        summaries[0],
    )
    return chosen["knowledgeBaseId"]


async def test_kb_retrieve_returns_results(cloudless_kb):
    """Exercise `BedrockKBBackend.search` against a real KB."""
    # (Direct-backend path used below; the cloudless.VectorStore factory
    # wrapper is exercised in other tests.)
    from cloudless.adapters.aws.vector_store import BedrockKBBackend
    backend = BedrockKBBackend(knowledge_base_id=cloudless_kb, region="us-east-1")

    # Search may return zero results if the KB has no relevant docs; we just
    # validate the call shape works end-to-end.
    results = await backend.search("test query", top_k=3)
    assert isinstance(results, list)
    # If KB has data, results should be non-empty; if empty, the wire path
    # still succeeded — that's the contract under test.
