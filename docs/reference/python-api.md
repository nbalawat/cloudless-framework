# Python API reference

The cloudless public surface — everything you import from `cloudless.*`.

## Top-level surface

```python
import cloudless

cloudless.agent            # @decorator + AgentMetadata
cloudless.Agent            # ABC
cloudless.LangGraphAgent   # framework base
cloudless.StrandsAgent     # framework base

# Chunks
cloudless.TextChunk
cloudless.ReasoningChunk
cloudless.ToolCallChunk
cloudless.ToolResultChunk
cloudless.StateChunk
cloudless.PauseChunk
cloudless.FinalChunk
cloudless.ErrorChunk

# Service primitives
cloudless.LLM
cloudless.Embeddings
cloudless.Memory
cloudless.Secrets
cloudless.Sandbox
cloudless.VectorStore
cloudless.Tool
cloudless.tool             # decorator form

# Context
cloudless.Context
cloudless.InMemoryContext

# Governance
cloudless.policy
cloudless.get_policy_registry

# Resilience
cloudless.resilient
cloudless.with_retry
cloudless.with_timeout
cloudless.CircuitBreaker
cloudless.get_breaker

# Exceptions
cloudless.CloudlessError        # base
cloudless.TransientError         # safe to retry
cloudless.TimeoutError
cloudless.ThrottledError
cloudless.PeerUnreachable
cloudless.CircuitOpen
cloudless.PermanentError        # do NOT retry
cloudless.PolicyViolation
cloudless.GuardrailBlocked
cloudless.AuthenticationError
cloudless.InvalidInputError
cloudless.CostCapExceeded
```

## Runtime extras

```python
from cloudless.runtime import (
    tracing,                  # OTel span helpers
    pause, resume, get_task,  # HITL tasks
    A2APeerClient, CognitoIdentity, build_peer_client,
    build_a2a_app,           # inbound A2A server
    Manifest, ManifestRefresher, load_manifest,
    add_audit_sink, emit_audit, FileSink, InMemorySink, StructlogSink,
    add_cost_sink, JsonlCostSink, InMemoryCostSink,
)
```

## Type safety

The package ships with `py.typed`. mypy `--strict` is clean over the public
surface; adapters and CLI internals are excluded from strict checking due
to dynamic cloud-SDK shapes.

## Stability commitment

| Phase   | Promise                                              |
|---------|------------------------------------------------------|
| v0.x    | MINOR may break (Python ecosystem norm)              |
| v1.x    | SemVer; breaking changes only in MAJOR               |
| v2.0+   | LTS on even MAJORs (2.0, 4.0, ...)                   |

See [`ROADMAP.md`](../ROADMAP.md) for the v1.0 commitment timeline.
