"""
Spike 1 agent: minimal Strands agent exposed over A2A on AgentCore Runtime.

Validates the canonical AWS-side path that Q5 commits to:
  Strands → StrandsA2AExecutor → serve_a2a() → AgentCore Runtime (A2A mode)

The agent itself is intentionally tiny — Spike 1 is about observing the
agent card AgentCore publishes, not exercising sophisticated agent
behavior. Findings: SPIKE-FINDINGS.md F3 (Strands + a2a-sdk pin) and the
new findings this spike emits.
"""
from strands import Agent
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a


agent = Agent(
    name="cloudless-spike-01",
    description=(
        "Minimal Strands agent used by cloudless Spike 1 to validate "
        "AgentCore's A2A agent-card behavior. Replies with 'pong'."
    ),
    model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="Always reply with exactly the single word 'pong'.",
)


if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent))
