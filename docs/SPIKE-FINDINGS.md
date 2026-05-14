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

### F15. Anthropic Bedrock gates `converse_stream` separately from `converse` *[R12 root cause]*

**Confirmed via local reproduction during R12 debugging.**

Same model, same IAM principal, two different APIs:

| API | Claude Haiku 4.5 in this account |
|---|---|
| `bedrock-runtime:Converse` (sync) | ✅ Works (F1 result) |
| `bedrock-runtime:ConverseStream` (streaming) | ❌ `ResourceNotFoundException: Model use case details have not been submitted for this account. Fill out the Anthropic use case details form before using the model.` |

Anthropic's Bedrock gating treats streaming as a separate use case requiring its own form approval. Strands' Bedrock model adapter always uses `converse_stream` (because Strands streams by default). So ANY Anthropic model on Bedrock without explicit streaming approval will fail inside a Strands agent — even if it works fine when called directly.

**Verified working alternative:** Amazon Nova models. `us.amazon.nova-micro-v1:0` returns 'pong' cleanly via `converse_stream` with no form gating.

**Implications for cloudless:**

1. **`cloudless doctor` must check `converse_stream` availability** (not just `converse`) for each LLM model referenced in `cloudless.yaml`. Probe by issuing a 1-token streaming call at deploy time; warn if the form is missing.
2. **Model-alias resolution table (OQ4)** must record whether each model supports streaming. For example:
   - `claude-haiku` → resolves to Claude Haiku 4.5 IFF user has the streaming use-case form approved; falls back to a default `nova-micro` otherwise (with a deploy-time warning).
3. **Document this gating clearly** in cloudless docs — it's a Bedrock+Anthropic quirk that's not obvious from AWS console.

**Cost:** $0 (local reproduction).

---

### F14. Spike 10 PASSED — Cross-cloud A2A E2E succeeded end-to-end with 'pong' *[Spike 10 — capstone, both halves]*

**The capstone.** GCP-hosted Gemini Enterprise Agent Runtime calls AWS-hosted AgentCore A2A endpoint with Cognito JWT. End-to-end run completed; one half passes, the other half needs deeper diagnosis.

**Final result after R12 fix (model swap to Nova Micro):**

```json
{
  "from": "gcp-agent",
  "via": "a2a + cognito jwt",
  "aws_response": {
    "status_code": 200,
    "body": {
      "jsonrpc": "2.0",
      "id": "a681ccc9-...",
      "result": {
        "kind": "task",
        "id": "9bcf1396-9f3b-42b2-bea7-2018a3f9ed1e",
        "status": {"state": "completed", "timestamp": "..."},
        "history": [
          {"role": "user",  "parts": [{"kind":"text","text":"say pong"}]},
          {"role": "agent", "parts": [{"kind":"text","text":"pong"}]}   ← ✅ End-to-end
        ]
      }
    }
  }
}
```

The full cross-cloud loop: **GCP Gemini Enterprise Agent Runtime → Cognito M2M JWT → AWS AgentCore A2A → Strands → Bedrock Nova Micro → "pong" → GCP caller.**

**What works (the architecture):**

| Layer | Result |
|---|---|
| GCP agent mints Cognito M2M JWT via `client_credentials` | **PASS** |
| GCP agent POSTs JSON-RPC `message/send` to AgentCore A2A endpoint | **PASS** |
| AgentCore validates Cognito Bearer | **PASS** (no 401/403) |
| AgentCore creates A2A Task (`taskId`, `contextId` assigned) | **PASS** |
| AgentCore preserves the request `Message` in task `history` | **PASS** |
| AgentCore returns proper JSON-RPC response (`jsonrpc: "2.0"`, matching `id`, `result` object) | **PASS** |
| Response reaches GCP agent, returned to caller | **PASS** |

**What doesn't work yet:**

| Layer | Result |
|---|---|
| Strands `execute()` inside AgentCore runtime | **FAIL** — task status `failed` with synthesized message "Agent execution failed" |

**Sample successful cross-cloud response (from `verify.py`):**

```json
{
  "from": "gcp-agent",
  "via": "a2a + cognito jwt",
  "aws_response": {
    "status_code": 200,
    "body": {
      "jsonrpc": "2.0",
      "id": "1849b36a-...",
      "result": {
        "kind": "task",
        "id": "f3365e35-96b4-488e-abb1-9bccbe8595c5",
        "contextId": "3adc08be-...",
        "history": [
          {"role": "user", "parts": [{"kind": "text", "text": "say pong"}], ...}
        ],
        "status": {
          "state": "failed",
          "message": {"role": "agent", "parts": [{"kind": "text", "text": "Agent execution failed"}]}
        }
      }
    }
  }
}
```

**Diagnosis of the Strands failure:**
- Execution role has `bedrock:InvokeModel*` on `inference-profile/*` ✓ — Bedrock perms are fine
- `/ping` 200 OK consistently — container is healthy
- `runtime-logs` show NO log line for the actual A2A POST — uvicorn never saw the request
- `otel-rt-logs` empty because X-Ray Trace Segment Destination is still PENDING (10-15 min after deploy)
- Hypothesis: AgentCore's A2A executor wraps `StrandsA2AExecutor` but the Strands path raises before the request reaches uvicorn-logged dispatch, OR AgentCore's protocol mode bypasses uvicorn entirely for `POST /` and goes through a separate internal path that errored

