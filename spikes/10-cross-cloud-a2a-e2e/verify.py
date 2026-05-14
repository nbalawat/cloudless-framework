"""Spike 10 verify — invoke the GCP agent's query() and inspect the AWS response chain."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import vertexai
from vertexai import agent_engines


STATE_FILE = Path(__file__).parent / "deployment_state.json"


def main() -> int:
    state = json.loads(STATE_FILE.read_text())
    print(f"GCP engine: {state['resource_name']}")
    print(f"AWS peer:   {state['aws_peer_url']}\n")

    vertexai.init(project=state["project"], location=state["location"])
    remote = agent_engines.get(state["resource_name"])

    print("=== Invoking GCP agent.query('say pong') — triggers cross-cloud A2A ===")
    try:
        resp = remote.query(prompt="say pong")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return 1

    print(json.dumps(resp, indent=2))
    aws = resp.get("aws_response", {})
    status = aws.get("status_code")
    body = aws.get("body")

    print(f"\n=== Analyze chain ===")
    print(f"  AWS HTTP status: {status}")
    if status == 200:
        if isinstance(body, dict):
            # JSON-RPC response shape: {jsonrpc, id, result|error}
            if "result" in body:
                print("  [PASS] AWS returned a JSON-RPC result")
                print(json.dumps(body["result"], indent=2)[:800])
            elif "error" in body:
                print(f"  [PARTIAL] AWS returned JSON-RPC error: {body['error']}")
                # Still a real cross-cloud call — auth worked, request reached the agent
            else:
                print(f"  [PARTIAL] Unexpected JSON shape: {list(body.keys())}")
        else:
            print(f"  body (text): {str(body)[:400]}")
    elif status in (401, 403):
        print(f"  [FAIL] AWS rejected auth — Cognito setup or JWT validation issue")
        print(f"  body: {body}")
        return 1
    elif status is None:
        print(f"  [FAIL] No response from AWS — networking issue")
        return 1
    else:
        print(f"  [FAIL] Unexpected status {status}")
        print(f"  body: {body}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
