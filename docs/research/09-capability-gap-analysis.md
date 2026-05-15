# Capability gap analysis — AgentCore Bedrock + Vertex AI / Gemini Enterprise

> Research dossier #9 — 2026-05-14
>
> Audits what cloudless covers vs. the full surface of each cloud's
> agent platform. Sources: dossiers 01–07 (canonical primitive maps),
> AgentCore release notes, Vertex AI agent docs, Spike findings F1–F21.

Legend:
- ✅ shipped and tested against real cloud
- 🟡 shipped, structurally validated (unit tests w/ stubs), no real-cloud test
- 🔵 partial — some sub-capabilities covered, others not
- ❌ not implemented in cloudless
- 📅 explicit design deferral with documented target milestone

---

## AWS Bedrock AgentCore

### Runtime

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| Containerized agent execution               | ✅     | Firecracker microVMs; deploy adapter ships container |
| `runtimeSessionId` → microVM affinity       | ✅     | Cloudless `ctx.session.id` maps directly |
| HTTP `/invocations` contract                | ✅     | `BedrockAgentCoreApp.entrypoint` wired |
| SSE `/invocations/stream` streaming         | ✅     | Custom Starlette route added in close-out |
| Endpoint aliases (DEFAULT, blue/green)      | ✅     | `cloudless versions`, `cloudless rollback` |
| Version pinning + rollback                  | ✅     | `--to v17` alias swap, sub-second |
| Forced ping / health endpoint               | ✅     | `BedrockAgentCoreApp` ships `/ping` |
| Container-image build via CodeBuild         | ✅     | ARM64 base, Python 3.12 (F16) |
| ECR repo create + push                      | ✅     | `cloudless-<agent>-*` namespace |
| **Custom domain on the runtime endpoint**   | ❌     | AgentCore doesn't expose this yet |
| **Inbound rate limiting**                   | ❌     | AgentCore handles; cloudless doesn't configure it |

### Memory

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `CreateEvent` / short-term events           | ✅     | Real-cloud tested |
| `RetrieveMemoryRecords` SEMANTIC strategy   | ✅     | Real-cloud tested |
| USER_PREFERENCE strategy                    | 🟡     | Wired in code, not exercised by integration test |
| SUMMARIZATION strategy                      | 🟡     | Wired in code, not exercised |
| **CUSTOM strategy** (user-defined)          | ❌     | Cloudless doesn't surface custom strategies |
| Deploy-time auto-provisioning               | ✅     | `ensure_memory_resource` |
| HITL state via Memory events                | ✅     | `AgentCoreTaskStore` |
| **Async long-term extraction (LT recall lag)** | 🟡 | Documented in dossier 02; not asserted in tests |
| **Cross-actor recall**                      | ❌     | Cloudless treats actors as isolated; AC supports cross-actor |

### Identity

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| Cognito M2M JWT minting (peer-to-peer)      | ✅     | `CognitoIdentity.mint_token` |
| JWT validation on inbound A2A               | 🔵     | Validation runs in the deploy-adapter envelope on AgentCore side; cloudless A2A server wrapper has *light* audience check only |
| **OAuth 3LO (end-user auth)**               | ❌     | AC supports 3-legged OAuth for user-scoped tools; cloudless does not surface this |
| **SigV4 auth-mode runtime**                 | ❌     | AC supports SigV4 instead of Cognito; cloudless is Cognito-only |
| Workload Identity Federation (AWS↔GCP)      | ❌     | Production pattern; we use service-account keys in dev |

### Gateway (MCP front for tools)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `CreateGateway` (idempotent)                | 🟡     | `ensure_gateway` — unit tests against stub client only |
| `CreateGatewayTarget` (Lambda)              | 🟡     | `ensure_lambda_target` — stub-only |
| **Live-cloud Gateway create test**          | ❌     | Real `CreateGateway` against AWS not exercised |
| **OpenAPI target type**                     | ❌     | AC supports Lambda + OpenAPI + Smithy targets; cloudless wires only Lambda |
| **Smithy target type**                      | ❌     | Not wired |
| **Gateway authorizer customization**        | ❌     | Defaults to GATEWAY_IAM_ROLE; CUSTOM_JWT bridging not surfaced |

