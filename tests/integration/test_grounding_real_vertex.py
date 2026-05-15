"""Real-Vertex test for Gemini grounding with Google Search."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import cloudless

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


GCP_KEY = Path.home() / "development" / "fsi-banking-gcp-usecases" / "keys" / "agentic-experiments-71fb77221637.json"
GCP_PROJECT = "agentic-experiments"


@pytest.fixture(scope="module", autouse=True)
def _gcp_creds():
    if not GCP_KEY.is_file():
        pytest.skip(f"GCP service account key not found: {GCP_KEY}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_KEY)
    os.environ["CLOUDLESS_GCP_PROJECT"] = GCP_PROJECT
    yield


async def test_grounding_enables_search_in_response():
    """A current-events question should produce a response when grounding=True."""
    llm = cloudless.LLM(
        model="gemini-flash",
        project=GCP_PROJECT,
        grounding=True,
    )
    text = await llm.invoke(
        "In one sentence, what year was the Apollo 11 moon landing?",
        max_tokens=80,
    )
    assert text
    assert "1969" in text  # well-known historical fact, easy verification


async def test_grounding_off_still_works():
    """grounding=False (default) should also work — backward compat."""
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke("What is 2+2? Reply with a single digit.", max_tokens=10)
    assert "4" in text
