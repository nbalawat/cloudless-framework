# Research: AWS Bedrock AgentCore vs. GCP Vertex AI Agent Engine

> Captured 2026-05-14. Side-by-side comparison for cross-cloud abstraction design.
> Note: Vertex AI Agent Engine was rebranded to **Gemini Enterprise Agent Runtime** at Google Cloud Next '26 (April 22, 2026). See `05-gemini-enterprise-rebrand.md` for the rebrand details. This document uses the historical "Vertex AI Agent Engine" name for clarity.

## Comparison summary table

| Dimension | AWS Bedrock AgentCore | GCP Vertex AI Agent Engine (now Gemini Enterprise Agent Runtime) |
|---|---|---|
| Announcement | Preview Jul 16 2025 | Reasoning Engine 2024; renamed Mar 2025; renamed again Apr 2026 |
| GA | Oct 13 2025 | GA mid-2024 (as Reasoning Engine) |
| Regions (May 2026) | ~15 | ~10+ |
| Deployment unit | Container image (ECR, 2 GB) or direct code zip (250 MB) | Python `AgentEngine` object pickled and uploaded by SDK |
| Runtime contract | HTTP `/invocations`+`/ping` on 8080 (or MCP/A2A/AG-UI on other ports) | Python class with `set_up()`, `query()`, `stream_query()` |
| Isolation | Firecracker microVM per session | gVisor / Cloud Run-style managed container |
| Max session duration | 8 h; 15-min idle; 15-min sync timeout | ~10 min connection lifetime; longer via session resumption; **multi-day in Gemini Enterprise** |
| Max payload | 100 MB request/response | ~10–20 MB |
| Hardware/session | 2 vCPU / 8 GB max | Configurable; sub-second autoscaling |
| Concurrency | 1,000 active sessions/account (us-east-1, us-west-2); 500 elsewhere | `container_concurrency` configurable; default 1 req/instance |
| CPU pricing | $0.0895/vCPU-hr (no charge for I/O wait) | $0.0864/vCPU-hr |
| Memory pricing | $0.00945/GB-hr | $0.0090/GB-hr |
| Free tier | None | 50 vCPU-h + 100 GB-h / month |
| Framework support | Strands (1st), LangGraph, LangChain, CrewAI, ADK, OpenAI Agents, Claude Agents, custom | ADK (1st), LangGraph, LangChain, LlamaIndex, AG2/Autogen, custom |
| Memory | AgentCore Memory: 5 strategies (Semantic/Summary/User-pref/Episodic/Custom) | Memory Bank: Gemini-async extraction; topic-scoped; user-scoped |
| Identity broker | AgentCore Identity: token vault + workload identity + OAuth flows | IAM + ADC; **Agent Identity** added at Cloud Next '26 |
| Tools/MCP | AgentCore Gateway: zero-code Lambda/OpenAPI/Smithy → MCP | ADK supports MCP; MCP Toolbox for Databases; **Agent Gateway** at Cloud Next '26 |
| Code sandbox | AgentCore Code Interpreter | Code Execution (preview); GenAI SDK `ToolCodeExecution()`; **Agent Sandbox** at Cloud Next '26 |
| Browser tool | AgentCore Browser (Playwright; 1 vCPU/4 GB; profiles, proxies, live view) | **Agent Sandbox + Computer Use model** at Cloud Next '26 (different shape) |
| Observability | OTel/ADOT → CloudWatch GenAI Observability + X-Ray | OTel → Cloud Trace + Cloud Logging + **Agent Observability** at Cloud Next '26 |
| A2A protocol | Native runtime protocol mode (JSON-RPC on port 9000) | Native via ADK (Google authored A2A) |
| AG-UI | Supported as protocol | Not natively |
| Long-running | 8 hours max | **Multi-day** as of Cloud Next '26 |

---

## Detailed differences

### Deployment model

**AgentCore** — *container-first*. Build Docker image, push to ECR, call `CreateAgentRuntime`. The container must expose port 8080 with `/invocations` + `/ping`. Wrappers like `BedrockAgentCoreApp` simplify this.

