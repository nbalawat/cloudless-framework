"""
Spike 1 — fetch the agent card AgentCore serves for our deployed A2A runtime.

Compares the deployed card against the locally-served card we observed
in F9 to see what AgentCore rewrites (notably the `url` field) and what
it preserves (notably `protocolVersion`).
"""
from __future__ import annotations

import json
import sys
import urllib.parse

import boto3
import botocore.auth
import botocore.awsrequest
import httpx


REGION = "us-east-1"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:613112965612:runtime/cloudless_spike_01-0eCgMF2Kc1"


def sigv4_get(url: str, *, region: str, service: str = "bedrock-agentcore") -> httpx.Response:
    """GET `url` with SigV4 signing using current boto3 credentials."""
    session = boto3.session.Session(region_name=region)
    creds = session.get_credentials().get_frozen_credentials()
    req = botocore.awsrequest.AWSRequest(method="GET", url=url, headers={})
    signer = botocore.auth.SigV4Auth(creds, service, region)
    signer.add_auth(req)
    headers = dict(req.headers)
    return httpx.get(url, headers=headers, timeout=30.0)


def main() -> int:
    escaped = urllib.parse.quote(AGENT_ARN, safe="")
    base = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped}/invocations"

    paths = [
        "/.well-known/agent-card.json",
        "/.well-known/agent.json",     # legacy v0.3 location
    ]

    for p in paths:
        url = base + p
        print(f"\n=== GET {p} ===")
        print(f"URL: {url}")
        resp = sigv4_get(url, region=REGION)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Body: {resp.text[:600]}")
            continue
        try:
            body = resp.json()
            print(json.dumps(body, indent=2))
        except Exception:
            print(resp.text[:1500])

    return 0


if __name__ == "__main__":
    sys.exit(main())
