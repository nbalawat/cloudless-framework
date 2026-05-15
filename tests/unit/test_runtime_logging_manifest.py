"""Unit tests for cloudless.runtime.logging + manifest (Q39, Q12)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cloudless.runtime import (
    add_redact_pattern,
    bind_invocation,
    clear_invocation,
    configure,
    get_logger,
    load_manifest,
)


class TestLoggingRedaction:
    def setup_method(self):
        # Reset configuration each test
        import cloudless.runtime.logging as L
        L._configured = False
        L._user_redact.clear()
        clear_invocation()
        configure(json=True)

    def teardown_method(self):
        clear_invocation()
        # Restore default config
        import cloudless.runtime.logging as L
        L._configured = False

    def test_bearer_token_redacted(self, capsys):
        log = get_logger("test")
        log.info("called peer", auth="Bearer abc123.xyz789-foo_bar")
        out = capsys.readouterr().out
        assert "abc123" not in out
        assert "Bearer <REDACTED>" in out

    def test_aws_access_key_redacted(self, capsys):
        log = get_logger("test")
        log.info("event", key="AKIAIOSFODNN7EXAMPLE")
        out = capsys.readouterr().out
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert "<REDACTED:aws-access-key>" in out

    def test_jwt_redacted(self, capsys):
        log = get_logger("test")
        jwt = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0_extra_padding_chars_here_for_match"
               ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c_pad_padding_more")
        log.info("checked auth", token=jwt)
        out = capsys.readouterr().out
        # JWT body should be redacted
        assert "<REDACTED:jwt>" in out or jwt not in out

    def test_user_added_pattern(self, capsys):
        add_redact_pattern(r"ssn=\d{3}-\d{2}-\d{4}", "<REDACTED:ssn>")
        log = get_logger("test")
        log.info("user", note="ssn=123-45-6789 yes")
        out = capsys.readouterr().out
        assert "123-45-6789" not in out
        assert "<REDACTED:ssn>" in out


class TestLoggingContext:
    def setup_method(self):
        import cloudless.runtime.logging as L
        L._configured = False
        clear_invocation()
        configure(json=True)

    def teardown_method(self):
        clear_invocation()
        import cloudless.runtime.logging as L
        L._configured = False

    def test_bind_invocation_injects_fields(self, capsys):
        bind_invocation(agent_name="hello", run_id="r1", session_id="s1")
        log = get_logger("t")
        log.info("hi")
        line = capsys.readouterr().out.strip().split("\n")[-1]
        parsed = json.loads(line)
        assert parsed["agent.name"] == "hello"
        assert parsed["run.id"] == "r1"
        assert parsed["session.id"] == "s1"

    def test_clear_invocation_drops_fields(self, capsys):
        bind_invocation(agent_name="hello")
        clear_invocation()
        log = get_logger("t")
        log.info("hi")
        line = capsys.readouterr().out.strip().split("\n")[-1]
        parsed = json.loads(line)
        assert "agent.name" not in parsed


class TestManifest:
    def test_empty_manifest_when_missing(self):
        m = load_manifest(path="/nonexistent/cloudless-manifest.json")
        assert m.project == "<unknown>"
        assert m.agents == {}

    def test_loads_from_dict(self):
        m = load_manifest(contents={
            "project": "demo",
            "agents": {
                "hello": {"cloud": "aws", "http_url": "https://x", "idp_issuer": "https://idp"},
                "orders": {"cloud": "gcp", "a2a_url": "https://y"},
            },
        })
        assert m.project == "demo"
        assert set(m.agents) == {"hello", "orders"}
        assert m.get("hello").http_url == "https://x"
        assert m.get("orders").cloud == "gcp"

    def test_loads_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({
                "project": "demo",
                "agents": {"x": {"cloud": "aws", "http_url": "https://z"}},
            }, f)
            path = f.name
        try:
            m = load_manifest(path=path)
            assert m.get("x").http_url == "https://z"
        finally:
            Path(path).unlink()
