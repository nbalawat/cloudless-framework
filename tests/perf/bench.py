"""Latency benchmark helpers.

Tiny pure-Python benchmark runner — no pytest-benchmark dep. Reports
p50/p95/p99 and mean over N iterations.
"""
from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class BenchResult:
    name: str
    n: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float

    def __str__(self) -> str:
        return (
            f"{self.name:30s}  n={self.n:4d}  "
            f"p50={self.p50_ms:7.2f}ms  p95={self.p95_ms:7.2f}ms  "
            f"p99={self.p99_ms:7.2f}ms  mean={self.mean_ms:7.2f}ms  "
            f"min={self.min_ms:7.2f}  max={self.max_ms:7.2f}"
        )


async def bench_async(
    name: str,
    fn: Callable[[], Awaitable[object]],
    *,
    iterations: int = 200,
    warmup: int = 20,
) -> BenchResult:
    """Time an async callable across `iterations` runs after `warmup` warmups."""
    for _ in range(warmup):
        await fn()
    samples_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await fn()
        samples_ms.append((time.perf_counter() - t0) * 1000)

    samples_ms.sort()
    return BenchResult(
        name=name,
        n=iterations,
        p50_ms=samples_ms[len(samples_ms) // 2],
        p95_ms=samples_ms[int(len(samples_ms) * 0.95)],
        p99_ms=samples_ms[int(len(samples_ms) * 0.99)],
        mean_ms=statistics.mean(samples_ms),
        min_ms=samples_ms[0],
        max_ms=samples_ms[-1],
    )


def bench_sync(
    name: str,
    fn: Callable[[], object],
    *,
    iterations: int = 200,
    warmup: int = 20,
) -> BenchResult:
    """Time a sync callable."""
    for _ in range(warmup):
        fn()
    samples_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples_ms.append((time.perf_counter() - t0) * 1000)

    samples_ms.sort()
    return BenchResult(
        name=name,
        n=iterations,
        p50_ms=samples_ms[len(samples_ms) // 2],
        p95_ms=samples_ms[int(len(samples_ms) * 0.95)],
        p99_ms=samples_ms[int(len(samples_ms) * 0.99)],
        mean_ms=statistics.mean(samples_ms),
        min_ms=samples_ms[0],
        max_ms=samples_ms[-1],
    )
