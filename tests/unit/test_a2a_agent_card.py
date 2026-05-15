"""Unit tests for A2A agent-card publication."""
from __future__ import annotations

from typing import AsyncIterator

import pytest
from starlette.testclient import TestClient

import cloudless
from cloudless.chunks import Chunk, FinalChunk, TextChunk
from cloudless.runtime.a2a_server import build_a2a_app


class _Echo(cloudless.Agent):
    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        yield TextChunk(text="ok")
        yield FinalChunk()


@cloudless.agent(
    name="card-test-agent",
    interfaces=["a2a"],
    description="A test agent for agent-card publication.",
    version="0.2.0",
    tags=("test", "a2a"),
)
class CardTestAgent(_Echo):
    pass


def test_agent_card_served_at_well_known():
    app = build_a2a_app(CardTestAgent)
    client = TestClient(app)
    r = client.get("/.well-known/agent.json")
    assert r.status_code == 200
    card = r.json()
    assert card["name"] == "card-test-agent"
    assert card["description"] == "A test agent for agent-card publication."
    assert card["version"] == "0.2.0"
    assert card["protocolVersion"] == "0.3.0"
    assert card["url"] == "/a2a"
    assert "skills" in card
    assert card["skills"][0]["tags"] == ["test", "a2a"]


def test_agent_card_overridable():
    custom = {"name": "custom", "description": "custom desc"}
    app = build_a2a_app(CardTestAgent, agent_card=custom)
    client = TestClient(app)
    r = client.get("/.well-known/agent.json")
    assert r.json() == custom


def test_agent_card_path_overridable():
    app = build_a2a_app(CardTestAgent, agent_card_path="/agent-card.json")
    client = TestClient(app)
    r = client.get("/agent-card.json")
    assert r.status_code == 200
    # Default path shouldn't serve the card now
    assert client.get("/.well-known/agent.json").status_code == 404
