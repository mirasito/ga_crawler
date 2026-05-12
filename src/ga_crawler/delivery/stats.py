"""Phase 6 delivery stats namespace builder.

Mirror of ReportStatsBuilder / MatchStatsBuilder / ViledStatsBuilder /
GoldappleStatsBuilder. Enforces ``deliver.`` prefix; reuses
``StatsNamespaceError`` from runner/stats.py (no re-definition, Pitfall 6
invariant: single error class across all 5 namespaces). All keys listed
below are write-able via bare-name or fully-namespaced; everything else
raises.

Source: 06-CONTEXT.md D-607 (8 keys, mirror D-514 7-key pattern);
06-PATTERNS.md "src/ga_crawler/delivery/stats.py" section.
"""

from __future__ import annotations

from typing import Any, Iterable

from ga_crawler.runner.stats import StatsNamespaceError

# 8 deliver.* keys, D-607. Any new key MUST be added here AND the
# regression test tests/test_delivery_stats.py::test_keys_canonical_order
# updated. Source-locked: order matters for tuple equality canary.
DELIVER_STATS_KEYS: tuple[str, ...] = (
    "deliver.delivery_status",              # str — enum D-606 (6 values)
    "deliver.route",                        # str — "business" | "ops_only" | "skipped" | ""
    "deliver.business_caption_message_id",  # int — Telegram message_id; -1 sentinel
    "deliver.business_document_message_id", # int — Telegram message_id; -1 sentinel
    "deliver.ops_message_id",               # int — Telegram message_id; -1 sentinel
    "deliver.attempt_count",                # int — cumulative across retries
    "deliver.last_error",                   # str — short truncated error; "" sentinel
    "deliver.delivered_at",                 # str — ISO 8601 UTC; "" sentinel
)


_DELIVER_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in DELIVER_STATS_KEYS
}


class DeliverStatsBuilder:
    """Mirror of ReportStatsBuilder / MatchStatsBuilder — deliver.* namespace.

    All set/inc/get calls go through ``_resolve`` which enforces the
    ``deliver.`` namespace. Cross-namespace writes (``viled.*``,
    ``goldapple.*``, ``match.*``, ``report.*``) raise
    ``StatsNamespaceError`` — Pitfall 7 invariant preserved.

    Usage (Wave 3 delivery_run.py):
        builder = DeliverStatsBuilder()
        builder.set("delivery_status", "delivered_business")
        builder.set("business_caption_message_id", 10001)
        run_writer.patch_stats(run_id, builder.delta)
    """

    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _DELIVER_BARE_TO_NAMESPACED:
            return _DELIVER_BARE_TO_NAMESPACED[bare_key]
        if bare_key in DELIVER_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in DELIVER_STATS_KEYS; "
            f"allowed: {sorted(DELIVER_STATS_KEYS)}"
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


__all__ = ["DELIVER_STATS_KEYS", "DeliverStatsBuilder"]
