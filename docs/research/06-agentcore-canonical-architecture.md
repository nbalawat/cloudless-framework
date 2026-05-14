# AWS Bedrock AgentCore — Canonical Architecture (from AWS diagram)

> User-provided AWS architecture diagram, 2026-05-14. Source-of-truth on what
> AgentCore offers — supersedes/extends the research-derived dossier
> in `01-agentcore-runtime.md` and `02-agentcore-primitives.md` where
> there's a conflict.

## Visual reference

```
        ┌──────────────────────────────────────────────────────────────┐
        │  Agent                                                       │
        │  Any framework, any model, all popular protocols             │
        └────────┬─────────────────────────────────────────────┬───────┘
                 │ Build                                       │ Deploy
                 ▼                                             ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │ AgentCore                                                        │
    │                                                                  │
    │   ┌──────────┐  ┌──────────┐  ┌──────────────────────────────┐   │
    │   │ Harness  │  │   CLI    │  │            SDK                │   │
    │   │ Models,  │  │ Strands, │  │ Strands, models, tools,       │   │
    │   │ tools,   │  │ models,  │  │ skills, memory                │   │
    │   │ skills,  │  │ tools,   │  │                               │   │
    │   │ memory   │  │ skills,  │  │                               │   │
    │   │          │  │ memory   │  │                               │   │
    │   └──────────┘  └──────────┘  └──────────────────────────────┘   │
    │                                                                  │
    │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
    │   │ Built-in │ │ Gateway  │ │ Identity │ │  Memory  │            │
    │   │  tools   │ │          │ │          │ │          │            │
    │   │          │ │ APIs,    │ │ Inbound  │ │ Short &  │            │
    │   │ Browser, │ │ Lambda   │ │ and      │ │ Long-    │            │
    │   │ Code     │ │ fns,     │ │ outbound │ │ term     │            │
    │   │ inter-   │ │ config   │ │ auth     │ │ memory   │            │
    │   │ preter,  │ │ bundles  │ │          │ │          │            │
    │   │ KB,      │ │          │ │          │ │          │            │
    │   │ Search   │ │          │ │          │ │          │            │
    │   └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
    │                                                                  │
    │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
    │   │ Policy   │ │ Payments │ │ Registry │ │ Runtime  │            │
    │   │          │ │          │ │          │ │          │            │
    │   │ Authn    │ │ Auto-    │ │ Agents,  │ │ Agents,  │            │
    │   │ control  │ │ mate     │ │ MCP      │ │ tools    │            │
    │   │          │ │ micro-   │ │ servers, │ │          │            │
    │   │          │ │ trans-   │ │ Tools,   │ │          │            │
    │   │          │ │ actions  │ │ Skills   │ │          │            │
    │   └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
    │                                                                  │
    │   ┌─────────────────────────┐  ┌──────────────────────────────┐  │
    │   │     Observability       │  │        Evaluations            │  │
    │   │     Monitor and debug   │  │ Batch evals, online eval     │  │
    │   │                         │  │ configs, custom evaluators   │  │
    │   └─────────────────────────┘  └──────────────────────────────┘  │
    └──────────────────────────────────────────────────────────────────┘
              ▲                                            │
              │ Assess ◄───────────────────────────────────┘
```

## Canonical AgentCore offering — itemized

### Entry points (three parallel access paths)

| Entry | What it surfaces |
|---|---|
| **Harness** | Models, tools, skills, memory. *New to my mental model — not covered in research dossiers. Worth a follow-up spike.* |
| **CLI** | Strands, models, tools, skills, memory. *The `agentcore` CLI we used in Spikes 1, 2.* |
| **SDK** | Strands, models, tools, skills, memory. *The `bedrock-agentcore` Python SDK we used in Spikes 1, 2.* |

### Eight primitives (the core service surface)

| # | Primitive | What it covers (per diagram) | Coverage in research dossiers / spikes |
|---|---|---|---|
| 1 | **Built-in tools** | **Browser, Code interpreter, Knowledge Bases, Search** | Dossier 02 had Browser + Code Interpreter only — **Knowledge Bases + Search were under-covered.** |
| 2 | **Gateway** | APIs, Lambda functions, configuration bundles | Dossier 02 covers thoroughly. |
| 3 | **Identity** | Inbound and outbound authentication | Validated in Spike 2 (Cognito inbound). |
| 4 | **Memory** | Short & long-term memory | Covered in dossier 02 (5 strategies). |
| 5 | **Policy** | Authorization control | Mentioned briefly in dossier 01 (Cedar-based, re:Invent 2025). **Treat as a real first-class primitive, not optional.** |
| 6 | **Payments** | Automate microtransactions | **NEW in my model.** Aligns with AP2 (Agent Payments Protocol) the user surfaced. Coinbase CDP + Stripe/Privy wallets per dossier 01 roadmap. |
| 7 | **Registry** | Agents, **MCP servers**, Tools, Skills | **Broader than I had captured.** I'd treated Registry as agent-catalog only. It also catalogs MCP servers + tools + skills — directly impacts Q12 (service discovery) and Q15 (tool model). |
| 8 | **Runtime** | Agents, tools | Spike 1, 2, 10 all validated this. |

