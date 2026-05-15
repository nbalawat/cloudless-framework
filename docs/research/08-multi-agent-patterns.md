# Multi-agent orchestration patterns (with HITL)

> Research dossier #8 — 2026-05-14
>
> Sources: Anthropic "Building Effective Agents" (Dec 2024), LangGraph multi-agent
> docs, OpenAI Swarm, Microsoft Autogen, AWS Bedrock AgentCore multi-agent guide,
> Google Vertex multi-agent reasoning engine docs.
>
> This document enumerates the canonical multi-agent patterns, when to use each,
> how `cloudless` supports it, and where Human-in-the-Loop (HITL) inserts.

---

## What this is

When you build a system out of more than one agent, you're committing to a
**topology**: who calls whom, when, with what state, and under what failure
modes. The literature has converged on roughly 10 patterns. Most real systems
are composites — pick the one closest to your use case, then bend it.

`cloudless` does not invent new patterns. It provides:

- **`@cloudless.agent`** classes you compose freely
- **`ctx.peer(name).call(...)`** for inter-agent calls (cross-cloud-safe)
- **`@cloudless.tool`** to expose any callable, including another agent
- **`PauseChunk` + `cloudless.runtime.tasks.pause/resume`** for HITL at any point
- **`asyncio`** for parallel composition
- **`@cloudless.policy`** to gate transitions

Below, each pattern names the canonical reference, the cloudless idiom, and
the HITL insertion point a reasonable system would use.

---

## 1. Single agent + tools (the baseline)

**Canonical:** Anthropic "Building Effective Agents" §"The augmented LLM".
A single agent loops `LLM.invoke → tool.invoke → LLM.invoke ...` until done.

**cloudless idiom:** one `@cloudless.agent` class, `cloudless.tool` for tools.

**HITL insertion:** any tool can `yield PauseChunk` for an approval gate
before a side-effecting action.

```python
@cloudless.agent(name="solo")
class SoloAgent(cloudless.LangGraphAgent):
    async def query(self, ctx, prompt):
        # ... normal LLM + tool loop ...
        if needs_human:
            rec = tasks.pause(agent_name=self.name, session_id=ctx.session.id,
                              reason="refund > $1000")
            yield PauseChunk(resume_token=rec.resume_token, reason=rec.reason)
            return
```

---

## 2. Sequential / pipeline (prompt chaining)

**Canonical:** Anthropic §"Prompt chaining". A→B→C, each agent consumes the
prior's output. Used when steps have clear sequential dependencies.

**cloudless idiom:** the orchestrating agent calls `await peerA.call(prompt)`,
then `await peerB.call(...)`, then `await peerC.call(...)`. Each peer is its
own deployed `@cloudless.agent`.

**HITL insertion:** typically between two stages, before an irreversible step.

```python
draft = await ctx.peer("drafter").call(prompt)
review = await ctx.peer("reviewer").call(draft)
# HITL gate before publishing
if review["needs_approval"]:
    yield PauseChunk(...)
    return
await ctx.peer("publisher").call(review["text"])
```

---

## 3. Routing / handoff

**Canonical:** Anthropic §"Routing". A router agent classifies the input and
hands off to one specialist agent. The router itself doesn't do the work.

**cloudless idiom:** the router classifies (often with a small fast model
like Nova Micro), then `await ctx.peer(chosen_specialist).call(...)`.

**HITL insertion:** if router confidence is below threshold, pause for a
human to pick the specialist.

```python
intent = await classifier.invoke(prompt, max_tokens=10)
if confidence < 0.7:
    yield PauseChunk(reason="low-confidence routing", ...)
    return
result = await ctx.peer(intent).call(prompt)
```

---

## 4. Parallelization / fan-out

**Canonical:** Anthropic §"Parallelization". The same prompt (or different
prompts) is fanned out to N agents simultaneously. Used for voting,
self-consistency, or independent subtasks.

**cloudless idiom:** `asyncio.gather(*[ctx.peer(n).call(p) for n in peers])`.

