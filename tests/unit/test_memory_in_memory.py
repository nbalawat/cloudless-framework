"""Unit tests for cloudless.Memory + InMemoryBackend (no cloud)."""
from __future__ import annotations

import pytest

import cloudless
from cloudless.catalog.memory import InMemoryBackend, Memory, MemoryEvent, MemoryRecord


class TestInMemoryBackendVerbs:
    async def test_add_event_returns_event_with_id(self):
        m = Memory()
        ev = await m.add_event(scope="user:1", role="user", content="hello")
        assert ev.id.startswith("event-")
        assert ev.scope == "user:1"
        assert ev.role == "user"
        assert ev.content == "hello"

    async def test_recall_facts_finds_substring_match(self):
        m = Memory()
        await m.add_event(scope="user:1", role="user", content="I love Tokyo")
        await m.add_event(scope="user:1", role="user", content="I dislike rain")
        await m.add_event(scope="user:1", role="assistant", content="noted")

        # Search for Tokyo — should find the matching event first
        results = await m.recall_facts(scope="user:1", query="Tokyo", top_k=5)
        assert len(results) >= 1
        # The matching event scores higher than the non-matching one
        assert results[0].text == "I love Tokyo"
        assert results[0].score == 1.0
        # Non-matching content gets a lower score
        if len(results) > 1:
            assert results[1].score == 0.5

    async def test_recall_facts_respects_top_k(self):
        m = Memory()
        for i in range(8):
            await m.add_event(scope="user:1", role="user", content=f"msg {i}")
        results = await m.recall_facts(scope="user:1", query="msg", top_k=3)
        assert len(results) == 3

    async def test_scope_isolation(self):
        m = Memory()
        await m.add_event(scope="user:1", role="user", content="A")
        await m.add_event(scope="user:2", role="user", content="B")
        u1 = await m.recall_facts(scope="user:1", query="A", top_k=5)
        u2 = await m.recall_facts(scope="user:2", query="A", top_k=5)
        # user:2 has no match for "A" content; user:1 has the match
        u1_texts = {r.text for r in u1}
        u2_texts = {r.text for r in u2}
        assert "A" in u1_texts
        assert "A" not in u2_texts
        assert "B" not in u1_texts
        assert "B" in u2_texts

    async def test_summarize_session_returns_None_when_no_events(self):
        m = Memory()
        summary = await m.summarize_session(scope="user:1", session_id="sess-1")
        assert summary is None

    async def test_summarize_session_aggregates_recent(self):
        m = Memory()
        for i in range(5):
            await m.add_event(
                scope="user:1", role="user", content=f"msg-{i}",
                metadata={"session_id": "sess-1"},
            )
        summary = await m.summarize_session(scope="user:1", session_id="sess-1")
        assert summary is not None
        assert "msg-0" in summary.text or "msg-4" in summary.text

    async def test_get_preferences_returns_user_role_events(self):
        m = Memory()
        await m.add_event(scope="user:1", role="user", content="I like apples")
        await m.add_event(scope="user:1", role="assistant", content="noted")
        prefs = await m.get_preferences(scope="user:1")
        # Only the user-role event surfaces as preference-like
        assert any("apples" in r.text for r in prefs)
        assert not any("noted" in r.text for r in prefs)

    async def test_list_events_returns_only_scope(self):
        m = Memory()
        await m.add_event(scope="user:1", role="user", content="x")
        await m.add_event(scope="user:2", role="user", content="y")
        only_u1 = await m.list_events(scope="user:1")
        assert all(e.scope == "user:1" for e in only_u1)

    async def test_clear_removes_scope_events(self):
        m = Memory()
        await m.add_event(scope="user:1", role="user", content="x")
        await m.add_event(scope="user:1", role="user", content="y")
        await m.add_event(scope="user:2", role="user", content="other")
        removed = await m.clear(scope="user:1")
        assert removed == 2
        # user:2 untouched
        u2 = await m.list_events(scope="user:2")
        assert len(u2) == 1


class TestBackendSelection:
    def test_default_is_in_memory(self):
        m = Memory()
        assert isinstance(m._backend, InMemoryBackend)

    def test_explicit_in_memory(self):
        m = Memory(backend="in_memory")
        assert isinstance(m._backend, InMemoryBackend)

    def test_agentcore_requires_memory_id(self):
        with pytest.raises(ValueError, match="requires memory_id"):
            Memory(backend="agentcore")

    def test_unknown_backend_rejected(self):
        with pytest.raises(ValueError, match="Unknown memory backend"):
            Memory(backend="redis")

    def test_user_can_pass_custom_backend_instance(self):
        b = InMemoryBackend()
        m = Memory(backend=b)
        assert m._backend is b


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.Memory is Memory
        assert cloudless.MemoryEvent is MemoryEvent
        assert cloudless.MemoryRecord is MemoryRecord
        assert cloudless.InMemoryBackend is InMemoryBackend
