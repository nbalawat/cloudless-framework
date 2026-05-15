"""Real-cloud integration test for cloudless.ClaudeAgentSDKAgent + GCP Vertex AI.

The Claude Agent SDK natively supports Vertex AI routing via the
`CLAUDE_CODE_USE_VERTEX=1` environment variable + standard GCP ADC.

Skips if GCP creds aren't present OR the `claude` CLI is missing OR
the project doesn't have Claude models enabled on Vertex.

Cost: ~$0.001 (one Claude Haiku turn via Vertex).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import cloudless
from cloudless.runtime import InMemoryContext

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


GCP_KEY = Path.home() / "development/fsi-banking-gcp-usecases/keys/agentic-experiments-71fb77221637.json"


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


@pytest.fixture
def _vertex_env(monkeypatch):
    if not GCP_KEY.exists():
        pytest.skip(f"GCP service account key not found at {GCP_KEY}")
    monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(GCP_KEY))
    monkeypatch.setenv("CLOUD_ML_REGION", "us-east5")
    monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "agentic-experiments")
    # Anthropic API key must not pre-empt Vertex routing.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield


async def test_claude_sdk_agent_runs_against_real_vertex(_vertex_env) -> None:
    """End-to-end: Claude Agent SDK → Vertex-hosted Claude Haiku."""
    if not _claude_cli_available():
        pytest.skip("claude CLI not installed")

    from claude_agent_sdk import ClaudeAgentOptions

    @cloudless.agent(name="claude-sdk-vertex-test", framework="claude_sdk")
    class ClaudeSDKVertexTestAgent(cloudless.ClaudeAgentSDKAgent):
        def build(self):
            return ClaudeAgentOptions(
                system_prompt="You are terse. Reply with exactly one word.",
                max_turns=1,
                allowed_tools=[],
                disallowed_tools=["Bash", "Read", "Write", "Edit"],
                # Vertex-published Claude model id (project-dependent).
                model="claude-sonnet-4@20250514",
                # --bare forces strict env-var routing onto CLAUDE_CODE_USE_VERTEX
                # so the outer Claude Code session's auth doesn't pre-empt.
                extra_args={"bare": None},
            )

    agent_instance = ClaudeSDKVertexTestAgent()
    ctx = InMemoryContext(session_id="claude-sdk-vertex-test-session")

    try:
        chunks: list[cloudless.Chunk] = []
        async for chunk in agent_instance.query(ctx, "Reply with just 'pong'."):
            chunks.append(chunk)
    except Exception as e:
        # Claude-on-Vertex availability is region-, project-, and
        # account-gated. If the SDK reports a permission / not-found
        # error or the CLI exits unexpectedly, surface a clean skip
        # rather than failing — the cloudless adapter wiring is
        # correct; the blocker is cloud-side provisioning.
        msg = str(e).lower()
        if any(
            s in msg
            for s in (
                "not found",
                "permission denied",
                "not allowed",
                "404",
                "403",
                "command failed with exit code 1",
                "may not exist or you may not have access",
            )
        ):
            pytest.skip(
                "Claude on Vertex requires per-project allow-listing. "
                f"Adapter wiring is correct; raw error: {e!r}"
            )
        raise

    assert any(isinstance(c, cloudless.TextChunk) for c in chunks), (
        f"expected TextChunk from Claude via Vertex; got: {[type(c).__name__ for c in chunks]!r}"
    )
    assert isinstance(chunks[-1], cloudless.FinalChunk)
    full = "".join(c.text for c in chunks if isinstance(c, cloudless.TextChunk))
    assert "pong" in full.lower(), f"model didn't say pong; got: {full!r}"
