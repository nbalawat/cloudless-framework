# Resilience

cloudless exposes three composable async wrappers + a decorator.

## with_retry

```python
from cloudless.runtime import with_retry

result = await with_retry(
    lambda: llm.invoke(prompt),
    attempts=3, backoff=0.25, max_backoff=10.0, jitter=0.1,
)
```

Honors `recoverable=True` on `TransientError` subclasses. `PermanentError`
raises immediately — no retry. Server-side `retry_after` (e.g. 429 with
Retry-After header) is honored verbatim.

## with_timeout

```python
from cloudless.runtime import with_timeout

result = await with_timeout(lambda: llm.invoke(prompt), seconds=10.0)
```

Translates `asyncio.TimeoutError` to `cloudless.TimeoutError` (which
*is* a `TransientError`, so it composes with retry).

## CircuitBreaker

```python
from cloudless.runtime import CircuitBreaker

breaker = CircuitBreaker(name="bedrock", failure_threshold=5, recovery_timeout=30.0)

result = await breaker.call(lambda: llm.invoke(prompt))
```

States: CLOSED → (N consecutive failures) → OPEN → (recovery_timeout)
→ HALF_OPEN → (one success) → CLOSED, or → (one failure) → OPEN again.

Permanent errors don't trip the breaker — they're not infrastructure issues.

## @resilient (composed)

```python
from cloudless.runtime import resilient

@resilient(attempts=3, timeout_seconds=10.0, circuit="bedrock")
async def call_llm(prompt):
    return await llm.invoke(prompt)
```

Order is `breaker(retry(timeout(fn)))` — the circuit sees the final
success or failure *after* retries are exhausted, which is the right
semantics for "is this dependency healthy?".
