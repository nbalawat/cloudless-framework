"""Real-Vertex integration test for cloudless.LLM(model='gemini-flash').

Calls real Gemini 2.5 Flash via Vertex AI in project agentic-experiments.

F2 coverage: defaults disable extended thinking so a small max_tokens budget
still produces user-visible text.
"""
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


async def test_gemini_flash_invoke_returns_text():
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke(
        "Output exactly: pong",
        system="Always reply with exactly what the user asks for.",
        max_tokens=40,
    )
    assert isinstance(text, str)
    assert "pong" in text.lower(), f"unexpected reply: {text!r}"


async def test_gemini_flash_stream_yields_chunks():
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    chunks: list[str] = []
    async for ch in llm.stream(
        "Reply with exactly: hello",
        system="Always reply with exactly what the user asks for.",
        max_tokens=40,
    ):
        chunks.append(ch.text)
    full = "".join(chunks)
    assert chunks, "no chunks yielded"
    assert "hello" in full.lower(), f"unexpected streamed reply: {full!r}"


async def test_gemini_invalid_project_raises_auth():
    """Bogus project should map to AuthenticationError or InvalidInputError."""
    from cloudless.exceptions import AuthenticationError, InvalidInputError
    llm = cloudless.LLM(model="gemini-flash", project="this-project-does-not-exist-xyz123")
    with pytest.raises((AuthenticationError, InvalidInputError)):
        await llm.invoke("hello", max_tokens=10)
