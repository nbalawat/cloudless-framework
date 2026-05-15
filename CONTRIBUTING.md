# Contributing to cloudless

Thanks for considering a contribution. cloudless is still pre-1.0, so we
move fast and prefer small, well-scoped PRs over large redesigns.

## Quick start

```bash
git clone https://github.com/nbalawat/cloudless-framework && cd cloudless
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,langgraph,strands,aws,gcp]"

# Run the fast suite (unit tests, no cloud calls)
pytest tests/unit -q

# Run the cheap real-cloud suite (~$0.005, needs AWS+GCP creds)
pytest tests/integration -m integration -q

# Type-check and lint
mypy src/cloudless --strict
ruff check src tests
```

## Repository layout

```
src/cloudless/
  __init__.py            ← user-facing surface (only export from here)
  agent.py               ← Agent base + @cloudless.agent
  chunks.py              ← Chunk taxonomy (Q16)
  exceptions.py          ← Q21 typed exception hierarchy
  catalog/               ← Service-catalog primitives (LLM, Memory, ...)
  adapters/aws/          ← AWS-side backends + AgentCore deploy
  adapters/gcp/          ← GCP-side backends + Vertex Agent Engine deploy
  adapters/frameworks/   ← LangGraph, Strands, ADK bases
  cli/                   ← Subcommand modules (init, dev, deploy, ...)
  runtime/               ← Embedded library (tracing, policy, peer, tasks)
  testing/               ← Cassettes + test helpers
  eval/                  ← Eval framework

tests/unit/              ← Pure-Python, no cloud
tests/integration/       ← Real AWS/GCP — marked @pytest.mark.integration

docs/                    ← ARCHITECTURE, DECISIONS, ROADMAP, RISKS, etc.
examples/                ← Runnable example projects
```

## Test methodology

**No mocks for cloud primitives.** Every catalog primitive has a real-cloud
integration test under `tests/integration/`. The unit suite is for
pure-Python types, dispatch, and validation only.

| Tier | Marker | Cost | Speed |
|---|---|---|---|
| Unit | (default) | $0 | <1s each |
| Cheap integration | `@pytest.mark.integration` | ~$0.0005 each | <10s each |
| Expensive integration | gated by `CLOUDLESS_RUN_DEPLOY_TESTS=1` | ~$0.05 each | ~3 min each |

When adding a new primitive or backend, you must ship at least one
integration test that exercises it against real cloud.

## Code conventions

- **No emojis in source files** unless explicitly requested.
- **Comments**: write only when the *why* is non-obvious. Don't restate what
  the code does.
- **Errors at boundaries**: validate user input at the user-facing surface;
  trust internal calls. Don't add defensive code for impossible scenarios.
- **No new abstractions** unless a real second caller exists. Three similar
  lines beats a premature helper.
- **No backwards-compat shims** for unreleased APIs. Just change the code.
- **Use the typed exception hierarchy.** `TransientError` vs `PermanentError`
  is load-bearing for the retry middleware.
- **Lazy cloud imports.** Adapters import `boto3` / `google.cloud.*` inside
  the constructor or method, never at module top level. Keeps `cloudless`
  importable without the cloud extras.

## Adding a new SPIKE-finding

When you hit a real-cloud gotcha (mismatched API, undocumented behaviour,
version drift), capture it in `docs/SPIKE-FINDINGS.md` with:

- One-line summary
- Reproducer
- Root cause
- Mitigation in cloudless code
- Reference to the test that asserts the mitigation

The findings list (F1–F21+) is one of the project's load-bearing artifacts —
keep it current.

## Updating DECISIONS.md

When a PR locks in a new architectural decision (Q40, Q41…), append the
ADR-style entry to `docs/DECISIONS.md`. Use the existing format:

```
### Q42: Title (date)
Decision: ...
Rationale: ...
Implications: ...
```

## Pull request checklist

- [ ] Tests added or updated for the change (`pytest tests/unit`)
- [ ] Real-cloud test added if the change touches an adapter (`pytest -m integration`)
- [ ] `mypy --strict src/cloudless` clean
- [ ] `ruff check src tests` clean
- [ ] `CHANGELOG.md` updated under the unreleased section
- [ ] If user-facing API changed: `docs/CERTIFICATION.md` reflects new surface
- [ ] If a real-cloud gotcha was discovered: `docs/SPIKE-FINDINGS.md` entry added
- [ ] Commits are well-scoped; squash before merge if requested

## Reporting security issues

See [`SECURITY.md`](./SECURITY.md). Do not open a public issue for
suspected vulnerabilities.

## Code of conduct

Be excellent to each other. Disagreements about technical direction are
expected; personal attacks aren't. Project maintainers reserve the right to
ban contributors who don't follow this norm.

## License

By contributing, you agree that your contributions will be licensed under
the project's Apache 2.0 license.
