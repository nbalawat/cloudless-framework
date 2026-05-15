"""Unit tests for cloudless.cli.security (SBOM + pip-audit shell-out)."""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from cloudless.cli import security


def test_generate_sbom_produces_valid_cyclonedx():
    sbom = security.generate_sbom()
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.4"
    assert sbom["serialNumber"].startswith("urn:uuid:")
    assert sbom["version"] == 1
    assert "timestamp" in sbom["metadata"]
    assert sbom["metadata"]["component"]["name"] == "cloudless"
    assert isinstance(sbom["components"], list)
    assert len(sbom["components"]) > 5  # at least our deps


def test_generate_sbom_includes_cloudless_dependency():
    sbom = security.generate_sbom()
    names = {c["name"] for c in sbom["components"]}
    assert "pydantic" in names
    assert "structlog" in names


def test_sbom_components_have_purl():
    sbom = security.generate_sbom()
    for comp in sbom["components"]:
        assert comp["purl"].startswith("pkg:pypi/")
        assert "@" in comp["purl"]


def test_sbom_command_writes_to_file(tmp_path: Path):
    out = tmp_path / "sbom.json"
    rc = security.sbom_command(output_path=str(out))
    assert rc == 0
    data = json.loads(out.read_text())
    assert data["bomFormat"] == "CycloneDX"


def test_sbom_command_prints_to_stdout(monkeypatch):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = security.sbom_command()
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["bomFormat"] == "CycloneDX"


def test_audit_command_when_pip_audit_missing(monkeypatch):
    """When pip-audit isn't on PATH, return 2 and instruct install."""
    monkeypatch.setattr(security.shutil, "which", lambda *a, **kw: None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = security.audit_command()
    assert rc == 2
    assert "pip-audit" in buf.getvalue()
