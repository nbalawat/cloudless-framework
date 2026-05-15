# Install

cloudless is a regular Python package, but cloud SDKs ride along as optional
extras so you don't pull `boto3` into a Vertex-only project (or vice versa).

## Requirements

- Python **3.11**, 3.12, or 3.13
- A valid AWS or GCP credential set (or both, for cross-cloud)

## Choose your extras

```bash
# AWS-only project
pip install "cloudless[langgraph,aws]"

# GCP-only project
pip install "cloudless[langgraph,gcp]"

# Both clouds, both frameworks
pip install "cloudless[langgraph,strands,aws,gcp]"

# Everything
pip install "cloudless[all]"
```

The available extras:

| Extra        | Brings in                                            |
|--------------|------------------------------------------------------|
| `langgraph`  | `langgraph`, `langchain`, `langchain-aws`            |
| `strands`    | `strands-agents`, `a2a-sdk` (v0.3 lane)              |
| `adk`        | `google-adk`                                         |
| `aws`        | `boto3`, `bedrock-agentcore`, starter-toolkit        |
| `gcp`        | `google-cloud-aiplatform[agent-engines]`, `google-genai` |
| `dev`        | pytest + ruff + mypy + httpx                         |
| `all`        | everything above                                     |

## Verify

```bash
cloudless --version
cloudless doctor
```

`cloudless doctor` runs 12 preflight checks across Python version, cloud
credentials, model inference-profile resolution (F1), and the SDK
dependency versions. Failures are actionable; warnings are informational.

## Upgrade

```bash
pip install -U "cloudless[langgraph,aws]"
```

cloudless follows semver loosely until v1.0 — MINOR may break. See
[`ROADMAP.md`](../ROADMAP.md) for the v1.0 commitment timeline.
