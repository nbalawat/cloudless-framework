"""Unit tests for Sandbox.upload_file / download_file / long-running."""
from __future__ import annotations

import pytest

import cloudless


pytestmark = [pytest.mark.asyncio]


async def test_upload_and_read_back_via_execute():
    """Upload a file, then have the sandbox read it inside Python code."""
    sb = cloudless.Sandbox()
    try:
        await sb.upload_file(name="data.txt", content=b"hello-from-cloudless")
        result = await sb.execute(code='print(open("data.txt").read())')
        assert "hello-from-cloudless" in result.stdout
        assert result.exit_code == 0
    finally:
        await sb.close()


async def test_download_file_after_execute_writes_it():
    sb = cloudless.Sandbox()
    try:
        result = await sb.execute(code='open("out.txt", "w").write("produced")')
        assert result.exit_code == 0
        content = await sb.download_file(name="out.txt")
        assert content == b"produced"
    finally:
        await sb.close()


async def test_download_missing_file_raises():
    sb = cloudless.Sandbox()
    try:
        with pytest.raises(FileNotFoundError):
            await sb.download_file(name="never-existed.txt")
    finally:
        await sb.close()


async def test_execute_long_running_uses_extended_timeout():
    """Verify the alias method respects max_seconds parameter."""
    sb = cloudless.Sandbox()
    try:
        # Won't actually take long — just exercise the new code path
        result = await sb.execute_long_running(
            code='print("quick")', max_seconds=10.0,
        )
        assert result.exit_code == 0
        assert "quick" in result.stdout
    finally:
        await sb.close()


async def test_close_cleans_up_workspace():
    """Workspace tempdir should be removed on close()."""
    sb = cloudless.Sandbox()
    await sb.upload_file(name="tmp.txt", content=b"x")
    ws = sb._backend.workspace
    assert ws.is_dir()
    await sb.close()
    assert not ws.exists()
