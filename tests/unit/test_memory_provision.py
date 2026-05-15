"""Unit tests for deploy-time Memory auto-provisioning."""
from __future__ import annotations

import pytest

from cloudless.adapters.aws.memory_provision import (
    _memory_name as aws_memory_name,
    ensure_memory_resource as ensure_aws,
)
from cloudless.adapters.gcp.memory_provision import (
    _engine_display_name as gcp_engine_name,
    ensure_agent_engine as ensure_gcp,
)


# --------------------------------------------------------------------- #
# AWS
# --------------------------------------------------------------------- #


class _FakeAWSClient:
    def __init__(self, *, existing: list[dict] | None = None):
        self.existing = existing or []
        self.created: list[dict] = []
        self._statuses = ["CREATING", "ACTIVE"]

    def list_memories(self):
        return {"memories": self.existing}

    def create_memory(self, **kw):
        self.created.append(kw)
        return {"memoryId": f"mem-{kw['name']}"}

    def get_memory(self, *, memoryId):
        # First call returns CREATING, second returns ACTIVE
        status = self._statuses.pop(0) if self._statuses else "ACTIVE"
        return {"memory": {"status": status}}


def test_aws_returns_existing_memory_id():
    client = _FakeAWSClient(existing=[
        {"name": aws_memory_name("demo"), "id": "mem-existing"},
    ])
    mid = ensure_aws(project="demo", client=client)
    assert mid == "mem-existing"
    assert client.created == []


def test_aws_memory_name_is_underscored_and_clamped():
    """AgentCore regex requires no hyphens and max 48 chars."""
    name = aws_memory_name("my-project-with-hyphens")
    assert "-" not in name
    assert name.startswith("cloudless_my_project_with_hyphens")
    assert len(name) <= 48


def test_aws_creates_memory_when_missing():
    client = _FakeAWSClient()
    mid = ensure_aws(project="demo", client=client)
    assert mid == "mem-cloudless_demo_memory"
    assert len(client.created) == 1
    kw = client.created[0]
    assert kw["name"] == "cloudless_demo_memory"
    # eventExpiryDuration is DAYS, max 365 (so default 90 stays 90)
    assert kw["eventExpiryDuration"] == 90
    strategies = kw["memoryStrategies"]
    assert len(strategies) == 1
    assert "semanticMemoryStrategy" in strategies[0]
    assert strategies[0]["semanticMemoryStrategy"]["name"] == "default_semantic"


def test_aws_creates_with_user_preference_strategy():
    client = _FakeAWSClient()
    ensure_aws(project="demo", strategy="user_preference", client=client)
    kw = client.created[0]
    assert "userPreferenceMemoryStrategy" in kw["memoryStrategies"][0]


# --------------------------------------------------------------------- #
# GCP
# --------------------------------------------------------------------- #


class _FakeEngine:
    def __init__(self, *, display_name: str, resource_name: str):
        self.display_name = display_name
        self.resource_name = resource_name


class _FakeGCPClient:
    def __init__(self, *, existing: list[_FakeEngine] | None = None):
        self._existing = existing or []
        self.created: list[dict] = []

    def list(self):
        return iter(self._existing)

    def create(self, **kw):
        self.created.append(kw)
        # Build a synthetic resource name
        return _FakeEngine(
            display_name=kw["display_name"],
            resource_name=f"projects/p/locations/us-central1/reasoningEngines/new-{kw['display_name']}",
        )


def test_gcp_returns_existing_engine_when_present():
    name = gcp_engine_name("demo")
    existing = [_FakeEngine(display_name=name,
                             resource_name="projects/p/locations/us-central1/reasoningEngines/123")]
    client = _FakeGCPClient(existing=existing)
    rn = ensure_gcp(project="demo", client=client)
    assert rn.endswith("/123")
    assert client.created == []


def test_gcp_creates_engine_when_missing():
    client = _FakeGCPClient()
    rn = ensure_gcp(project="demo", client=client)
    assert "new-cloudless-demo" in rn
    assert client.created[0]["display_name"] == "cloudless-demo"
