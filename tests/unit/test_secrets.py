"""Unit tests for cloudless.Secrets + LocalFileBackend."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import cloudless
from cloudless.catalog.secrets import LocalFileBackend, Secrets


@pytest.fixture
def secrets_file():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "dev-secrets.yaml"
        p.write_text(
            "bedrock_region: us-east-1\n"
            "openai_api_key: sk-test-12345\n"
            "slack_signing_secret: ABCDEF\n"
        )
        yield p


class TestLocalFileBackend:
    async def test_get_returns_value(self, secrets_file):
        secrets = Secrets(path=secrets_file)
        assert await secrets.get("openai_api_key") == "sk-test-12345"

    async def test_get_missing_returns_None(self, secrets_file):
        secrets = Secrets(path=secrets_file)
        assert await secrets.get("nonexistent") is None

    async def test_list_names_returns_sorted(self, secrets_file):
        secrets = Secrets(path=secrets_file)
        names = await secrets.list_names()
        assert names == ["bedrock_region", "openai_api_key", "slack_signing_secret"]

    async def test_missing_file_returns_None(self, tmp_path):
        # File does not exist; should not error — just no secrets
        backend = LocalFileBackend(path=tmp_path / "absent.yaml")
        assert await backend.get("any") is None
        assert await backend.list_names() == []

    async def test_in_memory_override(self, secrets_file):
        # Mostly for test setup convenience
        backend = LocalFileBackend(path=secrets_file)
        backend.set_in_memory("dynamic_key", "dynamic_value")
        assert await backend.get("dynamic_key") == "dynamic_value"


class TestBackendSelection:
    def test_default_is_local(self):
        s = Secrets()
        assert isinstance(s._backend, LocalFileBackend)

    def test_explicit_local(self):
        s = Secrets(backend="local")
        assert isinstance(s._backend, LocalFileBackend)

    def test_unknown_backend_rejected(self):
        with pytest.raises(ValueError, match="Unknown secrets backend"):
            Secrets(backend="vault")

    def test_custom_backend_instance_accepted(self):
        b = LocalFileBackend()
        s = Secrets(backend=b)
        assert s._backend is b


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.Secrets is Secrets
        assert cloudless.LocalFileBackend is LocalFileBackend
