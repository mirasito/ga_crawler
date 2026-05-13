"""Phase 3 stats namespace + builder (Pitfall 6 atomic merge into runs.stats).

The runs.stats JSON column is shared with Phase 2 (viled.* keys). Phase 3 writes
ONLY goldapple.* keys via RunWriter.patch_stats(run_id, delta) which uses
SQLite json_patch for atomic merge. Naive UPDATE would clobber the other
phase's keys (RESEARCH Pitfall 6 lines 808-816).

Source: 03-RESEARCH.md §Open Questions Q4 lines 1043-1066 (verbatim 13 keys).
"""

from __future__ import annotations

from typing import Any, Iterable

# 16 goldapple.* keys:
#   - 13 frozen at v1.0 Wave 0/4 boundary
#   - 3 appended in v1.1 Phase 8 PARSE-FIX-04 (D-815): volume_null_rate,
#     brand_null_rate, parser_drift_failure_reason
# Schema-locked: any new key must be added here AND in Phase 2 plan reviewer
# cross-check (mirror in the orchestrator's stats merge audit log).
GOLDAPPLE_STATS_KEYS: tuple[str, ...] = (
    "goldapple.fetch_count",
    "goldapple.fetch_failures",
    "goldapple.gate_shell_count",
    "goldapple.stale_count",
    "goldapple.parse_failures",
    "goldapple.unmatched_viled_brands",
    "goldapple.unmatched_goldapple_slugs_new",
    "goldapple.smoke_pass",
    "goldapple.smoke_diagnostics",
    "goldapple.fetch_duration_seconds",
    "goldapple.mean_fetch_seconds",
    "goldapple.camoufox_version",
    "goldapple.auto_suggest_m",
    # ---- v1.1 Phase 8 PARSE-FIX-04 additions (D-815) ----
    "goldapple.volume_null_rate",            # float in [0, 1]
    "goldapple.brand_null_rate",             # float in [0, 1]
    "goldapple.parser_drift_failure_reason", # str (sentinel "" when gate passed; see storage.sqlite Pitfall 4)
)

# Bare key name (without goldapple. prefix) → full namespaced key. Used by
# GoldappleStatsBuilder.set/inc to auto-prefix.
_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in GOLDAPPLE_STATS_KEYS
}


class StatsNamespaceError(KeyError):
    """Raised when a caller tries to set a key outside GOLDAPPLE_STATS_KEYS."""


class GoldappleStatsBuilder:
    """Accumulates goldapple.* keys for atomic merge via RunWriter.patch_stats.

    Usage (Wave 5 orchestrator):
        builder = GoldappleStatsBuilder()
        builder.set("smoke_pass", True)
        builder.from_run_loop_stats(run_loop_stats_dict)  # bulk-import
        builder.set("camoufox_version", "135.0.1.beta24")
        run_writer.patch_stats(run_id, builder.delta)

    The builder is a one-shot accumulator: emit at end-of-phase, not per-fetch
    (Pitfall 6: per-fetch UPDATE causes contention with Phase 2 viled writer).
    """

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        """Resolve a bare key name to its namespaced form. Raises if unknown."""
        if bare_key in _BARE_TO_NAMESPACED:
            return _BARE_TO_NAMESPACED[bare_key]
        # Allow caller to pass already-namespaced key directly
        if bare_key in GOLDAPPLE_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"unknown stats key {bare_key!r}; expected one of {sorted(_BARE_TO_NAMESPACED)}"
        )

    def set(self, bare_key: str, value: Any) -> None:
        """Set a namespaced stat. bare_key without 'goldapple.' prefix is auto-prefixed."""
        full = self._resolve(bare_key)
        self.delta[full] = value

    def inc(self, bare_key: str, n: int = 1) -> None:
        """Increment a counter. If absent, starts at 0."""
        full = self._resolve(bare_key)
        self.delta[full] = self.delta.get(full, 0) + n

    def get(self, bare_key: str, default: Any = None) -> Any:
        try:
            full = self._resolve(bare_key)
        except StatsNamespaceError:
            return default
        return self.delta.get(full, default)

    def from_run_loop_stats(self, run_loop_stats: dict) -> None:
        """Bulk-import from GoldappleFetcher.run_loop's stats dict.

        run_loop emits unprefixed keys: fetch_count, fetch_failures, gate_shell_count.
        Other namespaced keys (stale_count, parse_failures, etc.) come from caller's
        per-record post-processing.
        """
        # Only import keys that map cleanly into the namespace; ignore others
        # (defensive against future run_loop additions).
        for bare_key, value in run_loop_stats.items():
            if bare_key in _BARE_TO_NAMESPACED:
                self.delta[_BARE_TO_NAMESPACED[bare_key]] = value

    def keys(self) -> Iterable[str]:
        return self.delta.keys()

    def __len__(self) -> int:
        return len(self.delta)


