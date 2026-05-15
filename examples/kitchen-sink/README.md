# Kitchen-sink example

This is a deliberately maxed-out cloudless agent that exercises every primitive
in one place — useful as a reference, **not** as a template for real agents.

## What it shows

| Primitive | Where in the code |
|---|---|
| `cloudless.LLM` (Bedrock Nova Micro) | `_classify()` in `ConciergeAgent.query` |
| `cloudless.Embeddings` (Titan v2) | `self._embeddings` |
| `cloudless.VectorStore` (in-memory) | `self._vectors` |
| `@cloudless.tool` | `lookup_order_status`, `issue_refund` |
| `@cloudless.policy(stages=["before_llm"])` | `block_ssn` |
| `@cloudless.policy(stages=["after_llm"])` | `cap_response_length` |
| `cloudless.exceptions.CostCapExceeded` | session-cost guard in `query()` |
| `cloudless.runtime.resilient` decorator | wraps `_classify()` |
| `cloudless.runtime.tasks.pause` + `PauseChunk` | REFUND_LARGE branch (HITL) |
| Chunk taxonomy (`ReasoningChunk`, `ToolCallChunk`, `ToolResultChunk`, `FinalChunk`) | yields throughout |

## Try it

```bash
cd examples/kitchen-sink
cloudless doctor
cloudless dev concierge
```

In another terminal:

```bash
curl -X POST localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What is the status of my order?"}'

# Streaming:
curl -N -X POST localhost:8080/invocations/stream \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What is the status of my order?"}'
```

## Cost rollup

```bash
# Pipe a session of cost events through:
cloudless cost --by team
```

## Cleanup

If you deploy this example and want to nuke everything:

```bash
cloudless cleanup --prefix kitchen-sink --yes
```

(uses the `MIN_PREFIX_LENGTH = 8` safety rail).
