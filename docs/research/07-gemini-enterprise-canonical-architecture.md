# Gemini Enterprise Agent Platform — Canonical Architecture

> User-provided official Google diagram, 2026-05-14. Source-of-truth on
> what Gemini Enterprise Agent Platform offers. Supersedes/extends the
> research-derived dossier `05-gemini-enterprise-rebrand.md` where they
> diverge.

## Visual reference

```
┌───────────────────────── ✦ Gemini Enterprise Agent Platform ─────────────────────────┐
│                                                                                       │
│  ┌──────────────────────────────────── BUILD ────────────────────────────────────┐    │
│  │                                                                                │    │
│  │  ┌────────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌─────────┐ │    │
│  │  │ Agent Development  │ │ 3P agent         │ │ Agent Studio     │ │ Agent   │ │    │
│  │  │ Kit         [New]  │ │ frameworks       │ │           [New]  │ │ Garden  │ │    │
│  │  └────────────────────┘ └──────────────────┘ └──────────────────┘ └─────────┘ │    │
│  │                                                                                │    │
│  │  ── Gemini API and Model Garden ──    ── Tools, data, and other agents ──     │    │
│  │  ┌──────────────┐ ┌──────────────┐    ┌──────┐ ┌─────────┐ ┌──────┐           │    │
│  │  │ Gemini       │ │ 3P and open  │    │ A2A  │ │Grounding│ │ RAG  │           │    │
│  │  │ models       │ │ models       │    └──────┘ └─────────┘ └──────┘           │    │
│  │  └──────────────┘ └──────────────┘    ┌──────┐ ┌─────────┐ ┌─────────────┐    │    │
│  │  ┌──────────────┐ ┌──────────────┐    │ MCP  │ │  Search │ │ APIs/conn   │    │    │
│  │  │ Model        │ │ Model        │    └──────┘ └─────────┘ └─────────────┘    │    │
│  │  │ training     │ │ inference    │    ┌──────┐ ┌─────────┐ ┌─────────────┐    │    │
│  │  └──────────────┘ └──────────────┘    │A2UI  │ │ AP2/UCP │ │ Cloud Mkt   │    │    │
│  │                                       └──────┘ └─────────┘ └─────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                       │
│  ┌──────────────────────────────────── SCALE ────────────────────────────────────┐    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐    │    │
│  │  │ Agent Runtime │ │ Agent Sessions│ │ Agent Sandbox │ │ Agent Memory   │    │    │
│  │  │          [GA] │ │          [GA] │ │          [GA] │ │ Bank      [GA] │    │    │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                       │
│  ┌──────────────────────────────────── GOVERN ───────────────────────────────────┐    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐    │    │
│  │  │ Agent Gateway │ │ Agent Identity│ │ Agent Registry│ │ Agent Anomaly  │    │    │
│  │  │         [New] │ │          [GA] │ │         [New] │ │ Detection[New] │    │    │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └────────────────┘    │    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐    │    │
│  │  │ Model Armor   │ │ Agent Policy  │ │ Agent Security│ │ Agent          │    │    │
│  │  │               │ │               │ │         [New] │ │ Compliance     │    │    │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                       │
│  ┌──────────────────────────────────── OPTIMIZE ─────────────────────────────────┐    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐    │    │
│  │  │ Agent         │ │ Agent         │ │ Agent         │ │ Agent          │    │    │
│  │  │ Evaluation    │ │ Simulation    │ │ Observability │ │ Optimizer      │    │    │
│  │  │         [New] │ │         [New] │ │         [New] │ │         [New]  │    │    │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## Canonical Gemini Enterprise offering — itemized by pillar

### Build (frameworks, models, tools/data)

**Frameworks and design tools:**
| Component | Status | Notes |
|---|---|---|
| Agent Development Kit | **New** | The Google ADK — Python/Go/Java/JS. v1.33.0 as of May 2026. |
| 3P agent frameworks | — | LangGraph, LangChain, LlamaIndex, AG2/Autogen, custom. |
| Agent Studio | **New** | Low-code visual designer (developer-facing). |
| Agent Garden | — | Pre-built agent templates. |

**Gemini API and Model Garden:**
| Component | Notes |
|---|---|
| Gemini models | Gemini 3.1 Pro/Flash; 200+ models in Model Garden. |
| 3P and open models | Claude (Opus 4.7 / Sonnet / Haiku), Llama, DeepSeek, Mistral, Grok, Gemma 4. |
| Model training | Fine-tuning / customization. |
| Model inference | Hosted inference. |

**Tools, data, and other agents:**
| Component | Notes |
|---|---|
| **A2A** | Agent2Agent protocol — first-class. v1.2 under Linux Foundation. |
| **Grounding** | Google Search / proprietary data grounding for hallucination reduction. |
| **RAG** | Managed retrieval-augmented generation. |
| **MCP** | Model Context Protocol — tool-call interop. |
| **Search** | Google web search as an agent tool. |
| **APIs and connectors** | Pre-built connectors to Workspace, Salesforce, SAP, etc. |
| **A2UI** | **NEW IN MY MODEL.** Agent-to-UI rendering protocol (agent produces UI artifacts the host renders — analogous to Anthropic's Artifacts). Not present in AgentCore. |
| **AP2 and UCP** | Agent Payments Protocol + Universal Commerce Protocol — A2A commerce extensions. |
| **Cloud Marketplace** | Build-time integration with GCP Marketplace catalog. |

### Scale (deployment runtime layer — all GA)

| Component | Maps to AgentCore | Status |
|---|---|---|
| **Agent Runtime** | AgentCore Runtime | **GA** |
| **Agent Sessions** | (folded into AgentCore Runtime via runtimeSessionId) | **GA** |
| **Agent Sandbox** | AgentCore Code Interpreter | **GA** |
| **Agent Memory Bank** | AgentCore Memory | **GA** |

All four Scale primitives are GA. This is the layer cloudless's deploy adapter targets on GCP.

### Govern (8 sub-primitives — wider surface than AgentCore's 3)

| Component | Maps to AgentCore | Status |
|---|---|---|
| **Agent Gateway** | AgentCore Gateway | **New** |
| **Agent Identity** | AgentCore Identity | **GA** |
| **Agent Registry** | AgentCore Registry | **New** |
| **Agent Anomaly Detection** | (no AgentCore equivalent) | **New** — GCP-only |
| **Model Armor** | (Bedrock Guardrails on AWS — similar role) | — |
| **Agent Policy** | AgentCore Policy (Cedar) | — |
| **Agent Security** | (Security Command Center integration on GCP) | **New** — GCP-only as a packaged primitive |
| **Agent Compliance** | (no AgentCore equivalent) | — |

**This is bigger than my Q19 abstraction allowed for.** Q19 was a two-layer model (cloud-native guardrails + `@cloudless.policy`). On GCP the Govern pillar has 8 distinct components. Cloudless's adapter needs to expose Anomaly Detection + Compliance + Security as additional capability flags, not fold them all into "guardrails."

### Optimize (Agent Optimizer is the wildcard)

| Component | Maps to AgentCore | Status |
|---|---|---|
| **Agent Evaluation** | AgentCore Evaluations (production evals) | **New** |
| **Agent Simulation** | (no direct AgentCore equivalent — pre-deploy synthetic) | **New** |
| **Agent Observability** | AgentCore Observability | **New** |
| **Agent Optimizer** | (no AgentCore equivalent) | **New** — GCP-only, auto-refinement of prompts/agents |

Agent Optimizer is interesting — auto-refining prompts based on production traces is genuinely novel. No AgentCore equivalent. **Potential cloudless v2 differentiator if we wrap it.**

## Cross-cloud parallel primitive map

Updated mapping for cloudless's service catalog (Q9 + Q23 multi-region):

| Cloudless primitive | AWS (AgentCore) | GCP (Gemini Enterprise) | Notes |
|---|---|---|---|
| `cloudless.LLM` | Bedrock + inference profiles | Gemini API + Model Garden | F1 + F2 captured the gotchas |
| `cloudless.Memory` | Memory | Agent Memory Bank | Both GA; semantic-verb API hides strategy differences (Q14) |
| `cloudless.VectorStore` (RAG) | Built-in: Knowledge Bases | Build: RAG | **Map cloudless.VectorStore to Knowledge Bases on AWS, not raw OpenSearch** |
| `cloudless.WebSearch` (v2) | Built-in: Search | Build: Search | Future primitive |
| `cloudless.Grounding` (v2?) | (none) | Build: Grounding | GCP-only feature; cloudless adapter could degrade gracefully |
| `cloudless.Identity` | Identity | Agent Identity | Both GA. Q7 Cognito layer sits above. |
| `cloudless.Gateway` / `cloudless.Tool` | Gateway | Agent Gateway | F11a single-mode/runtime applies to Gateway too — verify in a spike |
| `cloudless.Sandbox` | Built-in: Code interpreter | Agent Sandbox | Both GA |
| `cloudless.Browser` | Built-in: Browser | (Computer Use via Sandbox) | Shape mismatch — feature flag (Q9 v1.5) |
| `cloudless.Runtime` (deploy target) | Runtime | Agent Runtime | Q4 cloud-native artifact per cloud |
| `cloudless.Registry` (v2 sync) | Registry | Agent Registry | Both register agents + MCP servers + tools + skills |
| `@cloudless.policy` layer | Policy + Bedrock Guardrails | Agent Policy + Model Armor + Anomaly Detection + Security + Compliance | **GCP has 5 distinct primitives here vs AWS's 2 — Q19 needs an extension** |
| `cloudless.Payments` (v2+) | Payments | AP2 + UCP (Build-time) | Different shape — AgentCore Payments is an operations primitive; GCP AP2/UCP are protocols at the Build layer |
| `cloudless.Observability` | Observability | Agent Observability | OTel everywhere (Q8) |
| Eval framework | Evaluations | Agent Evaluation + Simulation + Optimizer | Q8 owned by cloudless; native dashboards optional |
| **A2UI** (no cloudless mapping yet) | — | A2UI | **NEW — consider for v2+. Agent emitting UI artifacts.** |

## Key deltas vs research dossier 05 (Gemini Enterprise rebrand)

1. **A2UI surfaced as a Build-pillar primitive.** I hadn't captured this; it's analogous to Anthropic Artifacts in concept. No AgentCore equivalent. **Add to roadmap as a future cloudless primitive** if A2UI gains traction across cloud + framework boundaries.

2. **Govern pillar has 8 sub-primitives.** My research had 5-6. The new ones I missed:
   - Agent Compliance (probably packaged compliance attestations / pre-built FedRAMP/HIPAA controls)
   - Agent Security (Security Command Center integration as a packaged primitive)

3. **Agent Optimizer is real.** Auto-refinement of prompts/agents based on production traces. No AgentCore equivalent. Notable cloudless differentiator opportunity in v2.

4. **Cloud Marketplace** is a Build-pillar integration. Means GCP-deployed cloudless agents could be listed on GCP Marketplace as customer-purchasable agents. Tracks with the commercial-tier (Q22) vision.

5. **Search is a first-class Build-pillar tool** alongside Grounding and RAG. Three distinct retrieval primitives on GCP vs. AgentCore's two (Knowledge Bases + Search). Cloudless's "RAG" abstraction needs to acknowledge this richer GCP surface.

## Implications for cloudless v1 design (refinements; no decisions changed)

| Cloudless decision | Refinement after this diagram |
|---|---|
| Q9 v1 catalog (8 + 3 pulled-in) | Stands. `cloudless.VectorStore` on AWS → wrap AgentCore Knowledge Bases (preferred over raw OpenSearch). |
| Q19 Governance two-layer | **Expand** — cloud-native sub-layer now has 5+ components on GCP (Policy/Armor/Anomaly/Security/Compliance) and 2 on AWS (Policy/Guardrails). Cloudless config maps to all of them; surface capability flags for cloud-specific extras (Anomaly/Compliance on GCP). |
| Q15 Tool model | Stands. MCP-everywhere abstraction matches both clouds. |
| Q12 Service discovery | Stands; sync to both Registries (which both catalog agents + MCP + tools + skills). |
| ROADMAP | Add tracking notes: A2UI, Agent Optimizer, Search/Grounding as primitives to consider in v2+. |

## Action items

1. **Update `cloudless.VectorStore` plan:** AWS-side implementation = AgentCore Knowledge Bases (managed RAG with chunking/embedding/retrieval), not raw OpenSearch. GCP-side = Vertex's RAG primitive.

2. **Extend `cloudless.yaml` governance schema** (post-M1) to surface GCP's Anomaly Detection + Compliance + Security as capability flags. AWS users see them as "GCP-only" features.

3. **Add A2UI to the v2+ roadmap** as `cloudless.UI` exploratory primitive — agent produces UI artifacts, host renders. Track adoption; defer until cross-platform standardization.

4. **Add Agent Optimizer to v2+ roadmap.** Auto-refining prompts from prod traces is a genuine differentiator if cloudless wraps it; would require building an AWS-side equivalent (could be built on top of AgentCore Evaluations + Bedrock as the "optimizer LLM").

5. **AP2/UCP are protocols at the Build layer on GCP, not deploy primitives.** Cloudless's `cloudless.Payments` (v2+) needs to handle the protocol layer (AP2 client) AND optionally wrap AgentCore Payments + GCP commerce APIs underneath.

## Sources

- User-provided official Google diagram, 2026-05-14
- Cross-referenced with `05-gemini-enterprise-rebrand.md`
- Cross-cloud paired with `06-agentcore-canonical-architecture.md`
