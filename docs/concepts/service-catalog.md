# Service catalog

The catalog is the set of cloud-native primitives cloudless wraps with a
uniform Python API. Each primitive has an AWS-backed adapter and a
GCP-backed adapter so your agent code stays cloud-agnostic.

## The primitives

| Primitive            | AWS backend                            | GCP backend                                   |
|----------------------|----------------------------------------|-----------------------------------------------|
| `LLM`                | Bedrock (Nova, Claude)                 | Vertex Gemini                                 |
| `Embeddings`         | Bedrock (Titan, Cohere)                | Vertex `text-embedding-005`, Gemini Embed     |
| `Memory`             | AgentCore Memory                       | Vertex Memory Bank                            |
| `Secrets`            | AWS Secrets Manager                    | GCP Secret Manager                            |
| `Sandbox`            | AgentCore Code Interpreter             | (in-process subprocess at v0.x)               |
| `VectorStore`        | Bedrock Knowledge Bases                | (in-memory at v0.x)                           |
| `Tool`               | factory: function / Lambda / OpenAPI / MCP | same                                       |

## Construction

Primitives are constructed once, used many times:

```python
llm     = cloudless.LLM(model="nova-micro")
embed   = cloudless.Embeddings(model="titan-v2")
mem     = cloudless.Memory(strategy="semantic")
secrets = cloudless.Secrets()
```

Each construction takes the cloud config (region, project, etc.) implicitly
from environment or `cloudless.yaml`. Override per-instance if you need to:

```python
llm = cloudless.LLM(model="gemini-flash", project="my-gcp-proj", location="us-central1")
```

## Pricing-aware cost tracking

Every `LLM` call records to `ctx.cost`. The pricing table (per model,
per million tokens) lives in `cloudless.runtime.pricing`. `await ctx.cost.session_total_usd()`
returns the running total — cap it with a policy or `CostCapExceeded`.

## Adapter dispatch

The `provider` field on each alias determines the backend:

```python
from cloudless.catalog.llm import resolve_model
alias = resolve_model("gemini-flash")
alias.provider   # "gemini"
alias.model_id   # "gemini-2.5-flash"
```

Both Bedrock and Vertex aliases are first-class. Add custom models by
extending the `DEFAULT_ALIASES` tuple.
