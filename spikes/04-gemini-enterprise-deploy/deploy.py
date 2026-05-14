"""
Spike 4 deploy — provisions staging bucket + deploys CloudlessSpike04Agent
to Gemini Enterprise Agent Runtime.

Persists deployment_state.json next to this script so verify.py + cleanup.py
can find the engine resource_name.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cloudpickle
from google.cloud import storage as gcs_storage
from google.cloud.exceptions import Conflict
import vertexai
from vertexai import agent_engines

# Import the agent module + force cloudpickle to embed the class definition
# (otherwise remote runtime gets ModuleNotFoundError: No module named 'agent'). F13.
sys.path.insert(0, str(Path(__file__).parent))
import agent as agent_module  # noqa: E402
cloudpickle.register_pickle_by_value(agent_module)
from agent import CloudlessSpike04Agent  # noqa: E402


PROJECT = "agentic-experiments"
LOCATION = "us-central1"
STAGING_BUCKET_NAME = "cloudless-spike-04-staging-613112965612"
DISPLAY_NAME = "cloudless-spike-04"
STATE_FILE = Path(__file__).parent / "deployment_state.json"


def ensure_bucket(bucket_name: str) -> str:
    """Create the bucket if it doesn't exist; return gs:// URL."""
    client = gcs_storage.Client(project=PROJECT)
    try:
        client.create_bucket(bucket_name, location=LOCATION)
        print(f"  created bucket gs://{bucket_name}")
    except Conflict:
        print(f"  bucket gs://{bucket_name} already exists; reusing")
    return f"gs://{bucket_name}"


def main() -> int:
    print("=== Spike 4: Gemini Enterprise Agent Runtime deploy ===\n")

    # 1. Staging bucket
    print("[1/3] Staging bucket")
    staging = ensure_bucket(STAGING_BUCKET_NAME)

    # 2. Vertex init
    print(f"\n[2/3] vertexai.init project={PROJECT} location={LOCATION}")
    vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=staging)

    # 3. Deploy
    print(f"\n[3/3] agent_engines.create(...)")
    instance = CloudlessSpike04Agent()
    remote = agent_engines.create(
        agent_engine=instance,
        requirements=[
            "google-cloud-aiplatform[agent-engines]",
            "google-genai",
        ],
        # extra_packages alone isn't enough — cloudpickle defaults to pickling
        # classes by reference, so the remote runtime tries to import `agent`
        # and fails. Combined with cloudpickle.register_pickle_by_value(agent_module)
        # above, the class definition is embedded in the pickle so the remote
        # can deserialize without importing `agent`. F13 in SPIKE-FINDINGS.
        display_name=DISPLAY_NAME,
        description="cloudless Spike 4 — validates Q4 GCP-side picklable-class deploy path.",
    )
    print(f"  resource_name: {remote.resource_name}")

    STATE_FILE.write_text(json.dumps({
        "resource_name": remote.resource_name,
        "staging_bucket": staging,
        "project": PROJECT,
        "location": LOCATION,
    }, indent=2))
    print(f"\nState saved to {STATE_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
