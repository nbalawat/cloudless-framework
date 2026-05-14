# cloudless — Spike Findings

> Running ledger of empirical findings from Phase 0 validation spikes.
> Each finding includes: source spike, observed behavior, implication for cloudless design,
> and either a captured risk or an architectural revision.
> Last updated 2026-05-14.

## How this document is used

- Add a finding as soon as it's observed in a spike (don't wait for "completion").
- If a finding contradicts a locked decision (Q1-Q39), open an "Architectural revision required" note linking back to the relevant Qn.
- If a finding is operational (cost, perf, dep version), capture as a "Risk" or "Operational note."
- Each entry is dated; chronological order within a section.

---

## Phase 0 — Pre-spike discovery (2026-05-14)

### F1. Bedrock requires inference-profile IDs for newer Claude models *[AWS]*

**Spike:** `00-shared/aws_discovery.py`.

**Observed:** Calling `bedrock-runtime.Converse` with the raw model ID `anthropic.claude-3-5-haiku-20241022-v1:0` fails with:

> `ValidationException: Invocation of model ID … with on-demand throughput isn't supported. Retry your request with the ID or ARN of an inference profile that contains this model.`

The fix is to prefix with `us.` (e.g. `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Confirmed working for Haiku 4.5 and Sonnet 4.5 (5-token "pong" response, ~$0.0001 total).

**Implication for cloudless:** Our LLM adapter (Q9 service catalog, OQ4 model-alias resolution table) MUST default to inference-profile IDs on Bedrock, not raw model IDs. The `us.` / `eu.` / `apac.` prefix encodes the cross-region inference profile and is region-dependent. Users who write `cloudless.LLM(model="claude-haiku")` should get an inference-profile ID resolved by region.

**Action:** Bake "use inference profile by default" into the AWS LLM adapter in M1. Document the prefix-by-region mapping.

---

### F2. Gemini 2.5 extended thinking eats `max_output_tokens` *[GCP]*

**Spike:** `00-shared/gcp_discovery.py`.

**Observed:** Calling `google-genai` `models.generate_content` on `gemini-2.5-flash` with `max_output_tokens=10` returned empty `resp.text` because the model spent its entire output budget on internal thinking. The response had `thoughts_token_count=17` (yes, exceeded the 10-token cap internally) and `candidates_token_count=1` once we bumped to `max_output_tokens=50`.

**Implication for cloudless:** Gemini 2.5 models include extended thinking by default. `max_output_tokens` is shared between thinking and emission. Naive users who set a small `max_tokens` get silent empty responses.

**Action:**
- AWS-side and GCP-side LLM adapters must coordinate on a "reasoning vs emission" budget split.
- Either: (a) cloudless `LLM(max_tokens=N)` reserves a min N for output and adds thinking budget on top for Gemini, OR (b) thinking is disabled by default and the user opts in via `LLM(extended_thinking=True)`.
- Add a `cloudless.ReasoningChunk` (already in Q16 streaming taxonomy) emitter for Gemini thinking spans so users can see what's happening.

**Decision:** Option (b) — default thinking OFF; opt-in via param. Aligns with cost-conscious defaults from Q20.

---

### F3. Strands 1.39 ↔ a2a-sdk version compatibility *[Resolved by version pin]*

**Spike:** Pre-flight import check before Spike 1.

**Observed:** `from strands.multiagent.a2a.executor import StrandsA2AExecutor` fails on `a2a-sdk 1.0.x` with:

> `ImportError: cannot import name 'DataPart' from 'a2a.types'`

**Resolution (2026-05-14 same session):**

This is not protocol "drift" — it's a deliberate API surface change in a2a-sdk's v0.3 → v1.0 migration. a2a-sdk 1.x **does** include a v0.3 compatibility lane (`a2a.compat.v0_3.types` re-exports the proto types), but **does not** include the older `a2a.utils.new_agent_text_message` / `new_task` / `ServerError` helpers Strands depends on.

AgentCore's published agent cards advertise `protocolVersion: 0.3.0` — meaning AgentCore is itself running in v0.3 mode, not v1.0. So pinning cloudless's a2a-sdk to the **latest 0.3.x release (currently `0.3.26`)** is the architecturally correct choice for v0.x — it matches both AgentCore's actual spec and Strands' expected imports.

**Validated stack** (confirmed by composing `serve_a2a(StrandsA2AExecutor(Agent(...)))` cleanly):

```
a2a-sdk           >=0.3.9,<1.0.0     # resolves to 0.3.26 as of 2026-05-14
fastapi           >=0.115.0           # required by strands.multiagent.a2a.server.A2AServer
strands-agents    1.39.0
bedrock-agentcore 1.9.1
```

The bedrock-agentcore `build_a2a_app()` registers Starlette routes for both `/.well-known/agent-card.json` (v1.x location) and `/.well-known/agent.json` (v0.3 legacy location) — forward+backward compat built into the AgentCore SDK.

**Implication for cloudless:**

- **Q5 stands as-is**: Strands Tier-1 on AWS is validated.
- **v0.x cloudless pins `a2a-sdk<1.0`** in `pyproject.toml`. Documented in code comments.
- **v1.0 migration path**: when Strands ships a2a-sdk 1.x compat AND AgentCore moves its `protocolVersion` to ≥1.0, we revisit. Track via the compatibility matrix (Q27).
- **R1 reframes** in RISKS.md: the "AgentCore v0.3.0 protocol drift" risk is now an explicit "AgentCore is on v0.3 lane" capability statement.

**Action:** Spike venv `pyproject.toml` updated with the pin and a code-comment explanation. Use Strands native A2A in Spike 1 (validates the canonical AWS path). No upstream Strands issue needed — the breakage was a dependency-pinning question, not a Strands bug.

**Bonus context (user-provided 2026-05-14):** A2A Protocol Spec is at v1.0 under Linux Foundation governance; a2a-sdk 1.0 implements v1.0 with compat-mode for 0.3. AgentCore + Strands both track v0.3 today; will follow as the ecosystem moves to v1.0.

---

### F4. GCP SA missing `storage.objects.create` at project level *[Operational]*

**Spike:** `00-shared/gcp_discovery.py` `testIamPermissions`.

**Observed:** SA `fsi-gcp-factory-usecases@agentic-experiments.iam.gserviceaccount.com` has 10 of 11 project-level permissions needed for spikes. Missing: `storage.objects.create`.

**Implication:** Agent Engine deploy (Q4 GCP side) uses a staging bucket. If the SA can create the bucket but not put objects, deploy fails partway.

**Action:**
- Confirm bucket-level permissions before Spike 4 (Agent Engine deploy). Grant `roles/storage.objectAdmin` on a dedicated `cloudless-spikes-*` bucket if needed.
- Document in SETUP.md that the spike SA needs `roles/storage.objectAdmin` on the staging bucket, not just project-level powers.

---

### F5. AWS CLI v2.0.44 predates Bedrock/AgentCore *[Operational]*

**Spike:** Pre-flight discovery.

**Observed:** Locally installed `aws-cli/2.0.44` (from 2020) has no `bedrock`, `bedrock-agentcore-control`, or `bedrock-agentcore` commands. We worked around it by using `boto3 1.43.7` from the spike venv exclusively.

**Implication:** Contributor onboarding — `cloudless doctor` (Q9) should detect outdated AWS CLI versions. The spike venv approach is the right model for cloudless development (isolated, pinned).

**Action:** Add AWS CLI version check to `cloudless doctor`. Document minimum AWS CLI v2.15+ in contributor docs.

---

### F6. Bedrock account has 16 Claude variants visible; Opus 4.7 needs use-case form *[Operational]*

**Spike:** `00-shared/aws_discovery.py`.

**Observed:** Account 613112965612 in us-east-1 sees:
- `anthropic.claude-haiku-4-5-20251001-v1:0` (works via `us.` profile)
- `anthropic.claude-sonnet-4-5-20250929-v1:0` (works via `us.` profile)
- `anthropic.claude-sonnet-4-6` (not tested)
- `anthropic.claude-opus-4-6-v1` (not tested)
- `anthropic.claude-opus-4-7` (**fails** — requires Anthropic use-case form)
- 11 older variants

**Implication:** Opus-tier Claude models gated behind manual approval. Cloudless docs should mention this; the framework should surface a clear error ("you need to fill out Anthropic's use-case form for opus-4-7") rather than letting the user see Bedrock's cryptic error.

**Action:** `cloudless doctor` should call `bedrock:GetFoundationModelAvailability` for each model referenced in `cloudless.yaml` and warn if `agreementAvailability != AVAILABLE`. For Spike work, use Haiku 4.5 (cheap) and Sonnet 4.5 (capable). Opus 4.7 deferred until user fills the form.

---

### F7. AgentCore control plane is fully reachable in us-east-1 *[Confirming research dossier]*

**Spike:** `00-shared/aws_discovery.py`.

**Observed:** All 6 AgentCore control-plane Lists succeed: `ListAgentRuntimes`, `ListGateways`, `ListMemories`, `ListWorkloadIdentities`, `ListCodeInterpreters`, `ListBrowsers`. Account is "clean" — 0 resources of each type.

**Implication:** AgentCore is GA and usable in this account/region. Research dossier was correct.

**Action:** Proceed with deploy spikes. All resources created during spikes will be prefixed `cloudless-spike-*` for surgical teardown.

---

### F10. Spike 1 PASSED — AgentCore A2A agent card matches local card and confirms v0.3 lane *[Spike 1 — full deploy]*

**Spike:** Spike 1 deploy to real AgentCore Runtime, fetch agent card via SigV4.

**Deployed agent ARN:** `arn:aws:bedrock-agentcore:us-east-1:613112965612:runtime/cloudless_spike_01-0eCgMF2Kc1`

**Public agent card URL pattern (confirmed):**
```
https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<urlencoded-arn>/invocations/.well-known/agent-card.json
```

URL-encoding of the ARN follows the standard `urllib.parse.quote(..., safe="")` rules — `:` → `%3A`, `/` → `%2F`. Authentication is SigV4 against service `bedrock-agentcore`.

**Card observations:**

| Field | Locally served | Deployed served | Notes |
|---|---|---|---|
| `protocolVersion` | `"0.3.0"` | `"0.3.0"` | **No rewrite by AgentCore.** R1 fully confirmed: v0.3 lane. |
| `preferredTransport` | `"JSONRPC"` | `"JSONRPC"` | Preserved. |
| `url` | `http://localhost:9000/` | `https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<arn>/invocations` | **AgentCore rewrites the URL** — we don't need to inject it. |
| `name`, `description`, `version`, `skills`, `capabilities`, `defaultInputModes`, `defaultOutputModes` | (from agent metadata) | identical | preserved exactly |
| `securitySchemes` | not present | **not present** | AgentCore does NOT auto-derive from runtime auth (SigV4 by default). Cloudless gap. |

**Legacy `/.well-known/agent.json` path:**
- **Locally**: returned 200 with identical content + deprecation warning.
- **Deployed**: returns **404 `UnknownOperationException`**.

AgentCore's public routing **only exposes the v1.x agent-card URL**, even though the protocol it serves is v0.3. Strict v0.3 clients that hit `/.well-known/agent.json` will fail. Use `/.well-known/agent-card.json` exclusively across cloudless.

**Implications for cloudless:**

1. **Q12 manifest baking — `securitySchemes` is our responsibility.** Since both local serve_a2a AND AgentCore omit `securitySchemes`, our embedded runtime lib needs to inject the manifest-derived auth scheme (Cognito JWT per Q7) into the served card. Suggested pattern: a Starlette middleware that intercepts the agent-card response and merges `securitySchemes` from the baked manifest.

2. **`url` field is AgentCore-owned.** Cloudless manifest should NOT pre-bake the URL; let AgentCore generate it. We read it back from `bedrock-agentcore-control:GetAgentRuntimeEndpoint` post-deploy and include it in the cross-agent manifest.

3. **AgentCore-published cards are reachable cross-cloud** (public URL + SigV4). Once Cognito JWT inbound auth is enabled (Q7), GCP-side peers can fetch the card with a Bearer token.

4. **Use `/.well-known/agent-card.json` only** — never the legacy path.

**Spike 1 cost:** ~$0.01 (CodeBuild 32s ≈ $0.005, ECR minimal, AgentCore idle, IAM/S3 free tier).

**Spike 1 status: ✅ PASS — R1 resolved, manifest baking pattern identified.**

---

### F9. Local Strands+A2A+AgentCore stack composes and runs end-to-end *[Spike 1 — pre-deploy validation]*

**Spike:** Spike 1, local validation only (no cloud deploy yet).

**Observed:** Running `agent.py` (Strands Agent + StrandsA2AExecutor + serve_a2a) on the spike venv with the pinned versions binds uvicorn on `127.0.0.1:9000` and exposes:

| Endpoint | Status | Notes |
|---|---|---|
| `GET /ping` | 200 | `{"status":"Healthy","time_of_last_update":<unix>}` — matches AgentCore HTTP contract |
| `GET /.well-known/agent-card.json` | 200 | A2A v0.3 agent card (full content below) |
| `GET /.well-known/agent.json` | 200 | Identical content + server-side deprecation warning; SDK supports both for transition |

**Auto-generated agent card content:**

```json
{
  "name": "cloudless-spike-01",
  "version": "0.1.0",
  "description": "Minimal Strands agent used by cloudless Spike 1...",
  "url": "http://localhost:9000/",
  "protocolVersion": "0.3.0",
  "preferredTransport": "JSONRPC",
  "capabilities": {"streaming": true},
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  "skills": [{"id": "main", "name": "cloudless-spike-01", "tags": ["main"], "description": "..."}]
}
```

**Significant absences in the auto-built card:**
- **`securitySchemes`** — NOT declared. Clients wanting to call this agent have no in-card hint about how to authenticate. Strands generates the card from agent metadata but doesn't know about transport-layer auth (Cognito JWT, SigV4, etc.).
- **`provider`, `documentationUrl`, `iconUrl`** — none set; all optional per spec.

**Implication for cloudless (Q12 manifest baking):** When cloudless bakes the agent manifest into a deployed agent's image, it must **inject `securitySchemes` into the agent card** to advertise the chosen auth scheme (Cognito JWT in our default — Q7). Strands' auto-generated card alone is insufficient for production A2A.

**Action:**
- Add a `card_decorator` pattern in cloudless's embedded runtime lib that merges manifest-derived `securitySchemes` into the served card before each `/.well-known/agent-card.json` response.
- Document the gap in `docs/ARCHITECTURE.md` §3 (cross-cloud collaboration).
- File improvement issue against Strands to optionally accept `security_schemes` in `Agent(...)` constructor.

**Cost:** $0 — local validation only. Validates the deploy artifact before paying for cloud resources.

---

### F8. Gemini Enterprise Agent Runtime (`reasoningEngines`) reachable in us-central1 *[Confirming research dossier]*

**Spike:** `00-shared/gcp_discovery.py`.

**Observed:** `agent_engines.list()` succeeds, returning 0 engines. Confirms post-rebrand naming preserves the `reasoningEngines` API resource — Q4 GCP-side deployment plan is unaffected by the rebrand. SDK is `google-cloud-aiplatform 1.152.0`, `google-genai 1.75.0`.

**Implication:** GCP-side deploy path is open. New primitives (Agent Identity, Agent Gateway, Agent Sandbox) need additional spikes to verify their APIs.

**Action:** Spike 4 (GCP deploy) proceeds against `agent_engines.create()`. New-primitive spikes added if time/budget permits in Phase 0.

---

## Findings index by category

### Architectural revisions (require updating ARCHITECTURE.md / DECISIONS.md)
- ~F3 (Strands A2A drift) — qualifies Q5 framework rollout~ — **RESOLVED via a2a-sdk version pin; Q5 stands.**

### Risks (require updating RISKS.md)
- ~F3 → new R11 (Strands ↔ a2a-sdk drift)~ — **RESOLVED; R11 closed, R1 reframed.**
- F4 (GCP storage.objects.create) — operational risk for GCP Agent Engine deploy

### Operational defaults (capture in implementation docs)
- F1 (Bedrock inference profiles) → implementation default in M1
- F2 (Gemini thinking budget) → LLM adapter default off; opt-in param
- F5 (AWS CLI minimum) → `cloudless doctor` v1 check
- F6 (Anthropic use-case form for Opus 4.7) → `cloudless doctor` v1 check

### Confirmations (no change needed)
- F7 (AgentCore reachability in us-east-1)
- F8 (`reasoningEngines` API preserved post-rebrand)
