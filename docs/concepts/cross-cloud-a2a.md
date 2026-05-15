# Cross-cloud A2A

cloudless agents call each other through the **Agent-to-Agent (A2A) v0.3**
protocol — JSON-RPC 2.0 over HTTPS with JWT auth. The first-class promise
is that an agent on AWS can call an agent on GCP, and vice versa, without
the caller knowing.

## The call site

```python
async def query(self, ctx, prompt):
    result = await ctx.peer("orders").call(prompt)
    # result is the JSON-RPC `result` field from the peer
```

`ctx.peer("orders")` looks up `orders` in the baked `cloudless-manifest.json`
and returns an `A2APeerClient` configured for that peer's audience.

## The wire

Outbound:

1. Mint a Cognito M2M JWT scoped to the peer's audience (cached until ~60s
   before expiry)
2. Build a JSON-RPC envelope:
   ```json
   {"jsonrpc": "2.0", "id": "...", "method": "message/send",
    "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "..."}]}}}
   ```
3. POST to the peer's `a2a_url` with `Authorization: Bearer <jwt>`
4. Attach `X-Cloudless-Attribution-*` headers for cost rollup

Inbound (`cloudless.runtime.a2a_server.build_a2a_app`):

1. Validate the JWT against the configured issuer (deploy adapter wires this)
2. Parse the JSON-RPC envelope; reject malformed with `-32700` / `-32600`
3. Build an `InMemoryContext`, ingest attribution headers
4. Drive the agent's `query()` generator, collect chunks, assemble the
   response message
5. Return JSON-RPC `result` with `metadata.usd_cost` and the chunk list

## Cross-cloud is the default

Cognito on AWS issues a JWT, GCP's Vertex Agent Engine validates it
(per its inbound JWT auth config), and the agent runs. The cloud
boundary is transparent.

This was validated end-to-end during Phase 0 (Spike 10): a GCP-hosted
Vertex agent called a Strands agent on AgentCore, with the cross-cloud
A2A round-trip taking ~600ms.

## Attribution propagation

```python
ctx.cost.attribute(team="payments", project="checkout")
await ctx.peer("orders").call(prompt)
# The orders peer's ctx.cost.attribution now also has {team: payments, project: checkout}
```

The receiver merges via `ctx.cost.ingest_attribution_headers(headers)` —
`setdefault` semantics, so an existing local tag isn't clobbered.
