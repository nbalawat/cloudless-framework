# Research: AgentCore + Frameworks + A2A Protocol

> Captured 2026-05-14. Covers Strands, LangGraph, Google ADK, MS Agent Framework on AgentCore, and the A2A protocol.

## The AgentCore Runtime contract (foundation)

AgentCore Runtime is microVM-isolated per session. Exposes **four protocol contracts** on different ports — pick one per runtime:

| Protocol | Port | Mount | Discovery | Auth |
|---|---|---|---|---|
| HTTP | 8080 | `/invocations` + `/ping` (+ `/ws`) | – | SigV4, OAuth 2.0 |
| MCP | 8000 | `/mcp` | Tool list | SigV4, OAuth 2.0 |
| A2A | 9000 | `/` + `/.well-known/agent-card.json` | Agent Cards | SigV4, OAuth 2.0 |
| AG-UI | 8080 | `/invocations` SSE + `/ws` | – | SigV4, OAuth 2.0 |

**Single-protocol per runtime.** The `BedrockAgentCoreApp` SDK class handles HTTP/AG-UI; `serve_a2a()` handles A2A. Fixed at deploy time — **key design constraint for cloudless.**

All frameworks deploy the same way structurally: containerized (ARM64), SDK helper implements the contract, then `agentcore configure` + `agentcore deploy` provisions ECR + microVM.

---

## Framework-by-framework

### Strands Agents

**Status:** First-class (AWS-built). Deepest AgentCore integration.

**HTTP entry point:**
```python
from strands import Agent
from strands_tools import file_read, file_write, editor
from bedrock_agentcore.runtime import BedrockAgentCoreApp

agent = Agent(tools=[file_read, file_write, editor])
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    user_message = payload.get("prompt", "...")
    result = agent(user_message)
    return {"result": result.message}

app.run()
```

**Just works:**
- **Streaming:** `agent.stream_async()` + `yield` → SDK auto-converts to SSE
- **Memory:** AgentCore Memory client (native Strands integration)
- **Tools:** Code Interpreter and Browser exposed as Strands tools natively
- **Multi-agent in single deployment:** `strands.multiagent` (Swarm, Graph, A2A) all work in-process

**A2A:** Native. `from strands.multiagent.a2a.executor import StrandsA2AExecutor` + `from bedrock_agentcore.runtime import serve_a2a`.

**Local dev:** `python main.py` runs on 8080 (HTTP) or 9000 (A2A); `agentcore dev` opens browser inspector.

**Samples:** `awslabs/amazon-bedrock-agentcore-samples/03-integrations/agentic-frameworks/strands-agents`; `aws-samples/sample-strands-agent-with-agentcore`.

### LangGraph

**Status:** Officially supported with AWS-published samples + dedicated LangChain/AWS package.

**HTTP entry point:**
```python
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
llm = init_chat_model("us.anthropic.claude-3-5-haiku-20241022-v1:0", model_provider="bedrock_converse")
graph_builder = StateGraph(State)
# ... nodes/edges ...
graph = graph_builder.compile()

@app.entrypoint
def agent_invocation(payload, context):
    out = graph.invoke({"messages": [{"role": "user", "content": payload.get("prompt")}]})
    return {"result": out["messages"][-1].content}

app.run()
```

**Integration details:**
- **Checkpointing:** LangGraph's checkpointer swaps to AgentCore Memory via `langgraph-checkpoint-aws`: `AgentCoreMemorySaver` (short-term) + `AgentCoreMemoryStore` (semantic long-term). `thread_id` ↔ AgentCore `session_id`; `actor_id` ↔ AgentCore `actor_id`. **Replacement, not bridge.**
- **Streaming:** `astream_events` wraps with async generator yielding events; SDK formats as SSE. Slightly more code than Strands.
- **Multi-agent in single deployment:** supervisor/subgraph patterns in-process. AWS blog walkthrough published.
- **A2A:** Custom wrapper (~15 LOC) extending `a2a-sdk` `AgentExecutor`. AgentCore CLI supports `--protocol A2A` with LangGraph projects.

**Samples:** `awslabs/amazon-bedrock-agentcore-samples/03-integrations/agentic-frameworks/langgraph`.

### Google ADK

