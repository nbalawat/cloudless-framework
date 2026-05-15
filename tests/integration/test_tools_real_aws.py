"""Real-cloud integration test for cloudless.Tool.from_aws_lambda.

Creates a tiny test Lambda inline, invokes it via Tool.from_aws_lambda,
then deletes the Lambda. Cost: $0 (Lambda has a free tier).
"""
from __future__ import annotations

import json
import time
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
    except Exception:
        return False


@pytest.fixture(scope="module")
def lambda_resource(aws_available):
    """Create a tiny echo Lambda; tear down after."""
    if not aws_available:
        pytest.skip("AWS credentials not configured")

    iam = boto3.client("iam")
    lam = boto3.client("lambda", region_name="us-east-1")

    name = f"cloudless-spike-tool-{uuid.uuid4().hex[:8]}"
    role_name = f"{name}-role"

    # Trust policy for Lambda service
    assume = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow",
                       "Principal": {"Service": "lambda.amazonaws.com"},
                       "Action": "sts:AssumeRole"}],
    }
    role_resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(assume),
    )
    role_arn = role_resp["Role"]["Arn"]
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    # Wait for role to propagate
    time.sleep(8)

    # Tiny inline Lambda
    code = b'''
def handler(event, context):
    return {"echoed": event, "from": "cloudless-spike-tool"}
'''
    # Lambda needs a zip file
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("lambda_function.py", code)
    buf.seek(0)

    try:
        fn = lam.create_function(
            FunctionName=name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.handler",
            Code={"ZipFile": buf.read()},
            Description="cloudless integration test echo lambda",
            Timeout=10,
        )
    except Exception:
        # Cleanup role and re-raise
        iam.detach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        iam.delete_role(RoleName=role_name)
        raise

    # Wait until active
    waiter = lam.get_waiter("function_active_v2")
    waiter.wait(FunctionName=name)

    yield fn["FunctionArn"]

    # Teardown
    try:
        lam.delete_function(FunctionName=name)
    except Exception:
        pass
    try:
        iam.detach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        iam.delete_role(RoleName=role_name)
    except Exception:
        pass


async def test_tool_invokes_real_aws_lambda(lambda_resource):
    arn = lambda_resource
    t = cloudless.Tool.from_aws_lambda(arn, description="Echo")
    result = await t.invoke({"hello": "cloudless", "n": 42})
    assert result["from"] == "cloudless-spike-tool"
    assert result["echoed"] == {"hello": "cloudless", "n": 42}
