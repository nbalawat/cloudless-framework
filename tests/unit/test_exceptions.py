"""Tests for cloudless.exceptions — Q21 exception hierarchy semantics."""
from __future__ import annotations

import pytest

import cloudless
from cloudless.exceptions import (
    AuthenticationError,
    CircuitOpen,
    CloudlessError,
    CostCapExceeded,
    GuardrailBlocked,
    InvalidInputError,
    PeerUnreachable,
    PermanentError,
    PolicyViolation,
    ThrottledError,
    TimeoutError,
    TransientError,
)


class TestExceptionHierarchy:
    """The hierarchy must let `except TransientError` catch all retryable
    errors and `except PermanentError` catch all non-retryable ones."""

    def test_every_exception_extends_CloudlessError(self):
        for exc_class in [
            TransientError,
            TimeoutError,
            ThrottledError,
            PeerUnreachable,
            CircuitOpen,
            PermanentError,
            PolicyViolation,
            GuardrailBlocked,
            AuthenticationError,
            InvalidInputError,
            CostCapExceeded,
        ]:
            assert issubclass(exc_class, CloudlessError), \
                f"{exc_class.__name__} must extend CloudlessError"

    @pytest.mark.parametrize("exc_class", [
        TimeoutError,
        ThrottledError,
        PeerUnreachable,
        CircuitOpen,
    ])
    def test_transient_errors_are_recoverable(self, exc_class):
        assert issubclass(exc_class, TransientError)
        instance = exc_class("test")
        assert instance.recoverable is True

    @pytest.mark.parametrize("exc_class", [
        PolicyViolation,
        GuardrailBlocked,
        AuthenticationError,
        InvalidInputError,
    ])
    def test_permanent_errors_are_NOT_recoverable(self, exc_class):
        assert issubclass(exc_class, PermanentError)
        instance = exc_class("test")
        assert instance.recoverable is False

    def test_cost_cap_exceeded_is_not_retryable(self):
        # Special case — retry costs money, so we mark it as non-recoverable
        # even though it's not a permanent failure.
        instance = CostCapExceeded("$5 session cap exceeded")
        assert instance.recoverable is False
        assert isinstance(instance, CloudlessError)
        # NOT a PermanentError (semantically distinct from a true failure)
        assert not isinstance(instance, PermanentError)
        assert not isinstance(instance, TransientError)


class TestRetryAfter:
    """retry_after honors both the class default (None) and an instance override."""

    def test_default_retry_after_is_None(self):
        assert TimeoutError("x").retry_after is None

    def test_retry_after_can_be_set_via_constructor(self):
        e = ThrottledError("rate-limited", retry_after=12.5)
        assert e.retry_after == 12.5
        assert e.recoverable is True


class TestPublicSurface:
    """The exception hierarchy must be importable from the top-level package."""

    def test_top_level_imports(self):
        assert cloudless.CloudlessError is CloudlessError
        assert cloudless.TransientError is TransientError
        assert cloudless.PermanentError is PermanentError
        assert cloudless.CostCapExceeded is CostCapExceeded
