# Governance & audit

Two layers, both cloud-portable:

1. **`@cloudless.policy`** — Python policies that run regardless of cloud
2. **Bedrock Guardrails** — cloud-native filters that attach to the LLM

Both emit `AuditRecord` events to a pluggable sink chain.

## Python policies

```python
import re
import cloudless

@cloudless.policy(stages=["before_llm"], name="block-ssn", priority=10)
def block_ssn(stage, prompt, **kw):
    if re.search(r"\d{3}-\d{2}-\d{4}", prompt):
        raise cloudless.PolicyViolation("SSN detected")
    return None   # no transform
```

The six stages:

| Stage         | Receives                                    | Can transform     |
|---------------|---------------------------------------------|-------------------|
| `before_llm`  | `prompt, model, ctx`                        | `prompt`          |
| `after_llm`   | `prompt, response, model, ctx`              | `response`        |
| `before_tool` | `tool_name, args`                           | `args`            |
| `after_tool`  | `tool_name, args, result`                   | `result`          |
| `before_peer` | `peer, prompt`                              | `prompt`          |
| `after_peer`  | `peer, prompt, response`                    | `response`        |

Higher priority runs first. Raising `PolicyViolation` short-circuits the
stage; returning a value replaces the relevant field; returning `None` is
a pass-through.

## Bedrock Guardrails

```python
llm = cloudless.LLM(model="claude-haiku", guardrail_id="gd-abc123")
```

When the guardrail intervenes (returns `stopReason=guardrail_intervened`),
cloudless raises `GuardrailBlocked` and emits an audit record with the
guardrail trace embedded.

## Audit sink chain

The default sink is `StructlogSink` (WARN level under `cloudless.audit`).
You can append your own:

```python
from cloudless.runtime.audit import add_sink, FileSink

add_sink(FileSink("/var/log/cloudless-audit.jsonl"))
```

Every block + transform writes an `AuditRecord`:

```python
@dataclass(frozen=True)
class AuditRecord:
    timestamp: float
    stage: str            # e.g. "before_llm"
    decision: str         # "block" / "transform" / "allow"
    policy_name: str
    reason: str
    payload_hash: str     # SHA-256 prefix, not the raw payload
    agent_name: str | None
    session_id: str | None
    user_id: str | None
    extra: dict
```

Payloads are **hashed**, not stored — security teams get correlation
without retaining sensitive content.
