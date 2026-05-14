"""
Spike 2 verification:
  Verify-A1: Bearer token + AgentCore JWT runtime → 200
  Verify-A2: no Authorization header → 401/403 (JWT enforced)
  Verify-A3: invalid Bearer → 401/403
  Verify-B:  local PyJWT/JWKS validation (already proven in token-mint step;
             re-run as part of this script for self-containment).
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.parse
from pathlib import Path

import boto3
import botocore.auth
import botocore.awsrequest
import httpx
import jwt
from jwt import PyJWKClient


REGION = "us-east-1"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:613112965612:runtime/cloudless_spike_02-MSR6NF8xz5"
STATE_FILE = Path(__file__).parent / "cognito_state.json"


def mint_token(state: dict) -> str:
    """Mint a Cognito M2M token via client_credentials."""
    basic = base64.b64encode(f"{state['client_id']}:{state['client_secret']}".encode()).decode()
    resp = httpx.post(
        state["token_url"],
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": state["scope"]},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def sigv4_get(url: str) -> httpx.Response:
    sess = boto3.session.Session(region_name=REGION)
    creds = sess.get_credentials().get_frozen_credentials()
    req = botocore.awsrequest.AWSRequest(method="GET", url=url, headers={})
    signer = botocore.auth.SigV4Auth(creds, "bedrock-agentcore", REGION)
    signer.add_auth(req)
    return httpx.get(url, headers=dict(req.headers), timeout=30.0)


def main() -> int:
    state = json.loads(STATE_FILE.read_text())
    escaped = urllib.parse.quote(AGENT_ARN, safe="")
    base = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped}/invocations"
    card_url = base + "/.well-known/agent-card.json"

    # Local validation (Verify-B, replicated for self-containment)
    print("=== Verify-B: GCP-side JWT validation against Cognito JWKS ===")
    token = mint_token(state)
    header = jwt.get_unverified_header(token)
    jwks_client = PyJWKClient(state["jwks_url"])
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    verified = jwt.decode(
        token, signing_key.key, algorithms=[header["alg"]],
        issuer=state["issuer"], options={"verify_aud": False},
    )
    assert verified["client_id"] == state["client_id"]
    print("  [PASS] PyJWT+JWKS verifies the Cognito M2M token cleanly")

    # Verify-A1: valid Bearer → expect 200
    print("\n=== Verify-A1: AgentCore + valid Cognito Bearer ===")
    print(f"  GET {card_url}")
    resp = httpx.get(card_url, headers={"Authorization": f"Bearer {token}"}, timeout=30.0)
    print(f"  status: {resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        print(f"  [PASS] AgentCore accepted Cognito Bearer; protocolVersion={body.get('protocolVersion')}, name={body.get('name')}")
    else:
        print(f"  [FAIL] body: {resp.text[:600]}")
        return 1

    # Verify-A2: no Authorization header → expect 401/403
    print("\n=== Verify-A2: AgentCore + no auth ===")
    resp = httpx.get(card_url, timeout=30.0)
    print(f"  status: {resp.status_code}")
    if resp.status_code in (401, 403):
        print("  [PASS] AgentCore rejected unauthenticated request as expected")
    else:
        print(f"  [FAIL] expected 401/403, got {resp.status_code}; body: {resp.text[:300]}")

    # Verify-A3: invalid Bearer → expect 401/403
    print("\n=== Verify-A3: AgentCore + bogus Bearer ===")
    resp = httpx.get(card_url, headers={"Authorization": "Bearer this.is.not.a.real.jwt"}, timeout=30.0)
    print(f"  status: {resp.status_code}")
    if resp.status_code in (401, 403):
        print("  [PASS] AgentCore rejected invalid Bearer as expected")
    else:
        print(f"  [FAIL] expected 401/403, got {resp.status_code}; body: {resp.text[:300]}")

    # Verify-A4: SigV4 attempt against the JWT-only runtime (should fail or be rejected)
    print("\n=== Verify-A4: AgentCore + SigV4 (should fail since runtime is JWT-only) ===")
    resp = sigv4_get(card_url)
    print(f"  status: {resp.status_code}")
    if resp.status_code in (401, 403):
        print("  [PASS] AgentCore rejected SigV4 — auth modes are mutually exclusive at the runtime level")
    elif resp.status_code == 200:
        print("  [WARN] AgentCore accepted SigV4 even on a JWT-configured runtime — auth is permissive!")
    else:
        print(f"  body: {resp.text[:300]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
