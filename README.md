# cloudless

> Write your agent once. Ship it to any cloud.

**cloudless** is a Python SDK + CLI for building agentic AI applications that deploy
unchanged to **AWS Bedrock AgentCore** or **GCP Vertex AI Agent Runtime** ("Gemini
Enterprise Agent Platform"), with first-class cross-cloud agent-to-agent (A2A)
collaboration.

Status: **v0.x — internal alpha**. All 13 service-catalog primitives are real-cloud
validated (see [`docs/CERTIFICATION.md`](./docs/CERTIFICATION.md)). Public APIs may
break until v1.0.

---

## Five-minute quickstart

```bash
pip install cloudless[langgraph,aws]
cloudless init my-app --framework langgraph
cd my-app
cloudless doctor                         # preflight: verify creds + env
cloudless dev hello                      # local server on :8080, real Bedrock
curl -X POST localhost:8080/invocations -d '{"prompt": "hi"}'
cloudless deploy hello                   # ships to AWS AgentCore (~100s)
cloudless logs hello --follow
```

For GCP, swap `[aws]` for `[gcp]` and run `cloudless deploy hello` after
`gcloud auth application-default login`.

---

## What ships in v0.x

| Layer | Capability | Status |
|---|---|---|
| Frameworks | LangGraph, Strands Agents | ✅ |
| Frameworks | Google ADK | partial (GCP-only) |
| Frameworks | Microsoft Agent Framework | deferred to v3 |
| Service catalog | LLM (Bedrock Nova/Claude, Vertex Gemini) — async via `asyncio.to_thread` | ✅ |
| Service catalog | Multi-modal LLM input — `images=`, `videos=`, `audios=` | ✅ |
| Service catalog | Embeddings — Bedrock Titan/Cohere, Vertex `text-embedding-005`, `task_type`, `output_dimensionality` | ✅ |
| Service catalog | Memory — AgentCore + Memory Bank + Vertex Sessions; `recall_facts`, `recall_facts_cross_actor`, `export_facts` / `import_facts` | ✅ |
| Service catalog | Secrets — AWS Secrets Manager, GCP Secret Manager, local file | ✅ |
| Service catalog | Sandbox — AgentCore Code Interpreter + local subprocess; `upload_file` / `download_file` / `execute_long_running` | ✅ |
| Service catalog | VectorStore — Bedrock Knowledge Bases, Vertex AI Search, in-memory | ✅ |
| Service catalog | Tools — function / Lambda / OpenAPI / MCP + AgentCore Gateway (Lambda + OpenAPI targets) | ✅ |
| Deploy | AWS AgentCore Runtime — HTTP, SSE streaming, A2A protocol modes | ✅ |
| Deploy | GCP Vertex Agent Runtime via Agent Engines + `stream_query` | ✅ |
| Cross-cloud | A2A v0.3 — Cognito JWT, SigV4, OAuth 3LO end-user auth; agent-card publication; SSE streaming | ✅ |
| Governance | `@cloudless.policy` 6-stage hooks + Bedrock Guardrails + Vertex `safety_settings` + Model Armor | ✅ |
| Governance | Audit log with pluggable sinks (Structlog / File / InMemory) | ✅ |
| Resilience | retry / timeout / circuit-breaker (Q21) | ✅ |
| Observability | structlog + OTel spans + X-Ray + Cloud Trace + CloudWatch metrics + Cloud Monitoring | ✅ |
| Cost | per-model pricing + A2A attribution propagation + persistent JSONL sink | ✅ |
| HITL | `PauseChunk` + InMemory / AgentCore Memory / Vertex Memory Bank task stores | ✅ |
| Multi-agent | 10 canonical patterns validated on both clouds with HITL | ✅ |
| Grounding | Google Search + Vertex AI Search datastore + Gemini cached_content | ✅ |
| CLI | `init / dev / deploy / logs / versions / rollback / eval / cost / doctor / security / cleanup` | ✅ |

Complete primitive list and pass/fail per real-cloud test: see
[`docs/CERTIFICATION.md`](./docs/CERTIFICATION.md).

---

## Authoring an agent

```python
# src/agents/hello.py
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model

import cloudless


class State(TypedDict):
    messages: list


@cloudless.agent(name="hello", framework="langgraph", interfaces=["http", "a2a"])
class HelloAgent(cloudless.LangGraphAgent):
    def build(self):
        llm = init_chat_model("us.amazon.nova-micro-v1:0", model_provider="bedrock_converse")
        g = StateGraph(State)
        g.add_node("chat", lambda s: {"messages": [llm.invoke(s["messages"])]})
        g.add_edge(START, "chat")
        g.add_edge("chat", END)
        return g.compile()
```

```yaml
# cloudless.yaml
project: my-app
default_cloud: aws

agents:
  hello:
    cloud: aws
    framework: langgraph
    interfaces: [http, a2a]

service_catalog:
  llm: {provider: bedrock, model: nova-micro}
  memory: {strategy: semantic, retention_days: 90}

policies:
  cost_cap_usd_per_session: 5.0
  retries: {attempts: 3, backoff_seconds: 0.25}
```

That's it. `cloudless deploy hello` packages the agent, creates an AgentCore Runtime,
wires Cognito + IAM + ECR + CodeBuild, and prints the endpoint URL.

---

## Designed-in safety

- **No mock testing.** Every cloud primitive has a real-cloud integration test —
  see `tests/integration/`. 27 cheap-tier tests against real AWS+GCP, ~$0.005/run.
- **Cost caps.** Every invocation tracks tokens against a per-model pricing table
  and a session USD cap from `cloudless.yaml`. `CostCapExceeded` is a typed exception.
- **Cloud-portable governance.** `@cloudless.policy` runs Python policies regardless
  of cloud; Bedrock Guardrails attach automatically when `guardrail_id` is set; both
  emit the same `AuditRecord` to your sink chain.
- **Failure-aware exceptions.** `TransientError` vs `PermanentError` lets `with_retry`
  and `CircuitBreaker` make the right call automatically. No bare `except Exception`.

---

## Documentation

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — full design
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — ADR log (39 locked decisions)
- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — milestone plan
- [`docs/RISKS.md`](./docs/RISKS.md) — open questions
- [`docs/CERTIFICATION.md`](./docs/CERTIFICATION.md) — what's validated against real cloud
- [`docs/SPIKE-FINDINGS.md`](./docs/SPIKE-FINDINGS.md) — implementation gotchas (F1–F21)
- [`docs/research/`](./docs/research/) — AgentCore + Vertex + A2A research dossiers
- [`SECURITY.md`](./SECURITY.md) — vulnerability reporting

---

## License

Apache 2.0.
