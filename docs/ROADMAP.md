# cloudless — Roadmap

> Status: design-locked. Implementation pending. Last updated 2026-05-14.

## v1.0 (target: 22-26 weeks from kickoff)

### Milestone M1 — Bones (4 weeks)

**Goal:** A single LangGraph agent deploys to AWS AgentCore from local in under 5 minutes.

- SDK skeleton: `cloudless.Agent` base, `@cloudless.agent` decorator, typed `Chunk` taxonomy, exception hierarchy
- CLI scaffolding: `cloudless init`, `cloudless deploy`, `cloudless dev` (single-agent, single-cloud, LangGraph only)
- AgentCore Runtime adapter: ARM64 Dockerfile generation, ECR push, `CreateAgentRuntime`/`CreateAgentRuntimeEndpoint`, HTTP protocol contract
- Embedded runtime lib: logging, OTel emit, manifest loader
- Service catalog skeleton: LLM (Bedrock only), Memory (AgentCore Memory only), Secrets (Secrets Manager)
- `cloudless dev` mode 0: in-memory mocks except LLM, hot reload, local OTel→Jaeger

**Demo:** hello-world LangGraph agent → AgentCore in < 5 min.

### Milestone M2 — Cross-cloud (5 weeks)

**Goal:** Agent on AWS calls agent on GCP via A2A with Cognito JWT, end-to-end traces visible in both clouds.

- GCP adapter: Gemini Enterprise Agent Runtime via `client.agent_engines.create()` (picklable Python class shim)
- LLM, Memory, Secrets bindings on GCP via `google-genai` SDK + Memory Bank + Secret Manager
- LangGraph fully working on both clouds (`langgraph-checkpoint-aws` on AWS, `LanggraphAgent` template on GCP)
- A2A protocol mode on AgentCore (port 9000) and Agent Runtime
- Cognito User Pool auto-provisioning in `cloudless init`
- `cloudless-manifest.json` baking; cross-cloud peer routing
- BYO IdP escape hatch (Auth0 / Entra ID / Okta config swap)

**Demo:** agent on AWS calls agent on GCP via A2A, traces visible in CloudWatch + Cloud Trace.

### Milestone M3 — Production primitives (5 weeks)

**Goal:** Agents use external tools, execute code, run RAG against a vector store, respect cost caps.

- Tools/Gateway primitive: `Tool.from_function`, `Tool.from_openapi`, `Tool.from_aws_lambda`, `Tool.from_gcp_cloud_run`, `Tool.from_mcp_server`; AgentCore Gateway + Agent Gateway provisioning
- Sandbox primitive: AgentCore Code Interpreter + Agent Sandbox bindings; unified `execute(code, language, files)`
- Embeddings primitive
- **VectorStore primitive (pulled in)**: OpenSearch Serverless / S3 Vectors + Vertex Vector Search bindings
- Resilience config: retries, timeouts, circuit breakers per service class; typed exception hierarchy
- **Fallback chains (pulled in)**: `fallback: {model: claude-haiku}` cross-model failovers
- Cost telemetry: tracking + A2A attribution propagation + caps + `cloudless cost` CLI
- Versioning: auto-version per deploy + named endpoint aliases + traffic splitting + `cloudless rollback`

**Demo:** agent calls external OpenAPI tool, runs code in sandbox, retrieves from vector store, respects $5 session cost cap.

### Milestone M4 — Operational maturity (5 weeks)

**Goal:** Multi-framework multi-cloud topology with governance, HITL, evals, multi-region, dashboards.

- Strands adapter (AWS, native)
- ADK adapter (GCP, native)
- **Strands on GCP (pulled in)**: custom Vertex template + Strands standalone `A2AServer` path
- **ADK on AWS (pulled in)**: custom `AgentCoreMemorySessionService` bridging ADK session model to AgentCore Memory
- Governance: cloud-native guardrails (Bedrock Guardrails / Model Armor) + `@cloudless.policy` decorator with 6 stage hooks
- `@cloudless.task` long-running primitive + `ctx.request_approval()` HITL (webhook + polling delivery)
- Slack delivery channel for HITL
- Eval framework: `cloudless eval run/diff/gate` with cassette-based replay
- `cloudless.testing` fixtures and A2A contract tests
- `cloudless migrate scan/wrap/check` tooling
- Multi-account + multi-region deploy targets
- **Cross-region memory replication (pulled in)**
- Default Grafana / CloudWatch dashboard JSON; `cloudless dashboards install`

**Demo:** multi-agent topology (Strands+ADK+LangGraph) crossing clouds, full HITL approval flow via Slack, eval gate in CI blocks a prompt regression, multi-region traffic routes by user locale.

### Milestone M5 — Extended catalog (5 weeks)

**Goal:** Identity vault for outbound OAuth tools, browser automation, polish.

- **Identity vault primitive (pulled in)**: AgentCore Identity + Agent Identity unified API for outbound 3rd-party OAuth (Slack, GitHub, Salesforce, etc.)
- **Browser primitive (pulled in)**: unified `Browser` API abstracting AgentCore Browser (Playwright) and Agent Sandbox + Computer Use model
- Docs site polish, tutorials, examples
- v1.0 release-readiness audit

**Demo:** agent uses Slack OAuth to post messages, uses browser to scrape a real site, all via unified APIs.

---

## v1.0 explicit non-goals (deferred to v1.5 / v2 / commercial)

### v1.5 (open source, ~3-4 months after v1.0)
- Hosted approval inbox UI for HITL
- Mobile push HITL delivery (APNs/FCM)
- Native email approval flows
- Degraded modes in resilience (run without memory if Memory service is down)
- Bulkheads (resource isolation between agents on same runtime)

### v2.0 (open source, ~6 months after v1.0)
- **TypeScript SDK** (full first-class support)
- ADK on AWS scenario beyond v1's Strands+ADK natives
- Cross-region replication for non-memory primitives (e.g., vector stores)
- Threat / Anomaly Detection primitive (GCP-only wrap)
- Agent Registry sync (once cross-cloud federation matures)
- `cloudless workspace` mono-repo support

### v3.0 (open source)
- **MS Agent Framework support** on both clouds (DIY adapters)

### Commercial tier (separate from version stream)
- Multi-tenancy primitives (tenant-aware memory keys, secrets, policies, cost attribution)
- Advanced eval features (multi-judge consensus, regression-detection ML, golden-dataset management UI)
- Enterprise SSO with arbitrary IdPs
- On-prem control plane
- Audit-log delivery to SIEM
- Compliance kits: SOC2 / HIPAA / FedRAMP guides + Terraform modules
- Dedicated support + SLA

---

## Sequencing notes

- **M1 and M2 are sequential** (you need bones before cross-cloud).
- **M3 and M4 can partially parallelize** with two engineers — M3 is cloud-primitive integration work; M4 is framework adapter + ops work.
- **M5 partially parallels M4's final 2 weeks** if the Identity vault unblocks tool integrations the M4 team needs for governance examples.
- **Browser primitive** is the riskiest deliverable in M5 due to Playwright-vs-Computer-Use API shape mismatch — flag for design spike at start of M5.

## Pre-1.0 stability

We commit to v1.0 only after:
- 2+ customer prod deployments using v0.x
- 2 months of real-world burn-in
- Internal eval suite green across the published framework × cloud matrix
- Security review of cross-cloud auth and policy stages

During v0.x, MINOR may break. Documented in CHANGELOG.

## Beyond v1.0

Roadmap items above are signal, not commitment. We re-prioritize quarterly based on adoption, customer feedback, and platform evolution (AgentCore + Gemini Enterprise both still actively shipping new primitives in 2026).
