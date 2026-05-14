"""cloudless runtime — the embedded library every deployed agent imports.

Provides:
  - `Context`: per-invocation context passed to `agent.query(ctx, prompt)`
  - `Session`: stable session identifier (maps to AgentCore microVM session ID
    on AWS, custom session ID on GCP)
  - `CostTracker`: per-invocation cost accumulator (Q20)
  - `PeerClient`: A2A peer caller (Q12 + Q7)

The runtime lib is intentionally framework-agnostic. Framework adapters
(cloudless.adapters.frameworks.*) plumb framework-native concepts into
this runtime contract.
"""
from __future__ import annotations

from cloudless.runtime.context import (
    Context,
    CostTracker,
    InMemoryContext,
    PeerClient,
    Session,
    User,
)
from cloudless.runtime.logging import (
    add_redact_pattern,
    bind_invocation,
    clear_invocation,
    configure,
    get_logger,
)
from cloudless.runtime.manifest import Manifest, PeerEntry, load_manifest

__all__ = [
    "Context",
    "Session",
    "User",
    "CostTracker",
    "PeerClient",
    "InMemoryContext",
    "Manifest",
    "PeerEntry",
    "load_manifest",
    "get_logger",
    "configure",
    "bind_invocation",
    "clear_invocation",
    "add_redact_pattern",
]
