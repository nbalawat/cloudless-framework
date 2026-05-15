"""Unit tests for OAuth3LOIdentity + SigV4Identity."""
from __future__ import annotations

import time
import pytest

from cloudless.runtime.identity import (
    InMemoryTokenStore,
    OAuth3LOConfig,
    OAuth3LOIdentity,
    OAuthRequired,
    SigV4Identity,
    StoredToken,
)


pytestmark = [pytest.mark.asyncio]


def _cfg(**overrides) -> OAuth3LOConfig:
    base = OAuth3LOConfig(
        provider="testprov",
        client_id="client-id",
        client_secret="client-secret",
        authorize_endpoint="https://auth.example/oauth/authorize",
        token_endpoint="https://auth.example/oauth/token",
        redirect_uri="https://app.example/cb",
        scopes=("read", "write"),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ----------------------------- OAuth 3LO ------------------------------- #


async def test_get_token_raises_when_no_token_stored():
    identity = OAuth3LOIdentity(_cfg())
    with pytest.raises(OAuthRequired) as exc:
        await identity.get_token(user_id="u1")
    assert exc.value.state
    assert "auth.example" in exc.value.authorize_url
    assert "code_challenge" in exc.value.authorize_url
    assert "scope=read+write" in exc.value.authorize_url


async def test_get_token_returns_stored_unexpired_token():
    store = InMemoryTokenStore()
    store.put(user_id="u1", provider="testprov", token=StoredToken(
        access_token="abc123",
        expires_at=time.time() + 3600,
    ))
    identity = OAuth3LOIdentity(_cfg(), token_store=store)
    token = await identity.get_token(user_id="u1")
    assert token == "abc123"


async def test_expired_token_with_refresh_attempts_refresh(monkeypatch):
    """Expired + refresh_token → refresh path is exercised."""
    store = InMemoryTokenStore()
    store.put(user_id="u1", provider="testprov", token=StoredToken(
        access_token="old",
        refresh_token="rf-1",
        expires_at=time.time() - 1,  # already expired
    ))
    identity = OAuth3LOIdentity(_cfg(), token_store=store)

    refresh_called = {"n": 0}
    async def _fake_refresh(self_, refresh_token):
        refresh_called["n"] += 1
        return StoredToken(access_token="new", refresh_token=refresh_token,
                            expires_at=time.time() + 3600)

    monkeypatch.setattr(OAuth3LOIdentity, "_refresh",
                         lambda self, rt: _fake_refresh(self, rt))

    token = await identity.get_token(user_id="u1")
    assert token == "new"
    assert refresh_called["n"] == 1


def test_build_authorize_url_uses_pkce_s256():
    identity = OAuth3LOIdentity(_cfg())
    url, state = identity.build_authorize_url(user_id="u1")
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert state in identity._pending_pkce


def test_inmemory_token_store_returns_expired_tokens_for_refresh_logic():
    """The store should NOT hide expired tokens — identity layer handles refresh."""
    store = InMemoryTokenStore()
    store.put(user_id="u1", provider="p", token=StoredToken(
        access_token="x", refresh_token="rf", expires_at=time.time() - 100,
    ))
    got = store.get(user_id="u1", provider="p")
    assert got is not None
    assert got.refresh_token == "rf"


# ----------------------------- SigV4 ------------------------------- #


async def test_sigv4_identity_mints_sentinel_token():
    """SigV4 returns the sentinel '__sigv4__' so A2APeerClient knows to sign."""
    identity = SigV4Identity(service="execute-api", region="us-east-1")
    token, expires_in = await identity.mint_token(audience="anything")
    assert token == "__sigv4__"
    assert expires_in == 0  # never cache


def test_sigv4_sign_request_adds_authorization_header():
    """SigV4 signing produces the Authorization + AWS4-HMAC-SHA256 header."""
    identity = SigV4Identity(service="execute-api", region="us-east-1")
    signed = identity.sign_request(
        method="POST",
        url="https://api.example.com/a2a",
        body=b'{"jsonrpc":"2.0"}',
    )
    assert "Authorization" in signed
    assert "AWS4-HMAC-SHA256" in signed["Authorization"]
    assert "X-Amz-Date" in signed or "x-amz-date" in {k.lower() for k in signed}


def test_sigv4_sign_request_raises_when_no_creds(monkeypatch):
    import boto3
    sess = boto3.Session()
    # Force creds-resolution to return None
    monkeypatch.setattr(sess, "get_credentials", lambda: None)
    identity = SigV4Identity(service="execute-api", region="us-east-1", session=sess)
    with pytest.raises(RuntimeError, match="no AWS credentials"):
        identity.sign_request(method="GET", url="https://x.example", body=b"")
