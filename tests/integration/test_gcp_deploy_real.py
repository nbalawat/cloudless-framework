"""Real-cloud integration test for the cloudless GCP deploy adapter.

End-to-end: scaffold project with --cloud gcp → deploy via
cloudless.adapters.gcp.deploy() → invoke via vertexai.agent_engines.get
→ assert response → cleanup.

Gated by CLOUDLESS_RUN_DEPLOY_TESTS=1 (costs ~$0.02, takes ~3 min).
"""
from __future__ import annotations

import os
import sys
import time

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def deploy_enabled() -> bool:
    return os.environ.get("CLOUDLESS_RUN_DEPLOY_TESTS") == "1"


@pytest.fixture(scope="module")
def gcp_available() -> bool:
    try:
        import vertexai
        vertexai.init(project="agentic-experiments", location="us-central1")
        return True
    except Exception:  # noqa: BLE001
        return False


async def test_cloudless_gcp_deploy_hello_world(deploy_enabled, gcp_available, tmp_path_factory):
    if not gcp_available:
        pytest.skip("GCP credentials not configured")
    if not deploy_enabled:
        pytest.skip("Set CLOUDLESS_RUN_DEPLOY_TESTS=1 to run (costs ~$0.02, takes ~3 min)")

    import cloudless
    from cloudless.adapters.gcp import deploy

    # 1. Scaffold a project with --cloud gcp
    tmp = tmp_path_factory.mktemp("cloudless-gcp-deploy")
    from cloudless.cli import init as init_cmd
    rc = init_cmd.run("gcp-demo", framework="langgraph", cloud="gcp", target_dir=tmp)
    assert rc == 0

    project_root = tmp / "gcp-demo"
    # The scaffolded hello.py uses langchain_aws — for GCP we want a
    # Vertex-Gemini agent instead. Always overwrite (the langchain_aws
    # version would deploy but require Bedrock IAM at runtime).
    (project_root / "src" / "agents" / "hello.py").write_text(_GEMINI_HELLO_AGENT)
    sys.path.insert(0, str(project_root / "src"))
    # Clear any cached agents module before importing fresh
    for mod in list(sys.modules):
        if mod.startswith("agents"):
            del sys.modules[mod]
    from agents import hello as hello_module
    agent_class = hello_module.HelloAgent

    # 2. Deploy
    project = os.environ.get("CLOUDLESS_GCP_PROJECT", "agentic-experiments")
    print(f"\n[gcp-deploy] {agent_class.__name__} → {project}/us-central1 ...")
    t0 = time.time()
    result = deploy(
        agent_class,
        project=project,
        location="us-central1",
    )
    print(f"[gcp-deploy] Done in {time.time() - t0:.1f}s. Resource: {result.resource_name}")

    assert result.resource_name.startswith(f"projects/")
    assert "reasoningEngines/" in result.resource_name
    assert result.project == project

    # 3. Invoke
    import vertexai
    from vertexai import agent_engines
    vertexai.init(project=project, location="us-central1")
    remote = agent_engines.get(result.resource_name)

    print("[gcp-invoke] Calling query() on the deployed engine ...")
    try:
        resp = remote.query(prompt="Output exactly: pong")
        print(f"[gcp-invoke] Response: {resp}")
        # Cloudless GCP wrapper returns {"chunks": [...], "final_text": "...", "agent": "..."}
        # final_text is empty for non-streaming LangGraph nodes (which use
        # llm.invoke()); pong is still in the FinalChunk's state.messages.
        # Assert "pong" appears anywhere in the response payload.
        import json
        flat = json.dumps(resp).lower()
        assert "pong" in flat, f"unexpected: {resp!r}"
    finally:
        # 4. Cleanup
        try:
            agent_engines.delete(result.resource_name, force=True)
            print(f"[cleanup] Deleted {result.resource_name}")
        except Exception as e:  # noqa: BLE001
            print(f"[cleanup] delete failed: {e}")


# Minimal Vertex-Gemini agent that doesn't require Bedrock at all
_GEMINI_HELLO_AGENT = '''\
"""Hello world cloudless agent — Vertex Gemini-backed for GCP deploy."""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

import cloudless


class State(TypedDict):
    messages: list


@cloudless.agent(name="hello", framework="langgraph", interfaces=["http"])
class HelloAgent(cloudless.LangGraphAgent):
    def build(self):
        def chat(state: State) -> State:
            # Defer the genai client to runtime so it's not pickled
            from google import genai
            client = genai.Client(vertexai=True)
            prompt = state["messages"][-1]["content"]
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"max_output_tokens": 50},
            )
            return {"messages": state["messages"] + [{"role": "assistant",
                                                      "content": resp.text or ""}]}

        gb = StateGraph(State)
        gb.add_node("chat", chat)
        gb.add_edge(START, "chat")
        gb.add_edge("chat", END)
        return gb.compile()
'''
