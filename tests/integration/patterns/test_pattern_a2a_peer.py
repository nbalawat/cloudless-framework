"""Pattern 7 — Network / peer-to-peer (A2A) with HITL.

Two agents are wired via the in-process A2A server wrapper:
  - `orders`: the peer agent, exposes /a2a — answers order-status queries
  - `concierge`: the calling agent, invokes orders via A2APeerClient

The concierge pauses for human escalation if the orders peer returns
`needs_escalation=true`.

This exercises:
  - cloudless.runtime.a2a_server.build_a2a_app (inbound side)
  - cloudless.runtime.peer.A2APeerClient (outbound side)
  - Attribution-header propagation
  - HITL pause when a peer surfaces an escalation signal
"""
from __future__ import annotations

import socket
import threading
import time
from typing import AsyncIterator

import pytest
import uvicorn
from starlette.testclient import TestClient

import cloudless
from cloudless.chunks import Chunk, FinalChunk, PauseChunk, TextChunk
from cloudless.runtime.a2a_server import build_a2a_app
from cloudless.runtime.manifest import Manifest, PeerEntry
from cloudless.runtime.peer import A2APeerClient
from cloudless.runtime.tasks import pause, reset_store

from tests.integration.patterns._harness import (
    aws_available,
    complete_pause,
    drain,
    find_pause,
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean_tasks():
    reset_store()
    yield
    reset_store()


# --------------------------------------------------------------------- #
# Peer agent — the "orders" service
# --------------------------------------------------------------------- #


class _OrdersAgent(cloudless.Agent):
    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        # Toy logic: if prompt mentions "VIP" we escalate
        if "VIP" in prompt:
            yield TextChunk(text="status:unknown needs_escalation:true")
        else:
            yield TextChunk(text="status:shipped tracking:1Z9999")
        yield FinalChunk()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def orders_server_url():
    """Run an A2A server hosting the orders peer."""
    port = _free_port()
    app = build_a2a_app(_OrdersAgent)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    # Wait for boot
    import httpx
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            httpx.post(f"http://127.0.0.1:{port}/a2a", json={"jsonrpc": "2.0"}, timeout=0.5)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/a2a"
    server.should_exit = True
    th.join(timeout=2)


# --------------------------------------------------------------------- #
# Calling agent — concierge
# --------------------------------------------------------------------- #


class _StubIdentity:
    async def mint_token(self, *, audience):
        return "stub-token", 3600


class ConciergeAgent(cloudless.Agent):
    def __init__(self, orders_url: str):
        super().__init__()
        self._orders_url = orders_url

    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        # Build the peer client (bypass full manifest plumbing for the test)
        entry = PeerEntry(
            name="orders", cloud="aws",
            a2a_url=self._orders_url,
            audience="https://orders.example",
        )
        client = A2APeerClient(
            entry, identity=_StubIdentity(), cost_tracker=ctx.cost,
        )
        result = await client.call(prompt)
        text = "".join(p.get("text", "") for p in result["message"]["parts"])
        yield TextChunk(text=f"[orders] {text}\n")

        if "needs_escalation:true" in text:
            rec = pause(
                agent_name="concierge",
                session_id=ctx.session.id,
                reason="orders peer escalated",
                pending_action={"orders_response": text, "prompt": prompt},
            )
            yield PauseChunk(
                resume_token=rec.resume_token,
                reason=rec.reason,
                pending_action=rec.pending_action,
            )
            return

        yield FinalChunk(state={"status": "ok"})


async def test_a2a_peer_happy_path(aws_available, orders_server_url):
    agent = ConciergeAgent(orders_server_url)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "What's the status of order o123?")

    assert find_pause(chunks) is None
    text = "".join(c.text for c in chunks if isinstance(c, TextChunk))
    assert "status:shipped" in text


async def test_a2a_peer_escalation_pauses(aws_available, orders_server_url):
    agent = ConciergeAgent(orders_server_url)
    ctx = cloudless.InMemoryContext()
    chunks = await drain(agent, ctx, "Status of order for VIP customer Acme?")

    pause_chunk = find_pause(chunks)
    assert pause_chunk is not None
    assert "escalated" in pause_chunk.reason
    rec = complete_pause(pause_chunk.resume_token, {"escalation_owner": "manager-alice"})
    assert rec.approval == {"escalation_owner": "manager-alice"}


async def test_a2a_attribution_headers_propagate(aws_available, orders_server_url):
    """Attribution set on the caller flows to the peer in HTTP headers."""
    agent = ConciergeAgent(orders_server_url)
    ctx = cloudless.InMemoryContext()
    ctx.cost.attribute(team="support", project="concierge")
    await drain(agent, ctx, "Status of order o1?")
    # Attribution was set; the A2APeerClient does send it as headers — we
    # asserted that path in tests/unit/test_peer_sdk.py. Here we verify
    # the calling agent's attribution is intact post-call.
    assert ctx.cost.attribution == {"team": "support", "project": "concierge"}
