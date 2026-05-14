"""Real-cloud integration test for cloudless.Memory + AgentCoreBackend.

Creates a fresh AgentCore Memory resource with a SEMANTIC strategy, adds
events, calls recall_facts, cleans up.

Cost: ~$0.001 (a few CreateEvent calls + one retrieval). The Memory resource
itself costs $0 idle. AgentCore Memory's long-term extraction is async —
recall might not return our events immediately. We assert at least that the
API path works (events get stored, retrieve returns successfully).
"""
from __future__ import annotations

import time
import uuid

import boto3
import pytest

import cloudless
from cloudless.catalog.memory import Memory


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="module")
def memory_resource(aws_available):
    """Create a cloudless-spike-prefixed AgentCore Memory; tear down at session end."""
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
    name = f"cloudlessmemspikemem{uuid.uuid4().hex[:8]}"
    try:
        resp = control.create_memory(
            name=name,
            description="cloudless integration test — auto-created, auto-deleted",
            eventExpiryDuration=7,  # min retention per dossier 02
            memoryStrategies=[
                {"semanticMemoryStrategy": {
                    # Strategy name must match [a-zA-Z][a-zA-Z0-9_]{0,47}
                    "name": "default_semantic",
                    "namespaces": ["/"],
                }},
            ],
        )
        memory_id = resp["memory"]["id"]
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"could not create memory (perms or quota?): {e}")

    # Poll until memory status is ACTIVE (semantic strategy takes 30-90s)
    deadline = time.time() + 180
    while time.time() < deadline:
        status_resp = control.get_memory(memoryId=memory_id)
        status = status_resp["memory"].get("status", "")
        if status == "ACTIVE":
            break
        if status == "FAILED":
            pytest.skip(f"memory creation failed: {status_resp['memory']}")
        time.sleep(5)
    else:
        try:
            control.delete_memory(memoryId=memory_id)
        except Exception:  # noqa: BLE001
            pass
        pytest.skip(f"memory never became ACTIVE in 3 min")
    yield memory_id

    # Teardown
    try:
        control.delete_memory(memoryId=memory_id)
    except Exception:  # noqa: BLE001
        pass


async def test_agentcore_memory_add_event_and_list(memory_resource):
    """End-to-end add_event + list_events path against real AgentCore."""
    memory = Memory(
        backend="agentcore",
        memory_id=memory_resource,
        region="us-east-1",
    )
    scope = f"user:{uuid.uuid4().hex[:8]}"

    # Add two events
    ev1 = await memory.add_event(
        scope=scope, role="user", content="I love Tokyo and prefer window seats.",
    )
    assert ev1.id
    assert ev1.scope == scope

    ev2 = await memory.add_event(
        scope=scope, role="assistant", content="Got it — Tokyo window seats noted.",
    )
    assert ev2.id

    # list_events should return our two events
    events = await memory.list_events(scope=scope, limit=10)
    contents = [e.content for e in events]
    assert any("Tokyo" in c for c in contents), \
        f"expected our events in list. Got: {contents}"


async def test_agentcore_memory_recall_returns_path_without_crash(memory_resource):
    """Validate the recall API path works.

    Note: AgentCore extraction is async — newly-added events may not
    surface in recall for 30+ seconds. We assert the API call succeeds
    and returns a list (possibly empty in the seconds after add_event).
    """
    memory = Memory(
        backend="agentcore",
        memory_id=memory_resource,
        region="us-east-1",
    )
    scope = f"user:{uuid.uuid4().hex[:8]}"
    await memory.add_event(scope=scope, role="user",
                           content="I love Tokyo travel destinations.")

    # Try recall; whether or not records are extracted yet, the call must succeed
    records = await memory.recall_facts(scope=scope, query="travel", top_k=5)
    assert isinstance(records, list)
    # Each record must have the right shape
    for r in records:
        assert r.text is not None
        assert r.scope == scope
