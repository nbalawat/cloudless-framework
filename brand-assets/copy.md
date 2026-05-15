# cloudless marketing copy

Approved copy. Don't ad-lib — pull from here.

---

## Tagline (the one)

> **Write your agent once. Ship it to any cloud.**

Always 7 words. Always a period after "once". Always present-tense verbs.

## Sub-taglines (pick one for context)

- "One agent. Any cloud. Zero rewrites."
- "AWS Bedrock AgentCore and GCP Vertex AI in one Python file."
- "Cloud-portable agents — without the cloud-portability tax."
- "An agent framework that doesn't pick your cloud for you."
- "Real-cloud tested. Apache 2.0."

## Elevator pitch (1 paragraph)

> cloudless is a Python framework for building production agents that
> deploy unchanged to AWS Bedrock AgentCore or GCP Vertex AI Agent Engine.
> You write your agent once — in **LangGraph, Strands, Google ADK, Anthropic
> Claude Agent SDK, or Microsoft Agent Framework** — and `cloudless deploy`
> handles the cloud-native runtime, identity, memory, secrets, observability,
> and cross-cloud A2A wiring. No mocked tests; every primitive — and every
> framework — is validated against real cloud.

## One-liner (for headers)

> A Python framework for agents that ship to AWS Bedrock AgentCore and GCP
> Vertex AI Agent Engine — unchanged.

## Tweet pitch

> cloudless — write your agent once, ship to AWS Bedrock AgentCore or GCP
> Vertex AI without rewriting. **5 frameworks × 2 clouds = 10 cells**:
> LangGraph, Strands, Google ADK, Anthropic Claude Agent SDK, Microsoft
> Agent Framework — each running on both clouds. cloudless ships the
> cross-cloud bridges (no LiteLLM, no shims). Multi-modal, HITL, 10
> multi-agent patterns. 543 tests passing. Apache 2.0.
>
> github.com/nbalawat/cloudless-framework

## Feature blurbs (~25 words each)

### Two clouds, one codebase

Deploy the same `@cloudless.agent` class to AWS Bedrock AgentCore or GCP
Vertex AI Agent Engine. Pick the cloud at `cloudless deploy` time.

### Real cloud, not mocks

Every primitive — LLM, Memory, Sandbox, Tools, A2A, Vector — has a real-cloud
integration test. 537 passing tests; zero skipped. We test what we ship.

### Five frameworks × two clouds, all native

LangGraph, Strands Agents, Google ADK, Anthropic Claude Agent SDK, or Microsoft
Agent Framework — each works on both AWS Bedrock and GCP Vertex AI. Where the
framework's first-party SDK ships only one cloud, cloudless ships a native
bridge (no LiteLLM, no OpenAI shim). Every cell real-cloud validated.

### Multi-modal in, multi-modal out

Pass `images=`, `videos=`, `audios=` to `cloudless.LLM.invoke`. Gemini
gets all three; Bedrock gets images + video. One API across clouds.

### True async, real parallelism

`asyncio.gather` actually parallelizes — both Bedrock and Vertex sync
clients are wrapped via `asyncio.to_thread`. Verified 1.3-2.5× speedup
in the integration tests.

### Governance, portable

`@cloudless.policy` hooks run regardless of cloud. Bedrock Guardrails +
Vertex Model Armor + `safety_settings` all flow through one API. Every
decision lands in a pluggable audit sink.

### Cross-cloud A2A built in

`ctx.peer("orders").call(prompt)` works across clouds. Auth is your
choice: Cognito M2M JWT, SigV4 signing, or OAuth 3-legged for
end-user-scoped tools.

### Ten orchestration patterns, both clouds

Sequential, routing, parallel, supervisor, hierarchical, A2A peer,
map-reduce, debate, evaluator-optimizer, tool-as-agent — every pattern
tested with HITL pause-and-resume against both Bedrock and Vertex.

### Grounding + search + custom datastores

`grounding=True` enables Google Search citation; pass a Vertex AI Search
datastore resource name to ground against your own corpus.

## README hero (markdown)

```markdown
# cloudless

> **Write your agent once. Ship it to any cloud.**

A Python framework for agents that ship to AWS Bedrock AgentCore and GCP
Vertex AI Agent Engine — unchanged. Bring LangGraph, Strands, Google ADK,
Anthropic Claude Agent SDK, or Microsoft Agent Framework.

[Install](#install) · [Quickstart](#quickstart) · [Docs](https://cloudless.dev) · [Examples](./examples)
```

## Conference / podcast bio (50 words)

> cloudless is an open-source Python framework for production AI agents
> that deploy to either AWS Bedrock AgentCore or GCP Vertex AI Agent
> Engine without rewriting. Built around a service catalog (LLM, Memory,
> Sandbox, Tools, Vector, A2A) with adapters for both clouds. Every
> primitive is validated against real cloud — no mocks.

## Banned words

Don't use these in any cloudless copy:

- leverage / leveraging / leveraged
- powered by
- harness / harnessing
- empower / empowering
- next-generation / next-gen
- cutting-edge
- state-of-the-art
- world-class / industry-leading / best-in-class
- revolutionary / game-changing / disruptive
- AI-powered (we're FOR agents, but our product is a framework, not "AI-powered")
- democratize / democratizing
- seamless / seamlessly
