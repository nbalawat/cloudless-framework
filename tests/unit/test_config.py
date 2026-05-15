"""Unit tests for cloudless.config schema validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from cloudless.config import ConfigValidationError, load, validate


def test_valid_minimal_config():
    cfg = validate({
        "project": "demo",
        "default_cloud": "aws",
        "agents": {
            "hello": {"cloud": "aws", "interfaces": ["http"]},
        },
    })
    assert cfg.project == "demo"
    assert cfg.default_cloud == "aws"
    assert cfg.agents["hello"].interfaces == ("http",)


def test_full_config_round_trips():
    cfg = validate({
        "project": "demo",
        "default_cloud": "aws",
        "agents": {
            "support": {
                "cloud": "aws",
                "framework": "langgraph",
                "interfaces": ["http", "a2a"],
                "peers": ["orders"],
                "version": "0.1.0",
            },
            "orders": {
                "cloud": "gcp",
                "framework": "strands",
                "interfaces": ["a2a"],
            },
        },
        "service_catalog": {
            "llm": {"provider": "bedrock", "model": "nova-micro"},
        },
        "policies": {
            "cost_cap_usd_per_session": 5.0,
            "retries": {"attempts": 3, "backoff_seconds": 0.25},
        },
        "environments": {"dev": {"aws": "dev"}},
    })
    assert "orders" in cfg.agents
    assert cfg.agents["support"].framework == "langgraph"
    assert cfg.agents["support"].peers == ("orders",)
    assert cfg.policies["cost_cap_usd_per_session"] == 5.0


# ----------------------------- errors ---------------------------------- #


def test_missing_project_errors():
    with pytest.raises(ConfigValidationError, match="project"):
        validate({"default_cloud": "aws"})


def test_invalid_project_name():
    with pytest.raises(ConfigValidationError, match="kebab"):
        validate({"project": "Bad Project!", "default_cloud": "aws"})


def test_unknown_cloud():
    with pytest.raises(ConfigValidationError, match="default_cloud"):
        validate({"project": "demo", "default_cloud": "azure"})


def test_unknown_interface_listed():
    with pytest.raises(ConfigValidationError, match="interfaces"):
        validate({
            "project": "demo",
            "default_cloud": "aws",
            "agents": {"a": {"interfaces": ["http", "websocket"]}},
        })


def test_dangling_peer_reference():
    with pytest.raises(ConfigValidationError, match="peers"):
        validate({
            "project": "demo",
            "default_cloud": "aws",
            "agents": {
                "a": {"peers": ["nonexistent"]},
            },
        })


def test_invalid_framework():
    with pytest.raises(ConfigValidationError, match="framework"):
        validate({
            "project": "demo",
            "default_cloud": "aws",
            "agents": {"a": {"framework": "haystack"}},
        })


def test_accumulates_multiple_errors():
    try:
        validate({
            "project": "Bad Name",
            "default_cloud": "azure",
            "agents": {"a": {"framework": "haystack", "interfaces": ["ws"]}},
        })
    except ConfigValidationError as e:
        assert len(e.errors) >= 3
    else:
        raise AssertionError("expected ConfigValidationError")


# ----------------------------- file loading ---------------------------- #


def test_load_from_file(tmp_path: Path):
    cfg_path = tmp_path / "cloudless.yaml"
    cfg_path.write_text(
        "project: demo\n"
        "default_cloud: aws\n"
        "agents:\n"
        "  hello: {cloud: aws, interfaces: [http]}\n"
    )
    cfg = load(cfg_path)
    assert cfg.project == "demo"
    assert "hello" in cfg.agents


def test_load_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "missing.yaml")
