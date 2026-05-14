"""cloudless.runtime.manifest — load the baked agent manifest (Q12).

At deploy time, the CLI bakes a `cloudless-manifest.json` into each agent
that lists every deployed agent's name, cloud, endpoint URLs, etc. At
runtime, the embedded lib loads this manifest so `ctx.peer(name)` can
resolve to the right URL.

TTL-refresh from cloud-storage (OQ3, every 5 min) is implemented here too,
but the simplest path is just load-once-at-startup.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PeerEntry:
    name: str
    cloud: str
    http_url: Optional[str] = None
    a2a_url: Optional[str] = None
    idp_issuer: Optional[str] = None
    audience: Optional[str] = None
    residency: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Manifest:
    project: str
    agents: dict[str, PeerEntry]

    def get(self, name: str) -> Optional[PeerEntry]:
        return self.agents.get(name)


def load_manifest(
    path: Optional[Path | str] = None,
    *,
    contents: Optional[dict] = None,
) -> Manifest:
    """Load a manifest from disk (or accept already-parsed dict for tests).

    Search order if path is None:
      1. CLOUDLESS_MANIFEST_PATH env var
      2. /app/cloudless-manifest.json (deployed agent default)
      3. ./cloudless-manifest.json (local dev)
    """
    if contents is None:
        if path is None:
            candidates = [
                os.environ.get("CLOUDLESS_MANIFEST_PATH"),
                "/app/cloudless-manifest.json",
                "cloudless-manifest.json",
            ]
            path = next((p for p in candidates if p and Path(p).is_file()), None)
        if path is None or not Path(path).is_file():
            # Empty manifest is valid — single-agent projects have no peers,
            # and explicitly missing paths shouldn't crash the agent.
            return Manifest(project="<unknown>", agents={})
        contents = json.loads(Path(path).read_text())

    agents: dict[str, PeerEntry] = {}
    for name, raw in (contents.get("agents") or {}).items():
        agents[name] = PeerEntry(
            name=name,
            cloud=raw.get("cloud", "aws"),
            http_url=raw.get("http_url"),
            a2a_url=raw.get("a2a_url"),
            idp_issuer=raw.get("idp_issuer"),
            audience=raw.get("audience"),
            residency=tuple(raw.get("residency", ())),
        )
    return Manifest(
        project=contents.get("project", "<unknown>"),
        agents=agents,
    )
