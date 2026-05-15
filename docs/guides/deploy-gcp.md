# Deploy to GCP

`cloudless deploy <agent>` ships an agent to Vertex AI Agent Engine
(the renamed Vertex Reasoning Engine, part of Gemini Enterprise Agent
Platform).

## Prerequisites

- `gcloud auth application-default login` (or service account JSON via `GOOGLE_APPLICATION_CREDENTIALS`)
- A GCP project with Vertex AI API enabled
- A GCS staging bucket; cloudless creates `cloudless-staging-<project>` if missing

## What runs

In `cloudless.yaml`:

```yaml
default_cloud: gcp
agents:
  hello:
    cloud: gcp
```

Then:

```bash
cloudless deploy hello --region us-central1
```

The adapter does:

1. **Wrap** the user agent in `_CloudlessGCPAgent` (the F13a + F19 + F20 pattern):
   - `cloudpickle.register_pickle_by_value(<user_module>)` so the agent class travels by value
   - `nest_asyncio.apply()` inside `set_up()` to allow nested loops (F19)
   - Captured class attributes at `__init__` so unpickling doesn't re-import cloudless (F20)
2. **Bundle** the cloudless wheel into `requirements` (F17)
3. **Call** `vertexai.agent_engines.create(agent_engine=wrapper, ...)`
4. **Wait** for the engine to become ACTIVE (typically 2–3 min, sometimes longer under slot contention)

## Inspect

```bash
gcloud ai reasoning-engines list --region=us-central1
```

Or via the SDK:

```python
import vertexai
from vertexai import agent_engines
vertexai.init(project="my-proj", location="us-central1")
for e in agent_engines.list():
    print(e.display_name, e.resource_name)
```

## Known hazards

- **F2**: Gemini 2.5 extended thinking eats your `max_output_tokens` budget. `cloudless.LLM` disables it by default; pass `extended_thinking=True` to enable.
- **F13a**: cloudpickle by-reference fails inside Agent Engine. cloudless registers your agent module for pickle-by-value automatically.
- **F19**: Agent Runtime needs `nest_asyncio` to allow nested event loops.
- **F20**: The GCP wrapper captures cloudless classes as attributes at `__init__` (otherwise the unpickled wrapper can't import cloudless).
- **Slot contention**: Agent Engine creation occasionally times out (~10 min). Retry, or reuse an existing engine.
