"""Unit tests for cloudless.catalog.llm — model alias resolution.

No cloud calls; the resolve_model() function is pure Python lookup.
"""
from __future__ import annotations

import pytest

import cloudless
from cloudless.catalog.llm import (
    DEFAULT_ALIASES,
    ModelAlias,
    list_models,
    resolve_model,
)
from cloudless.exceptions import InvalidInputError


class TestResolveByAlias:
    @pytest.mark.parametrize("alias", ["nova-micro", "nova-lite", "nova-pro"])
    def test_resolves_nova_aliases(self, alias):
        a = resolve_model(alias)
        assert a.provider == "bedrock"
        assert a.model_id.startswith("us.amazon.nova-")
        assert a.streaming_safe is True

    @pytest.mark.parametrize("alias", ["claude-haiku", "claude-sonnet", "claude-opus"])
    def test_claude_aliases_flagged_streaming_unsafe(self, alias):
        # F15: Anthropic gates converse_stream separately
        a = resolve_model(alias)
        assert a.provider == "bedrock"
        assert a.model_id.startswith("us.anthropic.claude-")
        assert a.streaming_safe is False, \
            "Anthropic models must be flagged streaming_safe=False until form is approved (F15)"


class TestResolveByModelId:
    def test_known_model_id_resolves_to_alias_metadata(self):
        a = resolve_model("us.amazon.nova-micro-v1:0")
        assert a.alias == "nova-micro"
        assert a.streaming_safe is True

    def test_unknown_bedrock_model_id_passes_through(self):
        a = resolve_model("us.cohere.command-r-plus")
        assert a.provider == "bedrock"
        assert a.model_id == "us.cohere.command-r-plus"
        # Pessimistic default — we don't know if streaming is approved
        assert a.streaming_safe is False
        assert "Unknown" in a.notes


class TestResolveRejects:
    def test_rejects_garbage(self):
        with pytest.raises(InvalidInputError, match="Unknown LLM model"):
            resolve_model("definitely-not-a-real-model")

    def test_rejects_empty(self):
        with pytest.raises(InvalidInputError):
            resolve_model("")


class TestListModels:
    def test_lists_all_when_no_filter(self):
        assert len(list(list_models())) == len(DEFAULT_ALIASES)

    def test_filter_by_provider(self):
        bedrock = list(list_models(provider="bedrock"))
        gemini = list(list_models(provider="gemini"))
        assert all(m.provider == "bedrock" for m in bedrock)
        assert all(m.provider == "gemini" for m in gemini)
        assert len(bedrock) + len(gemini) == len(DEFAULT_ALIASES)


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.LLM is not None
        assert cloudless.ModelAlias is ModelAlias
        assert cloudless.resolve_model is resolve_model
