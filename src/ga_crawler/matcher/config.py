"""Phase 4 matcher config loader.

Single source of truth for runtime constants pulled from pyproject.toml's
`[tool.ga_crawler.match]` namespace. Operator edits TOML; CLI overrides in
`cli.py::_cmd_matcher` (Plan 04-05).

Source: 04-CONTEXT.md D-406..D-408, D-413; 04-PATTERNS.md §"AMEND pyproject.toml".
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MatchConfig:
    """Operator-tunable runtime constants for the matcher.

    Defaults mirror `[tool.ga_crawler.match]` in pyproject.toml so that
    constructing `MatchConfig()` directly (e.g. in tests) yields the same
    values as `MatchConfig.from_pyproject()` against the production toml.
    """

    sanity_gate_p: int = 20
    p_auto_suggest_factor: float = 0.7
    p_auto_suggest_after_runs: int = 4

    @classmethod
    def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "MatchConfig":
        """Read [tool.ga_crawler.match] from the given pyproject.toml.

        Missing keys (or a missing file) fall back to the dataclass defaults.
        """
        path = Path(pyproject_path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        match = (
            data.get("tool", {})
            .get("ga_crawler", {})
            .get("match", {})
        )
        return cls(
            sanity_gate_p=int(match.get("sanity_gate_p", cls.sanity_gate_p)),
            p_auto_suggest_factor=float(
                match.get("p_auto_suggest_factor", cls.p_auto_suggest_factor)
            ),
            p_auto_suggest_after_runs=int(
                match.get("p_auto_suggest_after_runs", cls.p_auto_suggest_after_runs)
            ),
        )


__all__ = ["MatchConfig"]
