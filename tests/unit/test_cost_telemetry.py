"""Unit tests for Q20 cost telemetry + A2A attribution propagation."""
from __future__ import annotations

import pytest

from cloudless.runtime.context import InMemoryContext
from cloudless.runtime.pricing import DEFAULT_PRICES, estimate_cost_usd

pytestmark = [pytest.mark.asyncio]


def test_estimate_cost_basic_nova_micro():
    cost = estimate_cost_usd(
        "us.amazon.nova-micro-v1:0",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    p = DEFAULT_PRICES["us.amazon.nova-micro-v1:0"]
    assert cost == pytest.approx(p.input_per_million + p.output_per_million)


def test_estimate_cost_cached_input_discount():
    # Cached portion shouldn't be billed at full input rate.
    cost_with_cache = estimate_cost_usd(
        "us.amazon.nova-pro-v1:0",
        input_tokens=1_000_000,
        output_tokens=0,
        cached_tokens=500_000,
    )
    cost_no_cache = estimate_cost_usd(
        "us.amazon.nova-pro-v1:0",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    # Today defaults treat cached at full input rate (cached_per_million=0
    # falls back). The math should still match the no-cache cost.
    assert cost_with_cache == pytest.approx(cost_no_cache)


def test_estimate_cost_unknown_model_uses_fallback():
    cost = estimate_cost_usd(
        "made-up-model-xyz",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost > 0  # falls back to FALLBACK_PRICE


def test_estimate_cost_reasoning_billed_as_output():
    cost = estimate_cost_usd(
        "gemini-2.5-flash",
        input_tokens=0,
        output_tokens=0,
        reasoning_tokens=1_000_000,
    )
    assert cost == pytest.approx(DEFAULT_PRICES["gemini-2.5-flash"].output_per_million)


async def test_session_total_usd_sums_calls():
    ctx = InMemoryContext()
    ctx.cost.record_llm_call(
        model="us.amazon.nova-micro-v1:0",
        input_tokens=1_000_000, output_tokens=0,
    )
    ctx.cost.record_llm_call(
        model="us.amazon.nova-micro-v1:0",
        input_tokens=0, output_tokens=1_000_000,
    )
    p = DEFAULT_PRICES["us.amazon.nova-micro-v1:0"]
    expected = p.input_per_million + p.output_per_million
    total = await ctx.cost.session_total_usd()
    assert total == pytest.approx(expected)


# ------------------- A2A attribution propagation ------------------------ #


def test_attribution_headers_set_on_attribute():
    ctx = InMemoryContext()
    ctx.cost.attribute(team="payments", project="checkout-redesign")
    headers = ctx.cost.attribution_headers()
    assert headers == {
        "X-Cloudless-Attribution-Team": "payments",
        "X-Cloudless-Attribution-Project": "checkout-redesign",
    }


def test_attribution_headers_ingest_merges():
    ctx = InMemoryContext()
    ctx.cost.ingest_attribution_headers({
        "X-Cloudless-Attribution-Team": "fraud",
        "X-Cloudless-Attribution-Project": "score-v2",
        "X-Unrelated-Header": "ignore me",
    })
    assert ctx.cost.attribution == {"team": "fraud", "project": "score-v2"}


def test_attribution_setdefault_does_not_overwrite_existing():
    """If a downstream agent already has its own tags, headers should not clobber."""
    ctx = InMemoryContext()
    ctx.cost.attribute(team="local-team")
    ctx.cost.ingest_attribution_headers({"X-Cloudless-Attribution-Team": "remote-team"})
    assert ctx.cost.attribution["team"] == "local-team"


async def test_peer_cost_propagation_adds_to_total():
    ctx = InMemoryContext()
    ctx.cost.record_peer_call(peer="orders", usd=0.42)
    ctx.cost.record_peer_call(peer="fraud", usd=0.08)
    total = await ctx.cost.session_total_usd()
    assert total == pytest.approx(0.50)
