"""
AWS account capability discovery for cloudless spikes.

Run with the cloudless-spikes venv's Python. No mocks; talks to real AWS.
"""
from __future__ import annotations

import json
import sys
import boto3
from botocore.exceptions import ClientError


def section(title: str) -> None:
    print(f"\n{'=' * 4} {title} {'=' * (70 - len(title))}")


def try_call(label: str, fn, *args, **kwargs):
    """Run an AWS call; print success/failure with brief detail."""
    try:
        result = fn(*args, **kwargs)
        print(f"  [OK]      {label}")
        return result
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "?")
        msg = e.response.get("Error", {}).get("Message", str(e))[:120]
        print(f"  [DENIED]  {label}  ({code}: {msg})")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR]   {label}  ({type(e).__name__}: {str(e)[:120]})")
        return None


REGION = "us-east-1"


def main() -> int:
    sess = boto3.session.Session(region_name=REGION)
    sts = sess.client("sts")
    me = sts.get_caller_identity()
    print(f"Account: {me['Account']}")
    print(f"User:    {me['Arn']}")
    print(f"Region:  {REGION}")

    section("Bedrock foundation models")
    bedrock = sess.client("bedrock")
    fm = try_call("ListFoundationModels", bedrock.list_foundation_models)
    if fm:
        claude_models = [m["modelId"] for m in fm["modelSummaries"] if "claude" in m["modelId"].lower()]
        print(f"  Claude variants visible: {len(claude_models)}")
        for m in claude_models[:6]:
            print(f"    - {m}")
        if len(claude_models) > 6:
            print(f"    ... and {len(claude_models) - 6} more")
    # Check actual model access (different from listing)
    try:
        access_resp = bedrock.get_foundation_model_availability(
            modelId="anthropic.claude-3-5-haiku-20241022-v1:0"
        )
        avail = access_resp.get("agreementAvailability", {}).get("status", "?")
        ent = access_resp.get("entitlementAvailability", "?")
        print(f"  Claude 3.5 Haiku — agreement: {avail}, entitlement: {ent}")
    except Exception as e:  # noqa: BLE001
        print(f"  [model-access-check error] {type(e).__name__}: {str(e)[:120]}")

    section("Bedrock runtime invoke (smoke test, costs ~$0.0001)")
    bedrock_rt = sess.client("bedrock-runtime")
    try:
        resp = bedrock_rt.converse(
            modelId="anthropic.claude-3-5-haiku-20241022-v1:0",
            messages=[{"role": "user", "content": [{"text": "reply with the single word 'pong'"}]}],
            inferenceConfig={"maxTokens": 10},
        )
        out = resp["output"]["message"]["content"][0]["text"].strip()
        usage = resp.get("usage", {})
        print(f"  [OK] Converse response: {out!r}")
        print(f"  Tokens: in={usage.get('inputTokens')} out={usage.get('outputTokens')}")
    except ClientError as e:
        print(f"  [DENIED] converse: {e.response.get('Error', {}).get('Code')}: {e.response.get('Error', {}).get('Message', '')[:200]}")
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] converse: {type(e).__name__}: {e}")

    section("AgentCore control plane (us-east-1)")
    acc = sess.client("bedrock-agentcore-control")
    try_call("ListAgentRuntimes", acc.list_agent_runtimes, maxResults=5)
    try_call("ListGateways",       acc.list_gateways, maxResults=5)
    try_call("ListMemories",       acc.list_memories, maxResults=5)
    try_call("ListWorkloadIdentities", acc.list_workload_identities, maxResults=5)
    try_call("ListCodeInterpreters",   acc.list_code_interpreters, maxResults=5)
    try_call("ListBrowsers",       acc.list_browsers, maxResults=5)

    section("Cognito user pools (idp)")
    cog = sess.client("cognito-idp")
    try_call("ListUserPools", cog.list_user_pools, MaxResults=5)

    section("ECR")
    ecr = sess.client("ecr")
    try_call("DescribeRepositories", ecr.describe_repositories, maxResults=5)

    section("IAM permissions snapshot for current user")
    iam = sess.client("iam")
    # Drop the leading 'user/' from arn so we can call iam:ListAttachedUserPolicies
    user_name = me["Arn"].rsplit("/", 1)[-1]
    try:
        attached = iam.list_attached_user_policies(UserName=user_name)["AttachedPolicies"]
        print(f"  Attached managed policies ({len(attached)}):")
        for p in attached:
            print(f"    - {p['PolicyName']}  ({p['PolicyArn']})")
    except ClientError as e:
        print(f"  [DENIED] list_attached_user_policies: {e.response.get('Error', {}).get('Code')}")
    try:
        groups = iam.list_groups_for_user(UserName=user_name)["Groups"]
        print(f"  Groups ({len(groups)}):")
        for g in groups:
            print(f"    - {g['GroupName']}")
    except ClientError as e:
        print(f"  [DENIED] list_groups_for_user: {e.response.get('Error', {}).get('Code')}")
    try:
        inline = iam.list_user_policies(UserName=user_name)["PolicyNames"]
        print(f"  Inline policies ({len(inline)}): {inline}")
    except ClientError as e:
        print(f"  [DENIED] list_user_policies: {e.response.get('Error', {}).get('Code')}")

    section("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
