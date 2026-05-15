---
hide:
  - navigation
  - toc
title: cloudless — write your agent once, ship it to any cloud
---

<div class="cl-hero" markdown>

# cloudless<span class="cl-dot">.</span>

<p class="tagline">Write your agent once. Ship it to any cloud.</p>

<div class="cl-cta">
  <a class="primary" href="getting-started/quickstart/">Start in 5 min</a>
  <a class="ghost" href="https://github.com/cloudless/cloudless">GitHub</a>
</div>

</div>

A Python framework for production AI agents that deploy unchanged to
**AWS Bedrock AgentCore** or **GCP Vertex AI Agent Engine**. Bring LangGraph,
Strands, or ADK. Cloudless handles the cloud-native runtime, identity, memory,
secrets, observability, and cross-cloud A2A wiring.

<div class="cl-stats" markdown>
<div class="cl-stat"><span class="num">2</span><span class="label">clouds</span></div>
<div class="cl-stat"><span class="num">15+</span><span class="label">primitives</span></div>
<div class="cl-stat"><span class="num">504</span><span class="label">tests passing</span></div>
<div class="cl-stat"><span class="num">0</span><span class="label">mocks</span></div>
</div>

```python
import cloudless

@cloudless.agent(name="hello", framework="langgraph", interfaces=["http", "a2a"])
class HelloAgent(cloudless.LangGraphAgent):
    def build(self):
        return self.llm_pipeline()  # any LangGraph StateGraph
```

```bash
$ cloudless deploy hello
✓ Built artifact (98s)
✓ Created AgentCore runtime: arn:aws:bedrock-agentcore:us-east-1:...
✓ DEFAULT endpoint → version 1
```

Swap `aws` for `gcp` in `cloudless.yaml` and the same code deploys to
Vertex AI Agent Engine instead.

---

## Why cloudless

<div class="cl-features" markdown>

<div class="cl-feature" markdown>
### <span class="cl-spark-dot"></span> Two clouds, one codebase

Deploy the same `@cloudless.agent` class to AWS Bedrock AgentCore or GCP
Vertex AI. Pick at `cloudless deploy` time — no rewrites.
</div>

<div class="cl-feature" markdown>
### <span class="cl-spark-dot"></span> Real cloud, not mocks

Every primitive — LLM, Memory, Sandbox, Tools, A2A — has a real-cloud
integration test. **437 passing tests, zero skipped.**
</div>

<div class="cl-feature" markdown>
### <span class="cl-spark-dot"></span> Frameworks, your choice

LangGraph, Strands Agents, or Google ADK. Cloudless adapts each to the
cloud's deployment model so your framework code stays untouched.
</div>

<div class="cl-feature" markdown>
### <span class="cl-spark-dot"></span> Multi-agent patterns

All 10 canonical patterns — sequential, routing, parallel, supervisor,
hierarchical, A2A, map-reduce, debate, evaluator-optimizer, tool-as-agent —
tested across both clouds with HITL.
</div>

<div class="cl-feature" markdown>
### <span class="cl-spark-dot"></span> Governance, portable

`@cloudless.policy` runs regardless of cloud. Bedrock Guardrails attach
automatically when configured. Every decision lands in a pluggable audit sink.
</div>

<div class="cl-feature" markdown>
### <span class="cl-spark-dot"></span> Cross-cloud A2A

`ctx.peer("orders").call(prompt)` mints a Cognito M2M JWT and issues an
A2A v0.3 message — even if "orders" lives on the other cloud.
</div>

</div>

---

## Quickstart

```bash
pip install cloudless[langgraph,aws]
cloudless init my-app --framework langgraph
cd my-app
cloudless doctor                    # preflight checks
cloudless dev hello                 # local server on :8080
cloudless deploy hello              # ~100s to live AgentCore runtime
cloudless logs hello --follow       # CloudWatch streaming
```

See the [5-minute quickstart](getting-started/quickstart.md) for the full walkthrough,
or [browse the concepts](concepts/index.md) for the deep dive.

---

## Trusted by serious systems

cloudless is **pre-1.0 alpha** — public APIs may shift until v1.0. Real-world
production deployment is welcomed but not yet recommended for mission-critical
systems. The path to v1.0 is documented in [`docs/ROADMAP.md`](ROADMAP.md).

License: **Apache 2.0**.

[Get started](getting-started/quickstart.md){ .md-button .md-button--primary }
[Read the architecture](ARCHITECTURE.md){ .md-button }
