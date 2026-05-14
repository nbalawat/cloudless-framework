"""cloudless service catalog — unified primitives over AWS + GCP services.

Per Q9, v1 catalog covers 11 primitives. This module exposes the user-
facing ones; each maps to a cloud-native implementation in
cloudless.adapters.aws.* / cloudless.adapters.gcp.*.

M1 ships LLM only (AWS-only); subsequent milestones add the rest:
  - Memory (M1 — AgentCore Memory backend)
  - Secrets (M1 — Secrets Manager backend)
  - VectorStore (M3 — Knowledge Bases preferred over raw OpenSearch per dossier 06)
  - Embeddings, Sandbox, Tools/Gateway, A2A, Observability, IdentityVault, Browser (M2-M5)
"""
from __future__ import annotations

from cloudless.catalog.llm import LLM, ModelAlias, resolve_model

__all__ = ["LLM", "ModelAlias", "resolve_model"]
