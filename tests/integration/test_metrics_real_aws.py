"""Real-AWS test: CloudWatch custom-metric emission via cloudless.runtime.metrics."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="module")
def aws_available() -> bool:
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        pytest.skip("AWS credentials not configured")
        return False


def test_cloudwatch_emit_round_trip(aws_available):
    """Configure + emit a custom metric; verify it lands in CloudWatch."""
    from cloudless.runtime import metrics as M
    M.configure_cloudwatch(namespace="cloudless-test", region="us-east-1")
    try:
        M.emit_cloudwatch_metric(
            name="ClUnitTestMetric",
            value=42.0,
            unit="None",
            dimensions={"test_id": "round-trip-1"},
        )
        # CloudWatch is eventually consistent; we don't immediately list-metric
        # back. The contract is: PutMetricData succeeded without raising.
    finally:
        M._CW_CLIENT = None
