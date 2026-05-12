"""Plan 06-02 (Wave 1) — unit tests for ``delivery/stats.py``::DeliverStatsBuilder.

Mirrors ``tests/unit/test_report_stats.py`` shape with the D-607 8-key
``deliver.*`` namespace. Re-uses ``StatsNamespaceError`` from
``runner.stats`` (no new error class — Pitfall 6 invariant).

Source anchors: 06-CONTEXT.md D-607; 06-PATTERNS.md "src/ga_crawler/delivery/stats.py".
"""

from __future__ import annotations

import pytest

from ga_crawler.delivery.stats import DELIVER_STATS_KEYS, DeliverStatsBuilder
from ga_crawler.runner.stats import StatsNamespaceError


def test_delivery_stats_keys_count():
    """D-607: 8-tuple namespace."""
    assert len(DELIVER_STATS_KEYS) == 8


def test_all_keys_have_deliver_prefix():
    for k in DELIVER_STATS_KEYS:
        assert k.startswith("deliver."), f"{k!r} missing deliver. prefix"


def test_keys_are_immutable_tuple():
    """tuple, not list — source-lock invariant (D-607)."""
    assert isinstance(DELIVER_STATS_KEYS, tuple)


def test_keys_canonical_order():
    """D-607 canonical order. Source-locked: drift here breaks Phase 6 contract."""
    assert DELIVER_STATS_KEYS == (
        "deliver.delivery_status",
        "deliver.route",
        "deliver.business_caption_message_id",
        "deliver.business_document_message_id",
        "deliver.ops_message_id",
        "deliver.attempt_count",
        "deliver.last_error",
        "deliver.delivered_at",
    )


def test_set_resolves_bare_key():
    b = DeliverStatsBuilder()
    b.set("delivery_status", "pending")
    assert b.delta == {"deliver.delivery_status": "pending"}


def test_set_resolves_namespaced_key():
    b = DeliverStatsBuilder()
    b.set("deliver.delivery_status", "delivered_business")
    assert b.delta == {"deliver.delivery_status": "delivered_business"}


def test_set_idempotent_overwrite():
    """Later set wins; single key in delta dict."""
    b = DeliverStatsBuilder()
    b.set("delivery_status", "pending")
    b.set("deliver.delivery_status", "delivered_business")
    assert b.delta == {"deliver.delivery_status": "delivered_business"}
    assert len(b) == 1


def test_set_raises_on_unknown_key():
    with pytest.raises(StatsNamespaceError):
        DeliverStatsBuilder().set("not_a_real_key", "x")


def test_set_viled_key_rejected():
    """Cross-namespace pollution rejected (Pitfall 7)."""
    with pytest.raises(StatsNamespaceError):
        DeliverStatsBuilder().set("viled.fetch_count", 100)


def test_set_report_key_rejected():
    with pytest.raises(StatsNamespaceError):
        DeliverStatsBuilder().set("report.summary_text", "x")


def test_inc_starts_at_zero_and_accumulates():
    b = DeliverStatsBuilder()
    b.inc("attempt_count")
    assert b.delta == {"deliver.attempt_count": 1}
    b.inc("attempt_count", 2)
    assert b.delta == {"deliver.attempt_count": 3}


def test_builder_len_matches_delta_keys():
    b = DeliverStatsBuilder()
    assert len(b) == 0
    b.set("delivery_status", "pending")
    b.set("route", "business")
    assert len(b) == 2
    assert set(b.keys()) == {"deliver.delivery_status", "deliver.route"}


def test_get_unknown_returns_default():
    b = DeliverStatsBuilder()
    assert b.get("not_a_real_key", "fallback") == "fallback"


def test_set_sentinel_values_accepted():
    """D-607 sentinels: -1 for int message_ids; "" for str last_error."""
    b = DeliverStatsBuilder()
    b.set("business_caption_message_id", -1)
    b.set("last_error", "")
    b.set("delivered_at", "")
    assert b.delta["deliver.business_caption_message_id"] == -1
    assert b.delta["deliver.last_error"] == ""
    assert b.delta["deliver.delivered_at"] == ""
