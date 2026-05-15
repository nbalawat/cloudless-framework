"""Real-cloud integration test for cloudless.LangGraphAgent + GCP Vertex AI.

Builds a minimal LangGraph agent backed by LangChain's official
`ChatVertexAI` (Gemini 2.0 Flash on Vertex AI). No LiteLLM, no shim —
direct native LangChain integration.

This closes the LangGraph × GCP cell of the 5-framework × 2-cloud
matrix. Cost: ~$0.0001 (one Gemini Flash turn).
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


async def test_langgraph_agent_runs_against_real_vertex_gemini() -> None:
    """End-to-end: LangGraph + ChatVertexAI → real Vertex AI Gemini."""
    from langchain_google_vertexai import ChatVertexAI
    from langgraph.graph import END, START, StateGraph
    from typing_extensions import TypedDict

    class State(TypedDict):
        messages: list

    @cloudless.agent(name="lg-vertex-test", framework="langgraph")
    class LGVertexTestAgent(cloudless.LangGraphAgent):
        def build(self):
            llm = ChatVertexAI(
                model_name="gemini-2.0-flash",
                project=os.environ["GOOGLE_CLOUD_PROJECT"],
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )

            def chat(state: State) -> State:
                response = llm.invoke(state["messages"])
                return {"messages": state["messages"] + [response]}

            gb = StateGraph(State)
            gb.add_node("chat", chat)
            gb.add_edge(START, "chat")
            gb.add_edge("chat", END)
            return gb.compile()

    agent_instance = LGVertexTestAgent()
    ctx = InMemoryContext(session_id="lg-vertex-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Reply with exactly the word 'pong'."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from Vertex; got: {chunks!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk)
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
