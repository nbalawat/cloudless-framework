"""Real-cloud integration test for cloudless.ClaudeAgentSDKAgent.

Drives Anthropic's Claude Agent SDK (`claude-agent-sdk`) against the
real Anthropic API (or Bedrock if `CLAUDE_CODE_USE_BEDROCK=1`), asserts
that TextChunks come back and the stream terminates with a FinalChunk.

The Claude Agent SDK shells out to the `claude` CLI for transport;
this test skips if the CLI is missing OR if neither ANTHROPIC_API_KEY
nor AWS credentials are available.

Cost: ~$0.001 (one short Claude Haiku turn).
"""
from __future__ import annotations

import os
import shutil

import pytest

import cloudless
from cloudless.runtime import InMemoryContext

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def _auth_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    # Bedrock route — claude CLI can route through AWS Bedrock with
    # CLAUDE_CODE_USE_BEDROCK=1 + standard AWS creds.
    try:
        import boto3

        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


async def test_claude_sdk_agent_runs_against_real_anthropic() -> None:
    """End-to-end: real Anthropic API call through cloudless.ClaudeAgentSDKAgent."""
    if not _claude_cli_available():
        pytest.skip(
            "claude CLI not installed — install with `npm install -g @anthropic-ai/claude-cli`"
        )
    if not _auth_available():
        pytest.skip(
            "Neither ANTHROPIC_API_KEY nor AWS credentials are configured"
        )

    from claude_agent_sdk import ClaudeAgentOptions

    @cloudless.agent(name="claude-sdk-test", framework="claude_sdk")
    class ClaudeSDKTestAgent(cloudless.ClaudeAgentSDKAgent):
        def build(self):
            return ClaudeAgentOptions(
                system_prompt="You are a terse assistant. Reply with exactly one word.",
                max_turns=1,
                # No tools allowed — pure-text turn keeps the test cheap and
                # avoids requiring tool permissions / cwd setup.
                allowed_tools=[],
                disallowed_tools=["Bash", "Read", "Write", "Edit"],
                model="claude-haiku-4-5",
            )

    agent_instance = ClaudeSDKTestAgent()
    ctx = InMemoryContext(session_id="claude-sdk-test-session")

    chunks: list[cloudless.Chunk] = []
    async for chunk in agent_instance.query(ctx, "Reply with just 'pong'."):
        chunks.append(chunk)

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected at least one TextChunk from Claude; got: {[type(c).__name__ for c in chunks]!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk), (
        "stream must terminate with a FinalChunk"
    )

    full_text = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full_text.lower(), f"model didn't say pong; got: {full_text!r}"

    # Final state should carry usage from the ResultMessage.
    final = chunks[-1]
    assert isinstance(final, cloudless.FinalChunk)
    if final.state:
        # total_cost_usd may legitimately be 0.0 for Bedrock routing where
        # the SDK doesn't report a cost; we only assert it's present-or-None.
        assert "session_id" in final.state or "num_turns" in final.state, (
            f"FinalChunk.state missing expected ResultMessage fields: {final.state!r}"
        )