### Cross-cutting concerns (bottom row)

| Layer | Scope |
|---|---|
| **Observability** | Monitor and debug — spans every primitive |
| **Evaluations** | Batch evals, online eval configs, custom evaluators — spans every primitive |

Both align with cloudless Q8 (own portable offline + OTel everywhere online).

### Lifecycle annotations

The diagram explicitly calls out three lifecycle stages flowing in/out of the agent:
- **Build** — the `Harness`/`CLI`/`SDK` paths feed in here
- **Deploy** — points down into AgentCore
- **Assess** — feeds back up from `Observability` + `Evaluations`

Build/Deploy/Assess is AWS's framing of the agent loop. cloudless's milestone names (M1 Bones / M3 Production primitives / M4 Operational maturity) overlap with this — `Build`, `Deploy`, `Assess` map approximately to our M1, M2-M3, and M4 work.

## Deltas vs. my earlier research

### Things I had wrong or under-scoped

1. **Built-in tools = 4 items, not 2.** Knowledge Bases and Search are first-class. These compete with cloudless's planned VectorStore primitive (Q9) — we should explicitly decide whether to wrap AgentCore Knowledge Bases as the AWS-side VectorStore implementation, or treat them as separate concerns.

2. **Payments is a real GA primitive.** I had it as "preview / niche." It's drawn in the same row as Memory, Identity, Gateway — i.e. AWS positions Payments as core, not extra. **Cloudless implication:** consider exposing a `cloudless.Payments` service-catalog primitive (v2+ scope per ROADMAP, but mark it now).

3. **Registry catalogs MCP servers + Skills, not just agents.** The Q12 service-discovery story stands (we keep our own manifest), but the Registry-sync path (Q12 optional sync) should consider syncing MCP server registrations too.

4. **Harness is a third entry point.** I'd been thinking CLI + SDK only. Harness likely competes with cloudless's CLI/SDK approach — need to understand the model.

5. **Policy is more prominent than I treated it.** Two layers in my Q19 governance design map cleanly to AgentCore Policy (cloud-native layer); the alignment is even stronger than I thought.

## Implications for cloudless v1 design (no decisions changed; some scope clarified)

| Cloudless decision | Status after this diagram |
|---|---|
| Q9 v1 service catalog (8 primitives + 3 pulled in) | Still right; Knowledge Bases + Search merit consideration as ways to *implement* VectorStore on AWS, not as separate primitives. |
| Q15 Tool model (multi-source Tool.from_*) | Still right; Registry-sync now also syncs MCP servers registered via `Tool.from_mcp_server()`. |
| Q19 Governance (two-layer) | Strengthened — AgentCore Policy is GA, our `@cloudless.policy` decorator stays as the portable layer above. |
| Q12 Service discovery | Manifest-in-repo stays primary; optional sync to AWS Registry now covers agents + MCP + tools + skills, not just agents. |
| ROADMAP non-goals | Payments stays deferred (v2+). Add a tracking note that AgentCore Payments is GA. |

## Action items

1. **Add `cloudless.Payments` (placeholder) to the service catalog plan** for v2. AP2 protocol + AgentCore Payments + GCP equivalents (not announced yet but likely coming). Banking use cases — high enterprise interest.

2. **Spike follow-up — investigate Harness.** It's listed as a peer to CLI and SDK; we haven't engaged with it. May be a no-code path that cloudless's CLI/SDK overlaps with. Add to Phase 0 backlog.

3. **Revisit Knowledge Bases vs VectorStore.** Cloudless's v1.5-scoped VectorStore primitive (now pulled into v1) should specifically map to AgentCore Knowledge Bases on the AWS side, not raw OpenSearch — KB gives chunking, embedding, retrieval, and source attribution out of the box.

4. **Add Search to the catalog roadmap.** AgentCore's `Search` built-in tool is probably backed by Bedrock-managed web search. Cloudless's GCP-side equivalent likely uses Google's grounding APIs. Worth a future primitive `cloudless.WebSearch`.

5. **Audit Registry's scope.** When cloudless implements optional Registry sync, sync all four: agents (Q12), MCP servers (Q15), Tools (Q15), and any user-defined Skills.

## Sources

- User-provided AWS architecture diagram, 2026-05-14
- Cross-referenced with dossiers `01-agentcore-runtime.md` and `02-agentcore-primitives.md`
- Aligned with AP2 protocol context the user surfaced earlier in this session
