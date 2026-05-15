# Your first agent

Building beyond the scaffolded hello world.

## The decorator

```python
import cloudless

@cloudless.agent(
    name="support",                       # stable identifier (kebab-case)
    framework="langgraph",                # or "strands" / "adk"
    interfaces=["http", "a2a"],           # protocols this agent serves
    description="Customer support agent.",
    version="0.1.0",
)
class SupportAgent(cloudless.LangGraphAgent):
    def build(self):
        # Return any compiled LangGraph state graph
        from langgraph.graph import StateGraph, START, END
        ...
```

Every cloudless agent is one Python class. The decorator records metadata
read by the deploy planner.

## The context

```python
async def query(self, ctx, prompt):
    ctx.session.id        # stable session ID
    ctx.user              # auth principal (or None)
    ctx.cost              # cost tracker — record_llm_call, etc.
    await ctx.peer("orders").call(...)   # cross-agent A2A
```

For local development, `ctx` is an `InMemoryContext`. For deployed
agents, AgentCore wires it from inbound JWTs + Cognito + Memory.

## Service primitives

```python
llm = cloudless.LLM(model="nova-micro")
embed = cloudless.Embeddings(model="titan-v2")
mem = cloudless.Memory(strategy="semantic")
secrets = cloudless.Secrets()
sandbox = cloudless.Sandbox()
vectors = cloudless.VectorStore()

response = await llm.invoke("hello", system="be brief", ctx=ctx)
```

Every primitive has a Bedrock backend on AWS and a Vertex backend on GCP.
The dispatch happens at construction time.

## Tools

```python
@cloudless.tool
def lookup_order(order_id: str) -> dict:
    """Look up an order by ID."""
    return {"id": order_id, "status": "shipped"}
```

Or from existing infrastructure:

```python
lambda_tool = cloudless.Tool.from_aws_lambda(arn="arn:aws:lambda:...")
api_tool    = cloudless.Tool.from_openapi("https://api.example.com/openapi.json", operation_id="search")
mcp_tool    = cloudless.Tool.from_mcp_server("https://mcp.example.com", tool_name="search")
```

## HITL pause

```python
from cloudless.chunks import PauseChunk
from cloudless.runtime.tasks import pause

async def query(self, ctx, prompt):
    if amount > 1000:
        rec = pause(
            agent_name=self.name,
            session_id=ctx.session.id,
            reason="refund > $1000 needs approval",
            pending_action={"amount": amount},
        )
        yield PauseChunk(
            resume_token=rec.resume_token,
            reason=rec.reason,
            pending_action=rec.pending_action,
        )
        return
```

A separate `resume(token, approval)` call delivers the human's decision
(typically from an approval UI). The state is persisted by the configured
`TaskStore` — in-memory in dev, AgentCore Memory or Memory Bank in cloud.

## Policies

```python
@cloudless.policy(stages=["before_llm"], name="block-ssn")
def block_ssn(stage, prompt, **kw):
    if re.search(r"\d{3}-\d{2}-\d{4}", prompt):
        raise cloudless.PolicyViolation("SSN detected")
    return None  # no transform; just inspect
```

Policies run in priority order across six stages: `before_llm`,
`after_llm`, `before_tool`, `after_tool`, `before_peer`, `after_peer`.
Every block / transform emits an `AuditRecord` to the configured sink chain.

## What's next

- [Multi-agent patterns](../concepts/patterns.md) — orchestrate beyond one agent
- [Deploy to AWS](../guides/deploy-aws.md) — what `cloudless deploy` does behind the scenes
- [Deploy to GCP](../guides/deploy-gcp.md) — the Vertex Agent Engine path
- [Examples](https://github.com/nbalawat/cloudless-framework/tree/main/examples) — including the kitchen-sink agent
