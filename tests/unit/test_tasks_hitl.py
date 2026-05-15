"""Unit tests for Q17 HITL pause/resume."""
from __future__ import annotations

import time

import pytest

import cloudless
from cloudless.chunks import PauseChunk
from cloudless.runtime.tasks import (
    TaskRecord,
    get_task,
    list_active_tasks,
    pause,
    reset_store,
    resume,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_store()
    yield
    reset_store()


# ----------------------------- PauseChunk ------------------------------ #


def test_pause_chunk_round_trips():
    """PauseChunk is frozen and serializable."""
    c = PauseChunk(
        resume_token="tok-1",
        reason="awaiting approval",
        pending_action={"amount": 1000},
        expires_at=time.time() + 3600,
    )
    assert c.kind == "pause"
    assert c.resume_token == "tok-1"

    # Should be in the Chunk union
    import typing

    from cloudless.chunks import Chunk
    assert PauseChunk in typing.get_args(Chunk)


def test_pause_chunk_is_immutable():
    from pydantic import ValidationError

    c = PauseChunk(resume_token="tok-1")
    # Pydantic v2 frozen models raise ValidationError on attempted mutation.
    with pytest.raises(ValidationError):
        c.resume_token = "other"


# ----------------------------- pause + resume -------------------------- #


def test_pause_creates_record_in_store():
    rec = pause(
        agent_name="orders",
        session_id="sess-1",
        reason="needs human approval",
        pending_action={"order_id": "o123"},
    )
    assert isinstance(rec, TaskRecord)
    assert rec.resume_token
    assert rec.agent_name == "orders"
    assert rec.resolved is False
    # Should be queryable by token
    stored = get_task(rec.resume_token)
    assert stored is not None
    assert stored.session_id == "sess-1"


def test_resume_resolves_and_returns_record():
    rec = pause(agent_name="orders", session_id="sess-1")
    resolved = resume(rec.resume_token, {"approved": True, "by": "alice"})
    assert resolved is not None
    assert resolved.resolved is True
    assert resolved.approval == {"approved": True, "by": "alice"}


def test_resume_returns_none_for_unknown_token():
    assert resume("nonexistent-token", {"x": 1}) is None


def test_resume_is_idempotent():
    """Double-resume returns None on the second call."""
    rec = pause(agent_name="orders", session_id="s")
    first = resume(rec.resume_token, {"ok": True})
    second = resume(rec.resume_token, {"ok": True})
    assert first is not None
    assert second is None


def test_expired_task_returns_none():
    rec = pause(agent_name="orders", session_id="s", ttl_seconds=-1)
    # ttl_seconds=-1 → expires_at < now → get returns None
    assert get_task(rec.resume_token) is None


def test_list_active_tasks_excludes_resolved():
    a = pause(agent_name="x", session_id="1")
    b = pause(agent_name="x", session_id="2")
    pause(agent_name="x", session_id="3")  # third pending
    resume(a.resume_token, {"ok": True})
    active = list_active_tasks()
    tokens = [r.resume_token for r in active]
    assert a.resume_token not in tokens
    assert b.resume_token in tokens
    assert len(active) == 2


# ----------------------------- public surface ------------------------- #


def test_public_imports():
    assert hasattr(cloudless, "PauseChunk")
    from cloudless.runtime import pause as r_pause
    from cloudless.runtime import resume as r_resume
    assert callable(r_pause)
    assert callable(r_resume)
