"""Real-cloud integration test for cloudless.MAFAgent + GCP Vertex AI.

`agent-framework-bedrock` exists; no official `agent-framework-vertex`
ships in v1.4. cloudless ships `VertexMAFChatClient` — a MAF
`BaseChatClient` subclass that talks to Vertex AI via `google.genai` —
so MAF users can deploy to GCP without LiteLLM.

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


async def test_maf_agent_runs_against_real_vertex_gemini() -> None:
    """End-to-end: MAF + VertexMAFChatClient → real Vertex AI Gemini."""
    from agent_framework import Agent as NativeMAFAgent

    from cloudless.adapters.frameworks._bridges import VertexMAFChatClient

    @cloudless.agent(name="maf-vertex-test", framework="maf")
    class MAFVertexTestAgent(cloudless.MAFAgent):
        def build(self):
            client = VertexMAFChatClient(
                model="gemini-2.0-flash",
                project=os.environ["GOOGLE_CLOUD_PROJECT"],
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
            return NativeMAFAgent(
                client,
                instructions="Reply with exactly the single word 'pong'.",
                name="maf_vertex_test",
            )

    agent_instance = MAFVertexTestAgent()
    ctx = InMemoryContext(session_id="maf-vertex-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Say pong."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from MAF+Vertex; got: {chunks!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk)
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
