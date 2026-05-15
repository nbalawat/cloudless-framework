"""Unit tests for cloud-backed TaskStore implementations.

Uses stub clients — no boto3 / google-cloud calls.
"""
from __future__ import annotations

import json
import time

import pytest

from cloudless.runtime.tasks import TaskRecord


# ----------------------------- AWS adapter ------------------------------ #


class _FakeAgentCorePaginator:
    def __init__(self, pages):
        self._pages = pages
    def paginate(self, **kw):
        return iter(self._pages)


class _FakeAgentCoreClient:
    def __init__(self):
        self.events: list[dict] = []

    def create_event(self, **kwargs):
        self.events.append(kwargs)

    def get_paginator(self, name):
        # Build a single page from stored events
        page = {
            "events": [
                {"payload": ev["payload"]} for ev in self.events
            ]
        }
        return _FakeAgentCorePaginator([page])


def _aws_store(client):
    from cloudless.adapters.aws.tasks import AgentCoreTaskStore
    return AgentCoreTaskStore(memory_id="cloudless-mem-test", client=client)


def _make_record(token="tok-1", agent="orders", session="sess-1", resolved=False):
    return TaskRecord(
        resume_token=token,
        agent_name=agent,
        session_id=session,
        reason="needs approval",
        pending_action={"x": 1},
        expires_at=time.time() + 3600,
        resolved=resolved,
    )


def test_aws_put_writes_event():
    client = _FakeAgentCoreClient()
    store = _aws_store(client)
    store.put(_make_record())
    assert len(client.events) == 1
    payload = client.events[0]["payload"][0]
    assert json.loads(payload["blob"])["resume_token"] == "tok-1"


def test_aws_get_with_agent_finds_latest():
    client = _FakeAgentCoreClient()
    store = _aws_store(client)
    rec = _make_record(token="tok-1")
    store.put(rec)
    found = store.get_with_agent("tok-1", "orders")
    assert found is not None
    assert found.resume_token == "tok-1"


def test_aws_get_with_agent_returns_none_for_missing():
    client = _FakeAgentCoreClient()
    store = _aws_store(client)
    store.put(_make_record(token="tok-1"))
    found = store.get_with_agent("nonexistent", "orders")
    assert found is None


def test_aws_resolve_with_agent_marks_resolved():
    client = _FakeAgentCoreClient()
    store = _aws_store(client)
    store.put(_make_record(token="tok-1"))
    out = store.resolve_with_agent("tok-1", {"approved": True}, "orders")
    assert out is not None
    assert out.resolved is True
    assert out.approval == {"approved": True}
    # A second resolve should return None (idempotent — latest event is resolved)
    out2 = store.resolve_with_agent("tok-1", {"approved": True}, "orders")
    assert out2 is None


def test_aws_get_raises_without_agent():
    """The unscoped get() must raise; AC needs the agent_name for ListEvents."""
    store = _aws_store(_FakeAgentCoreClient())
    with pytest.raises(NotImplementedError, match="agent_name"):
        store.get("any-token")


def test_aws_list_active_for_agent_excludes_resolved():
    client = _FakeAgentCoreClient()
    store = _aws_store(client)
    store.put(_make_record(token="a"))
    store.put(_make_record(token="b"))
    store.put(_make_record(token="c"))
    store.resolve_with_agent("b", {"ok": True}, "orders")
    active = store.list_active_for_agent("orders")
    tokens = sorted(r.resume_token for r in active)
    assert tokens == ["a", "c"]


# ----------------------------- GCP adapter ------------------------------ #


class _FakeMemory:
    """Stand-in for v1beta1.Memory."""
    def __init__(self, fact, scope, name=None, create_time=None):
        self.fact = fact
        self.scope = scope
        self.name = name or f"projects/x/locations/y/memories/{id(self)}"
        self.create_time = create_time


class _FakeMemoryBankClient:
    def __init__(self):
        self.memories: list[_FakeMemory] = []
        self.deleted: list[str] = []

    def create_memory(self, *, request):
        # request is v1beta1.CreateMemoryRequest; just store the memory
        mem = request.memory
        self.memories.append(_FakeMemory(
            fact=mem.fact,
            scope=dict(mem.scope),
            create_time=time.time(),
        ))

    def list_memories(self, *, request):
        f = request.filter or ""
        for mem in self.memories:
            if f:
                # Crude: handle 'scope.cloudless_task_token="X"'
                if "cloudless_task_token=" in f:
                    wanted = f.split('cloudless_task_token="', 1)[1].rstrip('"')
                    if mem.scope.get("cloudless_task_token") != wanted:
                        continue
            yield mem

    def delete_memory(self, *, name):
        self.deleted.append(name)
        self.memories = [m for m in self.memories if m.name != name]


def _gcp_store(client):
    from cloudless.adapters.gcp.tasks import MemoryBankTaskStore
    return MemoryBankTaskStore(
        agent_engine_name="projects/x/locations/us-central1/reasoningEngines/123",
        client=client,
    )


def test_gcp_put_writes_memory():
    """Needs the real Memory protobuf — verify via the request shape via monkeypatch."""
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    client = _FakeMemoryBankClient()
    store = _gcp_store(client)
    store.put(_make_record(token="tok-1"))
    assert len(client.memories) == 1
    mem = client.memories[0]
    assert json.loads(mem.fact)["resume_token"] == "tok-1"
    assert mem.scope == {"cloudless_task_token": "tok-1"}


def test_gcp_get_returns_record():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    client = _FakeMemoryBankClient()
    store = _gcp_store(client)
    store.put(_make_record(token="tok-1"))
    rec = store.get("tok-1")
    assert rec is not None
    assert rec.resume_token == "tok-1"


def test_gcp_get_missing_returns_none():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    client = _FakeMemoryBankClient()
    store = _gcp_store(client)
    assert store.get("tok-missing") is None


def test_gcp_resolve_persists_resolved_flag():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    client = _FakeMemoryBankClient()
    store = _gcp_store(client)
    store.put(_make_record(token="tok-1"))
    out = store.resolve("tok-1", {"approved": True})
    assert out is not None
    assert out.resolved is True
    # A subsequent get should now see the resolved record
    after = store.get("tok-1")
    assert after is not None
    assert after.resolved is True


def test_gcp_delete_removes_memories():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    client = _FakeMemoryBankClient()
    store = _gcp_store(client)
    store.put(_make_record(token="tok-1"))
    store.delete("tok-1")
    assert client.deleted  # at least one delete fired
    assert store.get("tok-1") is None
