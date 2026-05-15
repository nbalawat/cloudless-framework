"""Real-cloud integration test for cloudless.Secrets + GCP Secret Manager."""
from __future__ import annotations

import os
import uuid

import pytest

import cloudless

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="module")
def project() -> str:
    return os.environ.get("CLOUDLESS_GCP_PROJECT", "agentic-experiments")


@pytest.fixture(scope="module")
def gcp_available(project) -> bool:
    try:
        from google.cloud import secretmanager_v1
        secretmanager_v1.SecretManagerServiceClient().list_secrets(
            request={"parent": f"projects/{project}"}
        )
        return True
    except Exception:
        return False


async def test_secret_manager_round_trip(gcp_available, project):
    if not gcp_available:
        pytest.skip("GCP credentials or Secret Manager not available")

    from google.cloud import secretmanager_v1
    client = secretmanager_v1.SecretManagerServiceClient()

    name = f"cloudless-spike-test-{uuid.uuid4().hex[:8]}"
    full = f"projects/{project}/secrets/{name}"

    # Create + version
    client.create_secret(
        parent=f"projects/{project}",
        secret_id=name,
        secret={"replication": {"automatic": {}}},
    )
    client.add_secret_version(
        parent=full,
        payload={"data": b"hunter2-gcp"},
    )

    try:
        secrets = cloudless.Secrets(backend="gcp", project=project)
        value = await secrets.get(name)
        assert value == "hunter2-gcp", f"got {value!r}"

        # Missing returns None
        missing = await secrets.get(f"cloudless-spike-missing-{uuid.uuid4().hex[:8]}")
        assert missing is None
    finally:
        client.delete_secret(name=full)
