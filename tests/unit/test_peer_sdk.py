"""Unit tests for cloudless.runtime.peer (A2A peer-call SDK).

These run against an in-process httpx mock — A2A *protocol* coverage on
real Cognito is exercised separately in tests/integration.
"""
from __future__ import annotations

import pytest

from cloudless.exceptions import (
    AuthenticationError,
    InvalidInputError,
    PeerUnreachable,
)
from cloudless.runtime.context import InMemoryContext
from cloudless.runtime.manifest import Manifest, PeerEntry
from cloudless.runtime.peer import (
    A2APeerClient,
    CognitoIdentity,
    build_peer_client,
)


pytestmark = [pytest.mark.asyncio]


class StubIdentity:
    """Hand-rolled identity that returns a fixed token without HTTP."""
    def __init__(self, token: str = "stub-jwt") -> None:
        self.token = token
        self.calls: list[str] = []

    async def mint_token(self, *, audience: str) -> tuple[str, int]:
        self.calls.append(audience)
        return self.token, 3600


def _manifest_with_peer(name: str, *, a2a_url: str = "https://peer.example/a2a") -> Manifest:
    return Manifest(
        project="test",
        agents={
            name: PeerEntry(
                name=name,
                cloud="aws",
                a2a_url=a2a_url,
                audience=f"https://{name}.example",
            ),
        },
    )


# ----------------------------- build_peer_client ------------------------ #


def test_build_peer_client_unknown_peer_raises():
    m = Manifest(project="t", agents={})
    with pytest.raises(InvalidInputError, match="unknown peer"):
        build_peer_client("missing", m)


def test_build_peer_client_with_manifest_returns_client():
    m = _manifest_with_peer("orders")
    client = build_peer_client("orders", m, identity=StubIdentity())
    assert isinstance(client, A2APeerClient)
    assert client.entry.name == "orders"


# ----------------------------- error paths ------------------------------ #


async def test_call_without_a2a_url_raises():
    entry = PeerEntry(name="bad", cloud="aws", audience="https://x")
    client = A2APeerClient(entry, identity=StubIdentity())
    with pytest.raises(InvalidInputError, match="no a2a_url"):
        await client.call("hello")


async def test_call_without_audience_raises():
    entry = PeerEntry(name="bad", cloud="aws", a2a_url="https://x.example/a2a")
    client = A2APeerClient(entry, identity=StubIdentity())
    with pytest.raises(InvalidInputError, match="no audience"):
        await client.call("hello")


async def test_call_without_identity_raises():
    entry = PeerEntry(
        name="x", cloud="aws", a2a_url="https://x.example/a2a", audience="https://x",
    )
    client = A2APeerClient(entry)  # no identity
    with pytest.raises(AuthenticationError, match="no identity"):
        await client.call("hello")


# ----------------------------- httpx mocked happy path ----------------- #


async def test_call_happy_path_with_httpx_mock(monkeypatch):
    """Patch httpx.AsyncClient to return a canned JSON-RPC response."""
    import httpx

    class FakeResponse:
        status_code = 200
        text = ""
        def json(self):
            return {
                "jsonrpc": "2.0",
                "id": "1",
                "result": {
                    "message": {"parts": [{"text": "pong"}]},
                    "metadata": {"usd_cost": 0.0042},
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, json=None, headers=None):
            # Verify the headers include the Cognito token + attribution
            assert headers["Authorization"] == "Bearer stub-jwt"
            assert "X-Cloudless-Attribution-Team" in headers
            assert json["method"] == "message/send"
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    ctx = InMemoryContext()
    ctx.cost.attribute(team="payments")

    client = build_peer_client(
        "orders", _manifest_with_peer("orders"),
        identity=StubIdentity(), cost_tracker=ctx.cost,
    )
    result = await client.call("ping")
    assert result["message"]["parts"][0]["text"] == "pong"
    # Cost telemetry got the peer's reported usd
    total = await ctx.cost.session_total_usd()
    assert total == pytest.approx(0.0042)


async def test_call_401_raises_authentication_error(monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 401
        text = "Unauthorized"

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = build_peer_client(
        "orders", _manifest_with_peer("orders"), identity=StubIdentity(),
    )
    with pytest.raises(AuthenticationError):
        await client.call("ping")


async def test_call_500_raises_peer_unreachable(monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 503
        text = "down"

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = build_peer_client("orders", _manifest_with_peer("orders"), identity=StubIdentity())
    with pytest.raises(PeerUnreachable):
        await client.call("ping")


async def test_call_jsonrpc_error_raises_invalid_input(monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"jsonrpc": "2.0", "id": "1",
                    "error": {"code": -32601, "message": "method not found"}}

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = build_peer_client("orders", _manifest_with_peer("orders"), identity=StubIdentity())
    with pytest.raises(InvalidInputError, match="-32601"):
        await client.call("ping")


# ----------------------------- token caching --------------------------- #


async def test_token_is_cached_across_calls(monkeypatch):
    import httpx

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    identity = StubIdentity()
    client = build_peer_client("orders", _manifest_with_peer("orders"), identity=identity)
    await client.call("a")
    await client.call("b")
    await client.call("c")
    # Should only have minted once because expires_in=3600.
    assert len(identity.calls) == 1
