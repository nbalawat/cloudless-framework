# Spike 1 — AgentCore A2A agent-card serving

## What we're proving (R1)

When AgentCore deploys an agent in A2A protocol mode, what does its
`/.well-known/agent-card.json` actually look like? Specifically:

- What `protocolVersion` field does AWS serve?
- Does the served card validate against A2A spec v1.x?
- What `securitySchemes` / `capabilities` / `preferredTransport` are advertised?
- Is the URL pattern as documented?

Research dossier `03-agentcore-frameworks-and-a2a.md` flagged that AWS samples
advertise `protocolVersion: 0.3.0` while the upstream A2A spec is v1.x. We need
to confirm what AgentCore *actually* serves before designing cloudless's
manifest baking around assumptions.

## What we are NOT doing

- Not exercising A2A `message/send` (agent functionality irrelevant for Spike 1)
- Not testing cross-cloud auth (that's Spike 2)
- Not using Strands (broken against a2a-sdk 1.0 — see SPIKE-FINDINGS.md F3)

## How

1. **Build** a minimal a2a-sdk 1.0 `AgentExecutor` (no-op execute path).
2. **Configure** with `agentcore configure --protocol A2A
   --deployment-type direct_code_deploy`.
3. **Deploy** with `agentcore deploy`. CodeBuild is not needed for
   direct_code_deploy.
4. **Verify** by fetching `/.well-known/agent-card.json` via SigV4-signed HTTP
   GET to the runtime URL.
5. **Cleanup** with `agentcore destroy`.

All resources prefixed `cloudless-spike-01-*`.

## Files

- `agent.py` — minimal AgentExecutor + `serve_a2a()` entry point
- `requirements.txt` — pinned dependencies
- `deploy.py` — orchestrates configure + deploy via Python (no shell magic)
- `verify.py` — fetches the agent card and prints findings
- `cleanup.py` — destroys all spike resources

## Expected output

After `verify.py` runs we expect a JSON dump of the agent card with at least:

```json
{
  "name": "...",
  "version": "...",
  "url": "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/.../invocations/",
  "protocolVersion": "<X.Y>",
  "preferredTransport": "JSONRPC",
  "capabilities": {...},
  "securitySchemes": {...},
  "skills": [...]
}
```

Findings get appended to `docs/SPIKE-FINDINGS.md`.

## Estimated cost

- ECR storage: ~$0.10/month (deleted at cleanup)
- AgentCore runtime: $0 idle (no invocations). Each invoke ~$0.0001.
- Code Build: 1-2 minutes, ~$0.005.

**Total expected: under $0.05.**
