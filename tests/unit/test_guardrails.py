"""Unit tests for Bedrock Guardrail wiring in cloudless.LLM."""
from __future__ import annotations

import pytest

import cloudless
from cloudless.exceptions import GuardrailBlocked
from cloudless.runtime.audit import InMemorySink, reset_sinks, set_sinks
from cloudless.runtime.policy import get_registry


pytestmark = [pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _clean():
    sink = InMemorySink()
    set_sinks([sink])
    get_registry().clear()
    yield sink
    reset_sinks()
    get_registry().clear()


class FakeBedrock:
    """Stub bedrock-runtime client returning a guardrail_intervened response."""
    def __init__(self, *, response: dict):
        self._response = response
        self.last_kwargs: dict | None = None

    def converse(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


async def test_llm_passes_guardrail_config_to_bedrock(_clean):
    fake = FakeBedrock(response={
        "output": {"message": {"content": [{"text": "hi"}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 1, "outputTokens": 1},
    })
    llm = cloudless.LLM(
        model="nova-micro", client=fake,
        guardrail_id="gd-test-123", guardrail_version="1",
    )
    await llm.invoke("hello", max_tokens=10)
    assert fake.last_kwargs["guardrailConfig"] == {
        "guardrailIdentifier": "gd-test-123",
        "guardrailVersion": "1",
        "trace": "enabled",
    }


async def test_llm_raises_guardrail_blocked_on_intervention(_clean):
    fake = FakeBedrock(response={
        "output": {"message": {"content": []}},
        "stopReason": "guardrail_intervened",
        "trace": {"guardrail": {"reason": "blocked content"}},
    })
    llm = cloudless.LLM(
        model="nova-micro", client=fake, guardrail_id="gd-x",
    )
    with pytest.raises(GuardrailBlocked, match="gd-x"):
        await llm.invoke("naughty prompt", max_tokens=10)

    # Audit record should have been emitted
    assert len(_clean.records) == 1
    rec = _clean.records[0]
    assert rec.decision == "block"
    assert "bedrock-guardrail" in rec.policy_name


async def test_no_guardrail_config_when_not_set(_clean):
    fake = FakeBedrock(response={
        "output": {"message": {"content": [{"text": "ok"}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 1, "outputTokens": 1},
    })
    llm = cloudless.LLM(model="nova-micro", client=fake)
    await llm.invoke("hello", max_tokens=10)
    assert "guardrailConfig" not in fake.last_kwargs
