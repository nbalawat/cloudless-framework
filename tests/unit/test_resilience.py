"""Unit tests for cloudless.runtime.resilience (Q21 retry/timeout/circuit-breaker)."""
from __future__ import annotations

import asyncio

import pytest

from cloudless.exceptions import (
    CircuitOpen,
    InvalidInputError,
    ThrottledError,
)
from cloudless.exceptions import (
    TimeoutError as CloudlessTimeoutError,
)
from cloudless.runtime.resilience import (
    CircuitBreaker,
    get_breaker,
    reset_breakers,
    resilient,
    with_retry,
    with_timeout,
)

pytestmark = [pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean_breakers():
    reset_breakers()
    yield
    reset_breakers()


# ----------------------------- retry ------------------------------------ #


async def test_with_retry_succeeds_eventually():
    attempts = {"n": 0}

    async def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ThrottledError("throttled")
        return "ok"

    result = await with_retry(fn, attempts=5, backoff=0.001)
    assert result == "ok"
    assert attempts["n"] == 3


async def test_with_retry_does_not_retry_permanent_errors():
    attempts = {"n": 0}

    async def fn():
        attempts["n"] += 1
        raise InvalidInputError("bad")

    with pytest.raises(InvalidInputError):
        await with_retry(fn, attempts=5, backoff=0.001)
    assert attempts["n"] == 1  # no retry on permanent


async def test_with_retry_exhausts_and_raises_last():
    async def fn():
        raise ThrottledError("nope")

    with pytest.raises(ThrottledError):
        await with_retry(fn, attempts=3, backoff=0.001)


async def test_with_retry_respects_retry_after_hint():
    """retry_after hint should be honored (we check timing)."""
    import time
    attempts = {"n": 0}

    async def fn():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ThrottledError("throttled", retry_after=0.05)
        return "ok"

    t0 = time.monotonic()
    result = await with_retry(fn, attempts=2, backoff=0.001, jitter=0)
    elapsed = time.monotonic() - t0
    assert result == "ok"
    assert elapsed >= 0.04


# ----------------------------- timeout ---------------------------------- #


async def test_with_timeout_translates_asyncio_to_cloudless():
    async def slow():
        await asyncio.sleep(1.0)

    with pytest.raises(CloudlessTimeoutError):
        await with_timeout(slow, seconds=0.05)


async def test_with_timeout_passes_through_fast():
    async def fast():
        return 42

    assert await with_timeout(fast, seconds=1.0) == 42


# ----------------------------- circuit breaker -------------------------- #


async def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.05)

    async def failing():
        raise ThrottledError("nope")

    with pytest.raises(ThrottledError):
        await cb.call(failing)
    with pytest.raises(ThrottledError):
        await cb.call(failing)
    # Now OPEN — next call should raise CircuitOpen without invoking fn
    called = {"n": 0}

    async def tracker():
        called["n"] += 1
        raise ThrottledError("should not see")

    with pytest.raises(CircuitOpen):
        await cb.call(tracker)
    assert called["n"] == 0


async def test_circuit_breaker_half_opens_after_recovery():
    cb = CircuitBreaker(name="t", failure_threshold=1, recovery_timeout=0.05)

    async def fail():
        raise ThrottledError("x")

    with pytest.raises(ThrottledError):
        await cb.call(fail)
    # Should now be open
    with pytest.raises(CircuitOpen):
        await cb.call(fail)
    await asyncio.sleep(0.06)

    # Half-open: probe call allowed; success closes the breaker
    async def succeed():
        return "ok"

    assert await cb.call(succeed) == "ok"
    # Closed again — another success works
    assert await cb.call(succeed) == "ok"
    # And a single failure (threshold=1) re-opens it
    with pytest.raises(ThrottledError):
        await cb.call(fail)
    with pytest.raises(CircuitOpen):
        await cb.call(succeed)


async def test_permanent_errors_do_not_trip_circuit():
    cb = CircuitBreaker(name="p", failure_threshold=2)

    async def permanent():
        raise InvalidInputError("bad")

    for _ in range(5):
        with pytest.raises(InvalidInputError):
            await cb.call(permanent)
    # Still CLOSED
    async def ok():
        return 1
    assert await cb.call(ok) == 1


# ----------------------------- resilient() decorator -------------------- #


async def test_resilient_combines_retry_timeout_breaker():
    attempts = {"n": 0}

    @resilient(attempts=3, backoff=0.001, timeout_seconds=1.0, circuit="combo")
    async def call():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ThrottledError("retry me")
        return "fine"

    assert await call() == "fine"
    assert attempts["n"] == 2
    # Breaker is registered
    assert get_breaker("combo")._state == "CLOSED"


async def test_resilient_decorator_caps_runtime_via_timeout():
    @resilient(attempts=1, timeout_seconds=0.05)
    async def slow():
        await asyncio.sleep(1.0)

    with pytest.raises(CloudlessTimeoutError):
        await slow()
