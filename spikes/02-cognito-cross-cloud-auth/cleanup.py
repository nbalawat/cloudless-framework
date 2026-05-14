"""Spike 2 teardown — destroys AgentCore runtime + Cognito pool + supporting resources."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


REGION = "us-east-1"
AGENT_NAME = "cloudless_spike_02"
ECR_REPO = "bedrock-agentcore-cloudless_spike_02"
CB_PROJECT = "bedrock-agentcore-cloudless_spike_02-builder"
STATE_FILE = Path(__file__).parent / "cognito_state.json"

# IAM roles created by the starter toolkit during Spike 2 deploy
# (named with a deterministic hash of the agent name)
IAM_ROLES_PATTERN = "cloudless_spike_02"  # any role whose name contains this


def step(msg: str) -> None:
    print(f"  • {msg}")


def safe(label, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        step(f"deleted {label}")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("ResourceNotFoundException", "NoSuchEntity", "NotFoundException",
                    "RepositoryNotFoundException", "NoSuchBucket"):
            step(f"already gone: {label}")
        else:
            step(f"ERROR {label}: {code} {str(e)[:200]}")


def main() -> int:
    print("=== Spike 2 teardown ===")
    sess = boto3.session.Session(region_name=REGION)

    # 1. AgentCore Runtime + endpoint
    print("\n[1/5] AgentCore Runtime")
    acc = sess.client("bedrock-agentcore-control")
    try:
        runtimes = acc.list_agent_runtimes()["agentRuntimes"]
    except ClientError as e:
        print(f"  list failed: {e}")
        runtimes = []
    for r in [r for r in runtimes if r["agentRuntimeName"] == AGENT_NAME]:
        rid = r["agentRuntimeId"]
        try:
            for ep in acc.list_agent_runtime_endpoints(agentRuntimeId=rid)["runtimeEndpoints"]:
                safe(f"endpoint {ep['name']}", acc.delete_agent_runtime_endpoint,
                     agentRuntimeId=rid, endpointName=ep["name"])
        except ClientError:
            pass
        safe(f"runtime {rid}", acc.delete_agent_runtime, agentRuntimeId=rid)

    # 2. Cognito pool (idempotent via state file)
    print("\n[2/5] Cognito User Pool")
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        cog = sess.client("cognito-idp")
        # Delete user pool domain first (required before pool deletion)
        try:
            cog.delete_user_pool_domain(UserPoolId=state["pool_id"], Domain=state["domain_prefix"])
            step(f"deleted domain {state['domain_prefix']}")
        except ClientError as e:
            step(f"domain delete: {e.response.get('Error', {}).get('Code')}")
        safe(f"user pool {state['pool_id']}", cog.delete_user_pool, UserPoolId=state["pool_id"])
        STATE_FILE.unlink(missing_ok=True)
    else:
        step("no cognito_state.json — pool may already be deleted")

    # 3. CodeBuild project
    print("\n[3/5] CodeBuild")
    cb = sess.client("codebuild")
    safe(f"project {CB_PROJECT}", cb.delete_project, name=CB_PROJECT)

    # 4. ECR repository
    print("\n[4/5] ECR")
    ecr = sess.client("ecr")
    safe(f"ECR repo {ECR_REPO}", ecr.delete_repository, repositoryName=ECR_REPO, force=True)

    # 5. IAM roles created during Spike 2 deploy
    print("\n[5/5] IAM roles for Spike 2")
    iam = sess.client("iam")
    roles = iam.list_roles(MaxItems=200)["Roles"]
    for r in roles:
        name = r["RoleName"]
        # Match the starter-toolkit's hashed names that contain our agent name
        if "cloudless_spike_02" not in (r.get("AssumeRolePolicyDocument", "") + name) and not (
            name.startswith("AmazonBedrockAgentCoreSDK") and "cloudless_spike_02" in name
        ):
            continue
        try:
            for p in iam.list_attached_role_policies(RoleName=name)["AttachedPolicies"]:
                safe(f"detach {p['PolicyName']}",
                     iam.detach_role_policy, RoleName=name, PolicyArn=p["PolicyArn"])
            for pol in iam.list_role_policies(RoleName=name)["PolicyNames"]:
                safe(f"delete inline policy {pol}",
                     iam.delete_role_policy, RoleName=name, PolicyName=pol)
            safe(f"role {name}", iam.delete_role, RoleName=name)
        except ClientError as e:
            step(f"IAM cleanup for {name}: {e.response.get('Error', {}).get('Code')}")

    print("\n=== Teardown done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
