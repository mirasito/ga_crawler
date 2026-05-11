"""Phase 5 reporter config loader.

Single source of truth for runtime constants pulled from pyproject.toml's
`[tool.ga_crawler.report]` namespace. Operator edits TOML; CLI overrides in
`cli.py::_cmd_report` (Plan 05-05).

Source: 05-CONTEXT.md D-509, D-510, D-512, D-515, D-516; 05-PATTERNS.md
"src/ga_crawler/reporter/config.py" section.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReportConfig:
    """Operator-tunable runtime constants for the reporter.

    Defaults mirror `[tool.ga_crawler.report]` in pyproject.toml so that
    constructing `ReportConfig()` directly (e.g. in tests) yields the same
    values as `ReportConfig.from_pyproject()` against the production toml.

    Per D-516.
    """

    output_dir: str = "reports"
    size_limit_mb: int = 45
    top_n_deltas: int = 3
    timezone: str = "Asia/Almaty"

    @classmethod
    def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "ReportConfig":
        """Read [tool.ga_crawler.report] from the given pyproject.toml.

        Missing keys (or a missing file) fall back to the dataclass defaults.
        """
        path = Path(pyproject_path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        report = (
            data.get("tool", {})
            .get("ga_crawler", {})
            .get("report", {})
        )
        return cls(
            output_dir=str(report.get("output_dir", cls.output_dir)),
            size_limit_mb=int(report.get("size_limit_mb", cls.size_limit_mb)),
            top_n_deltas=int(report.get("top_n_deltas", cls.top_n_deltas)),
            timezone=str(report.get("timezone", cls.timezone)),
        )


__all__ = ["ReportConfig"]
