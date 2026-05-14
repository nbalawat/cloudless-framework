# cloudless — Architecture Decision Log

> Concise ADR-style log of decisions Q1–Q37 from the design interview.
> Full rationale in [`ARCHITECTURE.md`](./ARCHITECTURE.md). Research evidence in [`research/`](./research/).
> Status: design-locked; implementation pending.

| # | Decision | Choice | Date |
|---|---|---|---|
| Q1 | Target user persona | **AI-fluent application developer** — Python-comfortable, knows agents/tools/RAG, does NOT want to learn IAM, VPCs, AgentCore configs, Vertex deploy specs | 2026-05-14 |
| Q2 | Abstraction scope | **Abstract the cloud, not the framework.** Users write native ADK/LangGraph/Strands/MAF; unified service catalog over AWS+GCP | 2026-05-14 |
| Q3 | Runtime topology | **SDK + CLI + embedded runtime lib. No central control plane.** Decentralized A2A discovery via agent cards + repo manifest | 2026-05-14 |
| Q4 | Build strategy | **Cloud-native artifact per cloud.** ARM64 container on AWS, picklable Python class on GCP. Single source | 2026-05-14 |
| Q5 | Framework rollout | **Phased.** v1 = LangGraph (both), Strands (AWS), ADK (GCP) baseline; v1.0 expanded scope adds Strands/GCP + ADK/AWS. MAF in v3 | 2026-05-14 |
| Q6 | Protocol exposure | **Declarative `interfaces=[http, a2a]`.** AWS deploys 1-or-2 runtimes; GCP deploys 1 serving both | 2026-05-14 |
| Q7 | Cross-cloud A2A auth | **Auto-provision AWS Cognito as default IdP.** BYO Auth0/Entra/Okta via config swap. OAuth 2.0 client-credentials JWTs | 2026-05-14 |
| Q8 | Evals + observability | **Own portable offline eval framework + OTel-everywhere online.** Linked by `run.id`. Dual-write to Langfuse/Arize/Datadog optional | 2026-05-14 |
| Q9 | v1 service catalog | **8 baseline + 3 pulled-in = 11 primitives** at v1: LLM, Embeddings, Memory, Secrets, Observability, A2A, Sandbox, Tools/Gateway + VectorStore, Identity vault, Browser | 2026-05-14 |
| Q10 | Configuration model | **`@cloudless.agent` decorator + `cloudless.yaml`** with environment overlays | 2026-05-14 |
| Q11 | Language at v1 | **Python only.** TypeScript first-class in v2 | 2026-05-14 |
| Q12 | Service discovery | **`cloudless.yaml` agents block is source of truth.** Deploy bakes `cloudless-manifest.json` into each agent; optional cloud-registry sync | 2026-05-14 |
| Q13 | Local development | **`cloudless dev`** — local subprocess per agent, real LLM calls, mocked everything else, local Jaeger, hot reload, `--record`/`--replay` cassettes | 2026-05-14 |
| Q14 | Memory API shape | **High-level semantic verbs** (`recall_facts`, `summarize_session`, `get_preferences`, `replay_episode`); strategy is internal. Custom strategy AWS-only | 2026-05-14 |
| Q15 | Tools model | **Multi-source `Tool.from_*()` factory.** Decorator + OpenAPI + Lambda + Cloud Run + external MCP servers. Normalize to MCP under the hood | 2026-05-14 |
| Q16 | Streaming abstraction | **Async generator returning typed `Chunk` subclasses** (Text/ToolCall/ToolResult/Reasoning/State/Final/Error) | 2026-05-14 |
| Q17 | Long-running + HITL | **v1 `@cloudless.task` with checkpoints + `ctx.request_approval()`.** Webhook + polling + Slack delivery. Hosted approval UI in v1.5 commercial | 2026-05-14 |
| Q18 | Versioning model | **Auto-version per deploy + named endpoint aliases** (default/canary/prod) + **percentage traffic splitting.** `cloudless rollback` flips alias | 2026-05-14 |
| Q19 | Governance | **Two-layer.** Cloud-native guardrails (Bedrock Guardrails / Model Armor) + `@cloudless.policy` decorator with 6 stage hooks | 2026-05-14 |
| Q20 | Cost telemetry | **Full stack.** Per-invocation tracking + A2A attribution propagation + caps + `cloudless cost` CLI + default Grafana/CloudWatch dashboards | 2026-05-14 |
| Q21 | Resilience model | **Per-service config + typed exception hierarchy + circuit breakers.** Fallback chains and degraded modes in v1.5 | 2026-05-14 |
| Q22 | Distribution model | **Apache 2.0 open-core + commercial enterprise layer.** HashiCorp / Sentry / GitLab precedent | 2026-05-14 |
| Q23 | Deployment topology | **Multi-account + multi-region at v1.** Multi-tenancy in v1.5 / commercial | 2026-05-14 |
| Q24 | Project layout | **Convention-based `src/` layout.** `cloudless init` scaffolds. Auto-discovery of decorated symbols | 2026-05-14 |
| Q25 | Testing | **`cloudless.testing` pytest fixtures + cassette LLM replay + A2A contract tests.** `cloudless test peers --strict` is a CI gate | 2026-05-14 |
| Q26 | Migration path | **Three-phase gradual migration.** Phase 1 = 5-line wrap of existing code → get deploy + observability + cost + versioning. `cloudless migrate scan/wrap/check` tooling | 2026-05-14 |
| Q27 | Framework versioning | **Strict semver + 6-month deprecation window + published compatibility matrix + LTS on even MAJORs** | 2026-05-14 |
| Q28 | v1 milestones | **5 milestones over ~22-26 weeks** (M1 bones → M2 cross-cloud → M3 production primitives → M4 operational maturity → M5 extended catalog). Pulled VectorStore + Identity vault + Strands/GCP + ADK/AWS + fallbacks + cross-region memory + Browser into v1 | 2026-05-14 |
| Q29 | Naming + positioning | **Defer name; keep `cloudless` working name** until v1.0 branding exercise. Positioning: *"Write your agent once. Ship it to any cloud."* | 2026-05-14 |
| Q30 | CLI command catalog | **8 groups, ~30 commands** (lifecycle / config & infra / testing & quality / cost & ops / migration & introspection / long-running / identity / meta). Common flags `--env`, `--json`, `--watch`. Auth via local aws/gcloud CLI. | 2026-05-14 |
| Q31 | Documentation site | **Diátaxis IA + Mintlify primary + auto-API + 6 tutorials.** Docusaurus is the escape hatch. CI fails on doc drift. | 2026-05-14 |
| Q32 | Telemetry + governance | **Anonymous opt-out telemetry, off in CI, transparent field registry**; **lightweight governance at v0.x, formalize before v1.0** (CLA via CLA Assistant + RFC process + Contributor Covenant 2.1 + SECURITY.md). | 2026-05-14 |
| Q33 | Security + supply chain | **Documented threat model + SBOM + Sigstore + reproducible builds + pre-v1.0 third-party audit.** SLSA-aligned posture; annual audit cadence post-v1.0. | 2026-05-14 |
| Q34 | Performance SLOs | **Publish targets + continuous benchmark + public weekly dashboard; no OSS SLA** (SLA = commercial). 9 metrics; both clouds, all 3 framework × cloud combos. | 2026-05-14 |
| Q35 | Extensibility model | **Python entry points + `typing.Protocol` per extension point + first-party adapters in-tree.** 6 protocols: FrameworkAdapter / CloudAdapter / MemoryBackend / EvalJudge / HitlChannel / ToolSource. | 2026-05-14 |
| Q36 | Starter templates | **6 canonical templates in-tree** (`hello` / `chat-memory` / `rag` / `multi-agent` / `research-task` / `ops-bot`) + community templates via `--template github:user/repo`. Weekly real-cloud CI on each template. | 2026-05-14 |
| Q37 | Smaller open-question defaults | **Accepted 10 defaults** (Cognito Standard tier, OTel sampling, manifest TTL refresh, model-alias resolution table, custom-strategy size validation, GCP cold-start bench in M4, Slack approval app template, Grafana 11+ mixed sources, manifest signing deferred to v1.5, core-path CI per PR + full matrix nightly). | 2026-05-14 |

