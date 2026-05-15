"""Real-Vertex integration test for task_type + output_dimensionality."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import cloudless

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


GCP_KEY = Path.home() / "development" / "fsi-banking-gcp-usecases" / "keys" / "agentic-experiments-71fb77221637.json"
GCP_PROJECT = "agentic-experiments"


@pytest.fixture(scope="module", autouse=True)
def _gcp_creds():
    if not GCP_KEY.is_file():
        pytest.skip(f"GCP service account key not found: {GCP_KEY}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_KEY)
    os.environ["CLOUDLESS_GCP_PROJECT"] = GCP_PROJECT
    yield


async def test_retrieval_query_vs_document_yield_different_vectors():
    """The same text embedded with different task_type should yield
    different vectors — that's the whole point of task-typed embeddings."""
    text = "how do agents handle long-running tasks?"

    embed_q = cloudless.Embeddings(
        model="vertex-text-005",
        project=GCP_PROJECT,
        task_type="RETRIEVAL_QUERY",
    )
    embed_d = cloudless.Embeddings(
        model="vertex-text-005",
        project=GCP_PROJECT,
        task_type="RETRIEVAL_DOCUMENT",
    )
    v_q = (await embed_q.embed([text]))[0]
    v_d = (await embed_d.embed([text]))[0]
    assert v_q != v_d, "task_type made no difference — wiring likely broken"


async def test_output_dimensionality_shrinks_vector():
    """text-embedding-005 defaults to 768; force 256 and verify."""
    embed = cloudless.Embeddings(
        model="vertex-text-005",
        project=GCP_PROJECT,
        output_dimensionality=256,
    )
    vec = (await embed.embed(["hello"]))[0]
    assert len(vec) == 256, f"expected 256-dim vector, got {len(vec)}"


async def test_default_dimensionality_unchanged():
    """Without output_dimensionality, you get the model's default."""
    embed = cloudless.Embeddings(model="vertex-text-005", project=GCP_PROJECT)
    vec = (await embed.embed(["hello"]))[0]
    assert len(vec) == 768
