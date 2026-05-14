# cloudless — Risks and Open Questions

> What we know we don't know. What could break our assumptions. What needs to be validated before we commit further.
> Last updated 2026-05-14 (Q37 closed the 10 OQs originally listed here).

---

## High-impact risks

### R1. AgentCore is on A2A spec v0.3 (capability statement, not drift)

**Severity: medium. Status: confirmed 2026-05-14 (see SPIKE-FINDINGS.md F3).**

AgentCore advertises `protocolVersion: 0.3.0` deliberately. a2a-sdk 1.0 implements spec v1.0 with a v0.3 compat lane (`a2a.compat.v0_3.types`). For v0.x cloudless we pin `a2a-sdk>=0.3.9,<1.0.0` and target v0.3 across the stack (AgentCore + Strands + cloudless manifest). The bedrock-agentcore SDK auto-publishes BOTH agent-card paths (`/.well-known/agent-card.json` and the legacy `/.well-known/agent.json`).

**v1 architectural impact:** none — the version match is consistent across our stack.

**Cross-cloud impact:** GCP-side ADK clients targeting v1.0 spec must enable v0.3 compat (or our peer routing layer needs to negotiate). Validate when Spike 10 runs (cross-cloud A2A E2E).

**Migration trigger:** revisit when (a) Strands ships a2a-sdk 1.x compat AND (b) AgentCore moves its `protocolVersion` advertisement to ≥1.0. Track via Q27 compatibility matrix.

### R2. Google Gen AI SDK migration deadline (June 24, 2026)

**Severity: medium-high. Status: schedule-driven.**

The `vertexai.generative_models` module in the legacy Vertex AI SDK is removed on June 24, 2026. Our M2 milestone (cross-cloud) lands somewhere around that date depending on kickoff. If we slip, the GCP LLM adapter may experience temporary fragility.

**Mitigation**: standardize on `google-genai` from M1, before the deadline, even though M1 is AWS-only. Smoke-test the dual-SDK behavior (`google-cloud-aiplatform` for deploy, `google-genai` for model calls) during M1 to catch incompatibilities early.

### R3. ADK ↔ AgentCore Memory bridge (custom `AgentCoreMemorySessionService`)

**Severity: medium. Status: known gap.**

ADK has its own `SessionService` abstraction. AWS has not published a bridge to AgentCore Memory. We need to build `AgentCoreMemorySessionService` ourselves to support ADK on AWS (M4 pulled-in scope).

**Risk**: ADK's session API may change between v1.33 and whenever we ship; constant maintenance burden.

**Mitigation**: pin to an LTS ADK release for the adapter; write the adapter as a thin wrapper over `AgentCore Memory` so we can absorb ADK API changes by updating only the bridge.

### R4. AgentCore Gateway semantic-search throttle (25 TPM)

**Severity: medium. Status: documented limit.**

AgentCore Gateway's semantic tool search caps at 25 TPM per account. Agents with large tool catalogs may bottleneck.

**Mitigation**: client-side caching of tool lists; load-aware fallback to ListTools when search hits the throttle; clear docs warning about catalog scale.

### R5. Cross-cloud cost-attribution propagation untested at scale

**Severity: medium. Status: design-only.**

Q20 specifies that A2A peer calls propagate originating attribution via a header so finance can roll up cost. The mechanism (header + span attribute + downstream OTel correlation) is unimplemented; correctness under high concurrency, retries, and async tasks is unverified.

**Mitigation**: load-test propagation in M3 (when cost telemetry ships). Build the attribution-rollup query in `cloudless cost report` against synthetic traffic to verify correctness.

### R6. AgentCore single-protocol-per-runtime is unusual

**Severity: medium-low. Status: design absorbs it; user education gap.**

Users expecting "one agent, one URL" will be surprised that an HTTP+A2A agent on AWS is two deployments. Cost surprises ("why is this 2× the price?") are likely without clear messaging.

**Mitigation**: `cloudless deploy` prints cost delta at the time of deploy. Docs explain it as a property of AgentCore, not cloudless. `cloudless versions` shows both runtimes side by side.

### R7. MAF on either cloud has no first-party support

**Severity: low for v1 (deferred to v3); high for v3 itself.**

When we eventually add MAF in v3, we'll be writing and maintaining adapters for both clouds with no AWS or Google sample to anchor against. MAF is the youngest framework; semantics will keep evolving.

**Mitigation**: defer MAF to v3; reassess when MAF has clearer support story from either hyperscaler.