## How decisions interact

A handful of pairs are tightly coupled — changing one usually forces a re-look at the other:

- **Q2 (cloud-abstracted, framework-native) + Q5 (framework rollout)** — together define the v1 framework × cloud support matrix.
- **Q4 (cloud-native artifact) + Q6 (protocol exposure)** — together define the deployment artifact count per agent (1 on GCP, 1-or-2 on AWS).
- **Q7 (Cognito auth) + Q12 (manifest discovery)** — together define the cross-cloud A2A loop: manifest tells you the URL, Cognito tells you the JWT, A2A is the wire.
- **Q14 (memory verbs) + Q9 (catalog scope)** — verb taxonomy fixes the API surface that adapters must implement on each cloud.
- **Q17 (Task primitive) + Q21 (resilience) + Q20 (cost)** — long-running tasks compose all three: checkpoints survive transient errors, accumulate cost over hours, and respect caps.
- **Q22 (open-core) + Q23 (multi-tenancy in commercial)** — the line we draw between open and commercial.
- **Q33 (security audit) + Q34 (perf SLOs) + Q27 (LTS)** — together form the "enterprise-ready" posture distinguishing v1.0 from v0.x.
- **Q35 (plugin protocols) + Q5 (framework rollout) + Q11 (Python-only at v1)** — extension model determines how MAF lands in v3 and how a TypeScript SDK could later plug in.
- **Q32 (telemetry registry) + Q33 (SBOM) + Q34 (public bench dashboard)** — the three public-transparency artifacts that build trust without an SLA.

## Decisions deliberately NOT made yet

- **The real name** — deferred to v1.0 branding exercise (Q29).
- **CI/CD pipeline for cloudless itself** (branch strategy, release channels, pre-release flow) — conventional choices; defer to M1.
- **Logging conventions** (log levels, structured JSON, redaction defaults) — conventional choices; defer to M1.
- **Documentation site domain** — depends on naming (Q29).
- **Specific Bedrock vs Vertex LLM mapping table** (which Claude / Gemini variant maps to "claude-opus" alias) — Q37 OQ4 covers the *mechanism* (alias table maintained in cloudless); concrete values are implementation-time.
- **OpenTelemetry semantic-convention version** — pin during M1.

## How to add a new decision

1. Open a new GitHub issue tagged `architecture`.
2. Frame as a single question with a recommended answer and ≥2 alternatives with trade-offs.
3. Reference any related research, prior decisions (Q#s), and primary sources.
4. Once locked, append to this table with a Q-number and date.
5. Update `ARCHITECTURE.md` if it changes a section heading or invariant.
