"""Unit tests for `cloudless cleanup`."""
from __future__ import annotations

import io
from contextlib import redirect_stdout

from cloudless.cli import cleanup


def test_run_rejects_short_prefix():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup.run(prefix="c-x")  # 3 chars
    assert rc == 2
    assert "must be" in buf.getvalue()


def test_run_dry_run_no_matches(monkeypatch):
    """Empty plan should exit 0 with 'No matching' message."""
    monkeypatch.setattr(cleanup, "discover_aws",
                        lambda prefix, **kw: ([], [], [], []))
    monkeypatch.setattr(cleanup, "discover_gcp",
                        lambda prefix, **kw: ([], []))
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup.run(prefix="cloudless-spike-")
    assert rc == 0
    assert "No matching" in buf.getvalue()


def test_run_dry_run_with_matches(monkeypatch):
    """Matches present → dry-run prints them + returns 0 without deleting."""
    monkeypatch.setattr(
        cleanup, "discover_aws",
        lambda prefix, **kw: (
            ["cloudless-spike-01-abc"],
            ["cloudless-spike-repo"],
            ["cloudless-spike-role"],
            ["cloudless-spike-bucket"],
        ),
    )
    monkeypatch.setattr(cleanup, "discover_gcp", lambda prefix, **kw: ([], []))
    # execute_plan should NOT be called in dry-run mode
    called = {"n": 0}
    def fake_execute(*a, **kw):
        called["n"] += 1
        return 0
    monkeypatch.setattr(cleanup, "execute_plan", fake_execute)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup.run(prefix="cloudless-spike-")
    assert rc == 0
    assert "cloudless-spike-01-abc" in buf.getvalue()
    assert called["n"] == 0


def test_run_without_yes_refuses_to_delete(monkeypatch):
    monkeypatch.setattr(
        cleanup, "discover_aws",
        lambda prefix, **kw: (["x"], [], [], []),
    )
    monkeypatch.setattr(cleanup, "discover_gcp", lambda prefix, **kw: ([], []))
    monkeypatch.setattr(cleanup, "execute_plan", lambda *a, **kw: 0)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup.run(prefix="cloudless-spike-", dry_run=False, yes=False)
    assert rc == 2


def test_run_with_yes_calls_execute_plan(monkeypatch):
    monkeypatch.setattr(
        cleanup, "discover_aws",
        lambda prefix, **kw: (["x"], [], [], []),
    )
    monkeypatch.setattr(cleanup, "discover_gcp", lambda prefix, **kw: ([], []))
    called = {"n": 0}
    def fake_execute(*a, **kw):
        called["n"] += 1
        return 0
    monkeypatch.setattr(cleanup, "execute_plan", fake_execute)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cleanup.run(prefix="cloudless-spike-", dry_run=False, yes=True)
    assert rc == 0
    assert called["n"] == 1


def test_build_plan_aggregates_all_resource_types(monkeypatch):
    monkeypatch.setattr(
        cleanup, "discover_aws",
        lambda prefix, **kw: (["r1"], ["repo1", "repo2"], ["role1"], ["b1"]),
    )
    monkeypatch.setattr(cleanup, "discover_gcp",
                        lambda prefix, **kw: (["ae1"], ["gb1"]))
    plan = cleanup.build_plan("cloudless-spike-", gcp=True, gcp_project="p")
    assert plan.total == 7
    assert plan.aws_ecr_repos == ["repo1", "repo2"]
    assert plan.gcp_agent_engines == ["ae1"]


def test_min_prefix_length_constant():
    """Safety: prefix minimum hasn't been accidentally relaxed."""
    assert cleanup.MIN_PREFIX_LENGTH >= 8
