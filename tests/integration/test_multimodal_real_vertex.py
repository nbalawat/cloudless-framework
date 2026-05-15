"""Real-cloud test for multi-modal LLM input.

Generates a tiny PNG in-memory and sends it to Gemini Flash with a
question about its contents. Verifies that:
  - The image bytes travel through the SDK without crashing
  - The model produces a non-empty response (we don't strict-check the
    text — vision-model output is variable)
"""
from __future__ import annotations

import os
import struct
import zlib
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


def _make_solid_color_png(width: int = 32, height: int = 32,
                          r: int = 255, g: int = 92, b: int = 57) -> bytes:
    """Generate a tiny solid-color PNG (default: cloudless spark coral).
    Pure-Python so we don't need PIL/Pillow."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = b""
    row = bytes([r, g, b] * width)
    for _ in range(height):
        raw += b"\x00" + row  # filter type 0 + row data
    idat = zlib.compress(raw, 9)
    iend = b""
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", iend)


async def test_gemini_accepts_png_image_input():
    """The image bytes travel through the SDK successfully."""
    png = _make_solid_color_png()
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke(
        "Describe the predominant color of this image in one word.",
        images=[{"data": png, "mime_type": "image/png"}],
        max_tokens=20,
    )
    assert isinstance(text, str)
    assert text, "vision response empty"


async def test_gemini_multimodal_response_relates_to_image():
    """Send a clearly orange/red image; the response should reference that color."""
    png = _make_solid_color_png(r=255, g=80, b=40)
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke(
        "Is this image more red, blue, or green? Reply with one word.",
        images=[{"data": png, "mime_type": "image/png"}],
        max_tokens=10,
    )
    lower = text.lower()
    # Allow for "red", "orange", or "coral" — all valid descriptions of #FF5028
    assert any(c in lower for c in ("red", "orange", "coral")), \
        f"unexpected color description: {text!r}"


async def test_gemini_multimodal_with_no_images_still_works():
    """Backward compatibility — images=None matches the prior signature."""
    llm = cloudless.LLM(model="gemini-flash", project=GCP_PROJECT)
    text = await llm.invoke("Output exactly: ok", max_tokens=10)
    assert "ok" in text.lower()
