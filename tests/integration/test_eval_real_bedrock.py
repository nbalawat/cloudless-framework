"""Real-cloud integration test for cloudless.eval.

Runs a 3-row dataset against real Bedrock Nova Micro; computes deterministic
metrics; asserts the framework summarizes correctly.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import cloudless
from cloudless.eval import EvalDataset, contains_substring, run_eval

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


async def test_eval_against_real_bedrock_nova_micro(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "demo.jsonl"
        path.write_text(
            json.dumps({"id": "1",
                        "prompt": "Output exactly: pong",
                        "expected_contains": "pong"}) + "\n" +
            json.dumps({"id": "2",
                        "prompt": "Output exactly: 4",
                        "expected_contains": "4"}) + "\n" +
            json.dumps({"id": "3",
                        "prompt": "Output exactly: hello",
                        "expected_contains": "hello"}) + "\n"
        )
        dataset = EvalDataset.from_jsonl(path)
        assert len(dataset.cases) == 3

        async def target(prompt: str) -> str:
            llm = cloudless.LLM(model="nova-micro", region="us-east-1")
            return await llm.invoke(
                prompt,
                system="Always output exactly what the user asks for, no more.",
                max_tokens=40,
            )

        run = await run_eval(dataset, target, metrics=[contains_substring()])
        assert len(run.results) == 3  # 3 cases × 1 metric
        summary = run.summary["contains_substring"]
        # Real LLM, so we hope it passes all 3 but assert at least 2 (graceful)
        assert summary["passed"] >= 2, f"only {summary['passed']}/3 passed: {run.results}"
        assert summary["pass_rate"] >= 2 / 3