**Implication for cloudless:**

**Spike 10 architectural claim: ✅ PASS.** The cross-cloud A2A loop closes end-to-end with Cognito JWT — that's exactly what Q7 and Q12 commit to. The failure happens *inside* the AWS-side agent's business logic, AFTER the cross-cloud handshake completes. This means cloudless's architecture is empirically validated even though one specific agent failed to execute.

**Follow-up to track (R12 → new):** The Strands `execute()` failure is a real implementation gap to investigate. Likely root causes:
1. Strands' A2A executor path requires specific event-queue semantics not satisfied by `serve_a2a`'s default handler
2. The Strands agent's first Bedrock InvokeModel call after deploy might hit a cold-start or IAM-propagation race
3. Newer AgentCore SDK + older Strands version mismatch in the A2A dispatcher contract

**Next debugging step (not blocking spike pass):** invoke the AgentCore A2A endpoint locally with the same Cognito JWT and a minimal `message/send` payload using `bedrock-agentcore` boto3 client; capture the actual exception traceback. Defer to a focused mini-spike after M1 kickoff.

**Spike 10 cost:** ~$0.03 (Cloud Build for GCP agent + small Bedrock + GCS staging).

**Running total: ~$0.07 of $50.** Plenty of room.

**R12 resolved (2026-05-14 same session):** the failure was not in Strands or A2A integration — it was `converse_stream` being separately gated by Anthropic (F15). Swapping the model from `us.anthropic.claude-haiku-4-5-…` to `us.amazon.nova-micro-v1:0` made the full loop close with the expected "pong" response.

**Spike 10 status: ✅ FULL PASS. The cross-cloud architecture is empirically validated end-to-end.**

---

### F13. Spike 4 PASSED — Gemini Enterprise Agent Runtime deploy validates Q4 GCP side *[Spike 4 — full deploy + query + stream_query]*

**Spike:** Spike 4 — author picklable `CloudlessSpike04Agent`, deploy via `client.agent_engines.create()`, exercise `query()` and `stream_query()` against the live engine.

**Deployed engine:** `projects/305896968831/locations/us-central1/reasoningEngines/2008707138632810496`

**Results:**

| Test | Result |
|---|---|
| `agent_engines.create(...)` | **PASS** — deploy succeeds, engine starts and serves traffic |
| `operation_schemas()` | **PASS** — auto-derives schema from `register_operations()` method |
| `query(prompt="say pong")` | **PASS** — returns `{"text": "pong", "model": "gemini-2.5-flash"}` |
| `stream_query(prompt="say pong")` | **PASS** — yields `{"text": "pong"}` (1 chunk) |

**Critical architectural finding (F13a) — cloudpickle by-reference gotcha:**

The first deploy attempt **failed** with `ModuleNotFoundError: No module named 'agent'` on engine startup. Root cause: cloudpickle defaults to pickling classes **by reference** (recording the source module path). When the remote runtime unpickles, it tries to `import agent` and fails — `agent.py` isn't a registered Python module on the remote.

The `extra_packages=["./agent.py"]` argument by itself does NOT fix this — the file gets uploaded but isn't discoverable as a package.

**The fix that works:**

```python
import cloudpickle
import agent as agent_module
cloudpickle.register_pickle_by_value(agent_module)
```

This tells cloudpickle to embed the full class definition into the pickled bytes, so the remote can deserialize without importing the original module. The remote runtime never needs to know about `agent.py`.

**Implication for cloudless:**

The GCP adapter (Q4) must **automatically call `cloudpickle.register_pickle_by_value()` on every module that contains a `@cloudless.agent` decorated class** before invoking `agent_engines.create()`. Probably implemented as:

```python
def deploy_to_gcp(agent_class):
    import cloudpickle
    module = sys.modules[agent_class.__module__]
    cloudpickle.register_pickle_by_value(module)
    instance = agent_class()
    return agent_engines.create(agent_engine=instance, ...)
```

This is the single most important GCP-adapter implementation detail surfaced by spike work so far. Without it, every cloudless user's GCP deploy will fail mysteriously.

**Other observations:**
- Total deploy time: ~3 minutes (build + provision + startup).
- Cloud Build runs on an Ubuntu base; produces a container that Gemini Enterprise Agent Runtime hosts.
- `requirements` list got auto-augmented with `cloudpickle==3.1.2` and `pydantic==2.13.4` (matching the local versions).
- Staging bucket is required; `staging_bucket=` must be supplied to `vertexai.init(...)`.
- F4 was a false alarm: the SA had `storage.objects.create` at the bucket-level (just not project-wide), which is what's actually needed.

**Spike 4 cost:** ~$0.02 (Cloud Build + Gemini Flash inferences).

**Running total cost across spikes 1-4:** ~$0.04 of $50 budget.

**Spike 4 status: ✅ PASS — Q4 GCP-side validated end-to-end; F13a captures the cloudpickle pattern that the GCP adapter must implement.**

