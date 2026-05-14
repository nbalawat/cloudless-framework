"""
Spike 1 teardown — deletes every resource the spike created in account 613112965612.

Idempotent: safe to re-run. Logs each deletion. Never touches anything outside
the cloudless-spike-01 namespace.
"""
from __future__ import annotations

import sys
import boto3
from botocore.exceptions import ClientError


REGION = "us-east-1"
AGENT_NAME = "cloudless_spike_01"
ECR_REPO = "bedrock-agentcore-cloudless_spike_01"
CB_PROJECT = "bedrock-agentcore-cloudless_spike_01-builder"
S3_BUCKET = "bedrock-agentcore-codebuild-sources-613112965612-us-east-1"

# IAM resources created by the starter toolkit (named with deterministic hash suffix)
IAM_ROLES = [
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-7258a6e8ab",
    "AmazonBedrockAgentCoreSDKCodeBuild-us-east-1-7258a6e8ab",
]
IAM_INLINE_POLICY_NAMES = {
    "AmazonBedrockAgentCoreSDKRuntime-us-east-1-7258a6e8ab": [
        "BedrockAgentCoreRuntimeExecutionPolicy-cloudless_spike_01",
    ],
    "AmazonBedrockAgentCoreSDKCodeBuild-us-east-1-7258a6e8ab": [
        "CodeBuildExecutionPolicy",
    ],
}


def step(msg: str) -> None:
    print(f"  • {msg}")


def safe(label: str, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        step(f"deleted {label}")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("ResourceNotFoundException", "NoSuchEntity", "NotFoundException",
                    "RepositoryNotFoundException", "NoSuchBucket", "ResourceNotFound"):
            step(f"already gone: {label}")
        else:
            step(f"ERROR {label}: {code} {str(e)[:200]}")


def main() -> int:
    print("=== Spike 1 teardown ===")
    sess = boto3.session.Session(region_name=REGION)

    # 1. AgentCore Runtime endpoints + the runtime itself
    acc = sess.client("bedrock-agentcore-control")
    print("\n[1/5] AgentCore Runtime")
    try:
        runtimes = acc.list_agent_runtimes()["agentRuntimes"]
    except ClientError as e:
        print(f"  list failed: {e}")
        runtimes = []
    target = [r for r in runtimes if r["agentRuntimeName"] == AGENT_NAME]
    for r in target:
        rid = r["agentRuntimeId"]
        # Delete endpoints first
        try:
            eps = acc.list_agent_runtime_endpoints(agentRuntimeId=rid)["runtimeEndpoints"]
        except ClientError:
            eps = []
        for ep in eps:
            safe(f"endpoint {ep['name']}", acc.delete_agent_runtime_endpoint,
                 agentRuntimeId=rid, endpointName=ep["name"])
        # Then the runtime
        safe(f"runtime {rid}", acc.delete_agent_runtime, agentRuntimeId=rid)

    # 2. CodeBuild project
    print("\n[2/5] CodeBuild")
    cb = sess.client("codebuild")
    safe(f"codebuild project {CB_PROJECT}", cb.delete_project, name=CB_PROJECT)

    # 3. ECR repository (force-delete since it has images)
    print("\n[3/5] ECR")
    ecr = sess.client("ecr")
    safe(f"ECR repo {ECR_REPO}", ecr.delete_repository, repositoryName=ECR_REPO, force=True)

    # 4. S3 staging bucket (only delete if empty + matches our naming)
    print("\n[4/5] S3 staging bucket")
    s3 = sess.client("s3")
    try:
        # Empty bucket first
        paginator = s3.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{AGENT_NAME}/"):
            for obj in page.get("Contents", []):
                keys.append({"Key": obj["Key"]})
        if keys:
            s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": keys})
            step(f"deleted {len(keys)} objects under s3://{S3_BUCKET}/{AGENT_NAME}/")
        else:
            step(f"no objects under s3://{S3_BUCKET}/{AGENT_NAME}/")
        # Leave the bucket itself — it's shared infra the starter toolkit creates once.
    except ClientError as e:
        step(f"s3 cleanup: {e.response.get('Error', {}).get('Code')}")

    # 5. IAM roles (detach managed policies, delete inline policies, then delete role)
    print("\n[5/5] IAM roles")
    iam = sess.client("iam")
    for role in IAM_ROLES:
        try:
            attached = iam.list_attached_role_policies(RoleName=role)["AttachedPolicies"]
            for p in attached:
                safe(f"detach {p['PolicyName']} from {role}",
                     iam.detach_role_policy, RoleName=role, PolicyArn=p["PolicyArn"])
        except ClientError:
            pass
        try:
            inline = iam.list_role_policies(RoleName=role)["PolicyNames"]
            for pol in inline:
                safe(f"delete inline policy {pol} on {role}",
                     iam.delete_role_policy, RoleName=role, PolicyName=pol)
        except ClientError:
            pass
        safe(f"role {role}", iam.delete_role, RoleName=role)

    print("\n=== Teardown done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
