"""
Spike 4 agent: minimal picklable agent class for Gemini Enterprise Agent
Runtime (formerly Vertex AI Agent Engine).

Per Q4 GCP-side build strategy: nothing un-pickleable in __init__.
Live clients (google-genai) are instantiated in set_up(), which runs
once per worker after the platform deserializes the class.
"""
from __future__ import annotations

from typing import Iterator


class CloudlessSpike04Agent:
    """Minimal Gemini-backed agent."""

    def __init__(self, model_name: str = "gemini-2.5-flash",
                 system_prompt: str = "Always reply with exactly the single word 'pong'."):
        # Plain attributes only — must be pickleable.
        self.model_name = model_name
        self.system_prompt = system_prompt
        self._client = None  # initialized in set_up()

    def set_up(self) -> None:
        """Called once per worker after the class is deserialized on the runtime."""
        from google import genai
        self._client = genai.Client(vertexai=True)

    def query(self, prompt: str) -> dict:
        """Synchronous request/response. Returns a JSON-serializable dict."""
        if self._client is None:
            self.set_up()
        resp = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "system_instruction": self.system_prompt,
                # Give Gemini 2.5 enough budget for thinking + output (F2)
                "max_output_tokens": 200,
            },
        )
        return {"text": resp.text, "model": self.model_name}

    def stream_query(self, prompt: str) -> Iterator[dict]:
        """Streaming variant — yields dict chunks."""
        if self._client is None:
            self.set_up()
        for chunk in self._client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config={
                "system_instruction": self.system_prompt,
                "max_output_tokens": 200,
            },
        ):
            if chunk.text:
                yield {"text": chunk.text}

    def register_operations(self) -> dict:
        """Tells Agent Runtime which methods are callable. Optional but explicit."""
        return {
            "": ["query"],
            "stream": ["stream_query"],
        }
