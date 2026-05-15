# Security policy

## Reporting a vulnerability

If you believe you have found a security issue in cloudless, please **do not**
file a public GitHub issue. Email **naveen.balawat@gmail.com** with:

- A clear description of the vulnerability and its impact
- Steps to reproduce (or a minimal proof-of-concept)
- The affected version (run `cloudless --version`)
- Your assessment of severity (informational / low / medium / high / critical)

We will acknowledge within 3 business days and aim to publish a fix or
mitigation within 14 days for medium/high/critical issues.

## Scope

In scope:

- The `cloudless` Python package (this repository)
- The deploy adapters in `src/cloudless/adapters/aws/` and `src/cloudless/adapters/gcp/`
- The CLI commands in `src/cloudless/cli/`
- The embedded runtime in `src/cloudless/runtime/`

Out of scope:

- Vulnerabilities in the underlying cloud services (AWS Bedrock AgentCore,
  GCP Vertex AI). Report those directly to AWS Security / Google VRP.
- Vulnerabilities in transitive dependencies (boto3, google-genai, langgraph,
  etc.). Report upstream; we will track and update.
- Misconfiguration on the *user's* AWS/GCP account (IAM roles too broad, etc.).
  cloudless cannot prevent users from over-permissioning their own accounts.

## Threat model summary

cloudless is a **framework for deploying agents the user owns**. The framework
itself runs in the user's cloud account; it does not phone home, does not have
a control plane, and does not store user data outside the user's account.

Key trust boundaries:

1. **CLI → cloud APIs**: cloudless makes signed AWS / GCP API calls using the
   user's local credentials. It never persists or transmits those credentials.

2. **Deployed agent → A2A peer**: peer-to-peer calls are authenticated via
   Cognito M2M JWTs (audience-checked) over TLS. The cloudless runtime mints
   tokens at call time; it does not pre-mint or share tokens across peers.

3. **Agent → LLM**: every LLM call carries the user's session context. The
   cloudless runtime never injects content into prompts beyond what the user's
   policy decorators specify.

4. **Audit log**: policy-driven decisions (allow/transform/block) are recorded
   to the configured `AuditSink` chain with SHA-256 payload prefixes (not raw
   content). Sinks default to structlog at WARN; persistent sinks (FileSink)
   are user-opt-in.

5. **Secrets**: cloudless does not store secrets. The Secrets primitive
   wraps AWS Secrets Manager and GCP Secret Manager — credentials are fetched
   at runtime, not baked into deploy artifacts.

## Hardening checklist

For production deploys:

- [ ] Set a `cost_cap_usd_per_session` in `cloudless.yaml`
- [ ] Configure a Bedrock Guardrail and pass `guardrail_id=...` to `cloudless.LLM`
- [ ] Add a `FileSink` for the audit log (immutable bucket recommended)
- [ ] Pin `cloudless` to an exact version in your `pyproject.toml`
- [ ] Run `cloudless security audit` (pip-audit) in CI
- [ ] Run `cloudless security sbom -o sbom.json` and archive with each release
- [ ] Verify deployed agents have the principle-of-least-privilege IAM role
- [ ] Restrict A2A audiences in the manifest to your owned domains

## Known limitations

- **Pre-PyPI distribution**: until cloudless is published, deploy artifacts
  bundle a built wheel via the `wheelhouse/` mechanism (F17). This means each
  deploy carries a copy of the package — keep deploys current.
- **`bedrock-agentcore` SDK**: optional dependency for AWS deploys. We pin
  against `>=1.9.0`. Upstream is pre-1.0 and may break.
- **A2A protocol v0.3 lane**: cloudless pins `a2a-sdk>=0.3.9,<1.0.0`. The 1.x
  line of the SDK is a breaking change we have not migrated to (F3).
