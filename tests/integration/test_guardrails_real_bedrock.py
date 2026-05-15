"""Real-Bedrock integration test: live CreateGuardrail + cloudless.LLM wiring.

Creates a Bedrock Guardrail in the user's account scoped to deny PII,
exercises cloudless.LLM with the guardrail_id, asserts the block path
produces GuardrailBlocked and emits an audit record.

Resource prefix: cloudless-spike-gr-*  (so `cloudless cleanup` finds it).
"""
from __future__ import annotations

import pytest

import cloudless
from cloudless.exceptions import GuardrailBlocked
from cloudless.runtime.audit import InMemorySink, reset_sinks, set_sinks


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        pytest.skip("AWS credentials not configured")
        return False


@pytest.fixture(scope="module")
def guardrail_id(aws_available):
    """Create a guardrail that blocks high-confidence dangerous content
    and PII, yield its ID, tear down at end of module."""
    import boto3
    client = boto3.client("bedrock", region_name="us-east-1")
    name = "cloudless-spike-gr-test"

    # Look for existing first
    try:
        existing = client.list_guardrails(maxResults=100).get("guardrails", [])
        for g in existing:
            if g.get("name") == name:
                yield g["id"]
                return
    except Exception:  # noqa: BLE001
        pass

    # Create fresh
    try:
        resp = client.create_guardrail(
            name=name,
            description="cloudless integration test guardrail",
            blockedInputMessaging="Input blocked by guardrail.",
            blockedOutputsMessaging="Output blocked by guardrail.",
            contentPolicyConfig={
                "filtersConfig": [
                    {"type": "VIOLENCE",       "inputStrength": "HIGH", "outputStrength": "HIGH"},
                    {"type": "HATE",           "inputStrength": "HIGH", "outputStrength": "HIGH"},
                ],
            },
            sensitiveInformationPolicyConfig={
                "piiEntitiesConfig": [
                    {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "BLOCK"},
                    {"type": "CREDIT_DEBIT_CARD_NUMBER",  "action": "BLOCK"},
                ],
            },
        )
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"could not create guardrail: {e}")

    gid = resp["guardrailId"]

    # Wait for guardrail to become READY
    import time
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            got = client.get_guardrail(guardrailIdentifier=gid)
            if got.get("status") == "READY":
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)

    yield gid

    # Teardown
    try:
        client.delete_guardrail(guardrailIdentifier=gid)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture(autouse=True)
def _audit_sink():
    sink = InMemorySink()
    set_sinks([sink])
    yield sink
    reset_sinks()


async def test_guardrail_blocks_pii_prompt(guardrail_id, _audit_sink):
    """A prompt containing a fake SSN should be blocked by the guardrail."""
    llm = cloudless.LLM(
        model="nova-micro", region="us-east-1",
        guardrail_id=guardrail_id,
    )
    with pytest.raises(GuardrailBlocked):
        await llm.invoke(
            "My SSN is 123-45-6789 — please remember it.",
            max_tokens=40,
        )

    # An audit record should have been emitted with decision=block
    audit_records = _audit_sink.records
    assert audit_records, "no audit record emitted"
    rec = audit_records[-1]
    assert rec.decision == "block"
    assert "bedrock-guardrail" in rec.policy_name


async def test_guardrail_allows_safe_prompt(guardrail_id):
    """A benign prompt with the same guardrail should pass through."""
    llm = cloudless.LLM(
        model="nova-micro", region="us-east-1",
        guardrail_id=guardrail_id,
    )
    text = await llm.invoke(
        "What is 2 + 2? Reply with a single digit.",
        max_tokens=10,
    )
    assert text
    assert "4" in text


async def test_guardrail_id_carries_through(guardrail_id):
    """Verify the guardrail_id we created is actually a valid AgentCore guardrail."""
    import boto3
    client = boto3.client("bedrock", region_name="us-east-1")
    got = client.get_guardrail(guardrailIdentifier=guardrail_id)
    assert got["name"].startswith("cloudless-spike-gr-")
