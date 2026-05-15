"""Unit tests for VertexSessionsBackend wiring."""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.asyncio]


class _FakeContent:
    def __init__(self, role, text):
        self.role = role
        self.parts = [type("P", (), {"text": text})()]


class _FakeSessionEvent:
    def __init__(self, name, author, text):
        self.name = name
        self.author = author
        self.content = _FakeContent(author, text)


class _FakeSessionsClient:
    def __init__(self):
        self.events: list[_FakeSessionEvent] = []
        self.created_sessions: list[str] = []
        self.deleted_sessions: list[str] = []

    def create_session(self, *, request):
        self.created_sessions.append(request.session.name)
        return request.session

    def append_event(self, *, request):
        ev = _FakeSessionEvent(
            name=f"{request.name}/events/{len(self.events)}",
            author=request.event.author,
            text=request.event.content.parts[0].text,
        )
        self.events.append(ev)
        return ev

    def list_events(self, *, request):
        return self.events

    def delete_session(self, *, request):
        self.deleted_sessions.append(request.name)


async def test_sessions_backend_add_and_list():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    from cloudless.adapters.gcp.sessions import VertexSessionsBackend

    client = _FakeSessionsClient()
    backend = VertexSessionsBackend(
        agent_engine_name="projects/x/locations/us-central1/reasoningEngines/e1",
        client=client,
    )
    await backend.add_event(scope="user:42", role="user", content="hi there")
    await backend.add_event(scope="user:42", role="assistant", content="hello back")
    events = await backend.list_events(scope="user:42", limit=10)
    assert len(events) == 2
    assert events[0].content == "hi there"
    assert events[1].role == "assistant"


async def test_sessions_recall_facts_uses_keyword_overlap():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    from cloudless.adapters.gcp.sessions import VertexSessionsBackend

    client = _FakeSessionsClient()
    backend = VertexSessionsBackend(
        agent_engine_name="projects/x/locations/us-central1/reasoningEngines/e1",
        client=client,
    )
    await backend.add_event(scope="user:1", role="user",
                             content="I love Tokyo for the food")
    await backend.add_event(scope="user:1", role="user",
                             content="The weather in Paris is cold")

    results = await backend.recall_facts(scope="user:1", query="Tokyo food", top_k=5)
    # Both events have some overlap, but the Tokyo one has more
    assert len(results) >= 1
    assert "Tokyo" in results[0].text


async def test_memory_factory_wires_vertex_sessions():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    import cloudless
    # Construction itself shouldn't try to create the SDK client because
    # we pass agent_engine_name. We can't fully test without ADC, so just
    # verify the factory accepts the backend name without ValueError.
    try:
        cloudless.Memory(
            backend="vertex_sessions",
            agent_engine_name="projects/x/locations/us-central1/reasoningEngines/e1",
        )
    except RuntimeError:
        pass  # SDK init may fail without ADC; that's OK for this test
    except ValueError as e:
        pytest.fail(f"factory rejected vertex_sessions: {e}")


async def test_sessions_clear_deletes():
    pytest.importorskip("google.cloud.aiplatform_v1beta1")
    from cloudless.adapters.gcp.sessions import VertexSessionsBackend

    client = _FakeSessionsClient()
    backend = VertexSessionsBackend(
        agent_engine_name="projects/x/locations/us-central1/reasoningEngines/e1",
        client=client,
    )
    n = await backend.clear(scope="user:1")
    assert n == 1
    assert len(client.deleted_sessions) == 1