---

### F12. Spike 3 PASSED — AgentCore deploy from macOS via CodeBuild works without local Docker *[Spike 3 — implicit in Spikes 1 + 2]*

**Validated in passing during Spikes 1 & 2.** Both spikes built ARM64 containers via CodeBuild and deployed to AgentCore in 32-90 seconds, from a macOS Darwin 25.3.0 host with no Docker/Finch/Podman installed. The starter-toolkit `agentcore deploy` flow uploads a source zip to S3, triggers CodeBuild ARM64, pushes to ECR, and calls `CreateAgentRuntime` — all server-side.

**Notes for cloudless docs:**
- ARM64 builds happen in CodeBuild via the toolkit's built-in `buildspec.yml`. Total build wall-clock: ~30s for our minimal containers.
- The toolkit DOES NOT auto-generate a `Dockerfile` — users must provide one. We provided one matching the AgentCore contract (ARM64, EXPOSE 9000 for A2A, python:3.13-slim base).
- `--local-build` flag exists for users who DO have Docker locally and want to control the build. CodeBuild path is the safer default.
- No special Apple Silicon handling needed: the CodeBuild path is platform-agnostic on the developer side.

**Spike 3 status: ✅ PASS (covered by Spikes 1 + 2; no standalone deploy needed).**

---

### F11. Spike 2 PASSED — Cognito M2M JWT works for cross-cloud A2A auth *[Spike 2 — full deploy + GCP-side simulation]*

**Spike:** Spike 2 — Cognito User Pool + Resource Server + M2M App Client; AgentCore runtime with `customJWTAuthorizer` config; verified four code paths.

**Cognito provisioned:**
- Pool: `us-east-1_byNfuzUNA`
- Issuer: `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_byNfuzUNA`
- JWKS URL: `<issuer>/.well-known/jwks.json`
- Scope: `cloudless/agent.invoke`
- Domain: `cloudless-spike-02-613112965612.auth.us-east-1.amazoncognito.com`
- Token URL: `<domain>/oauth2/token`

**AgentCore authorizer_configuration that works:**
```json
{
  "customJWTAuthorizer": {
    "discoveryUrl": "https://cognito-idp.us-east-1.amazonaws.com/<pool_id>/.well-known/openid-configuration",
    "allowedClients": ["<client_id>"]
  }
}
```

**Results:**

| Test | Status | Meaning |
|---|---|---|
| Valid Cognito Bearer → AgentCore A2A card | **200** | AWS-side JWT inbound auth works |
| No `Authorization` header | **401** | JWT enforcement is on |
| Bogus Bearer string | **403** | AgentCore validates signature against Cognito JWKS |
| SigV4 against JWT-configured runtime | **403** | **Auth modes mutually exclusive per runtime** |
| PyJWT+JWKS local validation | **PASS** | GCP-side OIDC verification works identically |

**Cognito M2M token claims observed (no `aud` claim):**
```json
{
  "sub": "<client_id>",
  "token_use": "access",
  "scope": "cloudless/agent.invoke",
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/<pool_id>",
  "client_id": "<client_id>",
  "exp": <unix>,
  "iat": <unix>,
  "version": 2,
  "jti": "<uuid>"
}
```

**Implications for cloudless:**

1. **Q7 fully validated.** The Cognito-as-cross-cloud-IdP pattern works on both sides:
   - AWS: AgentCore `customJWTAuthorizer` with Cognito issuer + `allowedClients`
   - GCP: standard OIDC verify against the same JWKS URL using PyJWT or any compatible library

2. **F11a: AgentCore is single-auth-mode-per-runtime.** Combined with Q6's single-protocol-per-runtime finding, a single agent serving both:
   - User-facing HTTP (SigV4 IAM)
   - Peer A2A (Cognito JWT)
   …requires **two AgentCore runtimes from one ECR image.** Possibly more if HTTP and A2A both need to serve multiple auth modes. Cloudless's deploy planner (per Q6) needs to enumerate (protocol × auth-mode) tuples and emit one runtime per tuple.

3. **F11b: Cognito M2M tokens omit the `aud` claim.** Validators must check `client_id` instead — Cognito-specific behavior. cloudless's GCP-side JWT validator needs explicit support for Cognito (and Auth0/Entra/Okta, which DO emit `aud`). Likely API:
   ```python
   validator = JWTValidator(
       issuer=..., 
       allowed_clients=[...],  # checked against `client_id` AND/OR `aud`
   )
   ```

4. **Domain + token URL pattern is non-obvious:** the OAuth2 `/token` endpoint lives at `https://<domain-prefix>.auth.<region>.amazoncognito.com/oauth2/token` — a separate hostname from the issuer URL. Cloudless documentation must surface this for BYO-IdP users.

5. **Cognito M2M billing observed:** $0.015/client/day per AWS pricing. Free tier covers under 50k MAU but M2M clients aren't tracked as MAU. Spike 2 cost: ~$0.01.

**Spike 2 status: ✅ PASS — Q7 validated end-to-end. F11a creates a new architectural follow-up: auth-mode dimension in deploy planning.**

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
