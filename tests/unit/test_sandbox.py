"""Unit tests for cloudless.Sandbox + LocalSubprocessBackend."""
from __future__ import annotations

import pytest

import cloudless
from cloudless.catalog.sandbox import LocalSubprocessBackend, Sandbox, SandboxResult


class TestLocalBackend:
    async def test_execute_simple_python(self):
        sb = Sandbox()
        result = await sb.execute(code="print(1 + 2)")
        assert result.exit_code == 0
        assert result.stdout.strip() == "3"
        assert result.stderr == ""

    async def test_capture_stderr(self):
        sb = Sandbox()
        result = await sb.execute(code="import sys; sys.stderr.write('boom')")
        assert result.exit_code == 0
        assert "boom" in result.stderr

    async def test_nonzero_exit(self):
        sb = Sandbox()
        result = await sb.execute(code="raise SystemExit(2)")
        assert result.exit_code == 2

    async def test_uncaught_exception(self):
        sb = Sandbox()
        result = await sb.execute(code="raise RuntimeError('oops')")
        assert result.exit_code != 0
        assert "RuntimeError" in result.stderr

    async def test_unsupported_language(self):
        sb = Sandbox()
        result = await sb.execute(code="console.log(1)", language="javascript")
        assert result.exit_code != 0
        assert "python" in result.stderr.lower()

    async def test_timeout(self):
        sb = Sandbox()
        result = await sb.execute(
            code="import time; time.sleep(10)",
            timeout_s=0.5,
        )
        assert result.exit_code == 124  # timeout convention


class TestBackendSelection:
    def test_default_is_local(self):
        sb = Sandbox()
        assert isinstance(sb._backend, LocalSubprocessBackend)

    def test_unknown_backend_rejected(self):
        with pytest.raises(ValueError, match="Unknown sandbox backend"):
            Sandbox(backend="docker")


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.Sandbox is Sandbox
        assert cloudless.SandboxResult is SandboxResult
        assert cloudless.LocalSubprocessBackend is LocalSubprocessBackend
