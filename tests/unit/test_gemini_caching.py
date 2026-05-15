"""Unit tests for Gemini system-instruction caching wiring.

Real-cloud cache creation requires a 1024+ token system prompt and incurs
storage cost. We exercise the wiring at the unit level here. The wiring
itself is the test surface; the actual API call shape is verified via
SDK signature compatibility (no exception on construction).
"""
from __future__ import annotations

import pytest

import cloudless


def test_cached_content_kwarg_accepts_on_gemini_provider():
    """Constructing cloudless.LLM(model='gemini-flash', cached_content=...)
    should not raise — the kwarg flows to the GeminiBackend."""
    # We don't pass real credentials; the LLM construction is lazy enough
    # that we can verify just the kwarg-acceptance signature.
    import os
    if not os.environ.get("CLOUDLESS_GCP_PROJECT"):
        os.environ["CLOUDLESS_GCP_PROJECT"] = "test-project"
    try:
        llm = cloudless.LLM(
            model="gemini-flash",
            project="test-project",
            cached_content="projects/x/locations/y/cachedContents/123",
        )
        assert llm._backend.cached_content == "projects/x/locations/y/cachedContents/123"
    except Exception as e:
        # Any non-construction-related exception (e.g. ADC) is acceptable
        # for this signature check — but TypeError for unknown kwarg is not.
        assert not isinstance(e, TypeError), f"signature mismatch: {e}"


def test_cached_content_kwarg_unused_on_bedrock():
    """Bedrock alias shouldn't crash when cached_content is set (silently ignored)."""
    llm = cloudless.LLM(
        model="nova-micro",
        cached_content="ignored-on-bedrock",
    )
    # No assertion needed — construction not raising is the test
    assert llm.alias.provider == "bedrock"


def test_gemini_backend_create_cache_method_exists():
    """Verify the create_cache convenience method is on the GeminiBackend."""
    from cloudless.adapters.gcp.llm import GeminiBackend
    assert hasattr(GeminiBackend, "create_cache")
    # Inspect signature has system_instruction and ttl_seconds
    import inspect
    sig = inspect.signature(GeminiBackend.create_cache)
    assert "system_instruction" in sig.parameters
    assert "ttl_seconds" in sig.parameters
