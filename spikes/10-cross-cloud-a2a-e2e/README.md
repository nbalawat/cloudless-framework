# Spike 10 — Cross-cloud A2A E2E (capstone)

## What we're proving

The whole architecture. End to end. With money on the line.

A **GCP-hosted agent** (Gemini Enterprise Agent Runtime, from Spike 4 lineage)
calls an **AWS-hosted agent** (AgentCore Runtime in A2A mode + Cognito JWT
inbound auth, from Spike 2 lineage). The call goes:

1. GCP agent mints a Cognito M2M JWT (`client_credentials` against the Cognito
   pool created in Spike 2).
2. GCP agent issues an A2A JSON-RPC `message/send` against the AgentCore A2A
   endpoint with `Authorization: Bearer <jwt>`.
3. AgentCore validates the JWT against Cognito JWKS, dispatches to Strands.
4. Strands replies `pong`.
5. GCP agent receives the response and returns it to its own caller.

If this works, the entire cloudless architecture is empirically validated:
Q4 (build strategy) + Q5 (Strands on AWS) + Q6 (single-protocol per runtime)
+ Q7 (Cognito IdP) + Q12 (peer routing via manifest) all compose into a
working cross-cloud demo.

## How

1. Provision a Spike-2-style Cognito pool (or reuse Spike 2's if still live).
2. Provision a Spike-2-style AgentCore JWT-protected A2A runtime.
3. Author a GCP-side agent with a `call_aws_peer(peer_url, prompt)` method.
   - Cognito creds passed as env/secret (we use a Spike-10-only Cognito
     `cloudless-spike-10` pool + client to avoid mingling with Spike 2).
4. Deploy the GCP agent.
5. Verify by calling `query()` on the GCP engine; the GCP engine internally
   calls the AWS peer and returns the proxied response.

## Files

- `setup.py` — provisions Cognito + AgentCore runtime (analogous to Spike 2)
- `gcp_agent.py` — picklable agent class that calls AWS peer
- `deploy_gcp.py` — deploys the GCP agent
- `verify.py` — invokes the GCP engine and confirms the chain returns 'pong'
- `cleanup.py` — destroys all spike resources on both clouds

## Expected outcome

`verify.py` prints:
```
[PASS] GCP agent query() returned: {"text": "pong (proxied from AWS via A2A)", ...}
[PASS] AWS-side log shows incoming A2A message/send with Cognito Bearer
[PASS] Cross-cloud loop closed end-to-end
```

## Estimated cost

- Reuses Cognito + AWS resources or provisions new ones (~$0.01)
- GCP agent deploy ~$0.02
- Inference (Bedrock Haiku on AWS + Gemini Flash on GCP) ~$0.001

**Total expected: under $0.05.**
