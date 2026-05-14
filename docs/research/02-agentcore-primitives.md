# Research: AWS Bedrock AgentCore Primitives

> Captured 2026-05-14. Covers Memory, Identity, Gateway, Code Interpreter, Browser, Observability.
> All primitives GA as of October 2025 across 15 regions.

AWS explicitly markets AgentCore as **modular**: "composable capabilities that work together or independently" ([FAQs](https://aws.amazon.com/bedrock/agentcore/faqs/)). Each primitive consumable from outside AWS via boto3.

---

## 1. AgentCore Memory

**Status:** GA in all 15 regions.

**Definition:** Fully managed short-term + long-term agent memory. Short-term captures raw turn-by-turn events; long-term asynchronously extracts insights (facts, summaries, preferences, episodes) via Bedrock-based extraction pipelines.

**API surface:**
- Control: `bedrock-agentcore-control` — `CreateMemory`, `UpdateMemory`, `DeleteMemory`, `ListMemories`, `GetMemory`
- Data: `bedrock-agentcore` — `CreateEvent`, `GetEvent`, `ListEvents`, `ListSessions`, `DeleteEvent`, `GetMemoryRecord`, `ListMemoryRecords`, `RetrieveMemoryRecords` (semantic search)

**Example:**
```python
from bedrock_agentcore.memory import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

sm = MemorySessionManager(memory_id=memory_id, region_name="us-west-2")
session = sm.create_memory_session(actor_id="User1", session_id="OrderSupportSession1")
session.add_turns(messages=[ConversationalMessage("Hi, how can I help?", MessageRole.ASSISTANT)])
records = session.search_long_term_memories(query="summarize support issue", namespace_path="/", top_k=3)
```

**Framework adapters:** Strands (`AgentCoreMemorySessionManager`), LangGraph (`langgraph-checkpoint-aws`: `AgentCoreMemorySaver`, `AgentCoreMemoryStore`), LangChain, LlamaIndex. **Not MCP-native.**

**Data model:** `Memory → Strategy → Namespace → MemoryRecord`. Hierarchical namespaces support templating: `/users/{actorId}/facts`, `/summaries/{actorId}/{sessionId}`. Events immutable, scoped by `(actorId, sessionId)`, support metadata (not CMK-encrypted — don't put PII in metadata).

**Strategies (long-term extraction modes):**
- **SEMANTIC** — facts / knowledge, cross-session
- **SUMMARIZATION** — running session summary
- **USER_PREFERENCE** — preferences / styles
- **EPISODIC** — goals, reasoning, actions, outcomes, reflections; per-session
- **CUSTOM** — bring your own extraction prompt + LLM

**Retention:** 7–365 days (`EventExpirationDuration`).

**Standalone usability:** ✅ Yes — boto3 from anywhere with AWS credentials.

**Pricing:**
- Short-term events: $0.25 / 1,000
- Long-term storage (built-in strategy with extraction): $0.75 / 1,000 records / month
- Long-term storage (self-managed): $0.25 / 1,000 records / month
- Retrieval: $0.50 / 1,000

**Limits:**
- 150 memory resources / region / account
- **6 strategies / memory (hard cap)**
- 100 messages and 10 MB max per CreateEvent; 100 KB per message
- 5 CreateEvent/sec per (actor, session) with conversational payloads
- 150,000 tokens/min long-term extraction (account-level, adjustable)
- 50,000 tokens/min per session for episodic (not adjustable)

**Gotchas:**
1. Long-term extraction is **async** — refresh lag between CreateEvent and records appearing
2. 30 KB AppendToPrompt limit for custom strategies
3. Event metadata bypasses CMK encryption

**Sources:**
- [Memory overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)
- [Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
- [Memory blog](https://aws.amazon.com/blogs/machine-learning/amazon-bedrock-agentcore-memory-building-context-aware-agents/)
- [Episodic memory blog](https://aws.amazon.com/blogs/machine-learning/build-agents-to-learn-from-experiences-using-amazon-bedrock-agentcore-episodic-memory/)

---

## 2. AgentCore Identity

**Status:** GA in all 15 regions.

**Definition:** Identity broker for AI agents. Inbound auth (verifying who is calling the agent), outbound auth (letting the agent call third-party APIs as a user). Token vault, OAuth 2LO/3LO orchestration, integration with Secrets Manager for API keys.

**Key concepts:**
- **Workload Identity** — agent's identity record (~service account)
- **Agent Identity Directory** — Cognito-User-Pool-like registry
- **Resource Credential Provider** — config object for OAuth client creds / API keys for downstream services
- **Agent Access Token** — AWS-signed JWT carrying workload + user identity
- **2LO/3LO** — client-credentials vs authorization-code grants

**API:** `CreateWorkloadIdentity`, `CreateOauth2CredentialProvider`, `CreateApiKeyCredentialProvider`, `GetWorkloadAccessToken`, `GetResourceOauth2Token`, `GetResourceApiKey`. Inbound JWT validation enforced by OAuth 2.0 authorizer SDK component embedded in agent.

**Supported IdPs:** Cognito, Okta, Microsoft Entra ID, Auth0, Google, any custom OIDC. Pre-built credential-provider templates for Slack, GitHub, Salesforce, Zoom, JIRA, Atlassian, Google.

**Standalone usability:** ✅ Yes — explicitly marketed as usable from ECS / EKS / Lambda / on-prem / outside AWS. Cloud Run on GCP can call it via WIF (GCP SA → AWS IAM role) or static IAM keys.

**Pricing:** $0.010 per 1,000 token/API-key requests to non-AWS resources. **Free** when used through AgentCore Runtime or Gateway.

**Limits:** 1,000 workload identities, 50 OAuth2 credential providers, 50 API-key credential providers (all per region, **not adjustable**).

**Gotchas:**
1. 50-credential-provider cap is hard — enterprises with many SaaS may need multi-account
2. Three-legged OAuth requires user-facing callback URL — non-trivial for headless agents

**Sources:**
- [Identity overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-overview.html)
- [Identity terminology](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-terminology.html)
- [Securing AI agents blog](https://aws.amazon.com/blogs/security/securing-ai-agents-with-amazon-bedrock-agentcore-identity/)
- [Identity on ECS](https://aws.amazon.com/blogs/machine-learning/secure-ai-agents-with-amazon-bedrock-agentcore-identity-on-amazon-ecs/)

---

## 3. AgentCore Gateway

**Status:** GA in all 15 regions.

**Definition:** Turns Lambda functions, OpenAPI specs, Smithy models, API Gateway REST APIs, and existing MCP servers into a **unified MCP server endpoint** for any MCP client. Inbound auth (OAuth JWT / SigV4 / none), outbound auth (via Identity credential providers), semantic tool search.

**Two modes:**
- **MCP Aggregation mode** — combines multiple targets into one virtual MCP server with unified `tools/list`
- **HTTP target mode** — direct pass-through proxy

**Targets:** Lambda, API Gateway REST, OpenAPI spec, Smithy model, MCP server, built-in templates.

**API:** `CreateGateway`, `CreateGatewayTarget`, `UpdateGateway*`, `GetGateway`, `ListGateways`. Runtime URL: `https://{gateway-id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp` — **public HTTPS, reachable from anywhere.**

**Example (consuming from Strands):**
```python
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

def transport():
    return streamablehttp_client(gateway_url, headers={"Authorization": f"Bearer {access_token}"})

mcp_client = MCPClient(transport)
tools = mcp_client.list_tools_sync()
```

**Standalone usability:** ✅ **Excellent.** Public HTTPS MCP endpoint + JWT auth = consumable from anywhere. This is **the** AgentCore primitive most useful outside AWS.

**Pricing:**
- Tool invocations / ListTools / Ping: $0.005 / 1,000
- Semantic search: $0.025 / 1,000
- Tool indexing: $0.02 / 100 tools/month
- VPC egress: $0.006/GB

**Limits:**
- 1,000 gateways / account, 100 targets / gateway, 1,000 tools / target
- 1 MB inline schema; 10 MB via S3
- 1,000 concurrent connections / gateway, / account
- **Semantic search: 25 TPM** (surprisingly low)
- 6 MB max tool-call payload
- 15-min gateway invocation timeout

**Gotchas:**
1. Semantic search throttle at 25 TPM
2. HTTP target mode skips MCP aggregation + tool search — loses discovery
3. Tool name char-limit 256 — careful with auto-generated long names from OpenAPI

**Sources:**
- [Gateway core concepts](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-core-concepts.html)
- [Gateway quickstart](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/gateway/quickstart.html)
- [Gateway intro blog](https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-gateway-transforming-enterprise-ai-agent-tool-development/)

---

## 4. AgentCore Code Interpreter

**Status:** GA in all 15 regions.

**Definition:** Sandboxed Python/JavaScript/TypeScript execution. Pre-installed: pandas, numpy, matplotlib, seaborn, bokeh, scikit-learn, scipy, sympy.

**API:** `CreateCodeInterpreter`, `StartCodeInterpreterSession`, `InvokeCodeInterpreter`, `GetCodeInterpreterSession`, `StopCodeInterpreterSession`, `ListCodeInterpreterSessions`, `DeleteCodeInterpreter`. Built-in default: `aws.codeinterpreter.v1`.

**Standalone usability:** ✅ Yes — boto3 from anywhere with AWS credentials.

**Pricing:** $0.0895 / vCPU-hour, $0.00945 / GB-hour, 1-sec min, idle/IO-wait free.

**Limits:**
- 2 vCPU / 8 GB per session (hard cap)
- 10 GB disk
- 15-min sync timeout; 8-hour async max
- 100 MB payload
- 1,000 concurrent sessions / account

**Gotchas:**
- 2 vCPU / 8 GB not adjustable — heavy ML workloads need ECS/SageMaker
- Internet access requires creating custom interpreter (default is offline)

---

## 5. AgentCore Browser

**Status:** GA in all 15 regions.

**Definition:** Cloud-hosted, isolated headless Chromium. Playwright, BrowserUse, Nova Act supported. Live View (real-time human-in-the-loop) and Session Replay (DOM/console/network capture to S3).

**API:** `CreateBrowser`, `StartBrowserSession`, `ConnectBrowserAutomationStream` (WebSocket CDP), `ConnectBrowserLiveViewStream`, profiles via `CreateBrowserProfile` / `SaveBrowserSessionProfile`. Default: `aws.browser.v1`.

**Standalone usability:** ✅ Yes — boto3 from anywhere; WebSocket connects regardless of where agent runs.

**Pricing:** Same as Code Interpreter ($0.0895/vCPU-hr + $0.00945/GB-hr).

**Limits:**
- 1 vCPU / 4 GB / session; 10 GB disk
- Default session 15 min, max 8 h
- 1,000 concurrent sessions
- 1 automation stream + 1 live view stream / session
- Profiles: 50 MB each, 100 profiles / account
- Extensions: 10 MB each, max 10/session
- Proxies: 5/session, max 100 domain patterns

**Gotchas:**
- Only 1 automation stream / session — can't parallelize within a session
- Profile storage caps at 50 MB (cookies + localStorage combined)
- 15-min default timeout will surprise long-workflow teams

---

## 6. AgentCore Observability

**Status:** GA in all 15 regions.

**Definition:** OpenTelemetry-native tracing/metrics/logs. Lands in CloudWatch; dedicated **CloudWatch GenAI Observability** dashboard renders trace timelines, span graphs, token usage, error breakdowns.

**Data model:** OTEL spans, logs, metrics. Built-in metrics for agents/gateways/memory: session count, latency, duration, token usage, error rate. Custom instrumentation via ADOT (AWS Distro for OpenTelemetry).

**Framework-agnostic.** Datadog has a published integration.

**Standalone usability:** ✅ Yes — OTLP to CloudWatch endpoint with AWS credentials. Agent on Cloud Run can emit traces here.

**Pricing:** CloudWatch ingestion/storage rates. No separate Observability surcharge.

**Gotchas:**
- Rich trace UI is **only for Runtime-hosted agents** — external agents get raw CloudWatch but not curated dashboard
- Spans must follow GenAI semantic conventions to render properly

---

## Cross-cutting analysis

### Cloud portability from GCP

| Primitive | Cross-cloud reachable? | How |
|---|---|---|
| Gateway | **Excellent** | Public HTTPS MCP + OAuth JWT. 50-150ms latency cross-region. |
| Identity | Good | boto3 + WIF (GCP SA → AWS IAM role). |
| Memory | Good | boto3; async extraction tolerates latency. |
| Code Interpreter | Good | boto3 + WebSocket; cross-region adds latency. |
| Browser | Acceptable | WebSocket; latency-sensitive for live view. |
| Observability | Good | OTLP push to CloudWatch endpoint. |

**Recommended cross-cloud auth pattern:** GCP service account → Workload Identity Federation → AWS IAM role → SigV4 signed API calls. Alternative for Gateway specifically: OAuth JWT (Cognito M2M), avoiding AWS-credential coupling.

### MCP compatibility

| Primitive | MCP native? |
|---|---|
| Gateway | **Yes** — Streamable HTTP at public URL |
| Identity | Partially — designed to be MCP-aware (OAuth resource server) |
| Memory | No — AWS API |
| Code Interpreter | No — wrap with Gateway if MCP needed |
| Browser | No — WebSocket/CDP |
| Observability | No — OTLP/CloudWatch |

**Implication for cloudless:** Gateway is the only primitive that fits cleanly in an MCP-native abstraction. Others need wrapping.

### AgentCore Memory vs. DIY DynamoDB

- **DIY cost:** DynamoDB + S3 + OpenSearch/Pinecone + Lambda extraction + Bedrock summarization + retrieval API. 4-6 weeks of work, 5+ services to operate.
- **AgentCore value-add:**
  1. Pre-built strategies (semantic/summary/preference/episodic/custom) — episodic in particular is non-trivial to build correctly
  2. Built-in semantic search via `RetrieveMemoryRecords`
  3. Namespace templating gives clean multi-tenant model
  4. Async consolidation merges new info with existing records
  5. Framework adapters (Strands, LangGraph)
- **What you give up:** vendor lock-in, 6-strategy hard cap, opaque extraction model, linear pricing at high volume

### Gateway vs. raw Lambda tools

**Use Gateway when:** MCP compatibility across many runtimes, many tools (10+) with discovery, federated auth, OpenAPI/Smithy aggregation, outbound 3LO OAuth to SaaS.

**Skip Gateway when:** <5 tools and single runtime; >25 TPM semantic searches needed; tool latency budget <50 ms; cost-sensitive at extreme scale; >6 MB payloads.

**Sweet spot:** Mid-to-large tool catalogs (10-1000 tools) consumed by heterogeneous runtimes (some AWS, some GCP). MCP front door + Identity-managed outbound creds = exactly the abstraction we want for cross-cloud.

---

## Sources

See individual primitive sections for citation URLs. Key entry points:
- [AgentCore Overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AgentCore Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [AgentCore FAQs](https://aws.amazon.com/bedrock/agentcore/faqs/)
- [GitHub: awslabs/amazon-bedrock-agentcore-samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
