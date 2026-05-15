# Cassettes & eval

Two patterns for keeping agent quality high without burning budget on
every CI run.

## Cassettes

A *cassette* is a JSONL recording of LLM prompts and responses. Record
once against real Bedrock or Vertex; replay deterministically thereafter.

```python
from cloudless.testing import llm_cassette

# RECORD — real LLM call, persist to cassette
with llm_cassette("tests/cassettes/greeting.jsonl", mode="record"):
    llm = cloudless.LLM(model="nova-micro")
    text = await llm.invoke("hi")

# REPLAY — no real call; serves from cassette
with llm_cassette("tests/cassettes/greeting.jsonl", mode="replay"):
    llm = cloudless.LLM(model="nova-micro")
    text = await llm.invoke("hi")   # identical text every run
```

The CLI wires this for dev too:

```bash
cloudless dev hello --record tests/cassettes/hello.jsonl
cloudless dev hello --replay tests/cassettes/hello.jsonl
```

Cassettes are committed to git. Diffing a cassette is reviewing the
prompt-change impact on the model's response.

## Eval

```python
from cloudless.eval import EvalDataset, run_eval, contains_substring, llm_judge

dataset = EvalDataset.from_jsonl("evals/datasets/hello.jsonl")
run = await run_eval(
    dataset,
    target=lambda p: agent.query(ctx, p),
    metrics=[
        contains_substring(),
        llm_judge("Is this response concise and on-topic?",
                  model="gemini-flash"),
    ],
)
print(run.summary)
```

Or via the CLI:

```bash
cloudless eval run evals/datasets/hello.jsonl --model nova-micro
```

The CLI exits non-zero on failure rate above your threshold — wire it
into CI as a quality gate.

## Multi-cloud judge

`llm_judge` accepts both Bedrock and Vertex aliases:

```python
llm_judge("rubric", model="gemini-flash", project="my-proj")
llm_judge("rubric", model="claude-haiku")
```
