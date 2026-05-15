"""Real-cloud integration test for cloudless.Memory + GCP Memory Bank backend.

Creates a temp Agent Engine + Memory Bank parent, adds events, lists, deletes,
tears down. Cost: ~$0.05 (Agent Engine creation dominates).
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def gcp_available() -> bool:
    try:
        import vertexai
        vertexai.init(project="agentic-experiments", location="us-central1")
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def memory_bank_parent(gcp_available):
    """Resolve an Agent Engine resource name to use as the Memory Bank parent.

    Resolution order:
      1. CLOUDLESS_MEMORY_BANK_PARENT env var (full resource name)
      2. The first existing Agent Engine in the project (reused — no creation cost)
      3. Create a fresh one (CLOUDLESS_RUN_DEPLOY_TESTS=1 required; takes ~3 min,
         and is known to time out under Vertex slot contention)

    Reusing an existing engine sidesteps the 11-minute creation timeout
    documented in docs/CERTIFICATION.md.
    """
    if not gcp_available:
        pytest.skip("GCP credentials not configured")

    import vertexai
    from vertexai import agent_engines

    project = os.environ.get("CLOUDLESS_GCP_PROJECT", "agentic-experiments")
    vertexai.init(project=project, location="us-central1")

    # 1. Explicit env override
    env_parent = os.environ.get("CLOUDLESS_MEMORY_BANK_PARENT")
    if env_parent:
        yield env_parent
        return

    # 2. Reuse an existing engine if available
    existing = list(agent_engines.list())
    if existing:
        yield existing[0].resource_name
        return

    # 3. Last resort — create one (slow, may time out)
    if os.environ.get("CLOUDLESS_RUN_DEPLOY_TESTS") != "1":
        pytest.skip(
            "no existing Agent Engine in project and CLOUDLESS_RUN_DEPLOY_TESTS!=1"
        )

    vertexai.init(
        project=project, location="us-central1",
        staging_bucket=f"gs://cloudless-staging-{project}",
    )

    class _MinAgent:
        def query(self, prompt: str) -> dict:
            return {"echo": prompt}
        def register_operations(self) -> dict:
            return {"": ["query"]}

    inst = _MinAgent()
    try:
        remote = agent_engines.create(
            agent_engine=inst,
            requirements=["pydantic>=2.7.0"],
            display_name=f"cloudless-mem-test-{uuid.uuid4().hex[:8]}",
            description="cloudless Memory Bank integration test parent",
        )
    except Exception as e:
        pytest.fail(f"could not create Agent Engine: {e}")

    yield remote.resource_name

    # Teardown only if we created it
    try:
        agent_engines.delete(remote.resource_name, force=True)
    except Exception:
        pass


async def test_memory_bank_add_recall_clear(memory_bank_parent):
    import cloudless
    m = cloudless.Memory(
        backend="memory_bank",
        agent_engine_name=memory_bank_parent,
        location="us-central1",
    )
    scope = f"user:{uuid.uuid4().hex[:8]}"

    # Add a couple of events
    ev1 = await m.add_event(scope=scope, role="user", content="I love Tokyo.")
    assert ev1.id
    assert ev1.scope == scope

    ev2 = await m.add_event(scope=scope, role="user", content="I prefer window seats.")
    assert ev2.id

    # list_events should surface what we put in
    events = await m.list_events(scope=scope, limit=10)
    contents = [e.content for e in events]
    assert any("Tokyo" in c for c in contents)
    assert any("window" in c for c in contents)

    # recall_facts via similarity search
    results = await m.recall_facts(scope=scope, query="travel preferences", top_k=3)
    assert isinstance(results, list)
    # Should return at least the events we added (Memory Bank stores them directly)
    assert len(results) >= 1

    # Cleanup the events we added
    removed = await m.clear(scope=scope)
    assert removed >= 2
