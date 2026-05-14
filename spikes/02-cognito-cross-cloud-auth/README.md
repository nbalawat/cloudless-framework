# Spike 2 — Cognito M2M JWT for cross-cloud A2A auth

## What we're proving (Q7)

The single highest-stakes architectural assumption in cloudless:

1. **AWS-side**: An AgentCore Runtime configured with JWT inbound auth can be authenticated by a **Cognito-issued M2M (client_credentials) access token** — no SigV4 required.
2. **Cross-cloud (simulated GCP-side)**: The same JWT validates cleanly using standard OIDC libraries (`PyJWT` + JWKS fetch) — i.e., any GCP-hosted code that supports OIDC bearer validation will accept tokens from our Cognito issuer.

If both halves pass, cloudless's "Cognito as the shared cross-cloud IdP" pattern from Q7 holds. If either fails, we revise Q7 before M1.

## How

1. **Build** a Cognito User Pool + Resource Server (with scope
   `cloudless/agent.invoke`) + M2M App Client.
2. **Deploy** a new AgentCore Runtime (`cloudless_spike_02`) — same code as
   Spike 1, but `authorizer_configuration` points at the Cognito JWT issuer.
3. **Mint** an access token via the OAuth2 `client_credentials` grant against
   Cognito's `/oauth2/token` endpoint.
4. **Verify-A** (AWS-side): GET the agent card on the AgentCore endpoint with
   `Authorization: Bearer <jwt>` — expect 200 (validates AgentCore's JWT
   inbound).
5. **Verify-B** (GCP-side simulation): independently verify the JWT against
   Cognito's JWKS using `PyJWT` — expect a valid signature, matching issuer,
   matching audience.
6. **Cleanup**.

All resources prefixed `cloudless-spike-02-*`.

## Files

- `setup_cognito.py` — provisions Cognito pool + resource server + M2M client
- `agent.py` — same minimal Strands agent as Spike 1
- `deploy.py` — deploys AgentCore Runtime with JWT authorizer config
- `verify.py` — runs Verify-A (AgentCore) and Verify-B (GCP-side simulation)
- `cleanup.py` — destroys all spike resources
- `Dockerfile` — same as Spike 1

## Expected output

Verify-A and Verify-B both succeed; we record:
- Cognito issuer URL
- M2M client ID + audience
- AgentCore authorizer config schema
- Token TTL and refresh behavior

## Estimated cost

Cognito Standard tier: M2M app client billing is ~$0.015/client/day, free under 50k MAU otherwise. Spike 2 cost: well under $0.05.
