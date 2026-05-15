"""Unit tests for the A2A SSE streaming endpoint."""
from __future__ import annotations

import json
from typing import AsyncIterator

import pytest
from starlette.testclient import TestClient

import cloudless
from cloudless.chunks import Chunk, FinalChunk, TextChunk
from cloudless.runtime.a2a_server import build_a2a_app


class _StreamingAgent(cloudless.Agent):
    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        for word in prompt.split():
            yield TextChunk(text=word + " ")
        yield FinalChunk()


def _rpc_stream(client, prompt: str, **kw):
    body = {
        "jsonrpc": "2.0", "id": "s-1", "method": "message/stream",
        "params": {"message": {"messageId": "m1", "role": "user",
                                "parts": [{"kind": "text", "text": prompt}]}},
    }
    return client.post("/a2a/stream", json=body, **kw)


def test_stream_emits_one_event_per_chunk():
    app = build_a2a_app(_StreamingAgent)
    client = TestClient(app)
    with client.stream("POST", "/a2a/stream", json={
        "jsonrpc": "2.0", "id": "s-1", "method": "message/stream",
        "params": {"message": {"messageId": "m1", "role": "user",
                                "parts": [{"kind": "text", "text": "hello world test"}]}},
    }) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = b"".join(resp.iter_bytes()).decode()

    # 3 text chunks + 1 final + 1 done sentinel = 5 SSE events
    events = [e for e in body.strip().split("\n\n") if e]
    assert len(events) == 5
    # Each event is `data: <json>`
    first = json.loads(events[0].removeprefix("data: ").strip())
    assert first["result"]["chunk"]["kind"] == "text"
    assert first["result"]["done"] is False

    last = json.loads(events[-1].removeprefix("data: ").strip())
    assert last["result"]["done"] is True


def test_stream_unknown_method_returns_error():
    app = build_a2a_app(_StreamingAgent)
    client = TestClient(app)
    r = client.post("/a2a/stream", json={
        "jsonrpc": "2.0", "id": "s-1", "method": "wrong",
        "params": {},
    })
    assert r.json()["error"]["code"] == -32601


def test_stream_propagates_attribution_headers():
    captured = {}

    class _CapturingAgent(cloudless.Agent):
        async def query(self, ctx, prompt):
            captured["attribution"] = dict(ctx.cost.attribution)
            yield TextChunk(text="ok")

    app = build_a2a_app(_CapturingAgent)
    client = TestClient(app)
    body = {"jsonrpc": "2.0", "id": "s-1", "method": "message/stream",
            "params": {"message": {"messageId": "m1", "role": "user",
                                    "parts": [{"kind": "text", "text": "hi"}]}}}
    with client.stream("POST", "/a2a/stream", json=body,
                        headers={"X-Cloudless-Attribution-Team": "support"}):
        pass
    assert captured["attribution"] == {"team": "support"}
