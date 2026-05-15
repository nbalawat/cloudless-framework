# Multi-agent patterns

cloudless does not invent new orchestration patterns — it gives you
the composable primitives (`@cloudless.agent`, `ctx.peer().call()`,
`@cloudless.tool`, `PauseChunk`, `@cloudless.policy`, `asyncio`) that
make every canonical pattern straightforward.

The ten canonical patterns from the literature, all validated against
**both** Bedrock and Vertex Gemini in the integration suite:

| Pattern              | When to use                                  | Test                                          |
|----------------------|----------------------------------------------|-----------------------------------------------|
| Single agent + tools | Most agents start here                       | covered across many tests                     |
| Sequential / pipeline| Steps have clear deps                        | `test_pattern_sequential.py`                  |
| Routing / handoff    | One specialist handles each input            | `test_pattern_routing.py`                     |
| Parallel / fan-out   | Voting, independent subtasks                 | `test_pattern_parallel.py`                    |
| Supervisor           | Plan-then-execute                            | `test_pattern_supervisor.py`                  |
| Evaluator-optimizer  | Iterate until critic approves                | `test_pattern_evaluator_optimizer.py`         |
| Network / A2A peer   | Agents across teams or clouds                | `test_pattern_a2a_peer.py`                    |
| Hierarchical         | Multi-level supervision                      | `test_pattern_hierarchical.py`                |
| Map-reduce           | Independent items + aggregation              | `test_pattern_map_reduce.py`                  |
| Debate / consensus   | Reasoning benefits from arguing perspectives | `test_pattern_debate.py`                      |
| Tool-as-agent        | LLM decides when to invoke a sub-agent       | `test_pattern_tool_as_agent.py`               |

Each test exercises the pattern with a HITL pause at the canonical
insertion point. Read [research dossier #8](https://github.com/cloudless/cloudless/blob/main/docs/research/08-multi-agent-patterns.md)
for full descriptions, canonical references, and code sketches.

## What cloudless does NOT do

Honest scope:

- **No built-in planner.** The supervisor's planning LLM call is yours
  to write. We don't ship a "decompose this goal" prompt template.
- **No long-running scheduler.** A supervisor managing a fleet over
  hours is your queue (SQS, Cloud Tasks) on top of `cloudless.runtime.tasks`.
- **No service-discovery layer.** Peers live in the baked manifest.
- **No native consensus algorithm.** Debate / consensus runs a judge LLM.
