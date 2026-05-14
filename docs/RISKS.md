# cloudless — Risks and Open Questions

> What we know we don't know. What could break our assumptions. What needs to be validated before we commit further.
> Last updated 2026-05-14 (Q37 closed the 10 OQs originally listed here).

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
