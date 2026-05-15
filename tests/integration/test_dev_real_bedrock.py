"""Real-cloud integration test for `cloudless dev`.

Spawns `cloudless dev hello` as a subprocess, hits /ping and /invocations
with a real Bedrock-backed LangGraph agent, asserts 'pong' comes back.

Validates the full local-dev inner-loop (Q13):
  scaffold → dev server → real Bedrock → typed Chunks → HTTP response.

Cost: ~$0.0001 (Bedrock Nova Micro inference). Time: ~12s (boot + invoke).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


async def test_cloudless_dev_serves_real_bedrock_agent(aws_available, tmp_path_factory):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    # 1. Scaffold a project
    tmp = tmp_path_factory.mktemp("cloudless-dev-test")
    from cloudless.cli import init as init_cmd
    rc = init_cmd.run("dev-demo", framework="langgraph", cloud="aws", target_dir=tmp)
    assert rc == 0
    project = tmp / "dev-demo"

    # 2. Spawn `cloudless dev hello` as a subprocess
    port = _free_port()
    # Pick the cloudless CLI from our dev venv
    cloudless_cli = Path(sys.executable).parent / "cloudless"
    assert cloudless_cli.is_file(), f"cloudless CLI not found at {cloudless_cli}"

    proc = subprocess.Popen(
        [str(cloudless_cli), "dev", "hello", "--port", str(port)],
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    try:
        # 3. Wait for the server to come up (poll /ping)
        url_ping = f"http://127.0.0.1:{port}/ping"
        deadline = time.time() + 25.0
        while time.time() < deadline:
            try:
                r = httpx.get(url_ping, timeout=1.0)
                if r.status_code == 200:
                    break
            except Exception:
                time.sleep(0.3)
        else:
            # Server never came up — dump output to help diagnose
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            out = (proc.stdout.read() if proc.stdout else "")[-1200:]
            pytest.fail(f"`cloudless dev` never reached /ping. Output:\n{out}")

        # 4. POST /invocations with a real prompt
        url_inv = f"http://127.0.0.1:{port}/invocations"
        r = httpx.post(
            url_inv,
            json={"prompt": "Output exactly: pong"},
            timeout=30.0,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert "chunks" in body
        assert "final_text" in body
        assert body.get("agent") == "hello"
        assert "pong" in body["final_text"].lower(), f"unexpected response: {body!r}"

    finally:
        # 5. Tear down the subprocess
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