**Status:** Officially supported with AWS sample; less idiomatic than LangGraph/Strands due to ADK's async-heavy, session-aware runner model.

**HTTP entry point:**
```python
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import types
import asyncio
from bedrock_agentcore.runtime import BedrockAgentCoreApp

root_agent = Agent(model="gemini-2.0-flash", name="search_agent", tools=[google_search], ...)

async def call_agent_async(query, user_id, session_id):
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="x", user_id=user_id, session_id=session_id)
    runner = Runner(agent=root_agent, app_name="x", session_service=session_service)
    content = types.Content(role="user", parts=[types.Part(text=query)])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response():
            return event.content.parts[0].text

app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    return asyncio.run(call_agent_async(payload.get("prompt"), payload.get("user_id"), context.session_id))

app.run()
```

**Gaps and friction:**
- ADK is Gemini-first; using Bedrock models requires LiteLLM plumbing or OpenAI-compatible Bedrock endpoint
- **Sessions:** ADK has its own `SessionService`; sample uses `InMemorySessionService` (no persistence across microVMs). For persistence, you'd write custom `SessionService` backed by AgentCore Memory. **No AWS-published bridge as of May 2026.** ← This is the gap cloudless fills for ADK-on-AWS support.
- **Streaming:** Possible via async generator pattern; less polished than Strands
- **A2A:** ADK's `to_a2a()` auto-generates Agent Card from agent metadata — this is where ADK shines

**Samples:** `awslabs/amazon-bedrock-agentcore-samples/03-integrations/agentic-frameworks/adk`; `madhurprash/A2A-Multi-Agents-AgentCore` (third-party multi-framework demo).

### Microsoft Agent Framework (MAF)

**Status:** **NOT supported as first-class in AgentCore docs.** Missing from "Use any agent framework" docs page, CLI `--framework` wizard, and `awslabs/amazon-bedrock-agentcore-samples/03-integrations/agentic-frameworks/`.

**What works:**
- MAF can call Bedrock models via OpenAI-compatible endpoint
- AgentCore Runtime is framework-agnostic (just requires ARM64 container with `/invocations` + `/ping`); you write the wrapper yourself

**Hypothetical pattern (not AWS-published):**
```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

agent = ChatAgent(chat_client=OpenAIChatClient(...), instructions="...")
app = BedrockAgentCoreApp()

@app.entrypoint
async def handler(payload, context):
    result = await agent.run(payload["prompt"])
    return {"result": result.text}

app.run()
```

**A2A:** MAF 1.0 has **excellent** native A2A support (`agent-framework-a2a` Python, `Microsoft.Agents.AI.Hosting.A2A.AspNetCore` .NET). For AgentCore A2A: combine `A2AExecutor` + `a2a-sdk` Starlette + replace its run loop with AgentCore's `serve_a2a`. **No AWS sample.**

**Risk:** MAF Python 1.0 shipped early 2026; AWS support pattern undocumented. Treat as **"custom framework"** in cloudless.

---

## A2A protocol

**Origin:** Google, announced April 9, 2025 at Google Cloud Next.

**Governance:** Donated to Linux Foundation in June 2025; vendor-neutral.

