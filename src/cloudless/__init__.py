"""cloudless — cloud-agnostic agentic AI framework.

Write your agent once. Ship it to any cloud.

This package exposes the user-facing surface area. The major types are
imported eagerly so users can `from cloudless import Agent, TextChunk`
without diving into submodules.
"""
from __future__ import annotations

from cloudless._version import __version__
from cloudless.agent import (
    Agent,
    AgentMetadata,
    agent,
)
from cloudless.chunks import (
    Chunk,
    ErrorChunk,
    FinalChunk,
    PauseChunk,
    ReasoningChunk,
    StateChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)
from cloudless.exceptions import (
    AuthenticationError,
    CircuitOpen,
    CloudlessError,
    CostCapExceeded,
    GuardrailBlocked,
    InvalidInputError,
    PeerUnreachable,
    PermanentError,
    PolicyViolation,
    ThrottledError,
    TimeoutError,
    TransientError,
)
from cloudless.runtime import (
    Context,
    InMemoryContext,
    CircuitBreaker,
    get_breaker,
    get_policy_registry,
    policy,
    resilient,
    with_retry,
    with_timeout,
)
from cloudless.catalog import (
    LLM,
    InMemoryBackend,
    LocalFileBackend,
    Embeddings,
    EmbeddingsBackend,
    EmbeddingAlias,
    resolve_embedding,
    VectorStore,
    VectorStoreBackend,
    VectorMatch,
    InMemoryVectorBackend,
    LocalSubprocessBackend,
    Memory,
    MemoryBackend,
    MemoryEvent,
    MemoryRecord,
    ModelAlias,
    Sandbox,
    SandboxBackend,
    SandboxResult,
    Secrets,
    SecretsBackend,
    Tool,
    tool,
    resolve_model,
)

# Framework adapter bases — re-exported for ergonomic use:
#   `class X(cloudless.LangGraphAgent)` rather than
#   `from cloudless.adapters.frameworks.langgraph import LangGraphAgent`.
# Each is None if the corresponding optional extra isn't installed.
from cloudless.adapters.frameworks import LangGraphAgent, StrandsAgent

__all__ = [
    "__version__",
    # Agent surface
    "Agent",
    "AgentMetadata",
    "agent",
    # Chunks (Q16)
    "Chunk",
    "TextChunk",
    "ToolCallChunk",
    "ToolResultChunk",
    "ReasoningChunk",
    "StateChunk",
    "PauseChunk",
    "FinalChunk",
    "ErrorChunk",
    # Runtime
    "Context",
    "InMemoryContext",
    "policy",
    "get_policy_registry",
    "resilient",
    "with_retry",
    "with_timeout",
    "CircuitBreaker",
    "get_breaker",
    # Framework adapters
    "LangGraphAgent",
    "StrandsAgent",
    # Service catalog (Q9)
    "LLM",
    "ModelAlias",
    "resolve_model",
    "Memory",
    "MemoryBackend",
    "MemoryEvent",
    "MemoryRecord",
    "InMemoryBackend",
    "Secrets",
    "SecretsBackend",
    "LocalFileBackend",
    "Sandbox",
    "SandboxBackend",
    "SandboxResult",
    "LocalSubprocessBackend",
    "Embeddings",
    "EmbeddingsBackend",
    "EmbeddingAlias",
    "resolve_embedding",
    "VectorStore",
    "VectorStoreBackend",
    "VectorMatch",
    "InMemoryVectorBackend",
    "Tool",
    "tool",
    # Exceptions (Q21)
    "CloudlessError",
    "TransientError",
    "TimeoutError",
    "ThrottledError",
    "PeerUnreachable",
    "CircuitOpen",
    "PermanentError",
    "PolicyViolation",
    "GuardrailBlocked",
    "AuthenticationError",
    "InvalidInputError",
    "CostCapExceeded",
]
