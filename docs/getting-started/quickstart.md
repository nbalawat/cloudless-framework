# Quickstart

Five minutes from `pip install` to a deployed AgentCore runtime.

## 1. Scaffold a project

```bash
cloudless init my-app --framework langgraph
cd my-app
```

This produces a working project layout:

```
my-app/
├── cloudless.yaml
├── pyproject.toml
├── src/agents/hello.py
├── evals/datasets/hello.jsonl
└── tests/test_hello.py
```

## 2. Run locally

```bash
cloudless dev hello
```

That starts a local HTTP server on `127.0.0.1:8080` that speaks the same
`/invocations` contract AgentCore uses in production. Real Bedrock LLM
calls, in-memory context, in-memory peer stubs — fast iteration.

Test it:

```bash
curl -X POST localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Hello"}'
```

Want streaming? Hit `/invocations/stream` instead and read the
Server-Sent Events.

## 3. Run the unit test

```bash
pytest tests/
```

The scaffold includes a working unit test — pattern your own tests
after it.

## 4. Deploy to AWS

```bash
cloudless deploy hello
```

Cloudless does, in this order:

1. Builds your agent into a Docker container (Python 3.12 base, ARM64)
2. Pushes the container to ECR
3. Creates (or updates) the AgentCore runtime
4. Wires the DEFAULT endpoint alias to the new version

Total time: typically 90–120 seconds. The CLI streams CodeBuild output
as it runs.

When it's done, you get an ARN and a `runtimeSessionId`-anchored
invocation URL.

## 5. Operate

```bash
cloudless versions hello              # list versions + endpoints
cloudless logs hello --follow         # tail CloudWatch
cloudless rollback hello --to v17     # swap endpoint alias
cloudless eval run dataset.jsonl      # CI quality gate
cloudless cost                        # rollup usage from event logs
```

## Switch clouds

In `cloudless.yaml`, change:

```yaml
agents:
  hello:
    cloud: aws    # ← change this to: gcp
```

Then `cloudless deploy hello` ships to Vertex AI Agent Engine instead.
No code changes.

## Next steps

- [Author a real agent](first-agent.md)
- [Cross-cloud A2A](../concepts/cross-cloud-a2a.md)
- [Multi-agent patterns](../concepts/patterns.md)
- [Governance + audit](../concepts/governance.md)
