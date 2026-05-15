"""Unit tests for ManifestRefresher TTL behavior."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cloudless.runtime.manifest import Manifest, ManifestRefresher


def _write_manifest(path: Path, project: str, agents: dict) -> None:
    path.write_text(json.dumps({"project": project, "agents": agents}))


def test_refresher_loads_initial_from_path(tmp_path: Path):
    p = tmp_path / "manifest.json"
    _write_manifest(p, "demo", {"a": {"cloud": "aws", "http_url": "http://x"}})
    r = ManifestRefresher(path=p, interval_seconds=60)
    assert r.current().project == "demo"
    assert "a" in r.current().agents


def test_refresh_now_picks_up_file_changes(tmp_path: Path):
    p = tmp_path / "manifest.json"
    _write_manifest(p, "demo", {"a": {"cloud": "aws"}})
    r = ManifestRefresher(path=p, interval_seconds=60)
    assert "a" in r.current().agents
    # Rewrite the manifest with a different agent
    _write_manifest(p, "demo", {"b": {"cloud": "gcp"}})
    new = r.refresh_now()
    assert "b" in new.agents
    assert "a" not in new.agents


def test_refresher_handles_missing_file_gracefully(tmp_path: Path):
    p = tmp_path / "missing.json"
    r = ManifestRefresher(path=p, interval_seconds=60)
    # Should return empty Manifest, not crash
    assert isinstance(r.current(), Manifest)
    assert r.current().agents == {}


def test_refresher_thread_lifecycle(tmp_path: Path):
    p = tmp_path / "manifest.json"
    _write_manifest(p, "demo", {})
    r = ManifestRefresher(path=p, interval_seconds=0.05)
    r.start()
    # Mutate the file; wait briefly so the background loop sees it
    _write_manifest(p, "demo", {"new": {"cloud": "aws"}})
    time.sleep(0.2)
    r.stop()
    # Last refresh should have picked up the new agent
    assert "new" in r.current().agents


def test_refresh_failure_keeps_previous(tmp_path: Path, monkeypatch):
    """A failed refresh must not blow away the existing manifest."""
    p = tmp_path / "manifest.json"
    _write_manifest(p, "demo", {"good": {"cloud": "aws"}})
    r = ManifestRefresher(path=p, interval_seconds=60)
    p.write_text("not valid JSON {{{")  # corrupt
    r.refresh_now()
    # Previous manifest preserved
    assert "good" in r.current().agents


def test_url_source_via_httpx_mock(monkeypatch):
    """When CLOUDLESS_MANIFEST_URL is set, refresher fetches via httpx."""
    import httpx
    payload = {"project": "demo", "agents": {"x": {"cloud": "aws"}}}

    class _FakeResponse:
        def raise_for_status(self): pass
        def json(self): return payload

    def fake_get(url, timeout=None):
        assert url == "https://example.com/manifest.json"
        return _FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    r = ManifestRefresher(url="https://example.com/manifest.json", interval_seconds=60)
    assert "x" in r.current().agents
