"""Phase 2 config loader.

Single source of truth for runtime constants pulled from pyproject.toml's
`[tool.ga_crawler.crawl.viled]` namespace. Operator edits TOML; CLI overrides
provided in cli.py (Plan 05).

Source: 02-PATTERNS.md §"Pattern: pyproject.toml Namespace Mirror" (D-202, D-227).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_CATALOG_URLS: tuple[str, ...] = (
    "https://viled.kz/men/catalog/1310",
    "https://viled.kz/women/catalog/1310",
)


@dataclass(frozen=True)
class ViledConfig:
    """Operator-tunable runtime constants for the viled stack.

    Defaults mirror `[tool.ga_crawler.crawl.viled]` in pyproject.toml so that
    constructing `ViledConfig()` directly (e.g. in tests) yields the same
    values as `ViledConfig.from_pyproject()` against the production toml.
    """

    sanity_gate_n: int = 100
    pause_seconds: float = 2.0
    concurrency: int = 1
    retry_attempts: int = 3
    catalog_urls: tuple[str, ...] = _DEFAULT_CATALOG_URLS
    n_auto_suggest_factor: float = 0.7
    n_auto_suggest_after_runs: int = 4

    @classmethod
    def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "ViledConfig":
        """Read [tool.ga_crawler.crawl.viled] from the given pyproject.toml.

        Missing keys (or a missing file) fall back to the dataclass defaults.
        """
        path = Path(pyproject_path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        viled = (
            data.get("tool", {})
            .get("ga_crawler", {})
            .get("crawl", {})
            .get("viled", {})
        )
        return cls(
            sanity_gate_n=int(viled.get("sanity_gate_n", cls.sanity_gate_n)),
            pause_seconds=float(viled.get("pause_seconds", cls.pause_seconds)),
            concurrency=int(viled.get("concurrency", cls.concurrency)),
            retry_attempts=int(viled.get("retry_attempts", cls.retry_attempts)),
            catalog_urls=tuple(viled.get("catalog_urls", cls.catalog_urls)),
            n_auto_suggest_factor=float(
                viled.get("n_auto_suggest_factor", cls.n_auto_suggest_factor)
            ),
            n_auto_suggest_after_runs=int(
                viled.get("n_auto_suggest_after_runs", cls.n_auto_suggest_after_runs)
            ),
        )


__all__ = ["ViledConfig"]
