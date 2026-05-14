"""Sidecar JSON metadata for live HTML fixtures — TEST-HARNESS-02c (D-901).

Each _live-YYYY-MM-DD-<slug>.html fixture is paired with a JSON sidecar at
the same path with `.json` suffix carrying {date, url, status, html_size,
title, camoufox_version}.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixtureMetadata:
    date: str  # ISO 8601 UTC
    url: str
    status: int
    html_size: int
    title: str
    camoufox_version: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2, sort_keys=True)


def write_sidecar(fixture_path: Path, meta: FixtureMetadata) -> Path:
    """Writes <fixture>.json beside <fixture>.html. Idempotent."""
    sidecar = fixture_path.with_suffix(".json")
    sidecar.write_text(meta.to_json(), encoding="utf-8")
    return sidecar


def read_sidecar(fixture_path: Path) -> FixtureMetadata | None:
    sidecar = fixture_path.with_suffix(".json")
    if not sidecar.exists():
        return None
    return FixtureMetadata(**json.loads(sidecar.read_text("utf-8")))
