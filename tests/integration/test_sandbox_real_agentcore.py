"""Real-cloud integration test for cloudless.Sandbox + AgentCore Code Interpreter."""
from __future__ import annotations

import pytest

import cloudless


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        return False


async def test_agentcore_code_interpreter_runs_python(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    sb = cloudless.Sandbox(backend="agentcore", region="us-east-1")
    try:
        result = await sb.execute(code="print(7 * 8)", language="python")
        assert result.exit_code == 0, f"unexpected exit: {result!r}"
        assert "56" in result.stdout, f"unexpected stdout: {result.stdout!r}"
    finally:
        await sb.close()


async def test_agentcore_code_interpreter_handles_error(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    sb = cloudless.Sandbox(backend="agentcore", region="us-east-1")
    try:
        result = await sb.execute(code="raise RuntimeError('intended failure')")
        # AgentCore CI surfaces the traceback in stderr or stdout; assert
        # SOMETHING in the response indicates failure.
        full = result.stdout + result.stderr
        assert "RuntimeError" in full or "intended failure" in full or result.exit_code != 0
    finally:
        await sb.close()
