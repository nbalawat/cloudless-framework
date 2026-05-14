"""Spike 4 verify — call query() and stream_query() on the deployed engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import vertexai
from vertexai import agent_engines


STATE_FILE = Path(__file__).parent / "deployment_state.json"


def main() -> int:
    if not STATE_FILE.exists():
        print("No deployment_state.json — run deploy.py first.")
        return 1
    state = json.loads(STATE_FILE.read_text())
    print(f"Engine: {state['resource_name']}\n")

    vertexai.init(project=state["project"], location=state["location"])
    remote = agent_engines.get(state["resource_name"])

    # What operations did the engine register?
    print("=== Registered operations ===")
    try:
        schemas = remote.operation_schemas() if hasattr(remote, "operation_schemas") else None
        print(json.dumps(schemas, indent=2, default=str)[:800])
    except Exception as e:  # noqa: BLE001
        print(f"  (could not fetch schemas: {e})")

    # Verify-1: query (sync)
    print("\n=== Verify-1: query('say pong') ===")
    try:
        resp = remote.query(prompt="say pong")
        print(f"  response: {resp}")
        assert "pong" in str(resp).lower(), "did not get expected 'pong' in response"
        print("  [PASS] query() works")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] {type(e).__name__}: {str(e)[:400]}")
        return 1

    # Verify-2: stream_query
    print("\n=== Verify-2: stream_query('say pong') ===")
    try:
        chunks = []
        for chunk in remote.stream_query(prompt="say pong"):
            chunks.append(chunk)
            print(f"  chunk: {chunk}")
        joined = " ".join(str(c) for c in chunks)
        assert "pong" in joined.lower(), "stream_query never emitted 'pong'"
        print(f"  [PASS] stream_query yielded {len(chunks)} chunk(s)")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] {type(e).__name__}: {str(e)[:400]}")
        return 1

    print("\n=== Spike 4: PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
