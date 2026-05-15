# Deploy to AWS

`cloudless deploy <agent>` ships an agent to AWS Bedrock AgentCore. The
adapter handles ECR, CodeBuild, IAM, Cognito (for A2A), and the
AgentCore runtime + endpoint wiring.

## Prerequisites

- AWS credentials configured (env vars, profile, or IAM role)
- Bedrock model access enabled in your account (Nova family is on by
  default in most regions; Anthropic requires the use-case form per F15)
- A free ECR repository name slot (`cloudless` will create
  `cloudless-<agent>-*`)

## What runs

```bash
cloudless deploy hello --region us-east-1
```

Behind the scenes:

1. **Discover** the agent class (walks `src/agents/*.py`)
2. **Materialize** a build directory under `.cloudless/build/<agent>/`
   including a Dockerfile with Python 3.12 (F16 mitigation)
3. **Bundle** the cloudless wheel into `wheelhouse/` (F17)
4. **Build** the container via CodeBuild, push to ECR
5. **Create or update** the AgentCore runtime
6. **Wire** the DEFAULT endpoint to the new version

Total time: typically 90–120 seconds.

## Inspect

```bash
cloudless versions hello              # list versions + endpoint pointers
cloudless logs hello --follow         # tail CloudWatch
cloudless rollback hello --to v17     # swap alias
```

## Cost & attribution

Deployed agents auto-emit per-call cost events that you can roll up:

```bash
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/<id>-DEFAULT \
  --output text | cloudless cost --by team
```

## Known hazards

- **F1**: Bedrock requires `us.` inference profile IDs. The `LLM` primitive resolves these automatically.
- **F5**: AWS CLI v2.0.x is too old for AgentCore. cloudless uses boto3 directly.
- **F15**: Anthropic streaming requires the use-case form. Nova Micro / Lite are safe by default.
- **F16**: Container base must be Python 3.12 (numpy 1.26 arm64 wheels).
- **F17**: Pre-PyPI: cloudless wheel must be bundled into the deploy artifact.

`cloudless doctor` checks all of these before deploy.
