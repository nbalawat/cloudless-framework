# cloudless — Architecture

> Status: design-locked through 39 questions. Implementation pending. Working name `cloudless`.
> Last updated: 2026-05-14.

## Table of contents

1. [Foundations](#1-foundations)
2. [Deployment model](#2-deployment-model)
3. [Cross-cloud collaboration](#3-cross-cloud-collaboration)
4. [Service catalog](#4-service-catalog)
5. [Developer experience](#5-developer-experience)
6. [Operations](#6-operations)
7. [Quality: evals + observability](#7-quality-evals--observability)
8. [Distribution and versioning](#8-distribution-and-versioning)
9. [Project & ecosystem conventions](#9-project--ecosystem-conventions)
10. [Extensibility model](#10-extensibility-model)

---

## 1. Foundations

### 1.1 Target user (Q1)

**AI-fluent application developer.** Python-comfortable, understands agents / tools / RAG / streaming, but does NOT want to learn IAM roles, VPC peering, AgentCore configuration, Vertex deploy specs, Cognito setup, or A2A protocol internals. Thinks in terms of "agent," "tool," "memory," "handoff" — not "service account" or "execution role."

This persona shapes everything. We are opinionated enough to actually hide cloud complexity but stop short of being a no-code product. Power users can drop down to native cloud SDKs whenever they need to.

### 1.2 Abstraction scope (Q2)

**Abstract the cloud, not the framework.** Users pick one of the four agent frameworks (ADK, LangGraph, Strands, MAF) and write *native* code in it. The four frameworks have genuinely different mental models — ADK is session/graph-based, LangGraph is explicit state machines, Strands is model-driven loops, MAF is multi-agent orchestration — and pretending they're interchangeable produces a leaky meta-framework that satisfies no one.

What we abstract is the **cloud infrastructure beneath**: a unified service catalog (LLM, Memory, VectorStore, Tools, Identity, Secrets, Observability, A2A, Sandbox) that resolves to native AWS or GCP services at deploy time. The user writes framework-native agent code; we handle the rest.

The cost: users must learn one framework. The win: the abstraction holds under stress, and we don't ship a transpiler.

### 1.3 Runtime topology (Q3)

**SDK + CLI + embedded runtime lib. No central control plane.**

Every deployed agent imports a small runtime library (`cloudless.runtime`) that handles:

- A2A serving (exposes `/.well-known/agent-card.json` per A2A v1.2)
- OTel trace export
- Secret resolution at startup
- Service-catalog binding (LLM client, Memory client, etc.)
- Retry / timeout / circuit-breaker enforcement
- Cost telemetry emission
- Manifest loading (peer discovery)

The CLI (`cloudless deploy`) compiles agent code + service-catalog bindings into a cloud-native artifact (ARM64 container for AWS AgentCore, picklable Python class for GCP Agent Runtime) and provisions the runtime.

Service discovery is decentralized via A2A agent cards. There is no registry server to host. We avoid the "where do we host the control plane to make this cloud-agnostic?" paradox.

---

## 2. Deployment model

### 2.1 Build strategy (Q4)

**Cloud-native artifact per cloud, single source.**

- **On AWS**: CLI generates an ARM64 Dockerfile wrapping the user's `Agent` class with a `BedrockAgentCoreApp` server exposing the chosen protocol contract (HTTP `/invocations` + `/ping` on port 8080, or A2A on port 9000, or MCP, or AG-UI). Pushes to ECR. Calls `CreateAgentRuntime` + `CreateAgentRuntimeEndpoint`.
- **On GCP**: CLI wraps the user's `Agent` class in a thin shim implementing `set_up()` / `query()` / `stream_query()`. Pickles. Calls `client.agent_engines.create()` on Gemini Enterprise Agent Runtime (formerly Vertex AI Agent Engine).

The user never sees either artifact. Trying to force "containers everywhere" on GCP would lose the free tier, Memory Bank auto-integration, and Google's auto-instrumentation — defeats the reason to use Agent Runtime over Cloud Run.

### 2.2 Framework rollout (Q5)

Framework × cloud support is asymmetric. Phased rollout:

| Framework | AWS (AgentCore) | GCP (Gemini Enterprise) | v1 | v1.0 (expanded) | v2 | v3 |
|---|---|---|---|---|---|---|
| LangGraph | Tier-1 (`langgraph-checkpoint-aws`) | Tier-1 (`LanggraphAgent` template) | ✅ | ✅ | — | — |
| Strands | Tier-1 (AWS-native) | Tier-3 (DIY template) | AWS only | **both** | — | — |
| Google ADK | Tier-2 (needs custom `AgentCoreMemorySessionService`) | Tier-1 (Google-native) | GCP only | **both** | — | — |
| MS Agent Framework | Tier-3 (DIY) | Tier-3 (DIY) | — | — | — | ✅ |

v1 (expanded scope locked in Q28 follow-up) ships **all three frameworks on both clouds** with the natural-pair work as the foundation and the cross-pair work (Strands/GCP + ADK/AWS) pulled in. MAF defers to v3.

### 2.3 Protocol exposure (Q6)

AgentCore Runtime is **single-protocol-per-deployment** (HTTP, MCP, A2A, or AG-UI — pick one at deploy time). An agent that needs both user-facing HTTP and peer A2A on AWS requires **two AgentCore deployments** sharing the same source.

**Spike-2 finding (F11a):** AgentCore is also **single-auth-mode-per-deployment.** A runtime configured for JWT inbound rejects SigV4 (403) and vice versa. So an agent that needs user-facing HTTP via SigV4 (IAM) *and* peer A2A via Cognito JWT requires **two runtimes from one ECR image** — and an agent needing HTTP-via-SigV4 + HTTP-via-JWT + A2A-via-JWT could require **three.** Cloudless's deploy planner enumerates `(protocol × auth_mode)` tuples per agent and emits one runtime per tuple. GCP Agent Runtime serves both protocols + both auth modes from one deployment; the asymmetry surfaces only on AWS.

GCP Agent Runtime can serve both protocols from one deployment.

Users declare what they want:

```python
@cloudless.agent(name="support", interfaces=["http", "a2a"])
class SupportAgent(cloudless.LangGraphAgent):
    ...
```

- `interfaces=["http"]` → one runtime (user-facing).
- `interfaces=["a2a"]` → one runtime (peer worker).
- `interfaces=["http", "a2a"]` → AWS: 2 runtimes, same ECR image; GCP: 1 runtime, 2 routes.

The CLI prints the cost delta at deploy time ("on AWS this agent costs 2× because it serves two protocols").

### 2.4 Deployment topology: multi-account, multi-region (Q23)

`cloudless.yaml` declares accounts/projects, regions, and per-environment overlays.

```yaml
clouds:
  aws:
    accounts:
      dev:     { account: "111...", region: us-east-1, profile: cloudless-dev }
      prod-us: { account: "222...", region: us-east-1, profile: cloudless-prod-us }
      prod-eu: { account: "222...", region: eu-west-1, profile: cloudless-prod-eu }
  gcp:
    projects:
      dev:     { project: cloudless-dev,    region: us-central1 }
      prod-us: { project: cloudless-prod,   region: us-central1 }
      prod-eu: { project: cloudless-prod,   region: europe-west1 }

environments:
  dev:     { aws: dev,     gcp: dev }
  staging: { aws: dev,     gcp: dev,     endpoint_alias: staging }
  prod-us: { aws: prod-us, gcp: prod-us, endpoint_alias: prod }
  prod-eu: { aws: prod-eu, gcp: prod-eu, endpoint_alias: prod }

agents:
  support:
    cloud: aws
    residency: [us, eu]      # deploy twice; route by user region
  orders:
    cloud: gcp
    residency: us
```

Region routing in the embedded runtime: when agent A calls residency-aware peer B, the SDK picks B's endpoint based on (1) explicit `region=` hint, (2) the user's region attribute in context, (3) caller's own region (data-locality default).

Multi-tenancy (one infrastructure serving many customer orgs) is **deferred to v1.5 / commercial** — buildable on these v1 primitives but warrants its own abstraction layer.

---

## 3. Cross-cloud collaboration

### 3.1 A2A authentication (Q7)

**Auto-provision AWS Cognito as the default cross-cloud IdP; BYO IdP escape hatch.**

At `cloudless init`, the CLI provisions a Cognito User Pool + Resource Server. Each deployed agent registers an M2M app client with scoped permissions. The agent's A2A peer-call SDK grabs a client-credentials JWT (cached, auto-refreshed) and presents it as `Authorization: Bearer <jwt>`. AWS-side AgentCore validates against Cognito JWKS natively; GCP-side Agent Runtime A2A endpoints validate against the same Cognito issuer URL (standard OIDC JWT).

A2A is **also intra-cloud**: same auth pattern works whether peer is on the same cloud or across clouds. Location is orthogonal to authentication.

Customers can swap to Auth0 / Entra ID / Okta via a single config change (`identity.type: auth0`, `identity.issuer: https://...`). The framework only cares about the JWT issuer URL.

We rejected Workload Identity Federation (forces SigV4 inbound, mutually exclusive with OAuth, per-customer setup pain), pre-shared API keys (rotation nightmare), and mTLS (AgentCore mTLS undocumented; cert rotation cross-cloud is operationally heavy).

### 3.2 Service discovery (Q12)

**The `cloudless.yaml` `agents` block is the source of truth. Deploy bakes a `cloudless-manifest.json` into every deployed agent.**

At `cloudless deploy`:
1. Each agent deploys, returning its concrete endpoint URLs.
2. CLI generates manifest with `{name, cloud, http_url, a2a_url, idp_issuer, audience, residency}` per agent.
3. Manifest is mounted into each agent's deployment artifact.
4. Optional sync to AWS Agent Registry + GCP Agent Registry for human catalog browsing only — not the runtime source of truth.

Inside agent code:

```python
async def handle_order(ctx):
    response = await ctx.peer("orders").call(task)
    # SDK: looks up 'orders' in embedded manifest → gcp + URL
    # Mints Cognito JWT for orders' audience
    # Sends A2A message/send with Bearer
    # Returns parsed response
```

Manifest-in-repo benefits: versioned, atomic with code changes, no runtime registry SPOF, identical intra/cross-cloud semantics. AWS Agent Registry is still preview; cross-cloud federation isn't standardized — we don't depend on it.

---

## 4. Service catalog

### 4.1 v1 catalog scope (Q9 + Q28 follow-up)

Eight Tier-1 primitives at v1 baseline, plus three pulled in from v1.5:

| Primitive | AWS binding | GCP binding |
|---|---|---|
| **LLM** | Bedrock (Claude/Llama/Nova/etc.) | Gemini Enterprise via `google-genai` SDK |
| **Embeddings** | Bedrock Titan/Cohere | Vertex `text-embedding-005` |
| **Memory** | AgentCore Memory | Memory Bank |
| **Secrets** | Secrets Manager | Secret Manager |
| **Observability** | CloudWatch GenAI Obs (OTel) | Agent Observability (OTel) |
| **A2A** | AgentCore A2A runtime mode (port 9000) | Agent Runtime A2A endpoint |
| **Sandbox** | AgentCore Code Interpreter | Agent Sandbox |
| **Tools/Gateway** | AgentCore Gateway | Agent Gateway |
| **VectorStore** (pulled into v1) | OpenSearch Serverless / S3 Vectors | Vertex Vector Search |
| **Identity vault** (pulled into v1) | AgentCore Identity | Agent Identity |
| **Browser** (pulled into v1) | AgentCore Browser (Playwright) | Agent Sandbox + Computer Use model |

Deferred to v1.5: Threat/Anomaly Detection (GCP-only), Agent Registry sync, advanced eval features.

### 4.2 Memory API (Q14)

**High-level semantic verbs; "strategy" is an internal concept.**

```python
memory = cloudless.Memory(scope="user:{user_id}", retention_days=90)

await memory.add_event(role="user", content="My flight is to Tokyo")
await memory.add_event(role="assistant", content="Got it...")

facts   = await memory.recall_facts(query="travel destinations", top_k=5)
summary = await memory.summarize_session(session_id=ctx.session_id)
prefs   = await memory.get_preferences(user_id=user_id)
episode = await memory.replay_episode(goal="book Tokyo flight")  # warns on GCP
```

Mapping:

| Verb | AWS strategy | GCP impl |
|---|---|---|
| `recall_facts()` | `SEMANTIC` | Memory Bank w/ facts topic filter |
| `summarize_session()` | `SUMMARIZATION` | Memory Bank w/ summary topic |
| `get_preferences()` | `USER_PREFERENCE` | Memory Bank w/ preferences topic |
| `replay_episode()` | `EPISODIC` | Best-effort custom topic; warns at deploy |
| `with_custom_strategy()` | `CUSTOM` w/ prompt override | **Raises at deploy on GCP** |

Scope syntax: `scope="user:{user_id}"` | `scope="session:{session_id}"` | `scope="agent:global"`. Templates resolved from context at runtime.

Retention: 7–365 days (AgentCore hard limit; we use the stricter bound for portability).

### 4.3 Tools API (Q15)

**Multi-source `Tool.from_*()` factory. Everything normalizes to MCP.**

```python
@cloudless.tool
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    ...

weather_api    = cloudless.Tool.from_openapi("https://example.com/openapi.json")
billing_lambda = cloudless.Tool.from_aws_lambda(arn="arn:aws:lambda:...:billing")
inventory_run  = cloudless.Tool.from_gcp_cloud_run(url="https://inventory.run.app")
github_tools   = cloudless.Tool.from_mcp_server(
    url="https://api.githubcopilot.com/mcp/",
    auth=cloudless.OAuth(provider="github", scopes=["repo"]),
)
```

At deploy:
- **AWS**: AgentCore Gateway provisioned with tools as targets; decorated functions deployed as Lambda; agent talks to Gateway via MCP; OAuth creds stored in AgentCore Identity vault.
- **GCP**: Agent Gateway provisioned similarly; decorated functions deployed as Cloud Run services.
- **`cloudless dev`**: tools run as local Python; OpenAPI/Lambda/Cloud-Run proxied or mocked; local MCP stub.

Tool auth: IAM/SA for decorated tools; OAuth creds in Identity vault for external; A2A JWT for peer-as-tool.

### 4.4 Memory Bank ↔ AgentCore Memory impedance

The frameworks have different strategy models. We hide the difference at the verb layer (Q14) and document the few real escapes through:

- `with_custom_strategy()` is AWS-only.
- `replay_episode()` works on both but is best-effort on GCP (warning at deploy time + reduced fidelity).

---

## 5. Developer experience

### 5.1 Configuration model (Q10)

**Decorator (per-agent) + `cloudless.yaml` (project-wide) + environment overlays.**

```python
# src/agents/support.py
@cloudless.agent(name="support", framework="langgraph")
class SupportAgent(cloudless.LangGraphAgent):
    def build(self) -> StateGraph:
        ...
```

```yaml
# cloudless.yaml
project: my-agentic-app
default_cloud: aws
identity:
  type: cognito-auto         # or 'auth0', 'entra', 'cognito-byo'
service_catalog:
  llm:    { provider: bedrock, model: claude-opus-4-7 }
  memory: { strategy: semantic, retention_days: 90 }
environments:
  dev:  { llm: { model: claude-haiku-4-5 } }
  prod: { llm: { model: claude-opus-4-7 } }
```

Decorator owns *what the agent is* (name, framework, behavior); YAML owns *what surrounds it* (cloud, model, environment, observability sink). Switching dev→prod is a YAML edit, no code change.

### 5.2 Language support (Q11)

**Python-only at v1. TypeScript first-class in v2.**

- Python is deepest for every framework.
- AgentCore direct-code deploy is Python-only.
- Memory Bank ↔ LangGraph bridge is Python-only.
- TS users can deploy via the container path with no SDK help until v2.

### 5.3 Local development (Q13)

**`cloudless dev` — local subprocess per agent, real LLM calls, mocked everything else by default, local Jaeger, hot reload.**

```bash
cloudless dev support orders pricing
# support  → http://localhost:8081  a2a://localhost:9081
# orders   → a2a://localhost:9082
# pricing  → a2a://localhost:9083
# Traces:    http://localhost:16686
# Hot reload watching src/
```

Default mocking matrix:

| Service | Default in `cloudless dev` |
|---|---|
| LLM | Real Bedrock / Gemini (realism for prompt iteration) |
| Memory | In-memory dict |
| Secrets | Local `.cloudless/dev-secrets.yaml` (gitignored) |
| A2A peers | Local subprocess; manifest URLs rewritten to localhost |
| Sandbox | Local subprocess with security warning |
| Tools | Configurable: real pass-through OR mock JSON |
| Observability | Local Jaeger container + OTLP |
| Identity | Local mock IdP issuing valid JWTs |

Flags: `--use-real memory,sandbox`, `--offline` (mock LLM too), `--record` / `--replay` (cassette real LLM responses for deterministic CI).

### 5.4 Streaming abstraction (Q16)

**Async generator returning typed `Chunk` subclasses.**

```python
async def query(self, ctx, prompt: str) -> AsyncIterator[cloudless.Chunk]:
    async for event in self.graph.astream_events(...):
        ...
        yield cloudless.TextChunk(text=chunk.content)
        yield cloudless.ToolCallChunk(name=tool, args=args)
        yield cloudless.ReasoningChunk(text=think_text)
        yield cloudless.FinalChunk(state=final)
```

Chunk taxonomy: `TextChunk`, `ToolCallChunk`, `ToolResultChunk`, `ReasoningChunk`, `StateChunk`, `FinalChunk`, `ErrorChunk`. Adapter maps to SSE (AgentCore), `stream_query()` (GCP), or WebSocket per protocol.

### 5.5 Project layout (Q24)

**Convention-based `src/` layout. `cloudless init` scaffolds.**

```
my-app/
  cloudless.yaml
  pyproject.toml
  src/
    agents/         # @cloudless.agent decorated classes
    tasks/          # @cloudless.task long-running flows
    tools/          # @cloudless.tool functions + *.openapi.yaml specs
    policies/       # @cloudless.policy decorated functions
  evals/
    datasets/       # JSONL / Parquet
    judges/         # custom LLM-as-judge
    suites/         # suite definitions for CI gates
  tests/
  .cloudless/       # dev-secrets.yaml, cache/ — gitignored
```

CLI walks these directories and auto-registers decorated symbols. OpenAPI YAMLs under `src/tools/` are auto-registered as `Tool.from_openapi()` sources.

### 5.6 Testing (Q25)

**`cloudless.testing` pytest fixtures + cassette LLM replay + A2A contract tests.**

```python
import pytest
from cloudless.testing import agent_fixture, peer_mock, llm_cassette

@pytest.mark.asyncio
async def test_support_handles_greeting(support_agent):
    async with llm_cassette("greeting.cassette"):
        chunks = [c async for c in support_agent.query(prompt="hi")]
        assert any(isinstance(c, cloudless.TextChunk) for c in chunks)

def test_a2a_contract():
    cloudless.testing.assert_peer_contract(caller="support", peer="orders")
```

Fixtures: `agent_fixture(name)`, `peer_mock(name)`, `tool_mock(name)`, `memory_fixture()`, `policy_under_test(fn)`, `llm_cassette(name)`, `dev_topology(*agents)`.

Cassettes: first run records real LLM; subsequent runs replay; `pytest --record` re-records with safety gate. Commit cassettes alongside code. Diff = prompt change impact review.

Contract tests: manifest schema cross-checked at `cloudless test peers`. CI gate: `--strict` exits non-zero on mismatch.

### 5.7 Migration path (Q26)

**Three-phase gradual migration. `cloudless migrate scan/wrap/check` tooling.**

- **Phase 1 (1 day)**: 5-line decorator wrap of existing LangGraph/Strands/ADK code. Get deploy, OTel, cost telemetry, A2A routing, versioning. Existing LLM/memory/tool clients unchanged.
- **Phase 2 (per-primitive)**: Replace third-party clients with cloudless primitives one at a time.
- **Phase 3 (weeks)**: Adopt `cloudless.task`, `@cloudless.policy`, contract tests, eval suites.

Framework adapters ship from us:
- `cloudless.LangGraphAgent`
- `cloudless.StrandsAgent`
- `cloudless.ADKAgent`
- `cloudless.MAFAgent` (v3)

Translation helpers: `cloudless.translate_langgraph_event(event)` → typed Chunk; same for Strands and ADK.

CLI: `cloudless migrate scan` (analyzes repo), `cloudless migrate wrap path/to/agent.py --framework langgraph` (adds boilerplate), `cloudless migrate check` (validates wrapping).

---

## 6. Operations

### 6.1 Long-running tasks + HITL (Q17)

**v1 includes `@cloudless.task` decorator with checkpoints + `ctx.request_approval()` for HITL. Webhook + polling + Slack delivery. Hosted approval inbox UI deferred to v1.5 commercial.**

```python
@cloudless.task(name="deep-research", max_duration="24h", checkpoint_interval="5m")
async def deep_research(ctx, input):
    yield cloudless.TextChunk(text=f"Researching {input['topic']}")
    sources = await find_sources(input['topic'])
    await ctx.checkpoint({"phase": "sources", "sources": sources})

    approval = await ctx.request_approval(
        prompt=f"Proceed with {len(sources)} sources?",
        timeout="1h",
        deliver_via=["webhook", "slack"],
    )
    if not approval.approved:
        yield cloudless.FinalChunk(state={"status": "rejected"})
        return
    ...
    yield cloudless.FinalChunk(state={"summaries": summaries})
```

Runtime mapping:
- **AWS**: AgentCore Runtime async mode with `HealthyBusy` pings (up to 8 hours); >8h tasks save to Memory and resume in new microVMs.
- **GCP**: Gemini Enterprise Agent Runtime native multi-day execution.
- **`cloudless dev`**: local subprocess + SQLite checkpoints; CLI-prompt approvals.

Checkpoints are idempotent; task resumes from last checkpoint on restart with the same `task_id`.

### 6.2 Versioning, rollback, traffic splitting (Q18)

**Auto-version per deploy + named endpoint aliases + percentage traffic splitting.**

```bash
cloudless deploy support                           # creates v17, updates 'default' alias
cloudless deploy support --endpoint canary         # creates v18, updates 'canary' alias
cloudless promote support --from canary --to default
cloudless rollback support --to v16
cloudless traffic-split support --default 90% --canary 10%
cloudless versions support                         # list versions and aliases
```

- Versions are immutable; aliases are mutable pointers.
- Per-environment alias mapping in `cloudless.yaml` (dev→default, staging→staging, prod→prod).
- A2A manifest references aliases, not versions — promoting a new version updates routing instantly without manifest redeploy.
- Rollback is an alias swap; sub-second.
- Traffic splitting on AWS implemented via two endpoints + SDK dispatcher (AgentCore endpoints don't natively support weighted routing as of May 2026); on GCP via native revision splitting. Identical user experience.

### 6.3 Governance, guardrails, policy (Q19)

**Two-layer: cloud-native guardrails + Python `@cloudless.policy` decorator.**

Layer 1 — cloud-native (unified config in `cloudless.yaml`):

```yaml
service_catalog:
  guardrails:
    input:
      prompt_injection: { action: block }
      pii: { detect: [ssn, credit_card, email], action: redact }
      jailbreak: { action: block }
      topics_denied: ["competitor pricing", "legal advice"]
    output:
      pii: { action: redact }
      hallucination_check: { threshold: 0.7, action: flag_trace }
      groundedness: { enabled: true, knowledge_source: my-vector-store }
    tool_calls:
      allow: [weather, calendar, search]
      deny: [shell, file_write, send_email]
```

Maps to Bedrock Guardrails (AWS) / Model Armor (GCP).

Layer 2 — Python policies (portable business rules):

```python
@cloudless.policy(applies_to=["support", "research"], stage="before_tool_call")
async def restrict_shell(ctx, tool_call) -> cloudless.PolicyResult:
    if tool_call.name == "shell" and ctx.user.role != "admin":
        return cloudless.Deny("Shell access requires admin role")
    return cloudless.Allow()

@cloudless.policy(applies_to="*", stage="before_invoke")
async def cost_cap(ctx):
    if await ctx.cost.session_total_usd() > 5:
        return cloudless.Deny("Session cost cap exceeded")
    return cloudless.Allow()
```

Six stage hooks: `before_invoke`, `before_llm_call`, `before_tool_call`, `after_tool_call`, `after_llm_call`, `after_invoke`. Maps cleanly to AgentCore Hooks and Agent Gateway interceptors.

### 6.4 Cost telemetry and attribution (Q20)

**Full stack: per-invocation tracking + A2A attribution propagation + caps + CLI report + default dashboards.**

```python
@cloudless.agent(name="support")
class SupportAgent(...):
    async def query(self, ctx, prompt):
        if await ctx.cost.session_total_usd() > 5:
            yield cloudless.ErrorChunk(error="cost_cap_exceeded")
            return
        ctx.cost.attribute(team=ctx.user.team, project="onboarding")
        ...
```

Dimensions tracked as OTel span attributes: `cost.llm.{input,output,cached,reasoning}_tokens`, sandbox vCPU/GB-seconds, browser session minutes, memory events, tool invocations, A2A peer call cost (attributed to originator via header).

CLI:
```bash
cloudless cost report --since 7d --group-by agent,env
cloudless cost top-sessions --since 24h --limit 10
cloudless cost forecast --based-on 30d
cloudless cost budget set --agent support --monthly 500 --alert-at 80%
```

Cost ledger piggybacks on the OTel pipeline — no separate cost database.

Default Grafana / CloudWatch dashboard JSON shipped; install via `cloudless dashboards install`.

### 6.5 Resilience: retries, timeouts, circuit breakers (Q21)

**Per-service-class config + typed exception hierarchy. Fallbacks deferred to v1.5.**

```yaml
service_catalog:
  llm:
    timeout: 30s
    retry: { attempts: 3, backoff: exponential, jitter: true }
    circuit_breaker: { errors: 5, window: 60s, cooldown: 30s }
  memory:
    timeout: 5s
    retry: { attempts: 3, backoff: linear }
    on_failure: continue        # don't kill agent on memory write failure
  sandbox:
    timeout: 60s
    retry: { attempts: 1 }       # not idempotent
    on_failure: error
  a2a_peer:
    timeout: 60s
    retry: { attempts: 3, backoff: exponential, jitter: true }
    circuit_breaker: { errors: 3, window: 30s, cooldown: 60s }
```

Typed exception hierarchy:
```
cloudless.CloudlessError
├── cloudless.TransientError              # safe to retry
│   ├── TimeoutError
│   ├── ThrottledError
│   └── PeerUnreachable
├── cloudless.PermanentError              # do NOT retry
│   ├── PolicyViolation
│   ├── GuardrailBlocked
│   ├── AuthenticationError
│   └── InvalidInputError
└── cloudless.CostCapExceeded
```

Each has `recoverable: bool` and `retry_after: Optional[float]`.

Retries are tracked in cost telemetry. Circuit-breaker state observable as OTel gauge metric.

`on_failure: continue` for non-critical writes (memory, observability) → warning span emitted but flow continues; user can override per call.

**Fallback chains (`fallback: {model: claude-haiku}`) and degraded modes** deferred to v1.5. v1 covers retries + timeouts + breakers.

---

## 7. Quality: evals + observability (Q8)

**Own portable offline eval framework + OTel-everywhere online observability, linked by `run.id`.**

### 7.1 Offline evals

```bash
cloudless eval run dataset.yaml --against agent=support
cloudless eval diff v1 v2                # regression detection
cloudless eval gate --baseline v1 --tolerance 5%   # CI gate
```

- Datasets in YAML/JSONL committed to git; large binaries in object storage.
- Versioning via dataset hash, not git branch.
- Pluggable metrics: deterministic (regex/JSON-schema/golden match), LLM-as-judge (Claude/Gemini swap-in), embedding similarity, custom Python, RAGAS-style.
- Results as Parquet in `s3://cloudless-evals/` or `gs://cloudless-evals/`.
- Optional push to AgentCore Evaluations / Vertex Eval Service for native dashboards — source of truth remains portable.

### 7.2 Online observability

- Auto-instrument all agents with OTel spans following GenAI semantic conventions.
- Required attributes: `agent.name`, `agent.version`, `agent.framework`, `run.id`, `session.id`, `peer.cloud`, `cost.usd_estimate`.
- Default sinks: CloudWatch GenAI Obs (AWS), Cloud Logging + Agent Observability (GCP).
- Optional dual-write via OTLP to Langfuse, Arize Phoenix, Datadog, Honeycomb, Braintrust.

### 7.3 Online evals as judge-on-trace

- Sample N% of production traces (configurable per agent), replay through an LLM-judge, write scores back as span attributes.
- Surfaced as time-series in the same sink.

### 7.4 SLOs

`cloudless.yaml` SLO config (p95 latency, error rate, cost/session, eval-score threshold) → SDK emits alerts on breach.

### 7.5 The glue: `run.id`

Every offline eval result and every online trace carries the same `run.id` schema. Click from failed eval → trace that produced it, regardless of cloud. **This is the production-grade differentiator.**

---

## 8. Distribution and versioning

### 8.1 Commercial model (Q22)

**Apache 2.0 open-core + commercial enterprise layer.**

- **Open core (Apache 2.0)**: SDK, framework adapters, embedded runtime lib, CLI, basic cost telemetry, portable eval framework, all 11 primitives, governance + policy decorators, local dev runner.
- **Commercial enterprise**: hosted approval inbox UI, advanced eval (multi-judge consensus, regression-detection ML, golden-dataset management UI), enterprise SSO with arbitrary IdPs, on-prem control plane, audit-log delivery to SIEM, compliance kits (SOC2/HIPAA/FedRAMP guides + Terraform modules), dedicated support + SLA.

Precedents: HashiCorp Terraform / Vault, Sentry, GitLab, Mattermost.

### 8.2 Framework versioning policy (Q27)

**Strict semver + 6-month deprecation + compatibility matrix + LTS on even MAJORs.**

- **MAJOR** — breaking `cloudless.*` API change.
- **MINOR** — additive features.
- **PATCH** — bug/perf fixes.
- Deprecation: `DeprecationWarning` for ≥6 months before removal; removal in next MAJOR.
- `cloudless lint` flags deprecated API usage in CI with file:line references.
- LTS: even-numbered MAJORs (1.0, 2.0, 4.0…) get 18 months of security patches after next MAJOR ships; odd MAJORs (3.0, 5.0…) get 6 months.
- Pre-1.0 (v0.x): MINOR may break, Python ecosystem norm. We commit to 1.0 only after ≥2 customer prod deployments + 2-month real-world burn-in.

### 8.3 Dependency strategy

| Dep type | Strategy |
|---|---|
| Framework SDKs (`langgraph`, `strands-agents`, `google-adk`, `agent-framework`) | Loose lower bound; published tested matrix |
| Cloud SDKs (`boto3`, `google-cloud-aiplatform`, `google-genai`) | Pinned compatible range (`~=1.40`) |
| AgentCore SDK (`bedrock-agentcore`) | Pinned exact range until API stabilizes |
| A2A SDK (`a2a-sdk`) | Pinned to known-working per cloudless release |

Compatibility matrix published in docs; CI tests combinations weekly.

### 8.4 Naming and positioning (Q29)

**Naming deferred** until v1.0 (real branding exercise). `cloudless` is the working code name until then.

**Positioning tagline**: *"Write your agent once. Ship it to any cloud."*

This shapes docs voice and feature framing. We honestly caveat in docs that framework choice still matters per cloud at v1, but the deployment + service catalog + cross-cloud A2A story is genuinely "write once."

---

---

## 9. Project & ecosystem conventions

### 9.1 CLI command catalog (Q30)

Eight groups, ~30 commands. Common flags: `--env`, `--json`, `--watch`/`--follow`, `CLOUDLESS_PROJECT_DIR` override. Auth via local `aws`/`gcloud` CLI credentials — cloudless never asks for cloud secrets directly.

**Lifecycle:** `init`, `dev`, `deploy`, `rollback`, `promote`, `traffic-split`, `versions`, `logs`, `agents`.
**Config & infra:** `config show/set`, `secrets set/get/list`, `manifest show`, `dashboards install`.
**Testing & quality:** `test`, `test peers --strict`, `eval run/diff/gate`, `eval datasets list`.
**Cost & ops:** `cost report/top-sessions/forecast`, `cost budget set/list`.
**Migration & introspection:** `migrate scan/wrap/check`, `lint`, `doctor`.
**Long-running:** `tasks list/show`, `tasks approvals pending`, `tasks approve/reject/cancel`.
**Identity:** `identity show/rotate-secret/grant`.
**Meta:** `version`, `help`, `upgrade-check`.

Deliberately *not* in v1 surface: `cloudless plan` (AgentCore lacks reliable dry-run); `cloudless workspace` (v2); `cloudless studio` web UI (v1.5 commercial); `cloudless registry sync` (folded into `deploy --sync-registries` flag).

### 9.2 Documentation strategy (Q31)

- **Information architecture:** Diátaxis (tutorials / how-tos / reference / explanation).
- **Toolchain:** Mintlify primary (fast, polished, free for OSS); Docusaurus as escape hatch if we outgrow it. Content is portable Markdown.
- **API reference:** auto-generated from Python source + CLI docstrings + JSON Schema for `cloudless.yaml`. CI fails on docs drift.
- **Six v1 tutorials (one per milestone-aligned use case):** *Hello, cloudless* / *Your first cross-cloud agent pair* / *Long-running research agent with HITL* / *Migrating an existing Strands agent* / *Cost-capped customer support agent* / *Production deploy with eval gate*.
- **Versioning:** `latest` = main; pinned `v0.x`, `v1.0`, etc. snapshots. Compatibility matrix (Q27) updates weekly in docs via CI.
- **Translations:** English at v1.0; Japanese/Chinese mid-priority v1.5.
- **Domain:** TBD on Q29 naming. Mintlify handles brand changes cleanly.

### 9.3 Telemetry (Q32a)

**Anonymous, opt-out, transparent, off in detected CI.**

- Default opt-out; banner on first run; enable via `cloudless config set telemetry.enabled true` or `CLOUDLESS_TELEMETRY=1`.
- Auto-disabled when `CI=true`, GitHub Actions, GitLab CI, etc.
- **Collected fields** (registry in `docs/telemetry.md`): CLI command names + flags (not values), framework choice, cloud choice, OS, Python version, cloudless version, anonymous machine UUID.
- **Never collected:** agent code, prompts, model outputs, secrets, cloud account IDs.
- **Backend:** PostHog or Plausible. No Google Analytics.
- New fields require a PR that updates the registry. Auditable.

### 9.4 Governance (Q32b)

**Lightweight at v0.x; formalize pre-v1.0.**

- **v0.x:** small core-team review of PRs; informal proposals via GitHub issues + Discord/Slack.
- **Pre-v1.0:**
  - `MAINTAINERS.md` with Core / Adapters / Docs / Security roles.
  - RFC process for breaking changes and new top-level primitives; 14-day comment window; lazy-consensus accept; template in `.github/RFC_TEMPLATE.md`.
  - **Contributor License Agreement (CLA)** via CLA Assistant — preserves flexibility for future relicense / LF AI donation.
  - **Code of Conduct:** Contributor Covenant 2.1.
  - **Public roadmap:** GitHub Project board mirroring `docs/ROADMAP.md`.
  - **Security disclosure policy:** `SECURITY.md`; ≤72-hour acknowledgment; coordinated disclosure for high-severity; CVE issuance via GitHub Security Advisories.
- **Post-v1.0:** consider Linux Foundation hosting if enterprise adoption demands neutral governance.

### 9.5 Security posture and supply chain (Q33)

**Documented threat model + strict supply-chain hygiene + pre-v1.0 third-party audit + Sigstore-signed releases.**

**Threat model (full table in `docs/SECURITY.md` pre-v1.0):**
- User agent code, `cloudless.yaml`, and `Tool.from_aws_lambda`/`from_gcp_cloud_run` targets: **trusted** (user's own code in user's account).
- Embedded runtime lib: trusted by user but **our responsibility** — signed releases.
- A2A peers: trusted only if Cognito JWT validates AND peer is in manifest allowlist.
- `Tool.from_mcp_server(url=...)`: **untrusted** — schema validated, policies enforced.
- LLM output: **untrusted** — prompt injection real; mitigated by cloud-native guardrails before tool calls / external sends.
- Generated container image: reproducible from source + lockfile + pinned base; Sigstore-signed.

**Supply-chain hygiene must-haves pre-v1.0:**
- Reproducible builds via committed `uv.lock`; CI binary-diff check.
- CycloneDX SBOM per release; published as release asset.
- PyPI Trusted Publishers from GitHub Actions; releases signed with Sigstore (`cosign`-verifiable).
- Container images to GHCR with `cosign sign` + SLSA Level 3 provenance via GitHub OIDC.
- Dependabot + Renovate + `pip-audit` in CI.
- License compliance enforced via `pip-licenses` CI check.
- Secret scanning (GitHub native + `detect-secrets` pre-commit).
- `cloudless doctor` warns on outdated cloudless versions with known CVEs.
- `cloudless iam scaffold` emits minimum-permission CloudFormation/Terraform for the execution role.

**Pre-v1.0 third-party audit:** Trail of Bits / NCC Group (or equivalent). Scope: cross-cloud auth flow, embedded runtime, manifest baking + peer routing, secret resolution, policy bypass surface, supply chain. Public report alongside v1.0.

**Cadence post-v1.0:** annual third-party audit; quarterly internal review.

**Explicit non-protections** (documented):
- Malicious agent code running in the user's own account.
- Compromised cloud credentials.
- Poisoned OpenAPI specs / rogue MCP servers (without user policies).

### 9.6 Performance targets (Q34)

**Published targets + continuous benchmarking + no OSS-tier SLA** (SLA is commercial-tier upsell).

| Metric | Target |
|---|---|
| Cold start (first invoke after idle) | p95 < 2.5s |
| Warm-invocation cloudless overhead | p95 < 50ms |
| Deploy time (`cloudless deploy`) | p50 < 60s, p95 < 180s |
| Manifest update / alias swap (rollback) | p95 < 5s |
| A2A cross-cloud peer call (round-trip overhead) | p95 < 200ms |
| `cloudless dev` startup (3-agent topology) | p95 < 10s |
| `cloudless eval run` per-record overhead | p95 < 100ms |
| Memory `recall_facts(top_k=5)` | p95 < 250ms |
| Tool invocation via Gateway (warm) | p95 < 150ms |

- Public weekly dashboard at `docs/perf` (subdomain post-naming).
- Benchmarks run against all 3 v1 framework × cloud combos on both clouds.
- Regression alert: >20% week-over-week p95 degradation fails CI and emits an issue.
- Targets are design anchors, not PR gates; revising a target requires a public RFC.

### 9.7 Starter templates (Q36)

Six canonical templates ship in-tree at v1; community templates via `cloudless init --template github:user/repo`.

| Template | Demonstrates | Framework | Clouds |
|---|---|---|---|
| `hello` (default) | Bare-minimum LangGraph echo agent | LangGraph | AWS or GCP |
| `chat-memory` | Multi-turn chat + semantic memory | LangGraph | AWS or GCP |
| `rag` | Document Q&A with VectorStore | LangGraph | AWS or GCP |
| `multi-agent` | Supervisor + 2 workers across 3 frameworks + 2 clouds | LangGraph + Strands + ADK | Both |
| `research-task` | Long-running `@cloudless.task` + HITL via Slack | LangGraph | AWS (showcases 8h async) |
| `ops-bot` | Strands with tools + cost-cap policy + Bedrock Guardrails | Strands | AWS |

Each template ships: agent source, `cloudless.yaml`, tools/policies as relevant, eval dataset (5-10 cases), `cloudless.testing` tests, README, `.cloudless/dev-secrets.yaml.example`.

**Template CI:** every template goes through `init → deploy → test → eval` in real cloud accounts weekly. Broken template = release blocker.

### 9.8 CI/CD for the cloudless project itself (Q38)

**Trunk-based + release-please + multiple release channels + Sigstore-signed everything.**

**Branching:**
- `main` is always shippable; no long-lived dev branch.
- Feature branches off `main`; squash-merge with Conventional Commit messages.
- `release/v1.x` maintenance branches for LTS patch backports (per Q27 LTS-on-even-MAJORs).

**Release automation:**
- **release-please** maintains an open release PR with auto-generated changelog and version bumps.
- Conventional Commits drive versioning: `feat!:` → MAJOR; `feat:` → MINOR; `fix:`/`perf:` → PATCH.
- Merging the release PR triggers PyPI publish via Trusted Publishers and `cosign sign`.

**Release channels (PyPI):**
- `cloudless` — stable (tagged releases only).
- `cloudless==X.Y.ZaN` — alpha (may break).
- `cloudless==X.Y.ZbN` — beta (feature-complete).
- `cloudless==X.Y.ZrcN` — release candidate.
- `cloudless-nightly` (separate package) — auto-built from `main` every 24h.

**PR checks (every PR):**
- Lint (ruff) + type-check (mypy/pyright).
- Unit tests (mocked services).
- **Core-path integration tests** (Q37 OQ10): each framework × each cloud × {LLM, Memory, A2A} = 18 cells, ~9 min.
- Docs build succeeds.
- Telemetry registry diff check (new fields require explicit doc PR).
- `pip-licenses` + `pip-audit`.
- `cosign verify` round-trip on candidate build.

**Nightly checks:**
- Full integration matrix (66 cells). Failures file GitHub issues.
- Continuous benchmark (Q34) against real AWS + GCP test accounts.
- Template smoke (Q36): each of 6 templates `init → deploy → test → eval`.
- Cross-cloud A2A E2E loop test.

**Pre-release checks** before any stable release:
- All nightly checks + manual maintainer approval.
- Threat-model spot checks (Q33).
- Sigstore signature verification.
- SBOM published as release asset.
- Compatibility matrix (Q27) refreshed.

**Cloud test accounts:**
- Dedicated AWS + GCP accounts isolated from dev/prod.
- Budget caps with auto-pause alarms.
- `cloudless-test:*` resource naming for cleanup.
- Post-CI cleanup; nightly GC for orphans.

**Conventions:**
- ≥1 maintainer review on every PR.
- Squash-merge only; PR title becomes commit message.
- CLA (Q32) not DCO.
- `docs/` changes use `chore(docs):` prefix; don't bump release-please version.

### 9.9 Logging conventions (Q39)

**Structured JSON via `structlog` + OTel context propagation + auto-redact + per-component levels.**

**Output:**
- Cloud/production: JSON Lines, one log per line.
- Local/CLI: pretty-printed with colors via `rich`; same content, different rendering.
- `--json` flag on any CLI forces JSON regardless of TTY.

**Levels:** `TRACE` (off by default) / `DEBUG` (dev) / `INFO` (lifecycle, default-on) / `WARNING` (recoverable) / `ERROR` (operation failed) / `CRITICAL` (unrecoverable).

**Required fields on every log line** (auto-injected by cloudless logger):
- `timestamp`, `level`, `logger`, `message`
- `agent.name`, `agent.version`, `agent.framework`
- `cloud`, `region`
- `run.id`, `session.id`, `trace.id`, `span.id`

`trace.id` / `span.id` come from active OTel context — logs and traces share IDs (click from trace to logs in CloudWatch GenAI Obs / Cloud Logging). Matches the `run.id` glue from Q8 (traces ↔ evals); together they form the full observability spine: logs ↔ traces ↔ evals.

**Auto-redaction** (SDK-level, best-effort):
- Built-in patterns: Bearer tokens, AWS access/secret keys, GCP SA JSON, Cognito JWTs, common provider API keys (`sk-`, `xoxb-`, `gh[pousr]_`).
- Replaced with `<REDACTED:<class>>`.
- User-extensible via `cloudless.yaml`:
  ```yaml
  logging:
    redact_patterns:
      - regex: "ssn=\\d{3}-\\d{2}-\\d{4}"
        replacement: "<REDACTED:ssn>"
  ```
- **Not** a security guarantee; documented in `docs/SECURITY.md`. Tell users not to log sensitive data in the first place.

**Per-component log levels** in `cloudless.yaml`:

```yaml
logging:
  default_level: INFO
  levels:
    cloudless.runtime.peer: DEBUG
    cloudless.memory: WARNING
    cloudless.policy: DEBUG
    langgraph: WARNING                # silence third-party noise
```

Most-specific-prefix-wins lookup, matching Python's `logging.getLogger(name)` namespace convention.

**`cloudless logs` CLI:**
- Streams from CloudWatch Logs / Cloud Logging.
- `--level <LEVEL>`, `--since 1h`, `--follow`, `--grep <pattern>`.
- Pretty by default in a TTY; JSON via `--json`.

**Library:** `structlog` for internal logging with a thin stdlib-compatible wrapper so `logging.getLogger(__name__)` still works for contributors who prefer it.

### 9.10 Open-question defaults (Q37)

The smaller open questions surfaced during design were settled with the following defaults:

| # | Question | Default |
|---|---|---|
| OQ1 | Cognito feature tier | Standard tier with M2M App Clients (with secret) |
| OQ2 | Per-agent OTel sampling rate | 100% dev, 10% prod, adaptive auto-degrade to 1% under throttle |
| OQ3 | Manifest update propagation | Bake-time manifest + 5-min TTL refresh from known cloud-storage URL; fallback to embedded copy |
| OQ4 | Bedrock / Gemini model deprecations | Model-alias resolution table maintained in cloudless; warnings via `cloudless lint`; refreshed on `upgrade-check` |
| OQ5 | AgentCore Memory custom-strategy 30 KB cap | `with_custom_strategy()` validates at construction with clear error |
| OQ6 | GCP cold-start under multi-day resume | Benchmark in M4 as part of continuous suite; feature-gate the path |
| OQ7 | Slack OAuth approval app | Ship `cloudless/slack-approval-app` GitHub template; install in customer Slack workspace |
| OQ8 | Cost dashboard cross-cloud unification | Grafana 11+ mixed data sources (CloudWatch + Cloud Logging plugins); ship dashboard JSON via `dashboards install` |
| OQ9 | Manifest signing (A2A v1.2 signed cards) | Defer to v1.5; when shipped, use Sigstore keyless (same toolchain as release signing) |
| OQ10 | Test coverage SLA | Core path on every PR (each framework × each cloud × LLM+Memory+A2A = 18 cells, ~9 min); full matrix (66 cells) nightly |

---

## 10. Extensibility model

### 10.1 Plugin architecture (Q35)

**Python entry points + `typing.Protocol` contracts per extension point + first-party adapters ship in-tree.**

**Extension points** (each a documented `Protocol` in `cloudless/protocols.py`):

| Protocol | Purpose | First-party implementations |
|---|---|---|
| `FrameworkAdapter` | Wrap an agent framework into the runner contract | LangGraph, Strands, ADK at v1; MAF at v3 |
| `CloudAdapter` | Build artifact, deploy, resolve secrets per cloud | AWS, GCP at v1; Azure as community plugin later |
| `MemoryBackend` | Implement `add_event` / `recall_facts` / `summarize_session` / etc. | AgentCore Memory, Memory Bank |
| `EvalJudge` | Score (input, output, reference) | LLM judges (Claude / Gemini), deterministic, embedding similarity |
| `HitlChannel` | Deliver approval requests, listen for responses | Webhook, polling, Slack at v1; Discord, Teams as community plugins |
| `ToolSource` | Discover tools, invoke them | Decorator, OpenAPI, AWS Lambda, GCP Cloud Run, MCP server |

**Discovery:** Python entry points in plugin packages' `pyproject.toml`:

```toml
[project.entry-points."cloudless.frameworks"]
maf = "cloudless_maf:MAFAdapter"

[project.entry-points."cloudless.clouds"]
azure = "cloudless_azure:AzureFoundryAdapter"
```

Runtime enumerates installed plugins at startup, validates Protocol conformance, registers by declared name. `cloudless plugins list` shows installed; `cloudless plugins doctor` runs conformance checks.

**Repo strategy:**
- **In-tree:** first-party adapters (LangGraph/Strands/ADK frameworks, AWS/GCP clouds, all v1 service catalog primitives, built-in judges, webhook/poll/Slack HITL).
- **Out-of-tree, first-party-blessed** (separate packages in `cloudless` GitHub org): MAF (v3), Azure (v2.x), experimental adapters.
- **Community:** any user-published package implementing a Protocol gets auto-discovered.

**Protocol versioning:**
- Protocol changes are *always* a cloudless MAJOR (Q27 semver).
- Plugins declare `cloudless>=1.0,<2.0` in their `pyproject.toml`.

**Why entry points (vs subclass-and-register):** standard Python pattern (pytest, click, pre-commit, mkdocs); no import-time side effects; works with all packaging tools.

**Why `typing.Protocol` (vs ABCs):** structural typing matches duck-typing intuition; no multiple-inheritance gotchas; IDE autocomplete preserved; adapters don't inherit from a cloudless base class.

**What we deliberately do NOT support at v1:**
- Runtime plugin loading from arbitrary URLs or paths — installation goes through package managers only.
- Plugin sandboxing — same trust model as any pip install.
- Plugin marketplace UI — v2+ commercial-tier concern.

---

## Appendix A: Locked decisions (Q1-Q39)

See [`./DECISIONS.md`](./DECISIONS.md) for a concise ADR-style log.

## Appendix B: Roadmap

See [`./ROADMAP.md`](./ROADMAP.md).

## Appendix C: Risks and open questions

See [`./RISKS.md`](./RISKS.md).

## Appendix D: Research dossiers

See [`./research/`](./research/) for the five comprehensive research reports that informed these decisions:
1. AgentCore Runtime deep dive
2. AgentCore primitives (Memory, Identity, Gateway, Code Interpreter, Browser, Observability)
3. AgentCore + A2A protocol + framework integrations
4. AgentCore vs. Vertex AI Agent Engine comparison
5. Gemini Enterprise Agent Platform rebrand (May 2026)
