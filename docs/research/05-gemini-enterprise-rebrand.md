# Research: Gemini Enterprise Agent Platform (the Vertex AI rebrand)

> Captured 2026-05-14. Vertex AI was rebranded to Gemini Enterprise Agent Platform at Google Cloud Next '26 on April 22, 2026 — about 3 weeks before this research.

## Executive summary

Vertex AI has been rebranded to **Gemini Enterprise Agent Platform** at Google Cloud Next '26 (April 22, 2026). This is **not** marketing-only — it is a genuine product restructure with new managed primitives (Agent Identity, Agent Gateway, Agent Registry, Agent Sandbox, Agent Anomaly/Threat Detection) layered on top of the existing Vertex AI infrastructure.

However, **the underlying API endpoint (`aiplatform.googleapis.com`) and core resources (Agent Engine / `reasoningEngines`, Memory Bank, Sessions, Model Garden) remain intact for backward compatibility.**

Agent Engine has been renamed "**Agent Runtime**" (and surfaces as "Deployments" in the console). ADK is alive, healthy, and at v1.33.0 — still the recommended Google framework. A2A protocol is now Linux-Foundation-governed v1.2 and natively supported across all three hyperscalers.

For cloudless: the architectural target shifts from "Vertex AI Agent Engine + ADK + Memory Bank" to "Gemini Enterprise Agent Platform (Agent Runtime + ADK + Memory Bank)" — but SDK changes are **largely additive, not breaking.**

## The product structure

Gemini Enterprise is a product **family**, not a single SKU. Three integrated layers:

1. **Gemini Enterprise Agent Platform** — the developer/builder platform (evolution of Vertex AI). Our cloudless target. Docs at `docs.cloud.google.com/gemini-enterprise-agent-platform`.
2. **Gemini Enterprise app** — no-code, end-user front door (formerly Agentspace). Designer + Inbox + Projects + Canvas + Agent Gallery. **Out of scope for cloudless** (competitive surface for no-code agents).
3. **Partner ecosystem** — Oracle, Salesforce, ServiceNow, SAP, Workday agents via Agent Gallery / Marketplace. **Potential A2A integration targets.**

## Relationship to Vertex AI

The accurate answer is **rebrand + restructure**, not parallel SKU:

> "It's the evolution of Vertex AI, bringing the model selection, model building, and agent building capabilities that customers love… Moving forward, all Vertex AI services and roadmap evolutions will be delivered exclusively through the Agent Platform, rather than as a standalone service." — Google Cloud blog

In the Console, the "Vertex AI" left-nav entry **no longer exists** — searches redirect to "Agent Platform." Custom Training, AutoML, Model Registry, Endpoints, Pipelines now appear under an "Agent Platform → Models" sub-menu.

Persona split:
- **Agent Platform** (cloudless target) = developers, ML engineers, platform engineers
- **Gemini Enterprise app** = knowledge workers, line-of-business, no-code Agent Designer

## Naming changes (no code impact)

| Old name | New name |
|---|---|
| Vertex AI | Gemini Enterprise Agent Platform |
| Vertex AI Agent Engine | Agent Runtime (UI label: "Deployments") |
| Vertex AI Evaluation Service | Split: Agent Simulation (pre-deploy) + Agent Evaluation (production) + Agent Optimizer (auto-refinement) |
| Example Store | Folded into Memory Bank + Memory Profiles |

API resource names preserved for backward compat: `reasoningEngines` is still the underlying API resource for what's now called "Agent Runtime."

## Hard deprecation: Google Gen AI SDK migration

**Critical for cloudless schedule:** the GenAI module in the legacy Vertex AI SDK is **removed June 24, 2026** (~6 weeks from this research date).

- Migrate to **Google Gen AI SDK** (`google-genai`) for model calls
- `google-cloud-aiplatform` SDK remains supported for Agent Runtime deployment via `client.agent_engines.create()`
- **Cloudless must standardize on `google-genai` for LLM adapter from M1**

## New managed primitives (architecturally significant)

These are net-new at Cloud Next '26 and represent **convergence with AWS Bedrock AgentCore**:

| Primitive | What it does |
|---|---|
| **Agent Identity** | Every agent gets cryptographic ID; least-privilege enforcement; audit trail |
| **Agent Registry** | Central catalog of approved agents/tools/skills |
| **Agent Gateway** | Unified policy enforcement; integrates **Model Armor** (prompt-injection / data-leakage protection) |
| **Agent Sandbox** | Hardened VM/container for executing model-generated code; supports Computer Use for browser automation |
| **Agent Anomaly Detection** | LLM-as-judge + statistical models for runtime behavior monitoring |
| **Agent Threat Detection** | Detects reverse shells, malicious IP connections |
| **Agent Security Dashboard** | Security Command Center integration; agent/model relationship graph; package vuln scanning |
| **Agent Studio** | Low-code visual designer (developer-facing) |
| **Agent Garden** | Pre-built agent templates |
| **Agent Observability** | Full visual execution tracing of multi-step reasoning |
| **Bidirectional Streaming** | WebSocket for real-time audio/video |
| **Long-running agent runtime** | Multi-day execution (was hard 30-min limit on Agent Engine) |

