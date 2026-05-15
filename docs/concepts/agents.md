# The agent class

A cloudless agent is one Python class decorated with `@cloudless.agent`.
The decorator stores `AgentMetadata` on the class. The deploy planner
reads this metadata to produce cloud-native artifacts.

```python
@cloudless.agent(
    name="support",                  # required, kebab-case, used in URLs + manifest
    framework="langgraph",           # required for framework adapters
    interfaces=["http", "a2a"],      # protocols this agent serves
    description="Support agent.",
    version="0.1.0",                 # user-facing version
    tags=("support", "tier1"),
)
class SupportAgent(cloudless.LangGraphAgent):
    def build(self): ...
```

## Why one class per agent

- The deploy adapter packages each class as its own AgentCore runtime
  (AWS) or its own Vertex Agent Engine (GCP).
- A single repo can host many agents — they're discovered by walking
  `src/agents/*.py` and matching `@cloudless.agent` decorators.
- Cross-agent calls go through the manifest, not direct imports — so
  each agent stays a deployable unit.

## Framework adapters

Pick a framework, inherit from the corresponding base, and write your
framework code unchanged:

| Framework | Base class                    | Notes                              |
|-----------|-------------------------------|------------------------------------|
| LangGraph | `cloudless.LangGraphAgent`    | Compose `StateGraph`s as usual.    |
| Strands   | `cloudless.StrandsAgent`      | A2A v0.3-pinned (F3).              |
| ADK       | `cloudless.adapters.frameworks.ADKAgent` | GCP-only at v0.x.        |

Custom: inherit from `cloudless.Agent` directly and implement
`async def query(self, ctx, prompt)` as a chunk-yielding async generator.

## What `interfaces` means

The list declares which protocols the agent's runtime should expose:

- `http` — JSON POST `/invocations` endpoint, plus SSE `/invocations/stream`
- `a2a` — JSON-RPC 2.0 `/a2a` endpoint per A2A v0.3 spec
- `mcp` — Model Context Protocol endpoint (M3)
- `ag-ui` — Anthropic AG-UI protocol (M3)

The deploy planner emits exactly one runtime per `(protocol, auth_mode)`
tuple. On AWS, AgentCore is single-auth-mode per runtime (F11a), so the
planner may emit multiple runtimes per agent if `interfaces` mixes
auth-incompatible protocols.