# ---- NORM-06 forward direction (D-306) ----

def compute_norm06_forward(
    viled_brands: list[str],
    aliases: dict[str, list[str]],
    brand_bucket: dict[str, list[str]],
) -> tuple[list[str], int, list[str]]:
    """Wraps intersect_brand_pool for D-306 NORM-06 forward direction.

    brand_bucket is the precomputed brand-token prefix index from
    ga_crawler.enumeration.goldapple_sitemap.index_by_brand_token(
        slug_map, known_brand_tokens
    ) — NOT the raw sitemap_slugs product-slug dict (resolves
    03-VERIFICATION Truth 1 BLOCKER; brand-alias slugs cannot exact-match
    product-slug keys).

    Returns:
      (matched_urls, unmatched_count, unmatched_brands_list)

    The unmatched_count goes to stats.goldapple.unmatched_viled_brands.
    The unmatched_brands_list is logged for NORM-06 review queue (Phase 2
    owns persistence; Phase 3 hands it off to NORM-06 storage).
    """
    # Lazy import to avoid circular deps in module load order
    from ga_crawler.enumeration.slug import intersect_brand_pool

    matched, unmatched = intersect_brand_pool(viled_brands, aliases, brand_bucket)
    return matched, len(unmatched), unmatched


# ---- Phase 2 viled.* namespace (Plan 02-05; Open Q7 RESEARCH) ----

VILED_STATS_KEYS: tuple[str, ...] = (
    "viled.fetch_count",
    "viled.fetch_failures",
    "viled.parse_failures",
    "viled.fetch_duration_seconds",
    "viled.mean_fetch_seconds",
    "viled.sanity_gate_n_pass",
    "viled.parse_quality_pass",
    "viled.null_rate_required_fields",
    "viled.auto_suggest_n",
)

# Bare key name (without `viled.` prefix) → full namespaced key.
_VILED_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in VILED_STATS_KEYS
}


class ViledStatsBuilder:
    """Mirror of GoldappleStatsBuilder — viled.* namespace.

    Accumulates Phase 2 keys for atomic merge via RunWriter.patch_stats. The
    builder shares NO keys with GoldappleStatsBuilder (different namespace),
    so the two phases can safely write to the same `runs.stats` JSON column
    via separate single-call json_patch UPDATEs (Pitfall 6).

    Usage (Wave 5 viled_run.py):
        builder = ViledStatsBuilder()
        builder.set("fetch_count", 120)
        builder.set("parse_failures", 2)
        run_writer.patch_stats(run_id, builder.delta)

    Source: 02-RESEARCH.md §Open Q7; 02-PATTERNS.md lines 532-589.
    """

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _VILED_BARE_TO_NAMESPACED:
            return _VILED_BARE_TO_NAMESPACED[bare_key]
        if bare_key in VILED_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in VILED_STATS_KEYS; "
            f"allowed: {sorted(VILED_STATS_KEYS)}"
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


__all__ = [
    "GOLDAPPLE_STATS_KEYS",
    "VILED_STATS_KEYS",
    "StatsNamespaceError",
    "GoldappleStatsBuilder",
    "ViledStatsBuilder",
    "compute_norm06_forward",
]