**HITL insertion:** pause when results conflict materially (e.g., 50/50 split
on a yes/no question).

```python
results = await asyncio.gather(
    ctx.peer("legal").call(prompt),
    ctx.peer("compliance").call(prompt),
    ctx.peer("risk").call(prompt),
)
if not consensus(results):
    yield PauseChunk(reason="reviewers disagreed", ...)
    return
```

---

## 5. Orchestrator-workers (supervisor)

**Canonical:** Anthropic §"Orchestrator-workers". An orchestrator agent
decomposes the goal into sub-tasks, dispatches each to a worker agent,
gathers results, and synthesizes the final answer. The orchestrator is the
brain; workers are interchangeable.

**cloudless idiom:** orchestrator agent uses an LLM call to produce a plan
(list of sub-tasks), then `asyncio.gather` over peer calls to workers.

**HITL insertion:** pause AFTER the orchestrator produces the plan but BEFORE
workers execute. This is the highest-value HITL placement — humans validate
the plan once instead of N executions.

```python
plan = await llm.invoke(planning_prompt)
yield PauseChunk(reason=f"approve plan: {plan}", ...)  # ← gate the plan
# (after resume)
results = await asyncio.gather(*[
    ctx.peer("worker").call(step) for step in plan["steps"]
])
return await llm.invoke(synthesis_prompt + str(results))
```

---

## 6. Evaluator-optimizer (critic loop)

**Canonical:** Anthropic §"Evaluator-optimizer". A generator agent produces a
draft, a critic agent scores it, the generator revises. Iterates until the
critic approves or a max-iterations gate fires.

**cloudless idiom:** `while not approved: draft = generator.invoke(...);
score = critic.invoke(draft)`. Often within a single agent — generator and
critic are LLM calls with different system prompts.

**HITL insertion:** pause when iterations exceed a threshold without
convergence — human breaks the tie.

```python
for i in range(MAX_ITERATIONS):
    draft = await generator.invoke(prompt + last_critique)
    critique = await critic.invoke(draft)
    if critique["approved"]:
        return draft
    last_critique = critique["feedback"]
yield PauseChunk(reason=f"critic loop didn't converge in {MAX_ITERATIONS}", ...)
```

---

## 7. Network / peer-to-peer (A2A)

**Canonical:** Google/Linux Foundation A2A spec; LangGraph "network"
multi-agent. Agents call each other directly with no central coordinator.
Used when agents are owned by different teams or live on different clouds.

**cloudless idiom:** `ctx.peer("orders").call(...)` issues an A2A v0.3
`message/send` over HTTPS with a Cognito-minted JWT. Cross-cloud is
first-class (Spike 10 round-trip: AWS→GCP).

**HITL insertion:** pause when a peer returns "I need more info" or returns
data that requires escalation (e.g., PII flagged in response).

```python
result = await ctx.peer("orders").call(prompt)
if result.get("needs_escalation"):
    yield PauseChunk(reason="orders escalated", pending_action=result, ...)
```

---

## 8. Hierarchical (multi-level supervisor)

**Canonical:** LangGraph hierarchical multi-agent. Tree of supervisors —
executive → manager → workers. Lets domain experts (managers) compose their
own worker teams while a single executive owns final coordination.

**cloudless idiom:** orchestrator-workers nested: the executive treats each
manager as a peer, the manager itself is an orchestrator-workers agent.

**HITL insertion:** at the executive level, for high-impact decisions that
span multiple manager domains.

```python
# Executive agent
legal_plan = await ctx.peer("legal-manager").call(prompt)
sec_plan = await ctx.peer("security-manager").call(prompt)
if conflicts(legal_plan, sec_plan):
    yield PauseChunk(reason="legal/security plans conflict", ...)
```

---

## 9. Map-reduce

**Canonical:** classic distributed-computing pattern. Map step over a list
(each item → one sub-agent call), reduce step combines.

**cloudless idiom:** parallel fan-out followed by a synthesis LLM call.
Distinct from generic parallelization in that the inputs are *items in a
collection*, not different angles on the same prompt.

