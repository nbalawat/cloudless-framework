"""Unit tests for grounding kwarg dispatch (bool vs str)."""
from __future__ import annotations

import pytest


def test_grounding_true_emits_google_search_tool():
    pytest.importorskip("google.genai")
    from cloudless.adapters.gcp.llm import GeminiBackend
    # Construct without real client by mocking
    backend = GeminiBackend.__new__(GeminiBackend)
    backend.model_id = "gemini-2.5-flash"
    backend.extended_thinking = False
    backend.safety_settings = None
    backend.model_armor_template = None
    backend.grounding = True
    backend.cached_content = None

    config = backend._build_config(system=None, max_tokens=128)
    assert config["tools"] == [{"google_search": {}}]


def test_grounding_string_emits_vertex_search_tool():
    pytest.importorskip("google.genai")
    from cloudless.adapters.gcp.llm import GeminiBackend
    backend = GeminiBackend.__new__(GeminiBackend)
    backend.model_id = "gemini-2.5-flash"
    backend.extended_thinking = False
    backend.safety_settings = None
    backend.model_armor_template = None
    ds = "projects/p/locations/global/collections/default_collection/dataStores/myds"
    backend.grounding = ds
    backend.cached_content = None

    config = backend._build_config(system=None, max_tokens=128)
    assert config["tools"][0]["retrieval"]["vertex_ai_search"]["datastore"] == ds


def test_grounding_false_no_tools():
    pytest.importorskip("google.genai")
    from cloudless.adapters.gcp.llm import GeminiBackend
    backend = GeminiBackend.__new__(GeminiBackend)
    backend.model_id = "gemini-2.5-flash"
    backend.extended_thinking = False
    backend.safety_settings = None
    backend.model_armor_template = None
    backend.grounding = False
    backend.cached_content = None

    config = backend._build_config(system=None, max_tokens=128)
    assert "tools" not in config
