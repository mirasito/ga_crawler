"""Phase 5 reporter stats namespace builder.

Mirror of MatchStatsBuilder. Enforces `report.` prefix; reuses
`StatsNamespaceError` from runner/stats.py (no re-definition). All keys
listed below are write-able via bare-name or fully-namespaced; everything
else raises.

Source: 05-CONTEXT.md D-514 (7 keys, mirror D-414 pattern);
05-PATTERNS.md "src/ga_crawler/reporter/stats.py" section.
"""

from __future__ import annotations

from typing import Any, Iterable

from ga_crawler.runner.stats import StatsNamespaceError

# 7 report.* keys, D-514. Any new key MUST be added here AND the regression
# test tests/unit/test_report_stats.py::test_report_stats_keys_count updated.
REPORT_STATS_KEYS: tuple[str, ...] = (
    "report.xlsx_path",           # str — relative path from repo_root (e.g. "reports/2026-W19.xlsx")
    "report.xlsx_size_bytes",     # int
    "report.summary_text",        # str — multi-line emoji D-504 caption (Telegram-ready)
    "report.sheet_row_counts",    # dict[str, int] — JSON-serializable via patch_stats
    "report.skipped_reason",      # str — "" sentinel for non-skip path (Pitfall 4 None-rejection)
    "report.size_guard_passed",   # bool — D-515 flag (false ≠ run-failure)
    "report.generated_at",        # str — ISO 8601 UTC timestamp
)


_REPORT_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in REPORT_STATS_KEYS
}


class ReportStatsBuilder:
    """Mirror of MatchStatsBuilder / ViledStatsBuilder / GoldappleStatsBuilder.

    All set/inc/get calls go through `_resolve` which enforces the `report.`
    namespace. Cross-namespace writes (`viled.*`, `goldapple.*`, `match.*`)
    raise `StatsNamespaceError` — Pitfall 6 + Pitfall 7 invariant preserved.
    """

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _REPORT_BARE_TO_NAMESPACED:
            return _REPORT_BARE_TO_NAMESPACED[bare_key]
        if bare_key in REPORT_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in REPORT_STATS_KEYS; "
            f"allowed: {sorted(REPORT_STATS_KEYS)}"
        )

    def set(self, bare_key: str, value: Any) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = value

    def inc(self, bare_key: str, n: int = 1) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = self.delta.get(full, 0) + n

    def get(self, bare_key: str, default: Any = None) -> Any:
        try:
            full = self._resolve(bare_key)
        except StatsNamespaceError:
            return default
        return self.delta.get(full, default)

    def keys(self) -> Iterable[str]:
        return self.delta.keys()

    def __len__(self) -> int:
        return len(self.delta)


__all__ = ["REPORT_STATS_KEYS", "ReportStatsBuilder"]