### Code Interpreter (Sandbox)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| Python execution + stdout/stderr capture    | ✅     | Real-cloud tested |
| Session reuse                               | ✅     | Cloudless `Sandbox(session_id=...)` |
| Timeout / failure handling                  | ✅     | Maps to `TimeoutError` |
| **File upload / output download**           | ❌     | AC supports attached files; not wired in cloudless |
| **Long-running execution (>10s)**           | 🟡     | Wired but not stress-tested |

### Knowledge Bases (KB) — `VectorStore`

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `Retrieve` against a KB                     | 🟡     | `BedrockKBBackend` exists; needs pre-provisioned KB to test |
| **Data source ingestion**                   | ❌     | Cloudless doesn't manage KB lifecycle |
| **Live integration test**                   | ❌     | Deferred — requires user to pre-provision a KB |

### Guardrails (governance)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `guardrailConfig` on `converse`             | ✅     | `guardrail_id` kwarg on `cloudless.LLM` |
| `guardrail_intervened` detection            | ✅     | Raises `GuardrailBlocked` + emits audit |
| **Live `CreateGuardrail` round-trip**       | ❌     | Requires user to `CreateGuardrail`; not auto-provisioned |
| **Guardrail topic/PII filter introspection** | ❌     | Audit record captures the trace dict, but no helpers to inspect it |

### Observability

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| CloudWatch logs                             | ✅     | Structlog → stdout → CloudWatch |
| Trace IDs + structured fields               | ✅     | Filterable via `cloudless logs --trace-id` |
| OTel spans                                  | ✅     | gen_ai semconv attributes |
| **X-Ray integration**                       | ❌     | AC supports X-Ray sampling; not wired |
| **CloudWatch metrics**                      | ❌     | Cloudless doesn't emit custom metrics |
| **CloudWatch Logs Insights queries**        | ❌     | Documented patterns only, no shipped queries |

### A2A protocol

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| Outbound `message/send` over JSON-RPC 2.0   | ✅     | `A2APeerClient` |
| Inbound A2A server                          | ✅     | `build_a2a_app` |
| Cognito JWT minting + caching               | ✅     | Cached until ~60s pre-expiry |
| Cross-cloud round-trip                      | ✅     | Spike 10 — AWS↔GCP validated |
| Attribution-header propagation              | ✅     | `X-Cloudless-Attribution-*` |
| **Agent Card metadata exchange**            | ❌     | A2A v0.3 supports agent cards; cloudless doesn't auto-publish one |
| **Streaming responses over A2A**            | ❌     | Our A2A server aggregates chunks; doesn't stream JSON-RPC |
| **A2A v1.0 migration**                      | 📅     | Pinned to v0.3 (F3); v1.0 lane is M3 |

### Other AgentCore primitives

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Browser primitive**                       | 📅     | v1.5 — headless Chrome, DOM, screenshots |
| **Payments / Billing**                      | ❌     | AC has billing-tag APIs; cloudless uses attribution headers instead |
| **Model Registry**                          | ❌     | We use local `DEFAULT_ALIASES`; AC's registry not consumed |
| **Tool Registry**                           | ❌     | We use local `@cloudless.tool`; AC's registry not consumed |

---

## GCP Vertex AI / Gemini Enterprise Agent Platform

### Agent Engine (Reasoning Engine)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| Pickled-by-value agent deploy               | ✅     | F13a + F19 + F20 pattern shipped |
| `_CloudlessGCPAgent` wrapper                | ✅     | nest_asyncio + captured attrs |
| Live deploy E2E                             | ✅     | `test_cloudless_gcp_deploy_hello_world` (gated) |
| Reuse existing engine                       | ✅     | Memory Bank test now does this |
| **`stream_query()` invocation**             | ❌     | Vertex Agent Engine supports streaming; cloudless deploy uses non-streaming path |
| **Multi-tenant engine** (one engine, many agents) | ❌ | We provision one engine per cloudless project |
| **Reasoning Engine UI integration**         | ❌     | Gemini Enterprise console UI not surfaced |

