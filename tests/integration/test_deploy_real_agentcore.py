"""The M1 demo loop, end-to-end, against real AgentCore.

Goal (from ROADMAP M1): hello-world LangGraph agent deploys to AgentCore
from local in < 5 min. This test exercises:
  1. cloudless init demo-app (scaffolds project)
  2. cloudless.adapters.aws.deploy(HelloAgent) → real AgentCore runtime
  3. boto3.bedrock-agentcore.invoke_agent_runtime("say pong") → response
  4. cleanup: delete runtime + endpoint

Gated by environment variable CLOUDLESS_RUN_DEPLOY_TESTS=1 because:
  - It costs ~$0.01-0.02 per run (CodeBuild + ECR + Bedrock inference)
  - It takes ~2-3 minutes per run (CodeBuild is the bottleneck)

Run with:
  CLOUDLESS_RUN_DEPLOY_TESTS=1 pytest tests/integration/test_deploy_real_agentcore.py -v -m integration
"""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def deploy_enabled() -> bool:
    return os.environ.get("CLOUDLESS_RUN_DEPLOY_TESTS") == "1"


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


async def test_deploy_hello_world_to_agentcore_and_invoke(
    deploy_enabled, aws_available, tmp_path_factory
):
    """End-to-end: scaffold project → deploy → invoke → assert response."""
    if not aws_available:
        pytest.skip("AWS credentials not configured")
    if not deploy_enabled:
        pytest.skip("Set CLOUDLESS_RUN_DEPLOY_TESTS=1 to run (costs ~$0.02, takes ~3 min)")

    import boto3

    from cloudless.adapters.aws import deploy

    # 1. Scaffold a temp project
    tmp = tmp_path_factory.mktemp("cloudless-deploy-test")
    project_root = tmp / "deploy-demo"
    from cloudless.cli import init as init_cmd
    rc = init_cmd.run("deploy-demo", framework="langgraph",
                      cloud="aws", target_dir=tmp)
    assert rc == 0
    assert project_root.is_dir()

    # 2. Load the scaffolded HelloAgent class
    sys.path.insert(0, str(project_root / "src"))
    try:
        from agents import hello as hello_module
    finally:
        # We'll clean up sys.modules at the end too
        pass
    agent_class = hello_module.HelloAgent

    # 3. Deploy — real AgentCore. This is the slow step (~2-3 min).
    print(f"\n[deploy] Starting deploy of {agent_class.__name__} to us-east-1 ...")
    t0 = time.time()
    result = deploy(
        agent_class,
        region="us-east-1",
        build_dir=project_root / ".cloudless/build/m1deploytest",
        extra_user_files={"user_agent.py": (project_root / "src/agents/hello.py").read_text()},
    )
    elapsed = time.time() - t0
    print(f"[deploy] Done in {elapsed:.1f}s. Runtime: {result.runtime_arn}")

    assert result.runtime_arn.startswith(
        "arn:aws:bedrock-agentcore:us-east-1:613112965612:runtime/"
    )
    assert result.protocol == "HTTP"
    # ecr_uri parsing is best-effort and depends on toolkit output formatting;
    # skip the assertion (the runtime ARN is the real proof).

    # 4. Invoke the deployed runtime via boto3 data-plane API
    try:
        runtime_id = result.runtime_arn.split("/", 1)[1]
        print(f"[invoke] Calling {runtime_id} ...")
        rt = boto3.client("bedrock-agentcore", region_name="us-east-1")
        # The data-plane invoke API
        invoke_response = rt.invoke_agent_runtime(
            agentRuntimeArn=result.runtime_arn,
            runtimeSessionId="cloudless-m1-deploy-test-" + str(int(time.time())),
            payload=json.dumps({"prompt": "Output exactly: pong"}),
        )
        # Read the streaming body
        body_bytes = invoke_response["response"].read()
        body = json.loads(body_bytes)
        print(f"[invoke] Response: {body}")

        # cloudless entrypoint returns {"chunks": [...], "final_text": "...", "agent": "hello"}
        assert "chunks" in body
        assert "final_text" in body
        assert body.get("agent") == "hello"
        assert "pong" in body["final_text"].lower(), \
            f"deployed agent didn't return pong: {body!r}"

    finally:
        # 5. Cleanup — delete the runtime endpoint + runtime
        print(f"[cleanup] Deleting runtime {runtime_id}")
        control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
        try:
            control.delete_agent_runtime_endpoint(
                agentRuntimeId=runtime_id, endpointName="DEFAULT")
        except Exception as e:
            print(f"[cleanup] endpoint delete failed: {e}")
        try:
            control.delete_agent_runtime(agentRuntimeId=runtime_id)
        except Exception as e:
            print(f"[cleanup] runtime delete failed: {e}")
        # Drop the scaffolded sys.modules
        for mod in list(sys.modules):
            if mod.startswith("agents"):
                del sys.modules[mod]