**Direct analogs to AgentCore primitives** (Identity, Gateway, Memory, Code Interpreter, Browser, Observability) are now first-class on GCP. **Notable convergence of the two hyperscaler agent stacks** — the abstraction surface area is broadly similar, so a clean common interface in cloudless is feasible.

18 new APIs to enable, including:
- `agentregistry.googleapis.com`
- `modelarmor.googleapis.com`
- `apphub.googleapis.com`
- `apptopology.googleapis.com`
- `observability.googleapis.com`

## A2A protocol stance (strengthened)

- Donated to Linux Foundation June 2025
- Current version **v1.2** under Agentic AI Foundation
- 150+ organizations in production
- Natively supported in Azure AI Foundry, Amazon Bedrock AgentCore, **and** Gemini Enterprise Agent Platform
- 22,000+ GitHub stars on `a2aproject/A2A`

**For cross-cloud frameworks: A2A is the single most important interoperability primitive — and it's vendor-neutral now, not Google-controlled.**

## ADK status

- Repos: `github.com/google/adk-python`, `adk-go`, `adk-java`, `adk-docs`, `adk-web`
- **Latest Python version: v1.33.0**, released May 8, 2026
- Release cadence: roughly bi-weekly
- Stars: 19.6k; ~2,637 commits on main
- **Languages: Python, Go, Java, JavaScript/TypeScript** — all v1.x stable
- Adoption (per Google): processes "more than six trillion tokens monthly"; Python ADK "downloaded over 7 million times"
- Stance: "Optimized for Gemini" but explicitly "model-agnostic, deployment-agnostic, and compatible with other frameworks"
- **2026 updates:** native A2A support (as sub-agents AND exposing as A2A), Code Execution sandbox, graph-based sub-agent networks

ADK is the closest analog to Strands on the AWS side.

## Pricing changes

**Gemini Enterprise app** (knowledge-worker surface — not our target) has four editions: Business / Standard / Plus / Frontline. List entry $23–30/user/month.

**Agent Platform** (developer surface — cloudless target) pricing is consumption-based, largely inherited from Vertex AI:
- Agent Runtime: **$0.0864/vCPU-hour + $0.0090/GB-hour**
- Memory Bank / Sessions: **$0.25 per 1,000 events or memories** (effective Jan 28, 2026)
- Foundation models: per token via Model Garden — Gemini 3.1 Pro/Flash, Claude Opus 4.7 / Sonnet / Haiku, Llama, DeepSeek, Mistral, Grok, Gemma 4 — **200+ models**

## Migration path

- **API endpoint unchanged:** `aiplatform.googleapis.com`. Resource names (`reasoningEngines`, datasets, endpoints, indexes) stable.
- **Hard deprecation:** GenAI module in legacy Vertex AI SDK removed **June 24, 2026.** Migrate to `google-genai`.
- **`google-cloud-aiplatform` SDK still supported** for Agent Runtime deployment via `client.agent_engines.create()`.
- **No deprecation of Agent Engine itself** — renamed only.
- Gemini 2.5 retirement on Vertex AI is a separate model-level event scheduled for October 2026.

Practical migration: (a) swap `vertexai.generative_models` for `google-genai`, (b) optionally adopt new governance primitives, (c) no forced changes to Agent Engine / Memory Bank / Sessions code paths.

## Implications for cloudless

1. **GCP endpoint is unchanged** — `aiplatform.googleapis.com`. No redirection logic needed.
2. **Target abstraction shifts from three things to one umbrella with pillars:**
   - Build (ADK + Agent Studio + Agent Garden + Sandbox)
   - Scale (Agent Runtime + Memory Bank + Sessions)
   - Govern (Identity + Registry + Gateway + Model Armor)
   - Optimize (Simulation + Evaluation + Observability + Optimizer)
3. **ADK remains recommended code-first framework.** Wrapping it doesn't contradict Google's positioning.
4. **A2A is the cross-cloud lingua franca.** Cloudless should prefer A2A over proprietary inter-agent calls.
5. **Managed-primitive abstraction surface is now roughly equivalent** across hyperscalers. Cloudless can define a common interface and map cleanly.
6. **Persona bifurcation:** cloudless maps to Agent Platform, NOT the Gemini Enterprise app.
7. **Naming dissonance:** Console says "Deployments"; SDK says `agent_engines` / `reasoningEngines`. Document this.

