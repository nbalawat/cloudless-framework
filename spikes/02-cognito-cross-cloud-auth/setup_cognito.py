"""
Spike 2 — provision a Cognito User Pool + Resource Server + M2M App Client
for testing the Cognito-as-cross-cloud-IdP pattern from Q7.

Output: writes `cognito_state.json` next to this file capturing the resource
identifiers we need for `deploy.py` and `verify.py`.

Idempotent: re-running won't create duplicates if `cognito_state.json` exists.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


REGION = "us-east-1"
POOL_NAME = "cloudless-spike-02-pool"
RESOURCE_SERVER_IDENTIFIER = "cloudless"
RESOURCE_SERVER_NAME = "cloudless-spike-02-resource-server"
SCOPE_NAME = "agent.invoke"
SCOPE_DESCRIPTION = "Permission to call cloudless agents over A2A"
CLIENT_NAME = "cloudless-spike-02-m2m-client"
DOMAIN_PREFIX = "cloudless-spike-02-613112965612"  # account-id suffix for uniqueness

STATE_FILE = Path(__file__).parent / "cognito_state.json"


def log(msg: str) -> None:
    print(f"  {msg}")


def main() -> int:
    cog = boto3.client("cognito-idp", region_name=REGION)

    # Reload existing state if present (idempotent re-runs)
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        log(f"State file exists — pool_id={state.get('pool_id')}; verifying still alive")
        try:
            cog.describe_user_pool(UserPoolId=state["pool_id"])
            log("pool still exists, returning existing state")
            print(json.dumps(state, indent=2))
            return 0
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                log("pool was deleted; provisioning fresh")
                STATE_FILE.unlink()
            else:
                raise

    state: dict = {}

    # 1. Create user pool
    print("\n[1/4] Create Cognito User Pool")
    pool_resp = cog.create_user_pool(
        PoolName=POOL_NAME,
        Policies={"PasswordPolicy": {"MinimumLength": 12}},
        # M2M only — no human users, no email verification needed
    )
    pool_id = pool_resp["UserPool"]["Id"]
    state["pool_id"] = pool_id
    state["pool_arn"] = pool_resp["UserPool"]["Arn"]
    state["issuer"] = f"https://cognito-idp.{REGION}.amazonaws.com/{pool_id}"
    state["jwks_url"] = f"{state['issuer']}/.well-known/jwks.json"
    state["region"] = REGION
    log(f"pool_id={pool_id}")
    log(f"issuer={state['issuer']}")

    # 2. Create resource server (declares the scope our agents require)
    print("\n[2/4] Create Resource Server with scope")
    cog.create_resource_server(
        UserPoolId=pool_id,
        Identifier=RESOURCE_SERVER_IDENTIFIER,
        Name=RESOURCE_SERVER_NAME,
        Scopes=[{"ScopeName": SCOPE_NAME, "ScopeDescription": SCOPE_DESCRIPTION}],
    )
    full_scope = f"{RESOURCE_SERVER_IDENTIFIER}/{SCOPE_NAME}"
    state["scope"] = full_scope
    state["resource_server_identifier"] = RESOURCE_SERVER_IDENTIFIER
    log(f"scope={full_scope}")

    # 3. Create user pool domain (required for the /oauth2/token endpoint)
    print("\n[3/4] Create User Pool Domain")
    try:
        cog.create_user_pool_domain(UserPoolId=pool_id, Domain=DOMAIN_PREFIX)
        log(f"domain={DOMAIN_PREFIX}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidParameterException":
            log(f"domain {DOMAIN_PREFIX} taken or invalid; trying alternates...")
            raise
        raise
    state["domain_prefix"] = DOMAIN_PREFIX
    state["token_url"] = f"https://{DOMAIN_PREFIX}.auth.{REGION}.amazoncognito.com/oauth2/token"

    # 4. Create M2M App Client (client_credentials grant + the scope we declared)
    print("\n[4/4] Create M2M App Client")
    # Cognito requires resource server scopes to be "available" first; give it a moment.
    time.sleep(2)
    client_resp = cog.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthFlowsUserPoolClient=True,
        AllowedOAuthScopes=[full_scope],
        ExplicitAuthFlows=[],  # M2M only — no user-facing auth flows
    )
    client = client_resp["UserPoolClient"]
    state["client_id"] = client["ClientId"]
    state["client_secret"] = client["ClientSecret"]
    log(f"client_id={state['client_id']}")
    # We intentionally print the secret to stdout once so it's captured in the
    # spike log. State file also contains it for reuse.
    log("client_secret captured in cognito_state.json")

    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"\n=== Cognito ready. State saved to {STATE_FILE} ===")
    print(json.dumps({k: v for k, v in state.items() if k != "client_secret"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
