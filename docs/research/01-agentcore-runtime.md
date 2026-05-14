# Research: AWS Bedrock AgentCore Runtime (deep dive)

> Captured 2026-05-14. Original research conducted as background task during the architecture interview.
> Status: GA as of October 13, 2025; suite announced in preview July 16, 2025 at AWS Summit New York.

## What AgentCore Runtime is

AgentCore Runtime is a serverless, container-based hosting service purpose-built for AI agents. Per AWS: *"the foundational component that hosts your AI agent or tool code… a containerized application that processes user inputs, maintains context, and executes actions using AI capabilities"* ([How it works](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html)).

**GA:** October 13, 2025. Preview announced July 16, 2025.

**Region availability (May 2026):** 15 regions per [FAQs](https://aws.amazon.com/bedrock/agentcore/faqs/) — us-east-1, us-east-2, us-west-2, ca-central-1, sa-east-1, eu-west-1/2/3, eu-central-1, eu-north-1, ap-south-1, ap-southeast-1/2, ap-northeast-1/2. Capacity: 1,000 active sessions per account in us-east-1/us-west-2; 500 elsewhere ([Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)).

## Distinguishing from Bedrock Agents (v1)

| Aspect | Bedrock Agents (v1) | AgentCore Runtime |
|---|---|---|
| What it is | Managed orchestrator: AWS plans/executes the agent loop | Compute hosting plane: you ship code, AWS runs it |
| Configuration | No-code/low-code (action groups + KBs + instruction prompt) | Container or code package with a runtime contract |
| Framework | AWS proprietary orchestration | Bring-your-own (Strands, LangGraph, CrewAI, ADK, OpenAI Agents, custom) |
| Models | Bedrock foundation models only | Any model — Bedrock, Anthropic direct, OpenAI, Gemini, etc. |
| Tools | Action Groups (OpenAPI/Lambda) + Knowledge Bases | Whatever you wire up; can use AgentCore Gateway separately |
| Best for | Standard patterns, rapid prototyping | Complex agent logic, enterprise-specific requirements |

For cross-cloud frameworks, **AgentCore Runtime is the right primitive** — Bedrock Agents v1 forces AWS-specific configuration semantics that don't translate to GCP.

## Deployment model

Two officially supported paths:

### (a) Container deployment

OCI image to ECR. Hard requirements:
- **Host:** `0.0.0.0`
- **Port:** `8080`
- **Platform:** **ARM64** (Graviton) — required for AgentCore Runtime compatibility

CLI generates Dockerfile + `.bedrock_agentcore.yaml`. By default, builds happen via AWS CodeBuild (no local Docker daemon needed); `agentcore deploy --local-build` available.

### (b) Direct code deployment (Python-only)

Upload ZIP. AWS handles runtime image. Python 3.10–3.13 supported. ~30s first deploy, ~10s subsequent updates.

**Size caps:**
- Container: 2 GB image
- Direct code: 250 MB compressed / 750 MB uncompressed

## Runtime contracts (four protocols)

Each AgentCore Runtime is configured for **one protocol at deploy time** ([service contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html)):

| Protocol | Port | Mount | Notes |
|---|---|---|---|
| **HTTP** | 8080 | `/invocations` + `/ping` + optional `/ws` | Primary; SSE supported |
| **MCP** | 8000 | `/mcp` | For agents serving as MCP tool servers |
| **A2A** | 9000 | `/` + `/.well-known/agent-card.json` | JSON-RPC 2.0; first-class A2A support |
| **AG-UI** | 8080 | `/invocations` (SSE) + `/ws` | UI streaming protocol |

### HTTP contract specifics

- `POST /invocations` — JSON in; JSON or SSE (`text/event-stream`) out
- `GET /ping` — returns `{"status": "Healthy" | "HealthyBusy", "time_of_last_update": <unix>}`. `HealthyBusy` keeps session alive for background work.
- `GET /ws` (optional) — WebSocket upgrade

### SDK shortcut

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    return {"result": ...}

app.run()
```

Auto-implements `/invocations`, `/ping`, SSE streaming.

## Framework support

Officially supported with samples:
- **Strands Agents** — first-class (AWS's own framework)
- **LangGraph** — wraps `StateGraph.invoke()` in `@app.entrypoint`
- **Google ADK** — wraps `Runner` + `SessionService` with asyncio bridge
- **OpenAI Agents SDK** — wraps `agents.Agent` + `Runner.run`
- **CrewAI, LlamaIndex** — listed as integrations

**MS Agent Framework — no first-party AWS sample.** MAF doesn't have an Amazon Bedrock agent type; community workaround exists via `AWSSDK.Extensions.Bedrock.MEAI` ([Robert de Veen walkthrough](https://www.robertdeveen.com/aws/2025/11/12/Microsoft-Agent-Framework-with-Amazon-Bedrock.html)). For cloudless, MAF on AgentCore is **possible but DIY**.

## Session model

- **Isolation:** Each session in a dedicated microVM (strongly implied to be Firecracker based on billing model and AWS messaging; not explicitly documented). CPU, memory, filesystem isolated.
- **Session identity:** `runtimeSessionId` ≥33 chars. Same ID → same microVM (warm). New ID → fresh microVM.
- **Lifecycle:** Active → Idle (default 15 min, adjustable) → Terminated (at idle timeout, 8-hour max lifetime, or health failure).
- **Per-session hardware cap:** 2 vCPU / 8 GB RAM (**not adjustable**).
- **Per-session storage:** 1 GB disk; max 200 directory depth.
- **Payload caps:** 100 MB request/response; 10 MB max streaming chunk; WebSocket 64 KB frame, 250 fps.

After termination, microVM is sanitized. Session state is ephemeral — **use AgentCore Memory for durability**.

## Scaling

- Auto-scale to zero
- 1,000 active sessions per account in us-east-1 / us-west-2; 500 elsewhere; adjustable
- 100 TPM new sessions / endpoint (container deploy); 25 TPS (direct code); adjustable
- 25 TPS for `InvokeAgentRuntime`
- **Sync request timeout: 15 min** (not adjustable)
- **Async max: 8 hours** (with `HealthyBusy` pings)
- **Streaming connection: 60 minutes** max

## Pricing

- **$0.0895 / vCPU-hour**, 1-second minimum
- **$0.00945 / GB-hour**
- **No charge for I/O wait** — when agent is blocked on LLM/tool call, CPU clock pauses. Major cost win for LLM-bound workloads.
- Bedrock model inference billed separately.
- AgentCore Memory: $0.25 / 1k events; $0.75 / 1k records/mo (built-in extraction); $0.50 / 1k retrievals.
- Gateway: $0.005 / 1k invocations; $0.025 / 1k search calls; $0.02 / 100 tools indexed/mo.
- Identity: $0.010 / 1k token requests (free via Runtime / Gateway).

## Limits & quotas (consolidated)

| Dimension | Value | Adjustable |
|---|---|---|
| Active sessions / account | 1,000 (us-east-1, us-west-2); 500 elsewhere | Yes |
| Agents / account | 1,000 | Yes |
| Container image size | 2 GB | **No** |
| Direct-code zipped | 250 MB | **No** |
| Direct-code unzipped | 750 MB | **No** |
| Per-session hardware | 2 vCPU / 8 GB | **No** |
| Sync request timeout | 15 min | **No** |
| Async max | 8 h | **No** |
| Streaming duration | 60 min | **No** |
| Payload | 100 MB | **No** |
| Per-session storage | 1 GB | **No** |
| WebSocket frame | 64 KB; 250 fps | **No** |

## Networking

- **Default**: AWS-managed network with internet egress
- **VPC mode (GA)**: agent runs with ENIs in your subnets
- **PrivateLink (GA)**: three interface endpoints — data plane, Gateway, control plane
- Private resource access via VPC attach or VPC Lattice resource gateways

## IAM model

- **Caller permissions**: `bedrock-agentcore:InvokeAgentRuntime` on agent ARN
- **Execution role**: trust policy with `bedrock-agentcore.amazonaws.com`; typical perms include `bedrock:InvokeModel*`, CloudWatch Logs, X-Ray, ECR pull
- **Inbound auth**: SigV4 (default) or OAuth 2.0 (Cognito/Okta/Entra/Auth0)
- **Outbound auth**: AgentCore Identity (user-delegated or autonomous OAuth, API keys)
- Known security gotcha: overly broad execution-role policies create privilege-escalation paths — Sonrai flagged the need for SCP guardrails

## Tooling

- **SDKs**: `bedrock-agentcore` (in-container Python SDK), `boto3 ≥ 1.39.8`
- **CLI**: `bedrock-agentcore-starter-toolkit` (legacy) and new unified `aws/agentcore-cli` (supports TS scaffolding)
- **IaC**: CloudFormation GA; CDK (known bug aws-cdk #35852 on default execution-role policy); Terraform community modules
- **Local dev**: first-class — `python my_agent.py` runs `BedrockAgentCoreApp` on localhost:8080

## Observability

- OpenTelemetry-native (`aws-opentelemetry-distro` / ADOT)
- Auto-instrumented sessions, latency, duration, token usage, error rates
- CloudWatch GenAI Observability dashboard renders trace visualizations
- Third-party OTLP destinations supported (Datadog, Elastic, Honeycomb)

**Known trace gotcha**: Lambda → AgentCore propagates Lambda's X-Amzn-Trace-Id; if Lambda sampled=0, AgentCore skips span generation for that request.

## Gotchas

1. **ARM64 lock-in** — x86 Macs/CI need `docker buildx --platform linux/arm64`. CodeBuild path avoids this.
2. **Code update propagation lag** — sessions started before deploy continue using the old code until they terminate (up to 8h). Rotate sessions or use endpoints+versions for explicit rollover.
3. **Silent mid-execution failures** — outbound network calls without explicit egress permission can stop agents with no log line.
4. **Boto3 minimums** — `boto3 < 1.39.8` produces opaque ValidationException on `CreateAgentRuntime`.
5. **ECR Public auth churn** — first-time builds need `aws ecr-public get-login-password`.
6. **15-min sync timeout is hard** — long agent loops must use async + `HealthyBusy`.
7. **WebSocket frame fragmentation** — 64 KB frames + 250 fps cap; raw multimodal binary needs explicit chunking.
8. **Direct-code is Python-only** — TS/Go/etc. go through container path.
9. **Memory cost can exceed Runtime cost** for chatty multi-turn agents.
10. **No documented cold-start SLO** — marketing says "fast," numbers undocumented.

## Roadmap signals (re:Invent 2025 + 2026)

- **A2A protocol GA** — late 2025; first-class runtime protocol mode
- **AgentCore Evaluations** — launched re:Invent 2025; 13 built-in evaluators
- **AgentCore Payments** — x402 protocol, Coinbase CDP + Stripe/Privy wallets
- **AgentCore Registry** — central agent/tool catalog with free tier
- **AgentCore Policy** — Cedar-based deterministic policies; intercepts every tool call at Gateway
- **Outposts / Local Zones** — extending AgentCore to on-prem via MCP+A2A
- **Native TypeScript scaffolding** — new `agentcore` CLI supports TS

## Sources

- [GA announcement (Oct 2025)](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/)
- [Preview blog (Jul 2025)](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/)
- [Overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [How it works — Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html)
- [HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html)
- [A2A protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a-protocol-contract.html)
- [Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)
- [Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Direct code deployment blog](https://aws.amazon.com/blogs/machine-learning/iterate-faster-with-amazon-bedrock-agentcore-runtime-direct-code-deployment/)
- [Network connectivity patterns](https://aws.amazon.com/blogs/networking-and-content-delivery/network-connectivity-patterns-for-agents-deployed-on-amazon-bedrock-agentcore-runtime/)
- [Runtime IAM permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
- [Observability overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-telemetry.html)
- [Bedrock Agents vs AgentCore — re:Post](https://repost.aws/questions/QUjkf4WbikQ6WrpuH9sppjnw/bedrock-agents-vs-bedrock-agentcore)
- [AgentCore privilege escalation analysis — Sonrai](https://sonraisecurity.com/blog/aws-agentcore-privilege-escalation-bedrock-scp-fix/)
- [awslabs/amazon-bedrock-agentcore-samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [aws/agentcore-cli](https://github.com/aws/agentcore-cli)
