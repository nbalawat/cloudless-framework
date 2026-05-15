"""Live-AWS integration test for AgentCore Gateway create/use.

Gated by CLOUDLESS_RUN_GATEWAY_TESTS=1 because gateway creation has
billing implications (the resource is free at idle but creating/deleting
inventory is not free of API quota). The test creates a gateway with
prefix cloudless-spike-gw-* (so cloudless cleanup picks it up), verifies
list, and tears down.
"""
from __future__ import annotations

import os
import uuid

import pytest


pytestmark = [pytest.mark.integration]


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
def iam_role_arn(aws_available):
    """Find an IAM role suitable for Gateway (must have bedrock-agentcore trust).

    Reuses any existing cloudless deploy role. If none, skip.
    """
    import boto3
    iam = boto3.client("iam")
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        for r in page.get("Roles", []):
            name = r["RoleName"]
            if name.startswith("AmazonBedrockAgentCoreSDKRuntime"):
                return r["Arn"]
            if name.startswith("cloudless"):
                return r["Arn"]
    pytest.skip("no AgentCore Runtime IAM role found for Gateway test")


def test_ensure_gateway_creates_and_finds(iam_role_arn):
    """Idempotent create: first call creates, second call returns existing."""
    if os.environ.get("CLOUDLESS_RUN_GATEWAY_TESTS") != "1":
        pytest.skip("Set CLOUDLESS_RUN_GATEWAY_TESTS=1 (creates Gateway resource)")

    from cloudless.adapters.aws.gateway import ensure_gateway
    import boto3

    # Discover an existing Cognito pool for the CUSTOM_JWT authorizer config
    cognito = boto3.client("cognito-idp", region_name="us-east-1")
    pools = cognito.list_user_pools(MaxResults=10).get("UserPools", [])
    if not pools:
        pytest.skip("no Cognito user pool found for Gateway authorizer config")
    pool = pools[0]
    pool_id = pool["Id"]
    discovery_url = (
        f"https://cognito-idp.us-east-1.amazonaws.com/{pool_id}/.well-known/openid-configuration"
    )
    # Use the pool's first app client as the audience
    clients = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=10)
    pool_clients = clients.get("UserPoolClients", [])
    if not pool_clients:
        pytest.skip("Cognito pool has no app client for audience")
    audience = pool_clients[0]["ClientId"]

    name = f"cloudless-spike-gw-{uuid.uuid4().hex[:6]}"
    control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")

    out1 = None
    try:
        out1 = ensure_gateway(
            name=name,
            role_arn=iam_role_arn,
            region="us-east-1",
            client=control,
            cognito_discovery_url=discovery_url,
            cognito_audience=audience,
        )
        assert out1["id"], "create_gateway returned no id"

        out2 = ensure_gateway(
            name=name,
            role_arn=iam_role_arn,
            region="us-east-1",
            client=control,
            cognito_discovery_url=discovery_url,
            cognito_audience=audience,
        )
        assert out2["id"] == out1["id"], "idempotency failed"
    finally:
        if out1 is not None:
            try:
                control.delete_gateway(gatewayIdentifier=out1["id"])
            except Exception:  # noqa: BLE001
                pass


def test_gateway_module_smoke(aws_available):
    """Smoke test: module imports, list_gateways works."""
    import boto3
    from cloudless.adapters.aws.gateway import ensure_gateway  # noqa
    control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
    # list_gateways may or may not return any — we just verify the API is callable
    try:
        result = control.list_gateways()
        assert isinstance(result.get("gateways", result.get("items", [])), list)
    except control.exceptions.AccessDeniedException:
        pytest.skip("account doesn't have AgentCore Gateway access")
    except Exception as e:  # noqa: BLE001
        # If the API simply isn't available in this region, that's OK
        if "AccessDenied" in str(e) or "not authorized" in str(e):
            pytest.skip(f"AgentCore Gateway not available: {e}")
        raise