**HITL insertion:** pause for approval of the reduced output, especially
when individual map outputs are sensitive.

```python
items = ["item1", "item2", "item3"]
mapped = await asyncio.gather(*[ctx.peer("scorer").call(i) for i in items])
reduced = await synthesizer.invoke(f"Summarize: {mapped}")
yield PauseChunk(reason="approve aggregated report", pending_action=reduced)
```

---

## 10. Debate / consensus

**Canonical:** "Multi-Agent Debate" (Du et al. 2023); used in research
problems where reasoning quality benefits from multiple perspectives
arguing. N agents argue, a judge agent reads the transcript and decides.

**cloudless idiom:** N peer calls with adversarial system prompts, judge
synthesizes. Often run in rounds — each agent sees the others' arguments.

**HITL insertion:** pause when judge confidence is low, OR when one agent's
argument flags a risk the judge can't adjudicate alone.

```python
for round_num in range(3):
    args = await asyncio.gather(*[
        ctx.peer(name).call(prompt + str(prior_args)) for name in debaters
    ])
    prior_args = args
verdict = await judge.invoke(f"Decide: {prior_args}")
if verdict["confidence"] < 0.6:
    yield PauseChunk(reason="judge unsure — needs human", ...)
```

---

## 11. Tool-as-agent

**Canonical:** OpenAI Swarm, function-call-as-handoff. A tool, from the
LLM's point of view, is just a thing you call — so wrap another agent as a
tool and the LLM can decide when to invoke it.

**cloudless idiom:** wrap a peer call as a `@cloudless.tool` whose body is
`await ctx.peer(name).call(...)`. The supervising LLM sees it as a tool in
its tool-list.

**HITL insertion:** policy hook `before_tool` for the wrapped-peer tool
when the tool is high-impact.

```python
@cloudless.tool
async def consult_legal(question: str) -> str:
    """Ask the legal agent for an opinion."""
    result = await ctx.peer("legal").call(question)
    return result["answer"]

# A @cloudless.policy(stages=["before_tool"]) decorator can pause here
```

---

## HITL across all patterns: cloudless invariants

The framework provides three invariants that make HITL composable with
*any* of the above patterns:

1. **`PauseChunk` is a regular Chunk.** Any agent can yield it from any
   point in its `query()` generator. Consumers handle it uniformly.

2. **`tasks.pause()` returns a `TaskRecord` with a `resume_token`.** The
   token persists (in-memory for dev, AgentCore Memory in AWS, Memory Bank
   on GCP) so the resume can happen from a different process / API call.

3. **`resume(token, approval)` is idempotent.** Second call returns None.
   This makes retries safe and double-clicks harmless.

The cloud-backed task stores (`AgentCoreTaskStore`, `MemoryBankTaskStore`)
mean HITL state survives container restart and is queryable by an external
approval UI.

---

## Validation strategy

Each pattern has a dedicated integration test under
`tests/integration/patterns/` that:

- Spins the participating agents up in-process (no real deploys)
- Exercises the pattern against **real Bedrock LLM calls** (no mocks)
- Inserts a HITL pause at the canonical insertion point listed above
- Asserts: state flows correctly, pause record is persisted, resume
  delivers the human's decision, and the post-resume execution path uses it.

See `tests/integration/patterns/test_pattern_*.py`.

---

## What `cloudless` does NOT do

Honesty:

- **No built-in planner.** The orchestrator-workers planning LLM call is
  yours to write. We don't ship a "decompose this goal" prompt template.
- **No supervisor scheduler.** If you want a long-running supervisor that
  manages a fleet of agents over hours, you wire that yourself on top of
  `cloudless.runtime.tasks` and a queue (SQS, Cloud Tasks).
- **No agent registry.** Peers are discovered via the baked
  `cloudless-manifest.json`. There's no service-discovery layer at v1.
- **No native consensus algorithm.** Debate/consensus tests run a judge
  LLM. There's no provable consensus primitive (paxos, raft) — agents are
  not voting nodes.
