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
from cloudless.runtime.manifest import (
    Manifest,
    ManifestRefresher,
    PeerEntry,
    load_manifest,
)
from cloudless.runtime.peer import A2APeerClient, CognitoIdentity, build_peer_client
from cloudless.runtime.a2a_server import build_a2a_app
from cloudless.runtime.identity import (
    InMemoryTokenStore,
    OAuth3LOConfig,
    OAuth3LOIdentity,
    OAuthRequired,
    SigV4Identity,
    StoredToken,
    TokenStore,
)
from cloudless.runtime.tasks import (
    InMemoryTaskStore,
    TaskRecord,
    TaskStore,
    get_store as get_task_store,
    get_task,
    list_active_tasks,
    pause,
    reset_store as reset_task_store,
    resume,
    set_store as set_task_store,
)
from cloudless.runtime import tracing
from cloudless.runtime.cost_sinks import (
    CostRecord,
    CostSink,
    InMemoryCostSink,
    JsonlCostSink,
    add_cost_sink,
    emit_cost,
    get_cost_sinks,
    reset_cost_sinks,
    set_cost_sinks,
)
from cloudless.runtime.audit import (
    AuditRecord,
    AuditSink,
    FileSink,
    InMemorySink,
    StructlogSink,
    add_sink as add_audit_sink,
    emit_audit,
    get_sinks as get_audit_sinks,
    reset_sinks as reset_audit_sinks,
    set_sinks as set_audit_sinks,
)
from cloudless.runtime.policy import (
    PolicyEntry,
    PolicyRegistry,
    VALID_STAGES,
    get_registry as get_policy_registry,
    policy,
)
from cloudless.runtime.resilience import (
    CircuitBreaker,
    get_breaker,
    resilient,
    reset_breakers,
    with_retry,
    with_timeout,
)

__all__ = [
    "Context",
    "Session",
    "User",
    "CostTracker",
    "PeerClient",
    "InMemoryContext",
    "Manifest",
    "ManifestRefresher",
    "PeerEntry",
    "load_manifest",
    "get_logger",
    "configure",
    "bind_invocation",
    "clear_invocation",
    "add_redact_pattern",
    "PolicyEntry",
    "PolicyRegistry",
    "VALID_STAGES",
    "get_policy_registry",
    "policy",
    "CircuitBreaker",
    "get_breaker",
    "resilient",
    "reset_breakers",
    "with_retry",
    "with_timeout",
    "A2APeerClient",
    "CognitoIdentity",
    "build_peer_client",
    "build_a2a_app",
    "OAuth3LOConfig",
    "OAuth3LOIdentity",
    "OAuthRequired",
    "SigV4Identity",
    "StoredToken",
    "TokenStore",
    "InMemoryTokenStore",
    "tracing",
    "AuditRecord",
    "AuditSink",
    "FileSink",
    "InMemorySink",
    "StructlogSink",
    "add_audit_sink",
    "emit_audit",
    "get_audit_sinks",
    "reset_audit_sinks",
    "set_audit_sinks",
    "InMemoryTaskStore",
    "TaskRecord",
    "TaskStore",
    "get_task_store",
    "get_task",
    "list_active_tasks",
    "pause",
    "reset_task_store",
    "resume",
    "set_task_store",
    "CostRecord",
    "CostSink",
    "JsonlCostSink",
    "InMemoryCostSink",
    "add_cost_sink",
    "emit_cost",
    "get_cost_sinks",
    "reset_cost_sinks",
    "set_cost_sinks",
]
