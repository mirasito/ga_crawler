"""Phase 4 stats namespace + MatchStatsBuilder.

Mirror of ViledStatsBuilder / GoldappleStatsBuilder for the match.* namespace
(D-414). All three builders share NO keys (Pitfall 6 invariant) — they can
safely write the same runs.stats JSON column via separate single-call
json_patch UPDATEs. Reuses StatsNamespaceError from runner/stats.py to keep
a single exception class across all three namespaces.

Source: 04-CONTEXT.md D-414; 04-PATTERNS.md §"NEW src/ga_crawler/matcher/stats.py".
"""

from __future__ import annotations

from typing import Any, Iterable

from ga_crawler.runner.stats import StatsNamespaceError

# 10 match.* keys, frozen with the week-1 baseline (D-405 KPI formula freeze).
# Any new key must be added here AND the regression test in
# tests/unit/test_matcher_stats.py::test_match_stats_keys_count must be updated.
MATCH_STATS_KEYS: tuple[str, ...] = (
    "match.count",                       # int — numerator (rows in matches WHERE run_id=:N)
    "match.rate",                        # REAL — percent points, 2 decimals (e.g. 42.31)
    "match.numerator",                   # int — explicit dup of match.count for audit clarity
    "match.denominator",                 # int — comparable viled SKUs in brand-overlap (D-404)
    "match.brand_overlap_count",         # int — COUNT(DISTINCT brand_norm) intersection
    "match.viled_comparable_count",      # int — viled after multipack/volume/DELISTED filter
    "match.goldapple_comparable_count",  # int — goldapple after same filter
    "match.skipped_reason",              # str — "failed_upstream" / "in_progress_upstream" / "" if ran
    "match.threshold_p",                 # int — applied P threshold (D-408)
    "match.gate_passed",                 # bool — D-409 gate outcome
)

# Bare key name (without `match.` prefix) → full namespaced key. Used by
# MatchStatsBuilder.set/inc to auto-prefix.
_MATCH_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in MATCH_STATS_KEYS
}


class MatchStatsBuilder:
    """Mirror of ViledStatsBuilder / GoldappleStatsBuilder — match.* namespace.

    Accumulates Phase 4 keys for atomic merge via RunWriter.patch_stats. Shares
    NO keys with viled.* / goldapple.* (different namespace), so all three
    builders can safely write the same runs.stats column via separate
    single-call json_patch UPDATEs (Pitfall 6).

    Usage (Plan 04-04 orchestrator):
        builder = MatchStatsBuilder()
        builder.set("count", 42)
        builder.set("rate", 42.31)
        run_writer.patch_stats(run_id, builder.delta)

    Source: 04-CONTEXT.md D-414; 04-PATTERNS.md §"Pattern: Stats namespace builder".
    """

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _MATCH_BARE_TO_NAMESPACED:
            return _MATCH_BARE_TO_NAMESPACED[bare_key]
        if bare_key in MATCH_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in MATCH_STATS_KEYS; "
            f"allowed: {sorted(MATCH_STATS_KEYS)}"
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


__all__ = ["MATCH_STATS_KEYS", "MatchStatsBuilder"]
