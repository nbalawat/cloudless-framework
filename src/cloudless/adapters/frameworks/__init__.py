"""Framework adapter bases.

Each framework gets a `cloudless.<Framework>Agent` base class that:
  - Inherits from `cloudless.Agent`
  - Implements the abstract `query()` by driving the framework
  - Translates framework-native events to `cloudless.chunks.Chunk`

Per Q5 framework rollout: LangGraph + Strands at v1 baseline,
ADK + MAF in later milestones.
"""
from __future__ import annotations

try:
    from cloudless.adapters.frameworks.langgraph import LangGraphAgent
except ImportError:  # langgraph extra not installed
    LangGraphAgent = None  # type: ignore[assignment,misc]

try:
    from cloudless.adapters.frameworks.strands import StrandsAgent
except ImportError:  # strands extra not installed
    StrandsAgent = None  # type: ignore[assignment,misc]

__all__ = ["LangGraphAgent", "StrandsAgent"]
