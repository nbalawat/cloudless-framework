# `cloudless.yaml` schema

Project-wide config file. Validated by `cloudless.config.load()`.

## Top-level shape

```yaml
project: my-app                  # required, kebab-case
default_cloud: aws               # 'aws' or 'gcp'

clouds:
  aws:
    accounts:
      dev: {region: us-east-1}
      prod: {region: us-east-1}
  gcp:
    projects:
      dev: {project: my-dev-proj, region: us-central1}

environments:
  dev: {aws: dev}
  prod: {aws: prod}

service_catalog:
  llm:        {provider: bedrock, model: nova-micro}
  memory:     {strategy: semantic, retention_days: 90}
  embeddings: {provider: bedrock, model: titan-v2}

policies:
  cost_cap_usd_per_session: 5.0
  retries: {attempts: 3, backoff_seconds: 0.25}

agents:
  hello:
    cloud: aws                   # overrides default_cloud
    framework: langgraph         # 'langgraph' / 'strands' / 'adk' / 'maf'
    interfaces: [http, a2a]      # subset of {http, a2a, mcp, ag-ui}
    peers: [orders]              # other agents this one calls
    version: 0.1.0
```

## Reference resolution

Strings may contain `${secret:NAME}` and `${env:NAME}` references,
resolved at load time:

```yaml
service_catalog:
  llm:
    api_key: "${secret:openai_api_key}"
    region:  "${env:AWS_REGION:us-east-1}"
```

The default after the second colon is the literal fallback for missing
env vars. Secret references resolve via the `cloudless.Secrets` primitive
(LocalFileBackend in dev, Secrets Manager / Secret Manager in production).

## Validation errors

`cloudless config validate` runs the schema check and prints all errors
together (not fail-fast). Common errors:

- `project`: not kebab-case (`Bad_Name` → `bad-name`)
- `agents.<name>.interfaces`: unknown protocol
- `agents.<name>.peers`: references undefined peer
- `agents.<name>.framework`: unknown framework name
