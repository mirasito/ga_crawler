"""Phase 4 Plan 04-02 — MATCH_STATS_KEYS namespace + MatchStatsBuilder.

Mirrors tests/unit/test_viled_stats_builder.py for the match.* side. The three
builders (viled.*, goldapple.*, match.*) share NO keys (Pitfall 6 invariant) —
atomic merge into runs.stats via separate single-call json_patch UPDATEs relies
on this disjointness.

Source: 04-CONTEXT.md D-414; 04-PATTERNS.md §"NEW src/ga_crawler/matcher/stats.py".
"""

import pytest

from ga_crawler.matcher.stats import MATCH_STATS_KEYS, MatchStatsBuilder
from ga_crawler.runner.stats import (
    GOLDAPPLE_STATS_KEYS,
    VILED_STATS_KEYS,
    StatsNamespaceError,
)


def test_match_stats_keys_count():
    """Plan 04-02 + D-414: 10-tuple namespace."""
    assert len(MATCH_STATS_KEYS) == 10


def test_all_keys_have_match_prefix():
    for k in MATCH_STATS_KEYS:
        assert k.startswith("match.")


@pytest.mark.parametrize(
    "expected_key",
    [
        "match.count",
        "match.rate",
        "match.numerator",
        "match.denominator",
        "match.brand_overlap_count",
        "match.viled_comparable_count",
        "match.goldapple_comparable_count",
        "match.skipped_reason",
        "match.threshold_p",
        "match.gate_passed",
    ],
)
def test_each_required_key_present(expected_key):
    assert expected_key in MATCH_STATS_KEYS


def test_set_resolves_bare_key():
    b = MatchStatsBuilder()
    b.set("count", 42)
    assert b.delta == {"match.count": 42}


def test_set_namespaced_key_passes():
    b = MatchStatsBuilder()
    b.set("match.rate", 42.31)
    assert b.delta == {"match.rate": 42.31}


def test_set_unknown_key_raises():
    b = MatchStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("nonsense", 1)


def test_set_viled_key_rejected():
    """MatchStatsBuilder must reject viled.* keys (cross-namespace pollution)."""
    b = MatchStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("viled.fetch_count", 100)


def test_set_goldapple_key_rejected():
    """MatchStatsBuilder must reject goldapple.* keys (cross-namespace pollution)."""
    b = MatchStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("goldapple.fetch_count", 100)


def test_inc_accumulates():
    b = MatchStatsBuilder()
    b.inc("count")
    b.inc("count")
    assert b.delta["match.count"] == 2


def test_inc_with_n():
    b = MatchStatsBuilder()
    b.inc("count", n=7)
    assert b.delta["match.count"] == 7


def test_get_default():
    b = MatchStatsBuilder()
    assert b.get("count", default=0) == 0
    b.set("count", 42)
    assert b.get("count") == 42


def test_three_way_namespaces_disjoint():
    """Pitfall 6 three-way invariant: no key shared across viled/goldapple/match."""
    viled_set = set(VILED_STATS_KEYS)
    gold_set = set(GOLDAPPLE_STATS_KEYS)
    match_set = set(MATCH_STATS_KEYS)
    assert viled_set.isdisjoint(match_set), "viled.* ∩ match.* must be empty"
    assert gold_set.isdisjoint(match_set), "goldapple.* ∩ match.* must be empty"
    assert viled_set.isdisjoint(gold_set), "viled.* ∩ goldapple.* must be empty"


def test_set_bool_and_str_and_null_values():
    """D-414 supports bool (gate_passed), str (skipped_reason).

    Pitfall 4 None-rejection lives in SqliteRunWriter.patch_stats, NOT in the
    builder. Empty-string sentinel "" is valid at builder level.
    """
    b = MatchStatsBuilder()
    b.set("gate_passed", True)
    b.set("skipped_reason", "failed_upstream")
    assert b.delta["match.gate_passed"] is True
    assert b.delta["match.skipped_reason"] == "failed_upstream"
    b.set("skipped_reason", "")
    assert b.delta["match.skipped_reason"] == ""


def test_keys_and_len():
    """API parity with ViledStatsBuilder: .keys() and __len__ work."""
    b = MatchStatsBuilder()
    assert len(b) == 0
    assert list(b.keys()) == []
    b.set("count", 5)
    b.set("rate", 12.34)
    assert len(b) == 2
    assert set(b.keys()) == {"match.count", "match.rate"}
