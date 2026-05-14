"""Real-cloud integration test for cloudless.Secrets + Secrets Manager backend.

Creates a temp `cloudless-spike-` prefixed secret, reads it, deletes it.
Cost: $0 (Secrets Manager has a free tier for the few API calls we make).
"""
from __future__ import annotations

import uuid

import boto3
import pytest

import cloudless


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:  # noqa: BLE001
        return False


async def test_secrets_manager_get_round_trip(aws_available):
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    sm = boto3.client("secretsmanager", region_name="us-east-1")
    name = f"cloudless-spike-test-{uuid.uuid4().hex[:8]}"
    sm.create_secret(Name=name, SecretString="hunter2")
    try:
        secrets = cloudless.Secrets(backend="aws", prefix="")
        value = await secrets.get(name)
        assert value == "hunter2", f"got {value!r}"

        # Missing secret returns None (not raises)
        missing = await secrets.get(f"cloudless-spike-missing-{uuid.uuid4().hex[:8]}")
        assert missing is None
    finally:
        sm.delete_secret(SecretId=name, ForceDeleteWithoutRecovery=True)
