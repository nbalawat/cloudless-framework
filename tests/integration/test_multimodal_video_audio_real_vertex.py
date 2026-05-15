"""Real-Vertex test for multi-modal video + audio input.

Sends a tiny WAV audio clip and a minimal MP4 video to Gemini Flash and
asserts the request shape works end-to-end.
"""
from __future__ import annotations

import os
import struct
import wave
import io
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


def _make_silent_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a tiny silent WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        n_frames = int(sample_rate * duration_s)
        w.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def _make_minimal_mp4() -> bytes:
    """Read a tiny pre-recorded test MP4 from disk if available, else
    fabricate a 1-second silent black-frame MP4 via ffmpeg if installed.

    For CI environments without ffmpeg, this test skips."""
    import shutil, subprocess, tempfile
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed; can't synthesize test MP4")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        out_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=size=64x64:rate=1:color=black",
             "-t", "1", "-pix_fmt", "yuv420p", out_path],
            check=True, capture_output=True,
        )
        return Path(out_path).read_bytes()
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


async def test_gemini_accepts_audio_input():
    """Send a silent WAV to Gemini Flash; verify the SDK call succeeds."""
    audio = _make_silent_wav(duration_s=0.5)
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke(
        "Briefly describe what you hear (one sentence).",
        audios=[{"data": audio, "mime_type": "audio/wav"}],
        max_tokens=80,
    )
    assert isinstance(text, str)
    assert text  # response received


async def test_gemini_accepts_video_input():
    """Send a tiny black-frame MP4 to Gemini Flash; verify the SDK call succeeds."""
    video = _make_minimal_mp4()
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke(
        "Describe what you see in this video in one short sentence.",
        videos=[{"data": video, "mime_type": "video/mp4"}],
        max_tokens=80,
    )
    assert isinstance(text, str)
    assert text


async def test_gemini_audio_without_data_unchanged():
    """Backward compat — calling with no media kwargs still works."""
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke("Output exactly: ok", max_tokens=10)
    assert "ok" in text.lower()


async def test_bedrock_audio_input_raises_invalid_input():
    """Bedrock Converse doesn't accept inline audio — should raise InvalidInputError."""
    from cloudless.exceptions import InvalidInputError

    audio = _make_silent_wav(duration_s=0.5)
    llm = cloudless.LLM(model="nova-micro")
    with pytest.raises(InvalidInputError, match="audio"):
        await llm.invoke(
            "what is this?",
            audios=[{"data": audio, "mime_type": "audio/wav"}],
            max_tokens=10,
        )