## Recommended architectural posture (locked in cloudless decisions)

1. Rename GCP target in docs from "Vertex AI Agent Engine + ADK + Memory Bank" to "**Gemini Enterprise Agent Platform** (Agent Runtime + ADK + Memory Bank)." Footnote the Vertex AI lineage.
2. Standardize on **Google Gen AI SDK (`google-genai`)** for model calls. Deadline: June 24, 2026.
3. Keep `google-cloud-aiplatform` for Agent Runtime deployment via `client.agent_engines.create()`.
4. **Adopt A2A v1.2 as primary inter-agent protocol.**
5. **Plan abstraction layer over new managed primitives** — Identity, Gateway, Memory, Sandbox, Observability now near-1:1 with AWS AgentCore.
6. Treat Gemini Enterprise app as **out-of-scope**.

## Classification

**Closer to (ii) genuine product restructure with new APIs than (i) marketing rebrand:**

- **(i) Pure rebrand:** top-level naming, console UI reorg, Agent Engine → Agent Runtime / Deployments. API endpoints and resource names preserved.
- **(ii) Genuine restructure:** new APIs (`agentregistry`, `modelarmor`, `apphub`, `apptopology`, `observability`), new managed primitives, upgraded ADK graph framework, long-running agent runtime, hard SDK deprecation.
- **(iii) Net-new alongside existing:** Gemini Enterprise *app* (formerly Agentspace) is genuinely separate from Agent Platform.

## Ambiguity flags

1. Google's public messaging oscillates between "evolution" and "replacement" — blog says "evolution," but console removal of Vertex AI nav + docs URL change argue "replacement."
2. SKU pricing for standalone Agent Platform governance primitives (outside the bundled Gemini Enterprise app) is not cleanly published; expect this to firm up over Q3/Q4 2026.
3. Some Google docs still reference "Vertex AI Agent Builder" — legacy moniker not fully scrubbed.

## Roadmap signals

- **Long-running agents (multi-day)** — rolling out broadly months after Next '26
- **Eighth-gen TPUs (TPU 8t / 8i)** — 80% better perf-per-dollar on inference
- **Agentic Data Cloud** — Cross-Cloud Lakehouse on Apache Iceberg can query AWS-hosted data without migration
- **AI Agent Marketplace** — partners commercialize A2A-compliant agents inside Gemini Enterprise
- **Continued non-Google model integration** — Claude Opus 4.7/Sonnet/Haiku now first-class alongside Llama, DeepSeek, Mistral, Grok
- **Workspace Studio** + tighter Microsoft 365 interop — end-user app racing toward Copilot Studio parity

## Sources

- [Introducing Gemini Enterprise Agent Platform — Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform)
- [The new Gemini Enterprise: one platform for agent development](https://cloud.google.com/blog/products/ai-machine-learning/the-new-gemini-enterprise-one-platform-for-agent-development)
- [Gemini Enterprise Agent Platform (formerly Vertex AI) — Product Page](https://cloud.google.com/products/gemini-enterprise-agent-platform)
- [Vertex AI SDK Migration Guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/deprecations/genai-vertexai-sdk)
- [Deploy an Agent — Agent Runtime docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent)
- [Agent Platform Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)
- [Google Cloud Next 26 Recap](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/google-cloud-next-26-recap/)
- [Agent2Agent protocol upgrade](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade)
- [Google Cloud donates A2A to Linux Foundation](https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/)
- [A2A 150 orgs milestone — Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)
- [adk-python on GitHub](https://github.com/google/adk-python)
- [Vertex AI Replaced by Gemini Enterprise Agent Platform — gcpstudyhub](https://gcpstudyhub.com/blog/vertex-ai-replaced-by-gemini-enterprise-agent-platform)
- [Forrester: Google Cloud Next 2026 — End of AI Pilot Era](https://www.forrester.com/blogs/google-cloud-next-2026-the-end-of-the-ai-pilot-era/)
- [Gemini Enterprise Licensing Guide 2026 — Redress Compliance](https://redresscompliance.com/google-gemini-enterprise-licensing-guide-2026.html)
- [Gemini Enterprise Agent Platform adds connective tissue to Vertex AI — TechTarget](https://www.techtarget.com/searchitoperations/news/366642175/Gemini-Enterprise-Agent-Platform-adds-connective-tissue-to-Vertex-AI)
- [a2aproject/A2A on GitHub](https://github.com/a2aproject/A2A)
