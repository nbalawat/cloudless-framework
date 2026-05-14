"""cloudless.Sandbox — sandboxed code execution (Q9).

Backends:
  - LocalSubprocessBackend  — `cloudless dev` default. Forks a Python subprocess.
    Security warning: no isolation; do NOT run untrusted code locally.
  - CodeInterpreterBackend  — AWS AgentCore Code Interpreter (Firecracker microVM).
    Per dossier 02: 2 vCPU / 8 GB / 10 GB disk per session; 8h max async.

GCP backend (Agent Sandbox) defers to M2 because GCP exposes the sandbox
through a different API shape (Computer Use model vs. direct exec).
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True)
class SandboxResult:
    """Result of a single Sandbox.execute() call."""

    stdout: str
    stderr: str
    exit_code: int
    """0 on success; non-zero indicates failure (interpreter error or non-zero exit)."""


class SandboxBackend(Protocol):
    async def execute(
        self, *, code: str, language: str = "python",
        timeout_s: float = 60.0,
    ) -> SandboxResult: ...

    async def close(self) -> None: ...


# --------------------------------------------------------------------- #
# LocalSubprocessBackend — `cloudless dev` default
# --------------------------------------------------------------------- #


class LocalSubprocessBackend:
    """Run code via a local subprocess. SECURITY: no isolation."""

    async def execute(
        self, *, code: str, language: str = "python",
        timeout_s: float = 60.0,
    ) -> SandboxResult:
        if language != "python":
            return SandboxResult(
                stdout="",
                stderr=f"LocalSubprocessBackend only supports python (got {language!r})",
                exit_code=1,
            )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            script = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            except asyncio.TimeoutError:
                proc.kill()
                return SandboxResult(stdout="", stderr="execution timed out", exit_code=124)
            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        finally:
            try:
                Path(script).unlink()
            except OSError:
                pass

    async def close(self) -> None:
        pass


# --------------------------------------------------------------------- #
# User-facing Sandbox class
# --------------------------------------------------------------------- #


class Sandbox:
    """Unified sandbox primitive (Q9).

    Example:
        sandbox = cloudless.Sandbox()                          # local subprocess
        sandbox = cloudless.Sandbox(backend="agentcore")       # AWS AgentCore CodeInterpreter
        result = await sandbox.execute(code="print(2 + 2)", language="python")
        print(result.stdout)  # "4\\n"
    """

    def __init__(
        self,
        *,
        backend: str | SandboxBackend = "local",
        region: str = "us-east-1",
        code_interpreter_id: str = "aws.codeinterpreter.v1",
    ) -> None:
        if isinstance(backend, str):
            self._backend = self._build_backend(
                backend, region=region, code_interpreter_id=code_interpreter_id,
            )
        else:
            self._backend = backend

    @staticmethod
    def _build_backend(
        name: str, *, region: str, code_interpreter_id: str,
    ) -> SandboxBackend:
        if name == "local":
            return LocalSubprocessBackend()
        if name == "agentcore":
            from cloudless.adapters.aws.sandbox import CodeInterpreterBackend
            return CodeInterpreterBackend(
                region=region, code_interpreter_id=code_interpreter_id,
            )
        raise ValueError(f"Unknown sandbox backend: {name!r}")

    async def execute(
        self, *, code: str, language: str = "python",
        timeout_s: float = 60.0,
    ) -> SandboxResult:
        return await self._backend.execute(
            code=code, language=language, timeout_s=timeout_s,
        )

    async def close(self) -> None:
        await self._backend.close()
