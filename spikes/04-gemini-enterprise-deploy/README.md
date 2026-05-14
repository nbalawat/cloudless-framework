# Spike 4 — Gemini Enterprise Agent Runtime deploy

## What we're proving (Q4 GCP side)

Authoring a picklable Python class that the Vertex AI SDK can serialize and
deploy via `client.agent_engines.create()` — the canonical GCP-side build path
under Gemini Enterprise Agent Platform (formerly Vertex AI Agent Engine).

If this works, Q4's "cloud-native artifact per cloud" decision is validated
on the GCP side. Combined with Spike 1 (AWS-side ARM64 container deploy), the
two-artifact build strategy is end-to-end proven.

## How

1. **Bucket**: create a `cloudless-spike-04-*` GCS staging bucket the SA can write to.
2. **Agent class**: author `CloudlessSpike04Agent` with `set_up()` / `query()` /
   `stream_query()` — picklable (no live clients in `__init__`).
3. **Deploy**: `vertexai.init(...)` then `agent_engines.create(agent_engine=instance,
   requirements=[...], display_name=...)`.
4. **Verify**: `agent_engines.list()` shows the engine; call `query()` and
   `stream_query()` against the deployed engine.
5. **Cleanup**: delete the engine + bucket.

All resources prefixed `cloudless-spike-04-*`.

## Files

- `agent.py` — picklable Agent class
- `deploy.py` — provisions bucket + deploys
- `verify.py` — list + query + stream_query
- `cleanup.py` — destroys all spike resources

## Estimated cost

- Cloud Build for the agent image: ~$0.01
- GCS staging bucket: negligible
- Agent Runtime: ~$0 idle
- Gemini Flash inference for the smoke test: ~$0.0001

**Total expected: under $0.05.**
