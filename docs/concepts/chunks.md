# Chunks

Every `agent.query(ctx, prompt)` returns an `AsyncIterator[Chunk]`.
Chunks are typed Pydantic v2 frozen models — they serialize cleanly to
JSON, compose with framework adapters, and let frontends specialize per
chunk type.

## The taxonomy

| Chunk             | When yielded                                              |
|-------------------|-----------------------------------------------------------|
| `TextChunk`       | Token-by-token model output                               |
| `ReasoningChunk`  | Extended-thinking content (Claude / Gemini 2.5 thoughts)  |
| `ToolCallChunk`   | Tool invocation begin                                     |
| `ToolResultChunk` | Tool result (may be error)                                |
| `StateChunk`      | Graph-state snapshot (LangGraph state)                    |
| `PauseChunk`      | HITL pause point — agent halts, awaits human              |
| `FinalChunk`      | Terminal marker; optional final state                     |
| `ErrorChunk`      | Recoverable mid-stream error                              |

## Why typed chunks

- Frontend renderers specialize per type (text vs reasoning fold)
- Cost telemetry bills reasoning tokens separately from output (F2 — Gemini 2.5 reports them distinctly)
- A2A peers can react differently to tool calls vs final answers
- Forward-compatible: new chunk types added without breaking the stream

## Discriminator

Every chunk has a `kind` string. Pattern-match consumers can do either:

```python
async for chunk in agent.query(ctx, prompt):
    match chunk.kind:
        case "text":     ...
        case "pause":    ...
        case "final":    ...
```

or:

```python
if isinstance(chunk, TextChunk): ...
```

## Pause-and-resume semantics

`PauseChunk` is special: it's the only chunk that means "the agent has
yielded control until something external happens". The agent's `query`
generator returns immediately after yielding a `PauseChunk` — the
runtime persists the task state, and a later `resume(token, approval)`
call delivers the human's decision.

See [HITL & long-running tasks](hitl.md) for the full lifecycle.
