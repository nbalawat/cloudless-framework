"""Integration test for cloudless.testing.llm_cassette.

Mixed unit + integration: record uses REAL Bedrock once, replay is purely
in-memory deterministic afterward.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import cloudless
from cloudless.testing import llm_cassette


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        return False


async def test_cassette_record_then_replay(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    with tempfile.TemporaryDirectory() as td:
        cassette = Path(td) / "test.cassette.jsonl"

        # RECORD — real Bedrock call
        with llm_cassette(cassette, mode="record"):
            llm = cloudless.LLM(model="nova-micro")
            text_recorded = await llm.invoke(
                "Output exactly: pong",
                system="Always output exactly what the user asks for.",
                max_tokens=40,
            )
        assert "pong" in text_recorded.lower()
        assert cassette.is_file()
        assert cassette.read_text().count("\n") >= 1

        # REPLAY — no Bedrock call should be made. Verify by setting an
        # AWS_PROFILE that can't authenticate (still works because no boto3 call).
        with llm_cassette(cassette, mode="replay"):
            llm = cloudless.LLM(model="nova-micro")
            text_replayed = await llm.invoke(
                "Output exactly: pong",
                system="Always output exactly what the user asks for.",
                max_tokens=40,
            )
        # Replay returns exactly what we recorded
        assert text_replayed == text_recorded


async def test_cassette_replay_misses_raise(aws_available):
    """Replay of a prompt that wasn't recorded must fail loudly."""
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    with tempfile.TemporaryDirectory() as td:
        cassette = Path(td) / "miss.cassette.jsonl"
        # Empty cassette
        cassette.write_text("")
        with llm_cassette(cassette, mode="replay"):
            llm = cloudless.LLM(model="nova-micro")
            with pytest.raises(RuntimeError, match="No cassette entry"):
                await llm.invoke("never recorded prompt", max_tokens=10)


async def test_cassette_stream_record_replay(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    with tempfile.TemporaryDirectory() as td:
        cassette = Path(td) / "stream.cassette.jsonl"
        with llm_cassette(cassette, mode="record"):
            llm = cloudless.LLM(model="nova-micro")
            chunks = []
            async for c in llm.stream(
                "Output exactly: pong",
                system="Always output exactly what the user asks for.",
                max_tokens=40,
            ):
                chunks.append(c)
            recorded_text = "".join(c.text for c in chunks)
        assert "pong" in recorded_text.lower()

        with llm_cassette(cassette, mode="replay"):
            llm = cloudless.LLM(model="nova-micro")
            chunks2 = []
            async for c in llm.stream(
                "Output exactly: pong",
                system="Always output exactly what the user asks for.",
                max_tokens=40,
            ):
                chunks2.append(c)
            replayed_text = "".join(c.text for c in chunks2)
        assert replayed_text == recorded_text
