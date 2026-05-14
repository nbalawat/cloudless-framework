"""
GCP project capability discovery for cloudless spikes.

Run with GOOGLE_APPLICATION_CREDENTIALS pointing to the SA key JSON.
No mocks; talks to real GCP.
"""
from __future__ import annotations

import json
import os
import sys
import traceback

PROJECT = os.environ.get("GCP_PROJECT", "agentic-experiments")
REGION = os.environ.get("GCP_REGION", "us-central1")


def section(title: str) -> None:
    print(f"\n{'=' * 4} {title} {'=' * (70 - len(title))}")


def try_block(label: str, fn):
    try:
        fn()
        print(f"  [OK]      {label}")
    except Exception as e:  # noqa: BLE001
        msg = str(e)[:180]
        print(f"  [ERROR]   {label}  ({type(e).__name__}: {msg})")


def main() -> int:
    section("Identity + project")
    keypath = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {keypath}")
    if not keypath:
        print("  [WARN] GOOGLE_APPLICATION_CREDENTIALS not set — will fall back to ADC")
    if keypath:
        with open(keypath) as f:
            key = json.load(f)
        print(f"  SA email:   {key.get('client_email')}")
        print(f"  project_id: {key.get('project_id')}")
    print(f"  GCP_PROJECT (effective): {PROJECT}")
    print(f"  GCP_REGION  (effective): {REGION}")

    section("Vertex AI / Agent Engine SDK")
    import vertexai
    from vertexai import agent_engines
    try:
        vertexai.init(project=PROJECT, location=REGION)
        print(f"  [OK] vertexai.init project={PROJECT} location={REGION}")
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] vertexai.init failed: {e}")
        return 1

    # List Agent Engines (called reasoningEngines on the wire)
    try:
        engines = list(agent_engines.list())
        print(f"  [OK] agent_engines.list — found {len(engines)} engine(s)")
        for e in engines[:5]:
            try:
                print(f"      - {e.resource_name}")
            except Exception:  # noqa: BLE001
                print(f"      - {e}")
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] agent_engines.list failed: {type(e).__name__}: {str(e)[:200]}")

    section("google-genai SDK — Gemini model smoke test")
    # The new SDK (replaces vertexai.generative_models which is deprecated 2026-06-24)
    from google import genai
    try:
        client = genai.Client(vertexai=True, project=PROJECT, location=REGION)
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash-001",
            "gemini-1.5-flash-002",
        ]
        for m in models_to_try:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents="reply with the single word 'pong'",
                    config={"max_output_tokens": 10},
                )
                text = getattr(resp, "text", None) or "<no text>"
                usage = getattr(resp, "usage_metadata", None)
                in_tok = getattr(usage, "prompt_token_count", "?") if usage else "?"
                out_tok = getattr(usage, "candidates_token_count", "?") if usage else "?"
                print(f"  [OK]  {m}  → {text.strip()!r}  (in={in_tok} out={out_tok})")
                break  # one working model is enough
            except Exception as e:  # noqa: BLE001
                code = type(e).__name__
                msg = str(e)[:140]
                print(f"  [FAIL] {m}  ({code}: {msg})")
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] genai.Client init: {e}")
        traceback.print_exc()

    section("IAM project-level permissions snapshot (testIamPermissions)")
    # We probe whether THIS principal can do the things we'll need.
    try:
        from google.cloud import resourcemanager_v3
        client = resourcemanager_v3.ProjectsClient()
        from google.iam.v1 import iam_policy_pb2
        wanted = [
            "aiplatform.reasoningEngines.create",
            "aiplatform.reasoningEngines.get",
            "aiplatform.reasoningEngines.list",
            "aiplatform.reasoningEngines.delete",
            "aiplatform.endpoints.predict",
            "run.services.create",
            "run.services.update",
            "storage.buckets.create",
            "storage.objects.create",
            "logging.logEntries.create",
            "iam.serviceAccounts.actAs",
        ]
        req = iam_policy_pb2.TestIamPermissionsRequest(
            resource=f"projects/{PROJECT}",
            permissions=wanted,
        )
        resp = client.test_iam_permissions(request=req)
        granted = set(resp.permissions)
        print(f"  Checked {len(wanted)} permissions; {len(granted)} granted:")
        for p in wanted:
            mark = "OK   " if p in granted else "MISS "
            print(f"    [{mark}] {p}")
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] testIamPermissions failed: {type(e).__name__}: {str(e)[:200]}")

    section("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