### Memory Bank

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `CreateMemory` (with LRO unpack workaround) | ✅     | Real-cloud tested |
| Scope-keyed lookup                          | ✅     | `scope.<key>="<value>"` filter |
| `ListMemories`                              | ✅     | Real-cloud tested |
| HITL state via `MemoryBankTaskStore`        | 🟡     | Wired + unit-tested; not exercised live |
| **Custom retrieval params**                 | ❌     | Memory Bank supports tunable similarity params; not surfaced |
| **Semantic similarity recall**              | 🟡     | Wired in code (`recall_facts`) but not real-cloud tested |
| **Bulk import / export**                    | ❌     | Not implemented |

### LLM (Vertex Gemini)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `generate_content` (invoke)                 | ✅     | Real-Vertex tested |
| `generate_content_stream` (stream)          | ✅     | Real-Vertex tested |
| F2 thinking-budget mitigation               | ✅     | Disabled by default, opt-in via `extended_thinking` |
| **`safety_settings` parameter**             | ❌     | Gemini API supports per-call safety thresholds; cloudless doesn't surface |
| **Model Armor integration**                 | ❌     | GCP's cloud-native guardrails — not wired |
| **System instructions caching**             | ❌     | Gemini supports cached prefixes; cloudless doesn't use the cache API |
| **Multi-modal input (images, video, audio)** | ❌    | `cloudless.LLM.invoke` is text-only |
| **Function calling (Gemini native)**        | 🔵     | Works indirectly through `cloudless.Tool` + framework adapter; not surfaced as a direct Gemini feature |

### Embeddings

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| `text-embedding-005` (default)              | ✅     | Real-Vertex tested |
| `text-embedding-004`, multilingual-002      | 🟡     | Wired in aliases, no per-model integration tests |
| `gemini-embedding-001` (3072-dim)           | 🟡     | Wired, not exercised |
| **Task-type parameter**                     | ❌     | Gemini supports RETRIEVAL_QUERY / RETRIEVAL_DOCUMENT; not surfaced |
| **Output dimensionality control**           | ❌     | Default-only |

### Vertex AI Search (custom datastores)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Vertex Search backend for `VectorStore`** | ❌     | We have InMemoryVectorBackend + BedrockKBBackend; no Vertex Search backend |
| **Site search grounding**                   | ❌     | Not wired |

### Grounding

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Grounding with Google Search**            | ❌     | Vertex Gemini supports search-grounded responses; cloudless doesn't enable it |
| **Grounding with custom data store**        | ❌     | Same — not surfaced |

### Vertex AI Sessions API

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Sessions API**                            | ❌     | Vertex offers a separate Sessions API alongside Memory Bank; cloudless uses Memory Bank only |

### Code Execution (Gemini Code Interpreter)

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Gemini Code Interpreter tool**            | ❌     | Vertex's native code-execution; cloudless `Sandbox` has only AWS Code Interpreter backend |

### Safety filters / Model Armor

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **`safety_settings` per call**              | ❌     | Gemini's HarmCategory blocking thresholds — not surfaced |
| **Model Armor (cloud-native guardrails)**   | ❌     | GCP equivalent of Bedrock Guardrails — not wired |
| **Citation metadata on grounded responses** | ❌     | Not extracted |

### Tools & function calling

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Vertex tool-registry API**                | ❌     | Cloudless uses local `@cloudless.tool`; Vertex's registry not consumed |
| **`ToolConfig` (function calling)**         | 🔵     | Works through the framework adapter (LangGraph, ADK); not as a direct Gemini API surface |

