"""Spike 4 teardown — deletes agent engine + staging bucket."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import vertexai
from vertexai import agent_engines
from google.cloud import storage as gcs_storage


STATE_FILE = Path(__file__).parent / "deployment_state.json"
PROJECT = "agentic-experiments"
LOCATION = "us-central1"
STAGING_BUCKET = "cloudless-spike-04-staging-613112965612"


def main() -> int:
    print("=== Spike 4 teardown ===\n")

    vertexai.init(project=PROJECT, location=LOCATION)

    # 1. Delete agent engine(s) with cloudless-spike-04 display name
    print("[1/2] Agent engine(s)")
    for e in agent_engines.list():
        if "cloudless-spike-04" in (e.display_name or ""):
            try:
                agent_engines.delete(e.resource_name, force=True)
                print(f"  deleted {e.resource_name}")
            except Exception as ex:  # noqa: BLE001
                print(f"  delete failed for {e.resource_name}: {ex}")

    # 2. Delete the staging bucket and its contents
    print("\n[2/2] GCS staging bucket")
    client = gcs_storage.Client(project=PROJECT)
    try:
        bucket = client.bucket(STAGING_BUCKET)
        # Delete all objects first
        blobs = list(bucket.list_blobs())
        if blobs:
            bucket.delete_blobs(blobs)
            print(f"  deleted {len(blobs)} object(s)")
        bucket.delete()
        print(f"  deleted bucket gs://{STAGING_BUCKET}")
    except Exception as e:  # noqa: BLE001
        print(f"  bucket cleanup: {e}")

    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print("  removed deployment_state.json")

    print("\n=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
