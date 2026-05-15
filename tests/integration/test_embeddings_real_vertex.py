"""Real-Vertex integration test for cloudless.Embeddings (text-embedding-005)."""
from __future__ import annotations

import math
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


async def test_vertex_embeddings_basic_shape():
    embed = cloudless.Embeddings(model="vertex-text-005", project=GCP_PROJECT)
    vectors = await embed.embed(["hello world", "the quick brown fox"])
    assert len(vectors) == 2
    assert all(len(v) == 768 for v in vectors), [len(v) for v in vectors]
    # Embeddings should not be all zeros or NaN.
    for v in vectors:
        assert any(x != 0.0 for x in v)
        assert all(math.isfinite(x) for x in v)


async def test_vertex_embeddings_semantic_similarity():
    """Two related sentences should be closer than two unrelated ones."""
    embed = cloudless.Embeddings(model="vertex-text-005", project=GCP_PROJECT)
    vectors = await embed.embed([
        "the cat sat on the mat",
        "a feline rested on the rug",
        "quantum chromodynamics governs gluon interactions",
    ])

    def cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb)

    sim_related = cosine(vectors[0], vectors[1])
    sim_unrelated = cosine(vectors[0], vectors[2])
    assert sim_related > sim_unrelated, (
        f"related={sim_related:.3f} not greater than unrelated={sim_unrelated:.3f}"
    )
