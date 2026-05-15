"""Unit tests for the inbound A2A server wrapper."""
from __future__ import annotations

from collections.abc import AsyncIterator

from starlette.testclient import TestClient

import cloudless
from cloudless.chunks import Chunk, FinalChunk, TextChunk
from cloudless.exceptions import GuardrailBlocked, PolicyViolation
from cloudless.runtime.a2a_server import build_a2a_app


class _EchoAgent(cloudless.Agent):
    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        yield TextChunk(text=f"echo: {prompt}")
        yield FinalChunk()


def _build_client(factory):
    app = build_a2a_app(factory)
    return TestClient(app)


def _rpc(client, prompt: str, **kw):
    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": "m-1",
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
            },
        },
    }
    return client.post("/a2a", json=body, **kw)


def test_happy_path_returns_assistant_message():
    client = _build_client(_EchoAgent)
    r = _rpc(client, "hello")
    assert r.status_code == 200
    data = r.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "1"
    parts = data["result"]["message"]["parts"]
    assert parts[0]["text"] == "echo: hello"
    assert data["result"]["metadata"]["usd_cost"] >= 0
    assert any(c["kind"] == "final" for c in data["result"]["metadata"]["chunks"])


def test_unknown_method_returns_minus_32601():
    client = _build_client(_EchoAgent)
    body = {"jsonrpc": "2.0", "id": "1", "method": "wrong/method"}
    r = client.post("/a2a", json=body)
    assert r.status_code == 200
    err = r.json()["error"]
    assert err["code"] == -32601


def test_missing_prompt_returns_minus_32602():
    client = _build_client(_EchoAgent)
    body = {"jsonrpc": "2.0", "id": "1", "method": "message/send",
            "params": {"message": {"parts": []}}}
    r = client.post("/a2a", json=body)
    err = r.json()["error"]
    assert err["code"] == -32602


def test_invalid_jsonrpc_envelope_returns_minus_32600():
    client = _build_client(_EchoAgent)
    body = {"id": "1", "method": "message/send"}  # missing jsonrpc field
    r = client.post("/a2a", json=body)
    err = r.json()["error"]
    assert err["code"] == -32600


def test_malformed_json_returns_minus_32700():
    client = _build_client(_EchoAgent)
    r = client.post("/a2a", content="not json{{", headers={"Content-Type": "application/json"})
    err = r.json()["error"]
    assert err["code"] == -32700


def test_policy_violation_maps_to_internal_error():
    class _PolicyBlocker(cloudless.Agent):
        async def query(self, ctx, prompt):
            raise PolicyViolation("blocked")
            yield  # unreachable

    client = _build_client(_PolicyBlocker)
    err = _rpc(client, "hi").json()["error"]
    assert err["code"] == -32603
    assert "policy" in err["message"].lower()


def test_guardrail_blocked_maps_to_internal_error():
    class _GBAgent(cloudless.Agent):
        async def query(self, ctx, prompt):
            raise GuardrailBlocked("nope")
            yield

    client = _build_client(_GBAgent)
    err = _rpc(client, "hi").json()["error"]
    assert err["code"] == -32603
    assert "guardrail" in err["message"].lower()


def test_audience_mismatch_rejected():
    app = build_a2a_app(_EchoAgent, require_audience="my-aud")
    client = TestClient(app)
    r = _rpc(client, "hi", headers={"X-A2A-Audience": "wrong"})
    err = r.json()["error"]
    assert err["code"] == -32600
    assert "audience" in err["message"].lower()


def test_audience_match_accepted():
    app = build_a2a_app(_EchoAgent, require_audience="my-aud")
    client = TestClient(app)
    r = _rpc(client, "hi", headers={"X-A2A-Audience": "my-aud"})
    assert r.status_code == 200
    assert "echo" in r.json()["result"]["message"]["parts"][0]["text"]


def test_attribution_headers_ingested():
    """Inbound X-Cloudless-Attribution-* headers should flow into ctx.cost."""
    captured = {}

    class _CapturingAgent(cloudless.Agent):
        async def query(self, ctx, prompt):
            captured["attribution"] = dict(ctx.cost.attribution)
            yield TextChunk(text="ok")

    app = build_a2a_app(_CapturingAgent)
    client = TestClient(app)
    _rpc(client, "hi", headers={
        "X-Cloudless-Attribution-Team": "payments",
        "X-Cloudless-Attribution-Project": "checkout",
    })
    assert captured["attribution"] == {"team": "payments", "project": "checkout"}
