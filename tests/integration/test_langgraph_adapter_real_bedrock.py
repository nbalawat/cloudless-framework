"""Real-cloud integration test for cloudless.LangGraphAgent.

Builds a minimal LangGraph agent backed by real Bedrock (Nova Micro),
runs it through cloudless.LangGraphAgent.query(), asserts that text
chunks come back and the final state is captured.

Per user directive (2026-05-14): every component validated in real env,
not just unit-mocked. Cost: ~$0.0001 (Bedrock Nova Micro inference).
"""
from __future__ import annotations

import pytest

import cloudless
from cloudless.runtime import InMemoryContext

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    """Skip if no AWS credentials in env."""
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


async def test_langgraph_agent_runs_against_real_bedrock_nova_micro(aws_available):
    """End-to-end: real Bedrock invocation through cloudless.LangGraphAgent."""
    if not aws_available:
        pytest.skip("AWS credentials not configured in this environment")

    # Defer imports to keep the test discoverable without langgraph installed
    from langchain.chat_models import init_chat_model
    from langgraph.graph import END, START, StateGraph
    from typing_extensions import TypedDict

    class State(TypedDict):
        messages: list

    @cloudless.agent(name="lg-bedrock-test", framework="langgraph")
    class LGBedrockTestAgent(cloudless.LangGraphAgent):
        def build(self):
            # Nova Micro — confirmed working via converse_stream per F15
            llm = init_chat_model(
                "us.amazon.nova-micro-v1:0",
                model_provider="bedrock_converse",
                region_name="us-east-1",
            )

            def chat(state: State) -> State:
                response = llm.invoke(state["messages"])
                return {"messages": state["messages"] + [response]}

            gb = StateGraph(State)
            gb.add_node("chat", chat)
            gb.add_edge(START, "chat")
            gb.add_edge("chat", END)
            return gb.compile()

    agent_instance = LGBedrockTestAgent()
    ctx = InMemoryContext(session_id="lg-bedrock-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Reply with exactly the word 'pong'."):
        chunks.append(chunk)

    # Assertions:
    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), \
        "expected at least one TextChunk from Bedrock streaming"
    assert isinstance(chunks[-1], cloudless.FinalChunk), \
        "stream must terminate with a FinalChunk"

    # All text combined should mention 'pong'
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"

    # Cost tracker stayed sane (in-memory, always 0.0)
    assert await ctx.cost.session_total_usd() == 0.0
