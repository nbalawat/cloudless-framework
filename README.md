# cloudless

> Write your agent once. Ship it to any cloud.

**cloudless** is a Python SDK + CLI for building agentic AI applications that deploy
unchanged to **AWS Bedrock AgentCore** or **GCP Vertex AI Agent Runtime** ("Gemini
Enterprise Agent Platform"), with first-class cross-cloud agent-to-agent (A2A)
collaboration.

Write your agent in **any of 5 frameworks** (LangGraph, Strands Agents, Google ADK,
Anthropic Claude Agent SDK, Microsoft Agent Framework) — ship it to **either cloud**.
cloudless ships the cross-cloud bridges natively (no LiteLLM, no OpenAI-compat shim);
every framework × cloud cell is real-cloud certified.

Status: **v0.x — internal alpha**. All 13 service-catalog primitives + the full
5 × 2 framework/cloud matrix are real-cloud validated — see
[`docs/CERTIFICATION.md`](./docs/CERTIFICATION.md). Public APIs may break until v1.0.

---

## Five-minute quickstart

```bash
# Pick your framework + cloud extras:
pip install cloudless[langgraph,aws]      # LangGraph on AWS
# or: cloudless[strands,gcp]              # Strands on GCP
# or: cloudless[adk,aws]                  # ADK on AWS (uses cloudless.bridges.BedrockADKLlm)
# or: cloudless[maf,gcp]                  # MAF on GCP (uses cloudless.bridges.VertexMAFChatClient)
# or: cloudless[claude_sdk,aws]           # Claude Agent SDK, env-var routed to Bedrock

cloudless init my-app --framework langgraph
cd my-app
cloudless doctor                          # preflight: verify creds + env
cloudless dev hello                       # local server on :8080, real cloud LLM
curl -X POST localhost:8080/invocations -d '{"prompt": "hi"}'
cloudless deploy hello                    # ships to AWS AgentCore (~100s) or GCP Agent Engine (~210s)
cloudless logs hello --follow
```

The `cloudless deploy` command picks the cloud from `cloudless.yaml`; no agent
code changes when you swap clouds.

---

## What ships in v0.x

| Layer | Capability | Status |
|---|---|---|
| Frameworks | LangGraph, Strands Agents, Google ADK, Anthropic Claude Agent SDK, Microsoft Agent Framework — **all five on both AWS Bedrock and GCP Vertex** (10-cell matrix; cloudless ships the cross-cloud bridges, no LiteLLM) | ✅ |
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

Pick your framework, pick your cloud, write `build()`:

```python
# LangGraph + AWS Bedrock
import cloudless
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list

@cloudless.agent(name="hello", framework="langgraph", interfaces=["http", "a2a"])
class HelloAgent(cloudless.LangGraphAgent):
    def build(self):
        llm = init_chat_model("us.amazon.nova-micro-v1:0", model_provider="bedrock_converse")
        g = StateGraph(State)
        g.add_node("chat", lambda s: {"messages": [llm.invoke(s["messages"])]})
        g.add_edge(START, "chat"); g.add_edge("chat", END)
        return g.compile()
```

```python
# Strands on GCP — cloudless ships the Vertex bridge
import cloudless
from strands import Agent
from cloudless.adapters.frameworks._bridges import VertexStrandsModel

@cloudless.agent(name="hello", framework="strands")
class HelloAgent(cloudless.StrandsAgent):
    def build(self):
        return Agent(
            model=VertexStrandsModel(model="gemini-2.0-flash", project="my-gcp-proj"),
            system_prompt="Reply concisely.",
        )
```

```python
# Google ADK on AWS — cloudless ships the Bedrock bridge
import cloudless
from google.adk.agents import Agent
from cloudless.adapters.frameworks._bridges import BedrockADKLlm

@cloudless.agent(name="hello", framework="adk")
class HelloAgent(cloudless.ADKAgent):
    def build(self):
        return Agent(
            name="hello",
            model=BedrockADKLlm(model="us.amazon.nova-micro-v1:0", region="us-east-1"),
            instruction="Reply concisely.",
        )
```

```yaml
# cloudless.yaml
project: my-app
default_cloud: aws    # or gcp

agents:
  hello:
    framework: langgraph    # or strands / adk / claude_sdk / maf
    interfaces: [http, a2a]

service_catalog:
  llm: {provider: bedrock, model: nova-micro}
  memory: {strategy: semantic, retention_days: 90}

policies:
  cost_cap_usd_per_session: 5.0
  retries: {attempts: 3, backoff_seconds: 0.25}
```

`cloudless deploy hello` packages the agent, creates the cloud-native runtime
(AgentCore on AWS / Agent Engine on GCP), wires identity (Cognito + IAM on AWS,
ADC + service account on GCP), builds the container/blob, and prints the endpoint.

---

## The 5 × 2 framework × cloud matrix

|                                  | AWS Bedrock | GCP Vertex AI |
|----------------------------------|---|---|
| **LangGraph**                    | `langchain-aws.ChatBedrock` | `langchain-google-vertexai.ChatVertexAI` |
| **Strands Agents**               | native `BedrockModel` | `cloudless.bridges.VertexStrandsModel` |
| **Google ADK**                   | `cloudless.bridges.BedrockADKLlm` | native `Agent(model="gemini-*")` |
| **Anthropic Claude Agent SDK**   | env-var route (`CLAUDE_CODE_USE_BEDROCK=1`) | env-var route (`CLAUDE_CODE_USE_VERTEX=1`) |
| **Microsoft Agent Framework**    | `agent_framework_bedrock.BedrockChatClient` | `cloudless.bridges.VertexMAFChatClient` |

cloudless ships **three native bridges** (`BedrockADKLlm`, `VertexStrandsModel`,
`VertexMAFChatClient`) for the cells where the framework's first-party SDK only
covers one cloud. Each bridge is ~150 lines, calls the cloud's official SDK
directly (boto3 / google-genai), and matches the host framework's pluggable
Model/ChatClient interface 1:1 — no LiteLLM, no OpenAI-compat shim.

---

## Designed-in safety

- **No mock testing.** Every cloud primitive — and every framework × cloud
  cell — has a real-cloud integration test. 434 unit + ~110 integration tests
  against real AWS + GCP + Anthropic, all sub-$0.01 per run.
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
