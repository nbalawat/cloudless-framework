"""Unit test for `cloudless dev`'s SSE streaming route."""
from __future__ import annotations

import json
from typing import AsyncIterator

import pytest
from starlette.testclient import TestClient

import cloudless
from cloudless.chunks import Chunk, FinalChunk, TextChunk


class _StreamingAgent(cloudless.Agent):
    """Minimal agent that yields three text chunks then final."""
    async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
        yield TextChunk(text="hello ")
        yield TextChunk(text="world")
        yield FinalChunk()


@cloudless.agent(name="streaming-test", interfaces=["http"])
class StreamingTestAgent(_StreamingAgent):
    pass


def _build_app():
    from cloudless.cli.dev import _build_local_app
    return _build_local_app(StreamingTestAgent)


def _starlette_app(app):
    # BedrockAgentCoreApp IS a Starlette app (no .app wrapper)
    return app


def test_invocations_returns_aggregated_json():
    """Existing JSON contract on /invocations stays intact."""
    app = _build_app()
    client = TestClient(_starlette_app(app))
    resp = client.post("/invocations", json={"prompt": "go"})
    assert resp.status_code == 200
    data = resp.json()
    # bedrock-agentcore wraps the entrypoint return value; the keys we set
    # are inside `data`.
    payload = data if "chunks" in data else data.get("result", data)
    assert "chunks" in payload
    assert payload["final_text"] == "hello world"


def test_stream_endpoint_emits_sse_events_per_chunk():
    """The /invocations/stream route should emit one SSE event per Chunk."""
    app = _build_app()
    client = TestClient(_starlette_app(app))
    with client.stream("POST", "/invocations/stream", json={"prompt": "go"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = b"".join(resp.iter_bytes()).decode()

    # Should contain three real chunks + done sentinel
    assert body.count("event: text") == 2
    assert body.count("event: final") == 1
    assert body.count("event: done") == 1

    # First text chunk payload contains the actual text
    first_text_block = body.split("event: text", 1)[1].split("\n\n", 1)[0]
    data_line = [l for l in first_text_block.splitlines() if l.startswith("data:")][0]
    chunk_json = json.loads(data_line.removeprefix("data: ").strip())
    assert chunk_json["text"] == "hello "
    assert chunk_json["kind"] == "text"


def test_stream_endpoint_emits_error_event_on_failure(monkeypatch):
    """If the agent raises mid-stream, the SSE stream emits an error event."""

    class _FailingAgent(cloudless.Agent):
        async def query(self, ctx, prompt: str) -> AsyncIterator[Chunk]:
            yield TextChunk(text="partial ")
            raise RuntimeError("kaboom")

    @cloudless.agent(name="failing-test", interfaces=["http"])
    class FailingTestAgent(_FailingAgent):
        pass

    from cloudless.cli.dev import _build_local_app
    app = _build_local_app(FailingTestAgent)
    client = TestClient(_starlette_app(app))
    with client.stream("POST", "/invocations/stream", json={"prompt": "go"}) as resp:
        body = b"".join(resp.iter_bytes()).decode()

    assert "event: text" in body
    assert "event: error" in body
    assert "kaboom" in body
