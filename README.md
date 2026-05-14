# cloudless

> Write your agent once. Ship it to any cloud.

**Cloudless** is an open-source SDK and CLI for building agentic AI applications that deploy cleanly to AWS Bedrock AgentCore or Google Cloud's Gemini Enterprise Agent Platform (formerly Vertex AI), with first-class cross-cloud agent-to-agent (A2A) collaboration.

Working name. Status: design phase. Implementation targets are in [`docs/ROADMAP.md`](./docs/ROADMAP.md).

---

## What it is

- A **Python SDK** that exposes a unified service catalog (LLM, Embeddings, Memory, Secrets, Observability, A2A, Sandbox, Tools, VectorStore, Identity vault, Browser) over native AWS and GCP services.
- A **CLI** (`cloudless init`, `cloudless dev`, `cloudless deploy`) that hides all cloud-deployment complexity.
- An **embedded runtime library** that handles A2A serving, tracing, secrets resolution, retries, circuit breakers, and cost telemetry inside every deployed agent.
- A **framework-native experience**: users write code in their chosen agent framework — LangGraph, Strands Agents, Google ADK, or Microsoft Agent Framework — and we adapt to each cloud's deployment model behind the scenes.

## What it is not

- Not a meta-framework over the agent frameworks (we don't try to homogenize ADK and LangGraph).
- Not a managed service or central control plane (every agent is self-contained at runtime).
- Not a no-code / low-code product (target user is an AI-fluent application developer).
- Not for serverless function workloads — it's specifically for stateful, multi-turn, tool-using agents.

## Why

Building production-grade agentic systems on either AWS or GCP requires deep knowledge of cloud-specific deployment, identity, memory, gateway, and observability primitives. Doing it on *both* clouds with cross-cloud A2A means doubling that learning curve and reinventing the integration glue every time. Cloudless captures that glue once, in an opinionated SDK, so users can focus on the agent itself.

## Quick links

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — the full design document (29 locked decisions across 8 dimensions)
- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — milestone plan, v1 scope, what's deferred
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — concise ADR-style log of every decision and rationale
- [`docs/RISKS.md`](./docs/RISKS.md) — open questions and known risks
- [`docs/research/`](./docs/research/) — the comprehensive research dossiers (AgentCore, Vertex/Gemini Enterprise, A2A, frameworks)

## Target outcome

A working developer can run:

```bash
pip install cloudless
cloudless init my-app --frameworks langgraph,strands --clouds aws,gcp
cd my-app
cloudless dev hello                # runs locally with real LLM, mocked everything else
cloudless deploy hello             # ships to AWS AgentCore (or GCP Agent Runtime)
cloudless deploy hello --env prod
```

…and get cross-cloud A2A peer routing, OTel-everywhere observability, cost telemetry with attribution, automated versioning + rollback, eval-driven CI gates, and HITL approval flows — without touching IAM, VPCs, Cognito, AgentCore configuration, Vertex deploy specs, or A2A protocol details.

## License

Apache 2.0 (open-core). Enterprise-tier features (hosted approval inbox, advanced eval, on-prem control plane, compliance kits, support SLA) are a separate commercial offering.
