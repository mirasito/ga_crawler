"""Open Q7 + Plan 02-05 — VILED_STATS_KEYS namespace + ViledStatsBuilder.

Mirrors tests/unit/test_stats_namespace.py for the viled.* side. The two
builders share NO keys (different namespace prefixes) — Pitfall 6 atomic
merge into runs.stats relies on this invariant.

This file additionally pins the Phase 3 GoldappleStatsBuilder behavior to
guarantee no regression after the additive Plan 02-05 extension.

Source: 02-RESEARCH.md §Open Q7; 02-PATTERNS.md lines 532-589.
"""

import pytest

from ga_crawler.runner.stats import (
    GOLDAPPLE_STATS_KEYS,
    GoldappleStatsBuilder,
    StatsNamespaceError,
    VILED_STATS_KEYS,
    ViledStatsBuilder,
)


def test_viled_stats_keys_count():
    """Plan 02-05 + Open Q7: 9-tuple namespace."""
    assert len(VILED_STATS_KEYS) == 9


def test_viled_stats_keys_all_namespaced():
    for k in VILED_STATS_KEYS:
        assert k.startswith("viled.")


@pytest.mark.parametrize(
    "expected_key",
    [
        "viled.fetch_count",
        "viled.fetch_failures",
        "viled.parse_failures",
        "viled.fetch_duration_seconds",
        "viled.mean_fetch_seconds",
        "viled.sanity_gate_n_pass",
        "viled.parse_quality_pass",
        "viled.null_rate_required_fields",
        "viled.auto_suggest_n",
    ],
)
def test_each_required_key_present(expected_key):
    assert expected_key in VILED_STATS_KEYS


def test_set_resolves_bare_key():
    b = ViledStatsBuilder()
    b.set("fetch_count", 100)
    assert b.delta == {"viled.fetch_count": 100}


def test_set_namespaced_key_passes():
    b = ViledStatsBuilder()
    b.set("viled.parse_failures", 2)
    assert b.delta == {"viled.parse_failures": 2}


def test_set_unknown_key_raises():
    b = ViledStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("nonsense", 1)


def test_delta_separated_from_goldapple():
    """ViledStatsBuilder must reject goldapple.* keys (different namespace)."""
    b = ViledStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("goldapple.fetch_count", 100)


def test_inc_accumulates():
    b = ViledStatsBuilder()
    b.inc("fetch_failures")
    b.inc("fetch_failures")
    assert b.delta["viled.fetch_failures"] == 2


def test_inc_with_n():
    b = ViledStatsBuilder()
    b.inc("fetch_failures", n=5)
    assert b.delta["viled.fetch_failures"] == 5


def test_get_default():
    b = ViledStatsBuilder()
    assert b.get("fetch_count", default=0) == 0
    b.set("fetch_count", 42)
    assert b.get("fetch_count") == 42


def test_set_float_value():
    """null_rate_required_fields stored as a float (0.0..1.0)."""
    b = ViledStatsBuilder()
    b.set("null_rate_required_fields", 0.0234)
    assert b.delta["viled.null_rate_required_fields"] == pytest.approx(0.0234)


# ---- Phase 3 regression guard: GoldappleStatsBuilder unchanged ----


def test_existing_goldapple_unchanged():
    """Phase 3 GoldappleStatsBuilder must still accept its keys after Plan 02-05."""
    g = GoldappleStatsBuilder()
    g.set("fetch_count", 100)  # bare-key-resolved to goldapple.fetch_count
    assert g.delta.get("goldapple.fetch_count") == 100


def test_goldapple_stats_keys_unchanged():
    """Phase 3 baseline 13 keys preserved + Phase 8 PARSE-FIX-04 +3 (D-815)."""
    assert len(GOLDAPPLE_STATS_KEYS) == 16
    for k in GOLDAPPLE_STATS_KEYS:
        assert k.startswith("goldapple.")


def test_namespaces_disjoint():
    """No key shared between viled.* and goldapple.* (Pitfall 6 invariant)."""
    viled_set = set(VILED_STATS_KEYS)
    gold_set = set(GOLDAPPLE_STATS_KEYS)
    assert viled_set.isdisjoint(gold_set)
