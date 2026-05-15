# CLI reference

```bash
cloudless --help
```

## Subcommands

| Command         | Purpose                                                      |
|-----------------|--------------------------------------------------------------|
| `init`          | Scaffold a new project (`my-app/cloudless.yaml`, agents, tests) |
| `doctor`        | Run 12 preflight checks (creds, models, SDK versions)         |
| `dev`           | Run an agent locally on `:8080` with real LLM + in-memory ctx |
| `deploy`        | Ship an agent to AgentCore (AWS) or Agent Engine (GCP)        |
| `logs`          | Tail / filter deployed agent logs                              |
| `versions`      | List versions + endpoint aliases                              |
| `rollback`      | Swap an endpoint alias back to a prior version                |
| `eval`          | Run an eval dataset against an LLM                            |
| `cost`          | Roll up LLM cost from event JSONL or cassettes                |
| `security`      | Generate SBOM (`sbom`) or run pip-audit (`audit`)             |
| `cleanup`       | Namespace-scoped teardown of cloud resources                  |

## `cloudless dev`

```bash
cloudless dev <agent> [--host 127.0.0.1] [--port 8080] [--reload]
                       [--record CASSETTE | --replay CASSETTE]
cloudless dev --all                            # spawn every declared agent
```

`--reload` watches `src/agents/` for changes and respawns the dev server.

`--all` allocates a port per declared agent, writes a local manifest, and
spawns each agent so `ctx.peer(name).call(...)` works across them.

## `cloudless logs`

```bash
cloudless logs <agent> [--since 1h] [--follow]
                       [--trace-id ID] [--session-id ID] [--level WARN]
                       [--json]
```

Structlog field filtering: `--trace-id`, `--session-id`, `--level` operate
on the parsed log payload. `--json` emits one JSON object per line.

## `cloudless cleanup`

```bash
cloudless cleanup --prefix cloudless-spike- --aws --yes
cloudless cleanup --prefix kitchen-sink-    --gcp --gcp-project my-proj --yes
```

Always dry-run by default — `--yes` is required to actually delete.
Minimum prefix length is 8 chars to prevent accidental over-broad match.