### R8. AgentCore Browser ≠ GCP "browser"

**Severity: medium. Status: spike required in M5.**

AgentCore Browser is a managed Playwright environment. GCP doesn't have a direct equivalent; the closest is Agent Sandbox + a Computer Use model controlling a browser. The API shapes are genuinely different — one is "automation script targeting a browser," the other is "model that observes screenshots and emits clicks."

**Mitigation**: design spike at M5 kickoff. Likely we expose two sub-APIs (`Browser.automate(script)` for Playwright-style, `Browser.computer_use(goal)` for model-driven) and document each cloud's support.

### R9. Local dev `cloudless dev` sandbox is not microVM-isolated

**Severity: low. Status: documented behavior.**

`cloudless dev`'s Sandbox primitive runs as a local subprocess, not a Firecracker microVM. Untrusted code execution locally has no isolation guarantees.

**Mitigation**: clear security warning in `cloudless dev` output; recommend disabling sandbox in dev when running untrusted prompts; document that production behavior differs.

### ~R12. Strands `execute()` path inside AgentCore A2A mode raises mid-execution~ — RESOLVED 2026-05-14

**Status: closed (root cause was F15, not Strands/A2A).** The actual exception was `ResourceNotFoundException` from Bedrock — Anthropic gates `converse_stream` separately from `converse`. Strands uses `converse_stream`; the Spike 2 agent's model (Claude Haiku 4.5) lacked streaming approval in this account. Swapping the model to `us.amazon.nova-micro-v1:0` (no Anthropic form requirement) made Spike 10 fully pass with "pong" returned end-to-end. See SPIKE-FINDINGS.md F15 for the new gating risk this surfaced.

### R12-historical. Strands `execute()` path inside AgentCore A2A mode raises mid-execution

**Severity: high. Status: open (Spike 10 follow-up).**

Spike 10 closed the cross-cloud A2A loop end-to-end at the protocol+auth layer, but the AWS-side Strands agent (configured via `serve_a2a(StrandsA2AExecutor(agent))`) returned a synthesized task-status message "Agent execution failed" rather than running the Strands agent and producing a response. uvicorn logs show NO log line for the actual `POST /` JSON-RPC request, suggesting either the request bypasses uvicorn entirely in A2A protocol mode, or it errors so early that uvicorn doesn't get to log it.

**Hypotheses:**
1. A2A protocol mode in AgentCore does not route through uvicorn at all — it has its own JSON-RPC dispatcher that calls the executor directly via stdin/stdout or another IPC mechanism, bypassing the HTTP listener.
2. `StrandsA2AExecutor.execute()` requires event-queue semantics (TaskUpdater, EventQueue) that AgentCore's A2A handler doesn't supply correctly.
3. Bedrock IAM propagation race on first model invocation immediately after runtime cold-start.

**Validation plan:**
- Reproduce locally: start the agent on 127.0.0.1:9000, send a Cognito-bearer-less JSON-RPC `message/send`, see if Strands errors locally too. If yes → Strands/a2a-sdk integration bug; if no → AgentCore A2A dispatch contract issue.
- If AgentCore-side: enable X-Ray (wait 10-15 min after deploy for trace destination) and re-run; X-Ray spans should show where the failure originates.

**Mitigation paths (not blocking v1):**
1. Use a vanilla a2a-sdk `AgentExecutor` (not `StrandsA2AExecutor`) and call Strands manually inside `execute()`.
2. Pin to specific versions of `bedrock-agentcore` + `strands-agents` known to interop cleanly via the A2A protocol mode (compatibility matrix from Q27).

**Architectural impact:** none on Q1-Q39 design decisions. The cross-cloud architecture works; this is an implementation-debugging issue.

### ~R11. Strands A2A executor broken against a2a-sdk 1.0+~ — RESOLVED 2026-05-14

**Status: closed.** Pinning `a2a-sdk>=0.3.9,<1.0.0` (currently resolves to 0.3.26) unblocks `StrandsA2AExecutor`. AgentCore itself advertises `protocolVersion: 0.3.0` and the bedrock-agentcore SDK exposes both v0.3 and v1.x agent-card paths — so v0.3 is the architecturally correct target for v0.x cloudless. Migration to a2a-sdk 1.x deferred until Strands + AgentCore both move to spec v1.0. See SPIKE-FINDINGS.md F3 for the full investigation.

### R10. Eval cassette portability and bit-stability

**Severity: low. Status: design assumption.**

