# cloudless — Risks and Open Questions

> What we know we don't know. What could break our assumptions. What needs to be validated before we commit further.
> Last updated 2026-05-14.

---

## High-impact risks

### R1. AgentCore A2A protocol version drift

**Severity: high. Status: must validate in M2.**

AWS docs show AgentCore agent cards advertising `protocolVersion: 0.3.0` in samples, while upstream A2A spec is at v1.2 under Linux Foundation. Cross-cloud peers built against v1.2 (especially ADK 1.x clients on GCP) may reject AgentCore-served cards or require lenient version handling.

**Validation plan**: in M2 demo, confirm the actual `protocolVersion` field AgentCore serves, and confirm Gemini Enterprise / ADK clients accept it.

**Mitigation if drift confirmed**: maintain a card-rewriting middleware in our embedded runtime lib that upgrades AgentCore's card to the latest spec version on emit.

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

### R10. Eval cassette portability and bit-stability

**Severity: low. Status: design assumption.**

We assume cassettes recorded against Bedrock can be replayed against Vertex (and vice versa) for unit tests since the cassette mocks the LLM. Reality: cassettes record specific provider-shape responses; replaying a Bedrock cassette through a Vertex client (or vice versa) may fail on response-shape mismatches.

**Mitigation**: cassettes are tagged with `provider:bedrock` or `provider:vertex` at record time; replay refuses to swap unless `compat:portable` is set; document the limit.

---

## Open questions that need answers before v1.0

### OQ1. Which Cognito feature tier do we provision?

We need M2M client-credentials (which requires Cognito's "App Client with secret"). Standard tier handles this; advanced tier features (custom email/SMS, MFA) aren't needed. Confirm pricing assumption (free at our scale) holds for production usage patterns.

### OQ2. Per-agent OTel sampling rate

Default 100% sampling is expensive in production. We need a sane default sampling rate (probably 100% in dev, 10% in prod) and an SLO that drops sampling if the OTel sink throttles.

### OQ3. Manifest update propagation on rolling deploys

When a manifest entry changes (e.g., agent A moves from `us-east-1` to `us-west-2`), how do we propagate to peers without redeploying every agent? Options: (a) accept staleness, (b) re-deploy all peers automatically on manifest change, (c) make manifest fetchable from a known URL at agent start. Need to pick before M2.

### OQ4. How do we handle Bedrock model deprecations gracefully?

Bedrock periodically retires models (Anthropic Claude 2 went, Claude 3.5 will eventually go). Our LLM aliases (`claude-opus-4-7` etc.) should remain stable; we need a model-alias resolution table maintained in cloudless that maps logical names to current best Bedrock model IDs, and we need a deprecation-warning flow when a user pins a soon-to-retire model.

### OQ5. AgentCore Memory custom strategy prompt token budget

AgentCore custom-strategy `AppendToPrompt` is capped at 30 KB. We need to document this clearly in `with_custom_strategy()` docs and provide a `validate_prompt()` helper.

### OQ6. GCP Agent Runtime cold-start under multi-day load

GCP just shipped multi-day execution at Cloud Next '26. Cold-start behavior on resumption from a 3-day-old checkpoint is not benchmarked. We should run a load test in M4 once long-running is wired.

### OQ7. Slack OAuth flow inside `ctx.request_approval(deliver_via=["slack"])`

Slack approval flow requires a Slack app, OAuth scope grants, and a callback to receive the approval/reject button click. We need to publish a `cloudless/slack-approval-app` template that customers install in their workspace.

### OQ8. Cost dashboard cross-cloud unification

Default Grafana dashboard pulls from CloudWatch Logs + Cloud Logging. Unifying two log streams in one panel requires a Grafana data source that can do log-aggregation across both. Verify Grafana 11+ supports this without a separate ETL.

### OQ9. Manifest signing for cross-cloud trust

A2A v1.2 supports digitally signed Agent Cards for cryptographic domain verification. Do we sign our manifest entries? Adds key management complexity. Defer to v1.5 unless a customer asks.

### OQ10. Test coverage SLA for the framework × cloud matrix

We claim Strands/AWS, Strands/GCP, ADK/AWS, ADK/GCP, LangGraph/AWS, LangGraph/GCP at v1.0. That's 6 combinations × 11 primitives = 66 integration-test cells. Confirm CI budget and test runtime; consider a "core path" CI (all 6 combos × LLM+Memory+A2A) on every PR vs. a "full matrix" CI nightly.

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
