"""Spike 10 — deploy the GCP-side cross-cloud A2A agent."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from pathlib import Path

import cloudpickle
import vertexai
from vertexai import agent_engines

# Reuse Spike 2's Cognito state (same pool, same M2M client)
SPIKE_02_DIR = Path(__file__).parent.parent / "02-cognito-cross-cloud-auth"
SPIKE_02_STATE = SPIKE_02_DIR / "cognito_state.json"

# Spike 2's AWS AgentCore JWT-authenticated A2A runtime ARN
AWS_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:613112965612:runtime/cloudless_spike_02-MSR6NF8xz5"
AWS_REGION = "us-east-1"

PROJECT = "agentic-experiments"
LOCATION = "us-central1"
STAGING_BUCKET = "cloudless-spike-10-staging-613112965612"
DISPLAY_NAME = "cloudless-spike-10"

STATE_FILE = Path(__file__).parent / "deployment_state.json"

sys.path.insert(0, str(Path(__file__).parent))
import gcp_agent as gcp_agent_module  # noqa: E402
cloudpickle.register_pickle_by_value(gcp_agent_module)
from gcp_agent import CloudlessSpike10Agent  # noqa: E402


def ensure_bucket(name: str) -> str:
    from google.cloud import storage as gcs_storage
    from google.cloud.exceptions import Conflict
    client = gcs_storage.Client(project=PROJECT)
    try:
        client.create_bucket(name, location=LOCATION)
        print(f"  created bucket gs://{name}")
    except Conflict:
        print(f"  bucket gs://{name} already exists; reusing")
    return f"gs://{name}"


def main() -> int:
    if not SPIKE_02_STATE.exists():
        print(f"ERROR: Spike 2's cognito_state.json missing at {SPIKE_02_STATE}")
        print("Run spikes/02-cognito-cross-cloud-auth/setup_cognito.py first.")
        return 1

    cog = json.loads(SPIKE_02_STATE.read_text())
    escaped = urllib.parse.quote(AWS_RUNTIME_ARN, safe="")
    # A2A endpoint = AgentCore invocations URL (NOT the agent-card URL)
    aws_peer_url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{escaped}/invocations"

    print("=== Spike 10: deploy GCP cross-cloud A2A agent ===\n")
    print(f"AWS peer:      {aws_peer_url}")
    print(f"Cognito pool:  {cog['pool_id']}")
    print(f"Cognito client:{cog['client_id']}\n")

    staging = ensure_bucket(STAGING_BUCKET)
    vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=staging)

    instance = CloudlessSpike10Agent(
        cognito_token_url=cog["token_url"],
        cognito_client_id=cog["client_id"],
        cognito_client_secret=cog["client_secret"],
        cognito_scope=cog["scope"],
        aws_peer_url=aws_peer_url,
    )

    remote = agent_engines.create(
        agent_engine=instance,
        requirements=[
            "google-cloud-aiplatform[agent-engines]",
            "httpx",
        ],
        display_name=DISPLAY_NAME,
        description="cloudless Spike 10 — cross-cloud A2A capstone. Calls AWS AgentCore over A2A with Cognito JWT.",
    )
    print(f"\nDeployed: {remote.resource_name}")

    STATE_FILE.write_text(json.dumps({
        "resource_name": remote.resource_name,
        "aws_peer_url": aws_peer_url,
        "staging_bucket": staging,
        "project": PROJECT,
        "location": LOCATION,
    }, indent=2))
    print(f"State saved to {STATE_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
