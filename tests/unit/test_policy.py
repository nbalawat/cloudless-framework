"""Unit tests for cloudless.policy + stage hooks."""
from __future__ import annotations

import re

import pytest

import cloudless
from cloudless.exceptions import PolicyViolation
from cloudless.runtime.policy import get_registry


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test gets a clean policy registry."""
    reg = get_registry()
    reg.clear()
    yield
    reg.clear()


# ----------------------------- decorator -------------------------------- #


def test_policy_decorator_validates_stages():
    with pytest.raises(ValueError, match="unknown stage"):
        @cloudless.policy(stages=["before_invalid"])
        def _bad(stage, **kw):
            return None

    with pytest.raises(ValueError, match="non-empty"):
        @cloudless.policy(stages=[])
        def _empty(stage, **kw):
            return None


def test_policy_decorator_registers_in_registry():
    @cloudless.policy(stages=["before_llm"], name="my-policy")
    def my_policy(stage, prompt, **kw):
        return prompt

    entries = get_registry().for_stage("before_llm")
    assert any(e.name == "my-policy" for e in entries)


# ----------------------------- transforms ------------------------------- #


def test_before_llm_can_transform_prompt():
    @cloudless.policy(stages=["before_llm"])
    def upper(stage, prompt, **kw):
        return prompt.upper()

    out = get_registry().run("before_llm", prompt="hello", ctx=None, model="m")
    assert out["prompt"] == "HELLO"


def test_after_llm_can_redact_response():
    EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    @cloudless.policy(stages=["after_llm"])
    def redact(stage, prompt, response, **kw):
        return EMAIL.sub("<email>", response)

    out = get_registry().run(
        "after_llm", prompt="x", response="contact me at a@b.com", ctx=None, model="m",
    )
    assert out["response"] == "contact me at <email>"


def test_before_tool_can_transform_args():
    @cloudless.policy(stages=["before_tool"])
    def add_default(stage, tool_name, args, **kw):
        args.setdefault("source", "policy")
        return args

    out = get_registry().run("before_tool", tool_name="search", args={"q": "foo"})
    assert out["args"]["source"] == "policy"


# ----------------------------- blocking --------------------------------- #


def test_policy_violation_short_circuits():
    @cloudless.policy(stages=["before_llm"])
    def block_pii(stage, prompt, **kw):
        if "ssn" in prompt.lower():
            raise PolicyViolation("PII blocked")
        return None

    with pytest.raises(PolicyViolation, match="PII blocked"):
        get_registry().run("before_llm", prompt="my ssn is 123", ctx=None, model="m")


def test_buggy_policy_is_wrapped_as_policy_violation():
    @cloudless.policy(stages=["before_llm"])
    def buggy(stage, prompt, **kw):
        raise RuntimeError("kaboom")

    with pytest.raises(PolicyViolation, match="kaboom"):
        get_registry().run("before_llm", prompt="x", ctx=None, model="m")


# ----------------------------- ordering --------------------------------- #


def test_priority_orders_policies():
    log: list[str] = []

    @cloudless.policy(stages=["before_llm"], priority=0)
    def low(stage, prompt, **kw):
        log.append("low")
        return None

    @cloudless.policy(stages=["before_llm"], priority=10)
    def high(stage, prompt, **kw):
        log.append("high")
        return None

    get_registry().run("before_llm", prompt="x", ctx=None, model="m")
    assert log == ["high", "low"]


# ----------------------------- Tool integration ------------------------- #


@pytest.mark.asyncio
async def test_tool_invoke_runs_before_after_tool_policies():
    log: list[str] = []

    @cloudless.policy(stages=["before_tool"])
    def before(stage, tool_name, args, **kw):
        log.append(f"before:{tool_name}:{args}")
        return None

    @cloudless.policy(stages=["after_tool"])
    def after(stage, tool_name, args, result, **kw):
        log.append(f"after:{tool_name}:{result}")
        return result * 2 if isinstance(result, int) else result

    @cloudless.tool
    def double(n: int) -> int:
        """Doubles n."""
        return n * 2

    out = await double.invoke({"n": 3})
    assert out == 12  # tool returns 6, after_tool doubles → 12
    assert any("before:double" in s for s in log)
    assert any("after:double:6" in s for s in log)