**Current version:** **v1.0.0** (per [a2a-protocol.org/latest/specification/](https://a2a-protocol.org/latest/specification/)); evolving toward v1.2 by May 2026.

**Adoption:** 150+ supporting organizations including AWS, Cisco, Google, IBM, Microsoft, Salesforce, SAP, ServiceNow.

**Spec essentials:**
- **Transports:** JSON-RPC 2.0 (primary), gRPC, HTTP+JSON/REST
- **Agent Card:** `/.well-known/agent-card.json` (RFC 8615) — identity, capabilities, security schemes, skills, endpoints. May be signed.
- **Messages and Tasks:** parts (text/file/data/URL); Tasks have lifecycle `submitted → working → completed/failed/canceled/rejected` plus `input-required` / `auth-required` interrupted states.
- **Streaming:** polling, SSE/gRPC streaming, push notifications
- **Auth schemes:** HTTP Bearer (JWT/opaque), OAuth 2.0 (authcode/client-creds/device-code), API key, HTTP Basic/Digest, mTLS, OpenID Connect. Declared in Agent Card `securitySchemes` (mirrors OpenAPI 3).

### AgentCore Runtime native A2A support

**Yes, native** — announced November 2025.

AgentCore is a **transparent proxy** for A2A:
- Container binds `0.0.0.0:9000`, mount path `/` (JSON-RPC body passed through unmodified)
- Serves agent card at `/.well-known/agent-card.json`
- Serves `/ping`
- AgentCore injects `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` header for session isolation
- Auth: SigV4 or OAuth 2.0 (Cognito/Okta/Entra)
- Public URL: `https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped-arn}/invocations/.well-known/agent-card.json`

**Sample agent card from AgentCore:**
```json
{
  "name": "Agent Name",
  "version": "1.0.0",
  "url": "https://bedrock-agentcore.region.amazonaws.com/runtimes/agent-arn/invocations/",
  "protocolVersion": "0.3.0",
  "preferredTransport": "JSONRPC",
  "capabilities": {"streaming": true},
  "skills": [...]
}
```

⚠️ **Version drift warning:** AgentCore samples advertise `protocolVersion: 0.3.0`; upstream spec is v1.0+. Validate live behavior before relying on it.

### Framework A2A support matrix

| Framework | A2A server (expose) | A2A client (consume) | Auto agent card | AgentCore A2A samples |
|---|---|---|---|---|
| **Strands** | Native: `StrandsA2AExecutor` + `serve_a2a()` | Native: `A2AAgent(endpoint=...)` | Yes | Yes — scaffolded by `agentcore create --protocol A2A` |
| **LangGraph** | Custom wrapper (~15 LOC) extending `a2a-sdk` | `a2a-sdk` client or LangChain's | No — explicit `AgentCard` required | Yes — CLI supports `--protocol A2A` |
| **Google ADK** | Built-in: `to_a2a()` auto-generates card | `RemoteA2aAgent` wraps remote agents | Yes | Yes — CLI supports `--protocol A2A` |
| **MS Agent Framework** | `A2AExecutor` + `a2a-sdk` Starlette (Python); `MapA2A(...)` (ASP.NET) | `A2AAgent` (Python) | Manual card | **No AWS sample** |

**Strands native A2A example:**
```python
from strands import Agent, tool
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a

@tool
def add_numbers(a: int, b: int) -> int:
    return a + b

agent = Agent(model=..., system_prompt="...", tools=[add_numbers])

if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent))
```

`serve_a2a` handles port 9000, `/ping`, agent-card serving, `AGENTCORE_RUNTIME_URL` env, Bedrock header propagation.

### Cross-cloud A2A authentication

This is the **single most architecturally important** question for cloudless.

A2A's auth model: Agent Card declares `securitySchemes` (OAuth2, OIDC, mTLS, HTTP Bearer, API key). Client satisfies one. **Transport-agnostic — no mandated IdP.**

**Patterns:**

1. **OAuth 2.0 Client Credentials (recommended)**: shared IdP (Cognito, Auth0, Entra ID, Okta). Calling agent obtains JWT, presents as `Authorization: Bearer <jwt>`. AgentCore Identity supports this natively — Agent Card's `securitySchemes` declares OIDC issuer URL, AgentCore validates JWTs against IdP's JWKS. GCP-side Cloud Run / Agent Engine validates against same issuer or its own IdP that AgentCore trusts.

2. **Workload Identity Federation (no static keys)**: GCP SA exchanges Google identity token for short-lived AWS STS creds via OIDC-based WIF. GCP agent uses SigV4 to call AgentCore. Requires AgentCore configured for SigV4 inbound — **mutually exclusive with JWT** (pick one per runtime).

3. **mTLS**: A2A supports it; AgentCore doesn't advertise direct mTLS support — likely needs sidecar proxy. **Uncertain.**

### Service discovery across clouds

A2A spec defines three patterns:
1. **Well-known URI** — `/.well-known/agent-card.json` on the agent's hostname
2. **Curated registry** — no standardized registry API yet. AWS Agent Registry launched preview April 2026, claims provider-agnostic across AWS / other clouds / on-prem, supports MCP and A2A.
3. **Direct configuration** — hardcoded URLs / env vars

**Recommendation:** don't depend on standardized cross-cloud discovery (doesn't exist). Use direct configuration with our own manifest. Optionally sync to AWS Agent Registry post-GA.

---

## Implications for cloudless

1. **Always expose A2A** — every cloudless agent should serve A2A regardless of framework. Agent card = universal interop.
2. **AWS deployment** = AgentCore Runtime in A2A protocol mode (port 9000). Use Strands/LangGraph/ADK's A2A wrapper. For MAF (v3), plumb `A2AExecutor` + `a2a-sdk` Starlette + bind port 9000 + add `/ping`.
3. **GCP deployment** = Cloud Run / Agent Runtime container with same A2A endpoints. Google has published guidance: [docs.cloud.google.com/run/docs/deploy-a2a-agents](https://docs.cloud.google.com/run/docs/deploy-a2a-agents).
4. **Auth standard** = OAuth 2.0 Client Credentials with **configurable IdP**. Default to Cognito (auto-provisioned) on AWS-hosted projects; opt-in for Auth0 / Entra ID via config swap.
5. **Discovery** = our own manifest (`cloudless.yaml` → `cloudless-manifest.json` baked into agents).
6. **Adapter per framework:**

| Framework | Adapter responsibility | Memory bridge | Streaming bridge |
|---|---|---|---|
| Strands | Trivial — direct passthrough | Native AgentCore Memory | `agent.stream_async()` → yield |
| LangGraph | Compile graph; wrap `invoke`/`astream_events` | `langgraph-checkpoint-aws` | LangGraph events → SSE chunks |
| ADK | Bridge async Runner; `SessionService` per microVM | **Custom `AgentCoreMemorySessionService`** | Map ADK event stream to yields |
| MAF | Wrap `ChatAgent.run` / `run_streaming` | **Custom** | `run_streaming` yields natively |

---

## Risks for cloudless (carried into RISKS.md)

1. **AgentCore A2A protocol version drift** — samples show 0.3.0 vs spec at v1.0+
2. **MAF on AgentCore is unblazed trail** — DIY adapter
3. **Single-protocol-per-runtime constraint** — agent needing HTTP + A2A = 2 deployments on AWS
4. **ADK `AgentCoreMemorySessionService` is our work** — no AWS-published bridge
5. **Inbound auth is mutually exclusive (SigV4 OR JWT)** — design must commit to JWT to keep WIF an escape hatch
6. **A2A registry standard isn't finalized** — manifest as source of truth
7. **mTLS support on AgentCore A2A is uncertain**

---

## Sources

- [AgentCore: Use any agent framework](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-agent-framework.html)
- [AgentCore Runtime service contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html)
- [HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html)
- [A2A protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html)
- [Deploy A2A servers in AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html)
- [Integrate AgentCore Memory with LangChain/LangGraph](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html)
- [AgentCore Identity (OAuth)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html)
- [AWS Blog: A2A in AgentCore](https://aws.amazon.com/blogs/machine-learning/introducing-agent-to-agent-protocol-support-in-amazon-bedrock-agentcore-runtime/)
- [AWS Blog: AWS Agent Registry preview](https://aws.amazon.com/blogs/machine-learning/the-future-of-managing-agents-at-scale-aws-agent-registry-now-in-preview/)
- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A Agent Discovery](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [A2A Enterprise Features](https://a2a-protocol.org/latest/topics/enterprise-ready/)
- [Linux Foundation: A2A project launch](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)
- [Strands Agents: Deploy to AgentCore](https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/)
- [Strands Agents: A2A](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/)
- [ADK: A2A docs](https://adk.dev/a2a/)
- [Google Cloud: Deploy A2A agents to Cloud Run](https://docs.cloud.google.com/run/docs/deploy-a2a-agents)
- [Microsoft Learn: A2A Integration](https://learn.microsoft.com/en-us/agent-framework/integrations/a2a)
- [Robert de Veen: MAF with Amazon Bedrock](https://www.robertdeveen.com/aws/2025/11/12/Microsoft-Agent-Framework-with-Amazon-Bedrock.html)
- [Multi-framework A2A sample on AgentCore](https://github.com/madhurprash/A2A-Multi-Agents-AgentCore)
