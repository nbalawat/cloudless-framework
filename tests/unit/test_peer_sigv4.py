"""Verify A2APeerClient + SigV4Identity flow with mocked httpx."""
from __future__ import annotations

import pytest

from cloudless.runtime.identity import SigV4Identity
from cloudless.runtime.manifest import PeerEntry
from cloudless.runtime.peer import A2APeerClient

pytestmark = [pytest.mark.asyncio]


async def test_peer_call_with_sigv4_signs_request_per_call(monkeypatch):
    """A2APeerClient + SigV4Identity should sign every request individually."""
    captured: list[dict] = []

    class _FakeResponse:
        status_code = 200
        text = ""
        def json(self):
            return {"jsonrpc": "2.0", "id": "1",
                    "result": {"message": {"parts": []}, "metadata": {}}}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            captured.append({"url": url, "headers": dict(headers)})
            return _FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    # Stub SigV4 signer to return predictable signed headers
    class _StubSigV4:
        async def mint_token(self, *, audience):
            return "__sigv4__", 0

        def sign_request(self, *, method, url, body, headers=None):
            return {
                **(headers or {}),
                "Authorization": "AWS4-HMAC-SHA256 Credential=stub/...",
                "X-Amz-Date": "20260515T000000Z",
            }

    entry = PeerEntry(
        name="orders", cloud="aws",
        a2a_url="https://api.example/a2a",
        audience="https://orders.example",
    )
    client = A2APeerClient(entry, identity=_StubSigV4())
    await client.call("hello")
    await client.call("again")

    assert len(captured) == 2
    for call in captured:
        # The Authorization header should be SigV4-shaped, not Bearer
        assert call["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256")
        assert "X-Amz-Date" in call["headers"]


async def test_real_sigv4_signing_produces_aws4_header():
    """Real SigV4Identity (with real boto3 credentials) signs requests."""
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
    except Exception:
        pytest.skip("AWS credentials not configured")

    identity = SigV4Identity(service="execute-api", region="us-east-1")
    signed = identity.sign_request(
        method="POST",
        url="https://api.example.com/a2a",
        body=b'{"jsonrpc":"2.0"}',
    )
    assert "Authorization" in signed
    assert "AWS4-HMAC-SHA256" in signed["Authorization"]