**Vertex Agent Engine** — *Python-object-first*. Author Python class with `set_up()`, `query()`, `stream_query()`. SDK pickles object, captures `requirements.txt`, uploads. Google builds and runs the container for you. Constructor must be picklable — initialize service clients inside `set_up()`, not `__init__`.

**Real impedance mismatch.** AgentCore expects HTTP server in container; Agent Engine expects importable Python class with specific methods. The cloudless adapter must emit both artifacts from one source.

### Runtime contract

**AgentCore HTTP contract:**
- `POST /invocations` — JSON in, JSON or SSE out
- `GET /ping` — `{"status": "Healthy" | "HealthyBusy", "time_of_last_update": <unix>}`
- Optional `/ws` for WebSocket
- Port 8080
- Alternative protocols on different ports: MCP on `/mcp` port 8000, A2A on port 9000, AG-UI on 8080

**Vertex Agent Engine contract** — no user-visible HTTP contract. SDK routes traffic via gRPC/REST. Streaming via `stream_query()` which yields iteratively; bidirectional via separate WebSocket API.

**For cloudless:** standardize internally on streaming async generator. GCP adapter maps to `stream_query()`; AWS adapter maps to `/invocations` SSE.

### Framework support

| Framework | AgentCore | Agent Engine | Natural home |
|---|---|---|---|
| Strands Agents | **First-class** (AWS) | Possible via custom | AgentCore |
| Google ADK | Supported | **First-class** | Agent Engine |
| LangGraph | Supported (`BedrockAgentCoreApp` wrapper) | First-class (`LanggraphAgent`) | Both |
| LangChain | Supported | First-class (`LangchainAgent`) | Both |
| LlamaIndex | Possible | First-class | Agent Engine |
| AG2 / AutoGen | Possible | First-class | Agent Engine |
| CrewAI | Supported | Possible via custom | AgentCore |
| **MAF** | Possible (FastAPI + container) | Possible (custom) | Neither |
| OpenAI Agents SDK | Supported | Possible | AgentCore |

### Sessions

**AgentCore** — dedicated Firecracker microVM per `runtimeSessionId`. 2 vCPU / 8 GB, 1 GB filesystem, 8 h max, 15-min idle. 1,000 active / account in us-east/west, 500 elsewhere.

**Vertex Agent Engine** — managed serverless container; `container_concurrency` configurable (default 1 sync req/instance with 9 parallel agent processes per container). Connection lifetime ~10 min per WebSocket; longer via session resumption.

**Impedance mismatch:** AgentCore is microVM-per-session (strong isolation, longer-lived); Agent Engine is managed container with multiplexed concurrency + separate Sessions store. **Cloudless treats session ID as logical token only.**

### Memory

**AgentCore Memory** — 5 strategies (Semantic, Summarization, User-preference, Episodic, Custom). Built-in extraction with configurable LLM. 7–365 day retention. $0.25/1k events; $0.75/1k records/mo (built-in) or $0.25/1k (BYO model); $0.50/1k retrievals.

**Vertex Memory Bank** — single Gemini-powered async extraction. Configurable memory topics. Tightly integrated with Agent Engine Sessions. IAM Conditions for per-memory access control. $0.25/1k events or memories.

**Mapping in cloudless (Q14):** unified `Memory(scope, strategy)` API:
- `recall_facts()` → AWS SEMANTIC / GCP topic filter
- `summarize_session()` → AWS SUMMARIZATION / GCP topic
- `get_preferences()` → AWS USER_PREFERENCE / GCP topic
- `replay_episode()` → AWS EPISODIC / GCP best-effort with warning
- `with_custom_strategy()` → AWS CUSTOM; **raises on GCP**

### Identity

**AgentCore Identity** — workload identity, token vault (KMS-encrypted), OAuth 3LO/2LO orchestration. Inbound: IAM SigV4 or OAuth 2.0. Outbound: managed credentials for Slack/Zoom/GitHub. $0.010/1k token requests for non-AWS resources; free via Runtime/Gateway.

