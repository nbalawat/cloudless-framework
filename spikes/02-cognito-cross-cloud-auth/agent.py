"""
Spike 2 agent: minimal Strands agent exposed over A2A on AgentCore Runtime.

Validates the canonical AWS-side path that Q5 commits to:
  Strands → StrandsA2AExecutor → serve_a2a() → AgentCore Runtime (A2A mode)

The agent itself is intentionally tiny — Spike 2 is about observing the
agent card AgentCore publishes, not exercising sophisticated agent
behavior. Findings: SPIKE-FINDINGS.md F3 (Strands + a2a-sdk pin) and the
new findings this spike emits.
"""
from strands import Agent
from strands.multiagent.a2a.executor import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a


agent = Agent(
    name="cloudless-spike-02",
    description=(
        "Minimal Strands agent used by cloudless Spike 2 to validate "
        "AgentCore's A2A agent-card behavior. Replies with 'pong'."
    ),
    # Nova Micro chosen over Claude Haiku 4.5 because Anthropic's Bedrock
    # gating treats `converse_stream` as a separate use case requiring its
    # own use-case form. Strands always uses streaming → must use a model
    # whose streaming API is unblocked. See SPIKE-FINDINGS.md F15.
    model="us.amazon.nova-micro-v1:0",
    system_prompt="Always reply with exactly the single word 'pong'.",
)


if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent))
