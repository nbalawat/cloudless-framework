"""Unit tests for the multi-cloud LLM-judge dispatch."""
from __future__ import annotations

import pytest

from cloudless.eval.metrics import LLMJudge


def test_judge_with_bedrock_alias_resolves_bedrock():
    """A Bedrock alias should not require project/location kwargs."""
    j = LLMJudge(rubric="x", model="nova-pro")
    # Just constructing — no LLM call. Verify state.
    assert j.model == "nova-pro"
    assert j.project is None


def test_judge_with_gemini_alias_carries_project_location():
    j = LLMJudge(rubric="x", model="gemini-flash",
                  project="agentic-experiments", location="us-central1")
    assert j.project == "agentic-experiments"
    assert j.location == "us-central1"


def test_judge_default_threshold():
    assert LLMJudge(rubric="x").pass_threshold == 0.7


@pytest.mark.asyncio
async def test_judge_dispatches_to_gemini_provider(monkeypatch):
    """When model is a gemini alias, the LLM should be built with project= passed."""
    seen_kwargs: dict = {}
    real_llm_init = None

    class _FakeLLM:
        def __init__(self, **kw):
            seen_kwargs.update(kw)
        async def invoke(self, prompt, **kw):
            return '{"score": 0.95, "reason": "great"}'

    import cloudless
    monkeypatch.setattr(cloudless, "LLM", _FakeLLM)

    from cloudless.eval import EvalDataset
    from cloudless.eval.runner import EvalCase

    case = EvalCase(id="1", prompt="hi", expected_contains="x", expected_regex=None)
    judge = LLMJudge(rubric="be helpful", model="gemini-flash",
                     project="agentic-experiments")
    score = await judge.evaluate(case=case, response="hello")
    assert seen_kwargs["model"] == "gemini-flash"
    assert seen_kwargs.get("project") == "agentic-experiments"
    assert score.passed
    assert score.score == 0.95


@pytest.mark.asyncio
async def test_judge_dispatches_to_bedrock_provider(monkeypatch):
    """When model is a Bedrock alias, project should NOT be passed."""
    seen_kwargs: dict = {}

    class _FakeLLM:
        def __init__(self, **kw):
            seen_kwargs.update(kw)
        async def invoke(self, prompt, **kw):
            return '{"score": 0.8, "reason": "ok"}'

    import cloudless
    monkeypatch.setattr(cloudless, "LLM", _FakeLLM)

    from cloudless.eval.runner import EvalCase
    case = EvalCase(id="1", prompt="hi", expected_contains=None, expected_regex=None)
    judge = LLMJudge(rubric="be helpful", model="nova-pro")
    await judge.evaluate(case=case, response="hello")
    assert seen_kwargs["model"] == "nova-pro"
    assert "project" not in seen_kwargs
