"""GCP Memory Bank backend for cloudless.Memory.

Maps the cloudless verb taxonomy (Q14) to Vertex AI Memory Bank:

  Verb              | Memory Bank call
  ------------------|-----------------------------------------------------
  add_event         | CreateMemory(fact=role+": "+content, scope=cloudless_scope)
  recall_facts      | RetrieveMemories(similarity_search_params, scope)
  summarize_session | RetrieveMemories scoped by session_id (best-effort)
  get_preferences   | RetrieveMemories(simple_retrieval_params, scope)
  list_events       | ListMemories(filter by scope)
  clear             | ListMemories + DeleteMemory loop

Memories on Memory Bank are scoped under a "parent" — the Agent Engine
resource. cloudless requires the user to pass `agent_engine_name` so we
know which parent to use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud import aiplatform_v1beta1 as v1b
from google.api_core.exceptions import GoogleAPICallError, NotFound

from cloudless.catalog.memory import MemoryBackend, MemoryEvent, MemoryRecord


class MemoryBankBackend:
    def __init__(
        self,
        *,
        agent_engine_name: str,
        location: str = "us-central1",
    ) -> None:
        """
        Args:
            agent_engine_name: Full reasoning-engine resource name,
                e.g. "projects/305896968831/locations/us-central1/reasoningEngines/12345".
            location: Region (matches what's in agent_engine_name).
        """
        self.agent_engine_name = agent_engine_name
        self.location = location
        endpoint = f"{location}-aiplatform.googleapis.com"
        self._client = v1b.MemoryBankServiceClient(
            client_options={"api_endpoint": endpoint},
        )

    # ------------------------------------------------------------------ #
    # Scope-string helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _scope_to_dict(scope: str) -> dict[str, str]:
        """Map a cloudless scope like 'user:42' → Memory Bank scope dict {'user_id': '42'}.

        Falls back to {'cloudless_scope': scope} when no ':' separator present.
        """
        if ":" in scope:
            key, value = scope.split(":", 1)
            # Memory Bank scope keys must match [a-zA-Z_][a-zA-Z0-9_]*
            key = key.replace("-", "_")
            return {key: value}
        return {"cloudless_scope": scope}

    # ------------------------------------------------------------------ #
    # Verbs
    # ------------------------------------------------------------------ #

    async def add_event(
        self, *, scope: str, role: str, content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryEvent:
        fact = f"{role}: {content}"
        memory = v1b.Memory(
            fact=fact,
            scope=self._scope_to_dict(scope),
            display_name=metadata.get("display_name") if metadata else f"event-{role}",
        )
        try:
            resp = self._client.create_memory(
                parent=self.agent_engine_name,
                memory=memory,
            )
        except GoogleAPICallError as e:
            raise self._translate(e) from e

        # CreateMemory returns an LRO; resp.result() blocks until done
        created = resp.result()
        # name is like ".../memories/123456"
        return MemoryEvent(
            id=created.name.rsplit("/", 1)[-1],
            scope=scope,
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

    async def recall_facts(
        self, *, scope: str, query: str, top_k: int = 5,
    ) -> list[MemoryRecord]:
        scope_dict = self._scope_to_dict(scope)
        request = v1b.RetrieveMemoriesRequest(
            parent=self.agent_engine_name,
            scope=scope_dict,
            similarity_search_params=v1b.RetrieveMemoriesRequest.SimilaritySearchParams(
                search_query=query, top_k=top_k,
            ),
        )
        try:
            resp = self._client.retrieve_memories(request=request)
        except GoogleAPICallError as e:
            raise self._translate(e) from e

        out: list[MemoryRecord] = []
        for r in resp.retrieved_memories:
            out.append(MemoryRecord(
                id=r.memory.name.rsplit("/", 1)[-1],
                text=r.memory.fact,
                scope=scope,
                score=r.distance if r.distance is not None else None,
                metadata={"display_name": r.memory.display_name},
            ))
        return out

    async def summarize_session(
        self, *, scope: str, session_id: str,
    ) -> Optional[MemoryRecord]:
        results = await self.recall_facts(
            scope=scope, query=f"session {session_id} summary", top_k=1,
        )
        return results[0] if results else None

    async def get_preferences(self, *, scope: str) -> list[MemoryRecord]:
        return await self.recall_facts(
            scope=scope, query="user preferences", top_k=20,
        )

    async def list_events(self, *, scope: str, limit: int = 50) -> list[MemoryEvent]:
        scope_dict = self._scope_to_dict(scope)
        scope_filter = " AND ".join(f'scope.{k}="{v}"' for k, v in scope_dict.items())
        try:
            page = self._client.list_memories(
                parent=self.agent_engine_name,
                filter=scope_filter,
                page_size=limit,
            )
        except GoogleAPICallError as e:
            raise self._translate(e) from e

        events: list[MemoryEvent] = []
        for m in page:
            fact = m.fact or ""
            # Naive split of "<role>: <content>" since that's how we stored it
            if ": " in fact:
                role, content = fact.split(": ", 1)
            else:
                role, content = "other", fact
            events.append(MemoryEvent(
                id=m.name.rsplit("/", 1)[-1],
                scope=scope,
                role=role,
                content=content,
                timestamp=m.create_time or datetime.now(timezone.utc),
                metadata={"name": m.name, "display_name": m.display_name},
            ))
            if len(events) >= limit:
                break
        return events

    async def clear(self, *, scope: str) -> int:
        events = await self.list_events(scope=scope, limit=1000)
        deleted = 0
        for ev in events:
            full_name = ev.metadata.get("name")
            if not full_name:
                continue
            try:
                op = self._client.delete_memory(name=full_name)
                op.result()
                deleted += 1
            except (GoogleAPICallError, NotFound):
                pass
        return deleted

    @staticmethod
    def _translate(e: GoogleAPICallError) -> Exception:
        from cloudless.exceptions import (
            AuthenticationError, InvalidInputError, ThrottledError,
        )
        msg = str(e)
        # Map status codes if available
        status = getattr(e, "grpc_status_code", None) or getattr(e, "code", lambda: 0)()
        if status in (429,):
            return ThrottledError(msg)
        if status in (401, 403):
            return AuthenticationError(msg)
        if status in (400, 404):
            return InvalidInputError(msg)
        return e
