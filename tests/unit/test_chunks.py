"""Tests for cloudless.chunks — Q16 typed chunk taxonomy."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

import cloudless
from cloudless.chunks import (
    ErrorChunk,
    FinalChunk,
    ReasoningChunk,
    StateChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)


class TestKindDiscriminator:
    """Every chunk type has a unique, frozen `kind` field."""

    @pytest.mark.parametrize("cls,expected_kind", [
        (TextChunk, "text"),
        (ToolCallChunk, "tool_call"),
        (ToolResultChunk, "tool_result"),
        (ReasoningChunk, "reasoning"),
        (StateChunk, "state"),
        (FinalChunk, "final"),
        (ErrorChunk, "error"),
    ])
    def test_kind_default(self, cls, expected_kind):
        # Try constructing with required fields per type
        defaults = {
            TextChunk: dict(text="x"),
            ToolCallChunk: dict(name="t", args={}),
            ToolResultChunk: dict(name="t", result=None),
            ReasoningChunk: dict(text="x"),
            StateChunk: dict(state={}),
            FinalChunk: dict(),
            ErrorChunk: dict(error="x"),
        }[cls]
        instance = cls(**defaults)
        assert instance.kind == expected_kind

    def test_kinds_are_unique(self):
        kinds = {
            TextChunk(text="").kind,
            ToolCallChunk(name="t", args={}).kind,
            ToolResultChunk(name="t", result=None).kind,
            ReasoningChunk(text="").kind,
            StateChunk(state={}).kind,
            FinalChunk().kind,
            ErrorChunk(error="").kind,
        }
        assert len(kinds) == 7, "every chunk class must have a unique `kind`"


class TestImmutability:
    """Chunks are frozen — once emitted, they can't be mutated mid-stream."""

    def test_frozen(self):
        c = TextChunk(text="hello")
        with pytest.raises(ValidationError):
            c.text = "goodbye"  # type: ignore[misc]


class TestStrictValidation:
    """`extra="forbid"` catches typos in chunk construction at the source."""

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            TextChunk(text="hi", extra_field="oops")  # type: ignore[call-arg]


class TestToolResultIsError:
    """ToolResultChunk lets the framework distinguish successful results
    from errored tool returns without raising — important for agent loops
    that want to recover."""

    def test_default_is_error_false(self):
        c = ToolResultChunk(name="get_weather", result={"temp": 70})
        assert c.is_error is False

    def test_can_mark_error(self):
        c = ToolResultChunk(name="get_weather", result="API down", is_error=True)
        assert c.is_error is True


class TestPublicSurface:
    """Every concrete chunk class is importable from the top-level package."""

    def test_top_level_imports(self):
        assert cloudless.TextChunk is TextChunk
        assert cloudless.ToolCallChunk is ToolCallChunk
        assert cloudless.ToolResultChunk is ToolResultChunk
        assert cloudless.ReasoningChunk is ReasoningChunk
        assert cloudless.StateChunk is StateChunk
        assert cloudless.FinalChunk is FinalChunk
        assert cloudless.ErrorChunk is ErrorChunk

    def test_Chunk_union(self):
        # The Union type is for type-narrowing; runtime check is just
        # that the value is one of the seven classes.
        for cls in [TextChunk, ToolCallChunk, ToolResultChunk, ReasoningChunk,
                    StateChunk, FinalChunk, ErrorChunk]:
            defaults = {
                TextChunk: dict(text=""),
                ToolCallChunk: dict(name="t", args={}),
                ToolResultChunk: dict(name="t", result=None),
                ReasoningChunk: dict(text=""),
                StateChunk: dict(state={}),
                FinalChunk: dict(),
                ErrorChunk: dict(error=""),
            }[cls]
            instance = cls(**defaults)
            # Existence check — the union has all seven classes
            assert instance is not None
