"""Unit tests for ${secret:..} and ${env:..} reference resolution."""
from __future__ import annotations

import pytest

from cloudless.config_refs import resolve_refs
from cloudless.exceptions import InvalidInputError


class _StubSecrets:
    def __init__(self, store):
        self._store = store
    def get(self, name):
        if name not in self._store:
            raise KeyError(name)
        return self._store[name]


def test_env_ref_resolves_from_environ(monkeypatch):
    monkeypatch.setenv("MY_VAR", "hello")
    assert resolve_refs("${env:MY_VAR}") == "hello"


def test_env_ref_uses_default(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    assert resolve_refs("${env:MISSING_VAR:fallback}") == "fallback"


def test_env_ref_missing_no_default_raises(monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    with pytest.raises(InvalidInputError, match="unresolved"):
        resolve_refs("${env:MISSING}")


def test_secret_ref_resolves_via_secrets():
    secrets = _StubSecrets({"api_key": "sk-real-key"})
    assert resolve_refs("${secret:api_key}", secrets=secrets) == "sk-real-key"


def test_secret_ref_missing_uses_default():
    secrets = _StubSecrets({})
    assert resolve_refs("${secret:nope:default-val}", secrets=secrets) == "default-val"


def test_secret_ref_missing_no_default_raises():
    secrets = _StubSecrets({})
    with pytest.raises(InvalidInputError, match="unresolved"):
        resolve_refs("${secret:nope}", secrets=secrets)


def test_inline_reference_in_string():
    secrets = _StubSecrets({"token": "abc123"})
    s = resolve_refs("Bearer ${secret:token}", secrets=secrets)
    assert s == "Bearer abc123"


def test_multiple_references_in_string(monkeypatch):
    monkeypatch.setenv("HOST", "example.com")
    secrets = _StubSecrets({"key": "k"})
    out = resolve_refs("https://${env:HOST}/?k=${secret:key}", secrets=secrets)
    assert out == "https://example.com/?k=k"


def test_resolve_dict_recursively():
    secrets = _StubSecrets({"db_pwd": "secret123"})
    cfg = {
        "service_catalog": {
            "llm": {"api_key": "${secret:db_pwd}"},
        },
        "agents": {
            "x": {"interfaces": ["http"]},  # untouched
        },
    }
    out = resolve_refs(cfg, secrets=secrets)
    assert out["service_catalog"]["llm"]["api_key"] == "secret123"
    assert out["agents"]["x"]["interfaces"] == ["http"]


def test_resolve_list_recursively(monkeypatch):
    monkeypatch.setenv("A", "1")
    out = resolve_refs(["${env:A}", "literal", "${env:A}"])
    assert out == ["1", "literal", "1"]


def test_non_string_values_pass_through():
    cfg = {"port": 8080, "enabled": True, "ratio": 0.5}
    assert resolve_refs(cfg) == cfg


def test_string_without_refs_unchanged():
    assert resolve_refs("plain text") == "plain text"


def test_load_yaml_with_refs(monkeypatch, tmp_path):
    """End-to-end: cloudless.config.load resolves refs from a real file."""
    from cloudless.config import load
    monkeypatch.setenv("CLOUDLESS_TEST_PROJECT", "demo-resolved")
    cfg_path = tmp_path / "cloudless.yaml"
    cfg_path.write_text(
        "project: ${env:CLOUDLESS_TEST_PROJECT}\n"
        "default_cloud: aws\n"
    )
    cfg = load(cfg_path)
    assert cfg.project == "demo-resolved"