We assume cassettes recorded against Bedrock can be replayed against Vertex (and vice versa) for unit tests since the cassette mocks the LLM. Reality: cassettes record specific provider-shape responses; replaying a Bedrock cassette through a Vertex client (or vice versa) may fail on response-shape mismatches.

**Mitigation**: cassettes are tagged with `provider:bedrock` or `provider:vertex` at record time; replay refuses to swap unless `compat:portable` is set; document the limit.

---

## Open questions — defaults locked at Q37 (2026-05-14)

The ten open questions surfaced during design have been settled with the following defaults. Listed here for context; the canonical reference is `docs/ARCHITECTURE.md` §9.8 and `docs/DECISIONS.md` Q37.

| # | Question | Default | Revisit if |
|---|---|---|---|
| OQ1 | Cognito feature tier | Standard tier with M2M App Clients (with secret); free at our scale | Pricing model changes |
| OQ2 | Per-agent OTel sampling rate | 100% dev, 10% prod, adaptive auto-degrade to 1% under throttle | Observability sink cost dominates |
| OQ3 | Manifest update propagation | Bake-time manifest + 5-min TTL refresh from known cloud-storage URL; fallback to embedded copy if refresh fails | Cold-storage fetch becomes a SPOF |
| OQ4 | Bedrock / Gemini model deprecations | Model-alias resolution table maintained in cloudless (`claude-opus` → current best model ID); warnings via `cloudless lint`; refreshed on `upgrade-check` | New cloud provider added |
| OQ5 | AgentCore Memory custom-strategy 30 KB prompt cap | `Memory.with_custom_strategy()` validates prompt size at construction with clear file:line error | AWS raises or removes the cap |
| OQ6 | GCP cold-start under multi-day resume | Benchmark in M4 as part of continuous suite (Q34); feature-gate the multi-day path with a documented caveat | Benchmark reveals a hard limit |
| OQ7 | Slack OAuth approval app | Ship `cloudless/slack-approval-app` GitHub template; customer installs in their Slack workspace | Slack API breaking changes |
| OQ8 | Cost dashboard cross-cloud unification | Grafana 11+ mixed data sources (CloudWatch + Cloud Logging plugins); dashboard JSON ships via `cloudless dashboards install` | Grafana licensing changes |
| OQ9 | Manifest signing for cross-cloud trust (A2A v1.2 signed cards) | Defer to v1.5; when shipped, use Sigstore keyless (same toolchain as release signing — Q33) | Enterprise customer requires it pre-v1.0 |
| OQ10 | Test-coverage SLA for framework × cloud matrix | Core path on every PR (each framework × each cloud × LLM+Memory+A2A = 18 cells, ~9 min); full matrix (66 cells) nightly | CI bill exceeds budget |

---

## Assumptions we should reverify quarterly

| Assumption | Reason to recheck |
|---|---|
| AgentCore Runtime still requires ARM64 only | AWS may add x86 support |
| AgentCore A2A is single-protocol-per-runtime | AWS could relax (recently announced multi-protocol support is a strong signal it's coming) |
| Gemini Enterprise Agent Runtime is still picklable-class-based | GCP could add container deployment |
| Cognito free tier sufficient | AWS adjusts pricing |
| ADK in Python is still v1.x | ADK 2.0 is plausible within the year |
| MAF support is still tier-3 on both clouds | Either hyperscaler could publish first-party MAF samples |
| AgentCore Browser still has no GCP equivalent | GCP's Agent Sandbox + Computer Use model could mature into a near-Playwright shape |
| Apache 2.0 open-core is the right commercial model | Market evolves; might want to shift to BSL or other |

---

## Risks we're explicitly accepting

- **Strict semver pre-1.0 may slow iteration.** Acceptable cost; we'd rather build the discipline now than retrofit later.
- **`cloudless dev` runs real LLM calls by default.** Cost on every test run. Mitigated by cassettes for CI.
- **Manifest baked into agents means redeploys to add a peer.** Acceptable for v1; consider runtime-refresh in v2 if pain.
- **Python-only at v1 cuts out Node.js shops.** Conscious choice; TS in v2.
- **MAF users wait until v3.** Conscious choice given MAF maturity and tier-3 status on both clouds.

---

## How to use this file

- Add new risks with severity, status, validation plan, and mitigation.
- Sort by severity; update status as we learn more.
- When a risk is fully mitigated or invalidated, move to "Resolved" section (not yet created — add when first risk closes).
- Quarterly assumption review keeps our priors current.
