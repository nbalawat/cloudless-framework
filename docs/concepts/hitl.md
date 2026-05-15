# HITL & long-running tasks

Human-in-the-loop in cloudless is a `PauseChunk` plus a persistent
`TaskStore`. Any agent, any pattern, any point in a generator.

## The pattern

```python
from cloudless.chunks import PauseChunk
from cloudless.runtime.tasks import pause, resume

async def query(self, ctx, prompt):
    if amount > 1000:
        rec = pause(
            agent_name=self.name,
            session_id=ctx.session.id,
            reason="refund > $1000 needs approval",
            pending_action={"amount": amount, "order": order_id},
            ttl_seconds=86400,   # 24h default
        )
        yield PauseChunk(
            resume_token=rec.resume_token,
            reason=rec.reason,
            pending_action=rec.pending_action,
            expires_at=rec.expires_at,
        )
        return    # ← agent terminates; runtime persists state

    # ... happy path ...
```

A separate process — typically an approval UI — calls `resume(token, approval)`
when the human decides. `resume` is **idempotent**: a second call returns
`None`, so double-clicks are harmless.

## Task stores

| Store                  | Backing                       | Use case                       |
|------------------------|-------------------------------|--------------------------------|
| `InMemoryTaskStore`    | Python dict                   | `cloudless dev`, unit tests    |
| `AgentCoreTaskStore`   | AgentCore Memory events       | AWS production deploys         |
| `MemoryBankTaskStore`  | Vertex Memory Bank scopes     | GCP production deploys         |

The default in-process store is replaced by the deploy adapter at runtime
init — agents never see the difference.

## Composition with patterns

HITL is composable with every multi-agent pattern. Canonical insertion
points:

- **Sequential**: between two stages, before an irreversible step
- **Routing**: when classifier confidence is below threshold
- **Parallel**: when reviewers disagree materially
- **Supervisor**: after planning, before workers execute
- **Evaluator-optimizer**: when iteration limit exceeded without convergence
- **A2A peer**: when remote returns `needs_escalation=true`
- **Hierarchical**: at the executive level for high-impact decisions
- **Map-reduce**: for approval of the reduced output
- **Debate**: when judge confidence is low
- **Tool-as-agent**: via a `before_tool` policy

All ten are exercised in the [multi-agent pattern integration tests](https://github.com/nbalawat/cloudless-framework/tree/main/tests/integration/patterns).

## Querying pending tasks

```python
from cloudless.runtime.tasks import list_active_tasks

for task in list_active_tasks():
    print(f"{task.resume_token}  agent={task.agent_name}  reason={task.reason}")
```

An external approval UI typically queries the cloud store directly via
the per-cloud helper:

```python
from cloudless.adapters.aws.tasks import AgentCoreTaskStore
store = AgentCoreTaskStore(memory_id="cloudless-prod-memory")
pending = store.list_active_for_agent("orders")
```
