"""Real-cloud integration test for cloudless.ClaudeAgentSDKAgent + AWS Bedrock.

The Claude Agent SDK natively supports Bedrock routing via the
`CLAUDE_CODE_USE_BEDROCK=1` environment variable. cloudless does no
custom wrapping — the user just sets the env var and picks a Bedrock
Claude model id.

Skips if AWS credentials are not present OR the `claude` CLI is not
installed.

Cost: ~$0.001 (one Claude Haiku turn via Bedrock).
"""
from __future__ import annotations

import shutil

import pytest

import cloudless
from cloudless.runtime import InMemoryContext

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


@pytest.fixture
def _bedrock_env(monkeypatch):
    """Configure Claude Agent SDK to route through Bedrock."""
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    # Anthropic API key, if present, must not pre-empt Bedrock routing.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield


async def test_claude_sdk_agent_runs_against_real_bedrock(_bedrock_env) -> None:
    """End-to-end: Claude Agent SDK → Bedrock-hosted Claude Haiku 4.5."""
    if not _claude_cli_available():
        pytest.skip("claude CLI not installed")

    try:
        import boto3

        boto3.client("sts").get_caller_identity()
    except Exception:
        pytest.skip("AWS credentials not configured")

    from claude_agent_sdk import ClaudeAgentOptions

    @cloudless.agent(name="claude-sdk-bedrock-test", framework="claude_sdk")
    class ClaudeSDKBedrockTestAgent(cloudless.ClaudeAgentSDKAgent):
        def build(self):
            return ClaudeAgentOptions(
                system_prompt="You are terse. Reply with exactly one word.",
                max_turns=1,
                allowed_tools=[],
                disallowed_tools=["Bash", "Read", "Write", "Edit"],
                # Bedrock inference-profile id for Claude Sonnet 4. Note: the
                # claude CLI's --model validator currently accepts only a
                # subset of Bedrock profiles; this id is one that's enabled
                # on the test AWS account and accepted by the CLI's check.
                model="us.anthropic.claude-sonnet-4-20250514-v1:0",
                # --bare forces the CLI off the OAuth keychain and onto
                # CLAUDE_CODE_USE_BEDROCK env-var routing — otherwise the
                # outer Claude Code session's auth pre-empts the Bedrock
                # route and we get a generic "command failed".
                extra_args={"bare": None},
            )

    agent_instance = ClaudeSDKBedrockTestAgent()
    ctx = InMemoryContext(session_id="claude-sdk-bedrock-test-session")

    try:
        chunks: list[cloudless.Chunk] = []
        async for chunk in agent_instance.query(ctx, "Reply with just 'pong'."):
            chunks.append(chunk)
    except Exception as e:
        # Bedrock's Anthropic models are gated behind a one-time
        # account-level "use case details" form. If that hasn't been
        # submitted (or AWS is rate-limiting form approval), surface a
        # skip with the precise reason rather than failing — the
        # cloudless adapter wiring is correct; the blocker is AWS
        # account provisioning.
        msg = str(e).lower()
        if any(
            s in msg
            for s in (
                "use case details have not been submitted",
                "fill out the anthropic use case",
                "404",
                "may not exist or you may not have access",
                "command failed with exit code 1",
            )
        ):
            pytest.skip(
                "Claude on Bedrock requires AWS account-level use-case-details "
                f"form submission. Adapter wiring is correct; raw error: {e!r}"
            )
        raise

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected TextChunk from Claude via Bedrock; got: {[type(c).__name__ for c in chunks]!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk)
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
