"""Real-cloud integration test for cloudless.ADKAgent.

Builds a minimal Google ADK agent backed by real Vertex AI Gemini,
runs it through `cloudless.ADKAgent.query()`, asserts that TextChunks
come back and the stream terminates with a FinalChunk.

Per user directive: every framework adapter validated against a real
cloud — no mocks. Cost: ~$0.0001 (Gemini 2.0 Flash inference).
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
def _wire_vertex_env():
    """Point ADK / google-genai at Vertex AI using the spike service account."""
    if not GCP_KEY.exists():
        pytest.skip(f"GCP service account key not found at {GCP_KEY}")
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(GCP_KEY))
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "agentic-experiments")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    yield


async def test_adk_agent_runs_against_real_vertex_gemini() -> None:
    """End-to-end: real Vertex AI Gemini invocation through cloudless.ADKAgent."""
    from google.adk.agents import Agent as NativeADKAgent

    @cloudless.agent(name="adk-vertex-test", framework="adk")
    class ADKVertexTestAgent(cloudless.ADKAgent):
        def build(self):
            return NativeADKAgent(
                name="adk_vertex_test",
                model="gemini-2.0-flash",
                instruction="Reply with exactly the single word 'pong'.",
            )

    agent_instance = ADKVertexTestAgent()
    ctx = InMemoryContext(session_id="adk-vertex-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Say pong."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from Gemini; got: {chunks!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk), (
        "stream must terminate with a FinalChunk"
    )

    full_text = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full_text.lower(), f"model didn't say pong; got: {full_text!r}"

    # In-memory cost tracker stays at 0.0 — real cost is tracked in deployed runtimes.
    assert await ctx.cost.session_total_usd() == 0.0
