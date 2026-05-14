"""Unit tests for cloudless ops CLI helpers (no cloud calls)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from cloudless.cli.ops import _parse_since, _to_runtime_name


class TestParseSince:
    @pytest.mark.parametrize("s,expected", [
        ("10m", timedelta(minutes=10)),
        ("1h", timedelta(hours=1)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("90m", timedelta(minutes=90)),
    ])
    def test_known_formats(self, s, expected):
        assert _parse_since(s) == expected

    @pytest.mark.parametrize("bad", ["", "10", "1week", "1y", "abc"])
    def test_rejects_bad(self, bad):
        with pytest.raises(ValueError):
            _parse_since(bad)


class TestToRuntimeName:
    """The deploy adapter converts kebab → snake; ops commands must mirror."""

    @pytest.mark.parametrize("agent,runtime", [
        ("hello", "hello"),
        ("customer-support", "customer_support"),
        ("orders-v2", "orders_v2"),
        ("already_snake", "already_snake"),
    ])
    def test_kebab_to_snake(self, agent, runtime):
        assert _to_runtime_name(agent) == runtime
