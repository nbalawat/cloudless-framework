"""Unit tests for AgentCore Gateway create/use helpers."""
from __future__ import annotations

import pytest

from cloudless.adapters.aws.gateway import ensure_gateway, ensure_lambda_target


class _FakeControl:
    def __init__(self, *, gateways=None, targets=None):
        self._gateways = gateways or []
        self._targets = targets or {}
        self.created_gateways: list[dict] = []
        self.created_targets: list[dict] = []

    def list_gateways(self):
        return {"gateways": self._gateways}

    def create_gateway(self, **kw):
        self.created_gateways.append(kw)
        return {"gatewayId": f"gw-{kw['name']}",
                "gatewayUrl": f"https://gw.example/{kw['name']}"}

    def list_gateway_targets(self, *, gatewayId):
        return {"targets": self._targets.get(gatewayId, [])}

    def create_gateway_target(self, **kw):
        self.created_targets.append(kw)
        return {"targetId": f"tgt-{kw['name']}"}


# ----------------------------- Gateway --------------------------------- #


def test_ensure_gateway_reuses_existing():
    client = _FakeControl(gateways=[
        {"name": "my-gw", "gatewayId": "gw-existing",
         "gatewayUrl": "https://existing.example"},
    ])
    out = ensure_gateway(name="my-gw", role_arn="arn:aws:iam::123:role/x", client=client)
    assert out["id"] == "gw-existing"
    assert out["url"] == "https://existing.example"
    assert client.created_gateways == []


def test_ensure_gateway_creates_when_missing():
    client = _FakeControl()
    out = ensure_gateway(
        name="my-gw", role_arn="arn:aws:iam::123:role/x", client=client,
        cognito_discovery_url="https://cognito-idp.us-east-1.amazonaws.com/pool/.well-known/openid-configuration",
        cognito_audience="client-abc",
    )
    assert out["id"] == "gw-my-gw"
    assert out["url"] == "https://gw.example/my-gw"
    assert len(client.created_gateways) == 1
    kw = client.created_gateways[0]
    assert kw["name"] == "my-gw"
    assert kw["roleArn"] == "arn:aws:iam::123:role/x"
    assert kw["protocolType"] == "MCP"
    # CUSTOM_JWT authorizer config must be wired
    assert kw["authorizerConfiguration"]["customJWTAuthorizer"]["allowedAudience"] == ["client-abc"]


def test_ensure_gateway_rejects_custom_jwt_without_cognito_config():
    """CUSTOM_JWT authorizer requires Cognito config; raises if missing."""
    client = _FakeControl()
    with pytest.raises(RuntimeError, match="cognito"):
        ensure_gateway(name="my-gw", role_arn="arn:aws:iam::123:role/x", client=client)


# ----------------------------- Target ---------------------------------- #


SCHEMA = {"type": "object", "properties": {"q": {"type": "string"}}}


def test_ensure_target_reuses_existing():
    client = _FakeControl(targets={"gw-1": [
        {"name": "search", "targetId": "tgt-existing"},
    ]})
    out = ensure_lambda_target(
        gateway_id="gw-1", name="search",
        lambda_arn="arn:aws:lambda:::function:search",
        input_schema=SCHEMA, client=client,
    )
    assert out["id"] == "tgt-existing"
    assert client.created_targets == []


def test_ensure_target_creates_when_missing():
    client = _FakeControl()
    out = ensure_lambda_target(
        gateway_id="gw-1", name="search",
        lambda_arn="arn:aws:lambda:::function:search",
        input_schema=SCHEMA, client=client,
    )
    assert out["id"] == "tgt-search"
    assert len(client.created_targets) == 1
    kw = client.created_targets[0]
    assert kw["gatewayId"] == "gw-1"
    assert kw["name"] == "search"
    cfg = kw["targetConfiguration"]["mcp"]["lambda"]
    assert cfg["lambdaArn"] == "arn:aws:lambda:::function:search"
    assert cfg["toolSchema"]["inlineSchema"]["inputSchema"] == SCHEMA
    assert kw["credentialProviderConfigurations"][0]["credentialProviderType"] == "GATEWAY_IAM_ROLE"


def test_ensure_openapi_target_creates_when_missing():
    import json as _json

    from cloudless.adapters.aws.gateway import ensure_openapi_target

    class _FakeOpenAPIControl(_FakeControl):
        def list_gateway_targets(self, *, gatewayIdentifier):
            return {"items": self._targets.get(gatewayIdentifier, [])}

    client = _FakeOpenAPIControl()
    spec = {"openapi": "3.0.0", "paths": {"/echo": {"get": {"operationId": "echo"}}}}
    out = ensure_openapi_target(
        gateway_id="gw-1", name="echo-api",
        openapi_spec=spec, client=client,
    )
    assert out["id"] == "tgt-echo-api"
    kw = client.created_targets[0]
    inline = _json.loads(kw["targetConfiguration"]["mcp"]["openApiSchema"]["inlineSchema"])
    assert inline == spec


def test_ensure_openapi_target_reuses_existing():
    from cloudless.adapters.aws.gateway import ensure_openapi_target

    class _ExistingClient(_FakeControl):
        def list_gateway_targets(self, *, gatewayIdentifier):
            return {"items": [{"name": "echo-api", "targetId": "tgt-existing"}]}

    client = _ExistingClient()
    out = ensure_openapi_target(
        gateway_id="gw-1", name="echo-api",
        openapi_spec={"openapi": "3.0.0"}, client=client,
    )
    assert out["id"] == "tgt-existing"
    assert client.created_targets == []
