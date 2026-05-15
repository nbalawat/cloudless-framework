# Cost telemetry

Every LLM call inside a cloudless agent records to the per-invocation
`CostTracker`. Pricing comes from `cloudless.runtime.pricing` (per
1M tokens, per model).

## Per-call recording

You don't write this — `cloudless.LLM` handles it:

```python
result = await llm.invoke(prompt, ctx=ctx)
# Implicitly:
#   ctx.cost.record_llm_call(
#       model="us.amazon.nova-micro-v1:0",
#       input_tokens=42, output_tokens=128, ...
#   )
```

## Session totals

```python
total = await ctx.cost.session_total_usd()
if total > 5.0:
    raise cloudless.CostCapExceeded(f"session at ${total:.2f}")
```

Read the `cost_cap_usd_per_session` policy from `cloudless.yaml` for
declarative caps.

## Attribution propagation

```python
ctx.cost.attribute(team="payments", project="checkout")
```

The peer-call SDK attaches `X-Cloudless-Attribution-*` HTTP headers on
every A2A request, so finance rollups stay consistent across agent hops.

## Persistent sinks

Wire a `JsonlCostSink` to keep an audit trail:

```python
from cloudless.runtime.cost_sinks import add_cost_sink, JsonlCostSink

add_cost_sink(JsonlCostSink("/var/log/cloudless-cost.jsonl"))
```

Every `record_llm_call` emits a `CostRecord` to the chain.

## CLI rollup

```bash
cat /var/log/cloudless-cost.jsonl | cloudless cost --by team
```

```
                        cloudless cost — by team
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Team       ┃ Calls ┃ Input tok ┃ Output tok ┃     USD ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━┩
│ payments   │   142 │   382,401 │      9,182 │ $0.0214 │
│ fraud      │    38 │   124,000 │      3,420 │ $0.0061 │
│ TOTAL      │   180 │   506,401 │     12,602 │ $0.0275 │
└────────────┴───────┴───────────┴────────────┴─────────┘
```
