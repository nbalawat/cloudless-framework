"""Shared test harness for multi-agent pattern integration tests.

Each pattern test runs a tiny composition of cloudless agents in-process
against REAL LLM calls on either Bedrock (Nova Micro) or Vertex Gemini
(Gemini Flash). Most tests are parametrized to run on BOTH clouds so we
prove the pattern itself is cloud-agnostic.

  - `drain(agent, ctx, prompt)`: collect all chunks from agent.query()
  - `find_pause(chunks)`: extract the first PauseChunk if any
  - `complete_pause(token, approval)`: resolve a paused task
  - `fast_llm(provider)`: cloudless.LLM for the given provider
  - `aws_available()`: skip the module if AWS STS auth fails
  - `gcp_available()`: skip the module if GCP ADC isn't resolvable
  - `provider` fixture: parametrize over ('bedrock', 'gemini')

Cost per parametrized test: ~$0.0002 (one Bedrock Nova Micro + one Gemini
Flash call), within the certification budget.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import cloudless
from cloudless.chunks import Chunk, PauseChunk
from cloudless.runtime.tasks import TaskRecord, get_task, resume


GCP_KEY = Path.home() / "development" / "fsi-banking-gcp-usecases" / "keys" / "agentic-experiments-71fb77221637.json"
GCP_PROJECT = "agentic-experiments"


async def drain(agent, ctx, prompt: str) -> list[Chunk]:
    """Run agent.query() to completion, return all yielded chunks."""
    chunks: list[Chunk] = []
    async for chunk in agent.query(ctx, prompt):
        chunks.append(chunk)
    return chunks


def find_pause(chunks: list[Chunk]) -> PauseChunk | None:
    """Return the first PauseChunk in `chunks`, or None."""
    for c in chunks:
        if isinstance(c, PauseChunk):
            return c
    return None


def complete_pause(token: str, approval: dict) -> TaskRecord:
    """Resolve a paused task. Returns the record so tests can assert state."""
    rec = resume(token, approval)
    assert rec is not None, f"resume({token!r}) returned None — token unknown or already resolved"
    assert rec.resolved is True
    return rec


def fast_llm(provider: str = "bedrock") -> cloudless.LLM:
    """Cheap default LLM for pattern tests.

    Args:
        provider: "bedrock" (Nova Micro, us-east-1) or "gemini" (Gemini 2.5 Flash,
                   Vertex AI, us-central1 in project agentic-experiments).
    """
    if provider == "bedrock":
        return cloudless.LLM(model="nova-micro", region="us-east-1")
    if provider == "gemini":
        return cloudless.LLM(
            model="gemini-flash",
            project=os.environ.get("CLOUDLESS_GCP_PROJECT", GCP_PROJECT),
            location="us-central1",
        )
    raise ValueError(f"unknown provider: {provider!r}")


@pytest.fixture(scope="module")
def aws_available() -> bool:
    """Skip the module if AWS creds + STS aren't usable."""
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        pytest.skip("AWS credentials not configured")
        return False


@pytest.fixture(scope="module")
def gcp_available() -> bool:
    """Skip the module if GCP ADC can't be resolved.

    Also sets GOOGLE_APPLICATION_CREDENTIALS + CLOUDLESS_GCP_PROJECT
    if the conventional key file exists, so tests can run without
    manual env setup.
    """
    if GCP_KEY.is_file() and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_KEY)
    if not os.environ.get("CLOUDLESS_GCP_PROJECT"):
        os.environ["CLOUDLESS_GCP_PROJECT"] = GCP_PROJECT
    try:
        import google.auth
        google.auth.default()
        return True
    except Exception:  # noqa: BLE001
        pytest.skip("GCP credentials not configured")
        return False


@pytest.fixture(params=["bedrock", "gemini"], scope="function")
def provider(request, aws_available, gcp_available) -> str:
    """Parametrize a test over both LLM providers. Skips cleanly if either
    cloud is unavailable."""
    return request.param
