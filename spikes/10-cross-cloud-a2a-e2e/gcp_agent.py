"""
Spike 10 GCP-hosted agent that calls an AWS-hosted A2A peer.

This is the cross-cloud capstone. The agent:
  1. Mints a Cognito M2M JWT via client_credentials.
  2. Issues a JSON-RPC `message/send` against the AWS-side AgentCore A2A
     endpoint with `Authorization: Bearer <jwt>`.
  3. Returns the response to its own caller.

SECURITY NOTE: Cognito client_secret is baked into the pickled object and
ends up in the GCS staging bucket. Acceptable for spike work where the
user owns the project. For production cloudless, the GCP adapter should
inject creds via Secret Manager at `set_up()` time — see SPIKE-FINDINGS F14.
"""
from __future__ import annotations

import base64
import time
import uuid
from typing import Iterator


class CloudlessSpike10Agent:
    """GCP-hosted agent that proxies an A2A call to an AWS peer."""

    def __init__(
        self,
        # Cognito M2M creds (Spike 2 setup, reused here)
        cognito_token_url: str,
        cognito_client_id: str,
        cognito_client_secret: str,
        cognito_scope: str,
        # AWS A2A endpoint we want to call
        aws_peer_url: str,
    ):
        self.cognito_token_url = cognito_token_url
        self.cognito_client_id = cognito_client_id
        self.cognito_client_secret = cognito_client_secret
        self.cognito_scope = cognito_scope
        self.aws_peer_url = aws_peer_url
        self._cached_token: tuple[str, float] | None = None  # (token, expires_at)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def set_up(self) -> None:
        """Called once per worker after deserialization."""
        import httpx
        self._http = httpx.Client(timeout=30.0)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _mint_cognito_token(self) -> str:
        """client_credentials grant; cache the access token until expiry."""
        if self._cached_token and time.time() < self._cached_token[1] - 60:
            return self._cached_token[0]
        basic = base64.b64encode(
            f"{self.cognito_client_id}:{self.cognito_client_secret}".encode()
        ).decode()
        resp = self._http.post(
            self.cognito_token_url,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": self.cognito_scope},
        )
        resp.raise_for_status()
        tok = resp.json()
        self._cached_token = (tok["access_token"], time.time() + tok["expires_in"])
        return tok["access_token"]

    def _a2a_message_send(self, prompt: str) -> dict:
        """Issue an A2A v0.3 JSON-RPC `message/send` to the AWS peer."""
        token = self._mint_cognito_token()
        # A2A v0.3 Message structure: { messageId, role, parts: [{ kind: 'text', text }] }
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": str(uuid.uuid4()),
                    "role": "user",
                    "parts": [{"kind": "text", "text": prompt}],
                },
            },
        }
        resp = self._http.post(
            self.aws_peer_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        return {
            "status_code": resp.status_code,
            "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
        }

    # ------------------------------------------------------------------ #
    # Public Agent Runtime operations
    # ------------------------------------------------------------------ #

    def query(self, prompt: str) -> dict:
        """Caller-facing entrypoint: proxy the prompt to the AWS peer."""
        if not hasattr(self, "_http"):
            self.set_up()
        result = self._a2a_message_send(prompt)
        return {
            "from": "gcp-agent",
            "via": "a2a + cognito jwt",
            "aws_response": result,
        }

    def stream_query(self, prompt: str) -> Iterator[dict]:
        """Streaming variant — yields a single chunk for now (Spike 10 is request/response)."""
        if not hasattr(self, "_http"):
            self.set_up()
        yield self.query(prompt)

    def register_operations(self) -> dict:
        return {"": ["query"], "stream": ["stream_query"]}
