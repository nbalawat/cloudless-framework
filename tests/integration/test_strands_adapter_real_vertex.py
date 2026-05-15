"""Real-cloud integration test for cloudless.StrandsAgent + GCP Vertex AI.

Strands Agents ships only `BedrockModel` natively. cloudless ships
`VertexStrandsModel` (a Strands `Model` subclass that talks to Vertex
via `google.genai`) so Strands users can deploy to GCP without
LiteLLM or a third-party shim.

Cost: ~$0.0001 (one Gemini Flash turn).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import cloudless
from cloudless.runtime import InMemoryContext

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


GCP_KEY = Path.home() / "development/fsi-banking-gcp-usecases/keys/agentic-experiments-71fb77221637.json"


@pytest.fixture(scope="module", autouse=True)
def _wire_gcp_env():
    if not GCP_KEY.exists():
        pytest.skip(f"GCP service account key not found at {GCP_KEY}")
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(GCP_KEY))
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "agentic-experiments")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    yield


async def test_strands_agent_runs_against_real_vertex_gemini() -> None:
    """End-to-end: Strands + VertexStrandsModel → real Vertex AI Gemini."""
    from strands import Agent as StrandsNativeAgent

    from cloudless.adapters.frameworks._bridges import VertexStrandsModel

    @cloudless.agent(name="strands-vertex-test", framework="strands")
    class StrandsVertexTestAgent(cloudless.StrandsAgent):
        def build(self):
            return StrandsNativeAgent(
                name="strands_vertex_test",
                model=VertexStrandsModel(
                    model="gemini-2.0-flash",
                    project=os.environ["GOOGLE_CLOUD_PROJECT"],
                    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                ),
                system_prompt="Reply with exactly the single word 'pong'.",
            )

    agent_instance = StrandsVertexTestAgent()
    ctx = InMemoryContext(session_id="strands-vertex-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Say pong."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from Strands+Vertex; got: {chunks!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk)
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