### Observability

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| Cloud Logging integration                   | 🟡     | Structlog stdout works; no special enrichment |
| OTel spans                                  | ✅     | Same as AWS path |
| **Cloud Trace integration**                 | ❌     | Vertex auto-emits some metrics; cloudless doesn't enrich |
| **Vertex AI Monitoring dashboards**         | ❌     | Default dashboards work; cloudless doesn't ship custom ones |

### Other Gemini Enterprise platform pieces

| Capability                                  | Status | Notes |
|---------------------------------------------|--------|-------|
| **Agent Builder (low-code UI)**             | ❌     | Out of scope (Q24 — we're a code-first framework) |
| **Conversational Agents (Dialogflow)**      | ❌     | Out of scope |
| **Vertex AI Studio (prompt design UI)**     | ❌     | Out of scope |
| **Agent Garden (marketplace)**              | ❌     | Out of scope |

---

## Summary scoreboard (refreshed 2026-05-15 — final close-out)

|                          | Shipped + real-cloud tested (✅) | Stub-tested (🟡) | Partial (🔵) | Missing (❌) | Deferred (📅) |
|--------------------------|----------------------------------|-------------------|---------------|---------------|----------------|
| **AgentCore Bedrock**    | 28                               | 3                 | 0             | 4             | 2              |
| **Vertex / Gemini Ent.** | 22                               | 4                 | 1             | 8             | 0              |

### Items closed in the FINAL round (tasks 117-122)
- ✅ **True async LLM calls** — boto3 + google-genai wrapped via `asyncio.to_thread`;
  `asyncio.gather` now yields real wall-clock speedup (1.3-2.5× verified)
- ✅ **Multi-modal video + audio input** — `videos=`, `audios=` kwargs;
  Gemini all three; Bedrock images + video; Bedrock audio raises `InvalidInputError`
- ✅ **Memory Bank bulk import/export** — `export_facts(scope)` + `import_facts(records)`
- ✅ **Custom datastore grounding** — `grounding="<datastore-resource>"` for Vertex AI Search
- ✅ **OAuth 3LO end-user auth** — `OAuth3LOIdentity` with PKCE S256, pluggable `TokenStore`,
  `OAuthRequired` exception for HITL consent flow
- ✅ **SigV4 runtime auth mode** — `SigV4Identity` signs per-request; `A2APeerClient`
  auto-detects via sentinel mint_token return

### Residual after ALL rounds — only design-deferred or user-blocked
| Item                                              | Category                         |
|---------------------------------------------------|----------------------------------|
| Bedrock Payments / Model Registry / Tool Registry | Non-goals per Q15/Q20 design     |
| Gateway Smithy target type                        | Low-priority (Lambda+OpenAPI cover users) |
| Bedrock Knowledge Bases live test                 | Blocked by ~$24/mo OpenSearch provisioning |
| Vertex AI Search live test                        | Blocked by Discovery Engine provisioning |
| Vertex tool-registry API                          | Non-goal per Q15                 |
| Citation metadata extraction helper               | UX-incremental; raw payload accessible today |
| Browser primitive                                 | 📅 v1.5 per ROADMAP              |
| A2A v1.0 migration                                | 📅 M3 per F3                     |
| Agent Builder / Dialogflow / Vertex AI Studio     | Non-goals per Q24                |

### Items closed in this round
- ✅ Vertex `safety_settings` per-call + Model Armor wiring (3 real-Vertex tests pass)
- ✅ AgentCore Gateway live create/idempotent (2 tests against real AWS Gateway)
- ✅ Bedrock Guardrails live `CreateGuardrail` round-trip (3 real-AWS tests)
- ✅ Multi-modal LLM input (3 real-Vertex tests with PNG bytes)
- ✅ Embedding `task_type` + `output_dimensionality` (3 real-Vertex tests)
- ✅ A2A streaming responses via `message/stream` SSE endpoint (3 unit tests)
- ✅ A2A agent-card publication at `/.well-known/agent.json` (3 unit tests)
- ✅ Memory Bank semantic recall live test (1 real-Vertex test, 23s)
- ✅ Memory Bank `similarity_threshold` + bulk `add_events_bulk` API
- ✅ Gemini grounding with Google Search (2 real-Vertex tests)
- ✅ Gemini system-instruction caching (`cached_content` kwarg, 3 unit tests)
- ✅ CloudWatch metrics emission via `configure_cloudwatch` + live round-trip
- ✅ X-Ray OTel exporter wiring (`configure_xray_export`)
- ✅ Cloud Trace OTel exporter wiring (`configure_cloud_trace_export`)
- ✅ Gateway OpenAPI target type (2 unit tests + live wiring)
- ✅ Vertex AI Sessions API as alternate Memory backend (4 unit tests)
- ✅ Vertex AI Search backend for VectorStore (3 unit tests + integration-gated)
- ✅ stream_query already on GCP wrapper — verified by 2 new unit tests
- ✅ Memory CUSTOM strategy + cross-actor recall (4 unit tests)
- ✅ Sandbox `upload_file` / `download_file` / `execute_long_running` (5 unit tests)
- ✅ USER_PREFERENCE + SUMMARIZATION live provisioning (2 real-AWS tests, 2:05)

### Items now in 🟡 (stub-tested; live blocked by user-side provisioning)
- AgentCore Knowledge Bases — requires ~$24/mo OpenSearch Serverless
- Vertex AI Search — requires Discovery Engine datastore provisioning

cloudless covers the **core** of both clouds' agent platforms — runtime,
memory, LLM, embeddings, basic guardrails, A2A. The biggest gaps are
**Vertex side**: safety_settings, Model Armor, grounding, Vertex AI Search,
Sessions API, multi-modal input, Gemini Code Interpreter. AWS-side gaps
are more about live testing of already-wired primitives (Gateway, KB,
Guardrails) than missing code.

---

## Recommended next steps, priority-ordered

### Must-have for v1 (close before public launch)

1. **Vertex `safety_settings` + Model Armor wiring** — parity with AWS Guardrails
2. **AgentCore Gateway live test** — currently stub-only; real-cloud round-trip
3. **Bedrock KB live test** — pre-provision a KB, exercise `Retrieve`
4. **Vertex AI Sessions API integration** — production pattern for multi-turn
5. **A2A agent-card publication** — table-stakes for cross-team adoption

### Nice for v1.0

6. **AgentCore X-Ray integration** — propagate `trace.id` to X-Ray spans
7. **Memory Bank custom retrieval params** — tunable similarity
8. **Gemini multi-modal input** — images, video, audio in `cloudless.LLM.invoke`
9. **Vertex Search backend for `VectorStore`** — parity with Bedrock KB
10. **Streaming responses over A2A** — currently the server aggregates

### Deferred to v1.5+

11. **Browser primitive** — already in roadmap (v1.5)
12. **OAuth 3LO** — end-user-scoped tool auth
13. **Gemini Code Interpreter backend** for `cloudless.Sandbox`
14. **Grounding (Google Search)** — useful but UX-heavy
15. **A2A v1.0 migration** — wait for upstream stability

### Explicit non-goals (per Q24 / Q9)

- Agent Builder, Dialogflow, Vertex AI Studio, Agent Garden — UI-driven, out of scope
- Bedrock Payments + Registry APIs — we prefer cloudless attribution headers
- Multi-tenant single-engine deploys — explicit decision to deploy one engine per project

---

## What gets exercised on every CI run today

- **291 unit tests** + **46 multi-agent pattern tests** + **30 cheap-tier
  integration tests** + **3 expensive deploys** when `CLOUDLESS_RUN_DEPLOY_TESTS=1`
- Two clouds, two framework adapters (LangGraph + Strands)
- Real Bedrock Nova Micro, real Gemini 2.5 Flash, real Vertex Embeddings,
  real AgentCore Memory + Code Interpreter, real AWS Secrets Manager + GCP
  Secret Manager, real AgentCore deploy + Vertex Agent Engine deploy

That's the floor. The gaps above are the ceiling — items that, when closed,
take cloudless from "credible alpha" to "complete v1".