**Agent Engine identity (pre-Cloud-Next-'26)** — service account + ADC for Google APIs; IAM Conditions; **no native vault for third-party OAuth.** Workforce Identity Federation for cross-cloud. Apigee as separate API governance product.

**Post-Cloud-Next-'26** — GCP added **Agent Identity** as a first-class primitive. See `05-gemini-enterprise-rebrand.md`. Now near-parity with AgentCore Identity.

### Tools / MCP

**AgentCore Gateway** — zero-code Lambda/OpenAPI/Smithy/MCP-server → MCP server. Public HTTPS endpoint. Cognito inbound, IAM outbound. 100 targets/gateway, 1,000 tools/target, semantic search at 25 TPM (low cap), 6 MB payload, 1 MB inline schema.

**Vertex tool story:**
- ADK supports MCP tools natively
- MCP Toolbox for Databases (AlloyDB, Spanner, Cloud SQL, BigQuery, Bigtable)
- Apigee for governance
- **Agent Gateway** added at Cloud Next '26 — closes most of the gap

### Code execution sandbox

**AgentCore Code Interpreter** — Firecracker microVM, Python/JS/TS, 2 vCPU / 8 GB, 10 GB disk, 100 MB payload, 8 h async max. Pre-installed pandas/numpy/etc.

**Vertex Code Execution** — preview; also available via GenAI SDK `ToolCodeExecution()`. **Agent Sandbox** announced at Cloud Next '26.

**For cloudless:** unified `Sandbox.execute(code, language, files)`; limits differ (AgentCore more generous on duration/disk).

### Browser tool

**AgentCore Browser** — managed Playwright Chromium, profiles, live view, automation streams, 1 vCPU / 4 GB, 10 GB disk, 8 h max.

**Vertex AI** — no equivalent managed browser primitive pre-Cloud-Next-'26. **Agent Sandbox + Computer Use model** post-Cloud-Next-'26 — different shape (model controls a browser via screenshots, not Playwright automation).

**For cloudless:** v1 exposes Browser primitive with two sub-APIs:
- `Browser.automate(script)` for Playwright-style (AWS native, GCP via shim)
- `Browser.computer_use(goal)` for model-driven (GCP native, AWS optional)

### Observability

Both speak OTel. AgentCore lands in CloudWatch GenAI Observability + X-Ray; Vertex lands in Cloud Trace + Cloud Logging. **Cleanest unification of all dimensions.**

### A2A protocol

Both treat A2A as a peer protocol. AgentCore added as first-class runtime protocol mode (Nov 2025). Vertex/ADK treats A2A as first-class via dedicated dev/deploy paths. **For cloudless, A2A is the cross-cloud lingua franca.**

### Pricing (low-scale workload)

100 sessions/day × 5 min compute × 1 vCPU / 2 GB peak, with memory + 50 tool calls per session:

**AgentCore monthly:**
- CPU: 100×30×(5/60)×$0.0895 = ~$22.38
- Memory: 100×30×(5/60)×2×$0.00945 = ~$4.73
- Memory primitive events: ~$1.50 (3 events/session)
- Gateway: 5,000 invocations/day × 30 × $0.005/1k = ~$0.75
- **Subtotal: ~$30/month** (excluding model + CloudWatch)

**Agent Engine monthly:**
- vCPU: ~$21.60 minus 50 vCPU-h free ≈ $17.28
- Memory: ~$4.50 minus 100 GB-h free ≈ $3.60
- Sessions/Memory: ~$1.50
- **Subtotal: ~$22/month** (excluding model)

GCP ~25% cheaper at low scale due to free tier. Converge to within a few percent at enterprise scale. Foundation model cost dominates either bill.

---

## Synthesis for cloudless

### Unify (single API hides difference)

- **Runtime invocation** — `Runner.invoke(session_id, message)` maps to `/invocations` (AWS) or `query()` (GCP)
- **Sessions** as logical IDs only
- **Memory** — unified verbs (recall_facts / summarize_session / get_preferences / replay_episode); custom AWS-only with clear deploy-time error on GCP
- **Observability** — OTel everywhere; backend per cloud
- **A2A** — identical contract; **default inter-agent protocol**
- **Code sandbox** — unified `execute()`; limits documented per cloud
- **Pricing/cost telemetry** — normalized vCPU-sec + GB-sec + tool invocation metrics

### Feature-flag (capability-gated)

- **Browser** — different shape across clouds; expose two sub-APIs
- **AG-UI protocol** — AWS-only
- **Per-session writable filesystem** — AWS-only (1 GB ephemeral); GCP requires external state
- **OAuth token vault** — both native post-Cloud-Next-'26
- **Long-running >30 min** — both native post-Cloud-Next-'26

### Drop from abstraction

- **Code Interpreter disk limits** — expose as `Sandbox.max_disk_mb` capability, don't unify
- **Concurrency tuning** — fundamentally different (microVM vs container_concurrency); expose `platform_overrides`
- **Framework "natural home" optimizations** — let Strands→AgentCore, ADK→Agent Engine

### Hard impedance mismatches

1. **Deployment artifact**: container image vs picklable Python class. Build both from one source. Solvable but unavoidable.
2. **Session isolation guarantee**: AgentCore's microVM-per-session is a security claim GCP can't match exactly. Document the difference; don't promise equivalence.
3. **8-hour sync async**: AWS-native; GCP requires architectural workaround (session resumption + external state) — partially closed by Cloud Next '26's multi-day support.
4. **Identity vault**: pre-Cloud-Next-'26 GCP had no equivalent; now Agent Identity gives near-parity.
5. **Quotas/limits**: AgentCore lists specific numbers; Agent Engine quotas less explicit and project-based.
6. **Browser shape**: AgentCore Playwright vs GCP Computer-Use model — different mental models even if both can complete browser tasks.

### Recommended layering (locked in cloudless ARCHITECTURE.md)

```
+---------------------------------------------+
| User code: ADK / LangGraph / Strands / MAF  |
+---------------------------------------------+
| cloudless SDK: Agent, Tool, Memory,         |
|   Sandbox, Sessions, Identity, A2A          |
+---------+---------------------+-------------+
| AWS adapter                   | GCP adapter |
| - Container builder           | - Pickle+   |
| - AgentCore Runtime           |   shim       |
| - AgentCore Memory            | - Agent     |
| - Gateway / Identity          |   Runtime   |
| - Code Interpreter            | - Memory    |
| - Browser (native)            |   Bank      |
| - ADOT/CloudWatch             | - MCP shim  |
|                               | - Sandbox   |
|                               | - Browser   |
|                               |   BYO       |
|                               | - OTel/     |
|                               |   Trace     |
+---------+---------------------+-------------+
```

---

## Sources

- [Amazon Bedrock AgentCore GA (Oct 2025)](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/)
- [AgentCore preview (Jul 2025)](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/)
- [AgentCore Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Vertex AI Agent Engine overview](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)
- [Vertex AI pricing](https://cloud.google.com/vertex-ai/pricing)
- [Vertex Agent Engine custom agent](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/develop/custom)
- [Vertex Memory Bank overview](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview)
- [Vertex Memory Bank preview blog](https://cloud.google.com/blog/products/ai-machine-learning/vertex-ai-memory-bank-in-public-preview)
- [Vertex Agent Engine A2A](https://cloud.google.com/agent-builder/agent-engine/develop/a2a)
- [ADK on Agent Engine deploy](https://google.github.io/adk-docs/deploy/agent-engine/)
- [MCP Toolbox for Databases](https://cloud.google.com/blog/products/ai-machine-learning/mcp-toolbox-for-databases-now-supports-model-context-protocol)
- [google/adk-python](https://github.com/google/adk-python)
- [A2A protocol spec](https://a2a-protocol.org/latest/)
- [AgentMarketCap AWS vs Azure vs GCP comparison Q2 2026](https://agentmarketcap.ai/blog/2026/04/09/aws-bedrock-agentcore-vs-azure-ai-agent-service-vs-google-vertex-ai-agents-q2-2026)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
