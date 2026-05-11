"""Unit tests for ReportStatsBuilder — D-514 7-key namespace.

Mirrors tests/unit/test_matcher_stats.py with the three-way disjoint
invariant extended to four-way (viled ∩ goldapple ∩ match ∩ report = ∅).

Source: 05-CONTEXT.md D-514; 05-PATTERNS.md §"src/ga_crawler/reporter/stats.py".
"""

from __future__ import annotations

import pytest

from ga_crawler.matcher.stats import MATCH_STATS_KEYS
from ga_crawler.reporter.stats import REPORT_STATS_KEYS, ReportStatsBuilder
from ga_crawler.runner.stats import (
    GOLDAPPLE_STATS_KEYS,
    StatsNamespaceError,
    VILED_STATS_KEYS,
)


def test_report_stats_keys_count():
    """D-514: 7-tuple namespace (xlsx_path / xlsx_size_bytes / summary_text /
    sheet_row_counts / skipped_reason / size_guard_passed / generated_at)."""
    assert len(REPORT_STATS_KEYS) == 7


def test_all_keys_have_report_prefix():
    for k in REPORT_STATS_KEYS:
        assert k.startswith("report."), f"{k!r} missing report. prefix"


@pytest.mark.parametrize(
    "expected_key",
    [
        "report.xlsx_path",
        "report.xlsx_size_bytes",
        "report.summary_text",
        "report.sheet_row_counts",
        "report.skipped_reason",
        "report.size_guard_passed",
        "report.generated_at",
    ],
)
def test_each_required_key_present(expected_key):
    assert expected_key in REPORT_STATS_KEYS


def test_set_resolves_bare_key():
    b = ReportStatsBuilder()
    b.set("xlsx_path", "reports/2026-W19.xlsx")
    assert b.delta == {"report.xlsx_path": "reports/2026-W19.xlsx"}


def test_set_full_key_also_works():
    b = ReportStatsBuilder()
    b.set("report.xlsx_size_bytes", 12345)
    assert b.delta == {"report.xlsx_size_bytes": 12345}


def test_set_unknown_key_raises():
    with pytest.raises(StatsNamespaceError):
        ReportStatsBuilder().set("nonsense", 1)


def test_set_viled_key_rejected():
    """Cross-namespace pollution rejected (Pitfall 7)."""
    with pytest.raises(StatsNamespaceError):
        ReportStatsBuilder().set("viled.fetch_count", 100)


def test_set_goldapple_key_rejected():
    with pytest.raises(StatsNamespaceError):
        ReportStatsBuilder().set("goldapple.fetch_count", 100)


def test_set_match_key_rejected():
    with pytest.raises(StatsNamespaceError):
        ReportStatsBuilder().set("match.count", 100)


def test_four_way_namespaces_disjoint():
    """D-514 + Pitfall 7: report.* disjoint from viled.* / goldapple.* / match.*."""
    viled_set = set(VILED_STATS_KEYS)
    gold_set = set(GOLDAPPLE_STATS_KEYS)
    match_set = set(MATCH_STATS_KEYS)
    report_set = set(REPORT_STATS_KEYS)
    assert viled_set.isdisjoint(report_set), "viled.* ∩ report.* must be empty"
    assert gold_set.isdisjoint(report_set), "goldapple.* ∩ report.* must be empty"
    assert match_set.isdisjoint(report_set), "match.* ∩ report.* must be empty"
    # Re-assert three-way (Phase 4 invariant) so failure here flags any prior regression too
    assert viled_set.isdisjoint(gold_set)
    assert viled_set.isdisjoint(match_set)
    assert gold_set.isdisjoint(match_set)


def test_set_dict_value_accepts():
    """report.sheet_row_counts is a dict — builder accepts arbitrary value types."""
    b = ReportStatsBuilder()
    b.set("sheet_row_counts", {"summary": 1, "per_sku_deltas": 47})
    assert b.get("sheet_row_counts") == {"summary": 1, "per_sku_deltas": 47}


def test_inc_increments():
    b = ReportStatsBuilder()
    b.set("xlsx_size_bytes", 100)
    b.inc("xlsx_size_bytes", 50)
    assert b.get("xlsx_size_bytes") == 150


def test_get_unknown_returns_default():
    b = ReportStatsBuilder()
    assert b.get("nonsense", "fallback") == "fallback"


def test_keys_and_len():
    """API parity with other builders: .keys() and __len__ work."""
    b = ReportStatsBuilder()
    assert len(b) == 0
    assert list(b.keys()) == []
    b.set("xlsx_path", "reports/2026-W19.xlsx")
    b.set("xlsx_size_bytes", 12345)
    assert len(b) == 2
    assert set(b.keys()) == {"report.xlsx_path", "report.xlsx_size_bytes"}


def test_set_bool_and_str_values():
    """D-514 supports bool (size_guard_passed), str (skipped_reason / xlsx_path / generated_at).

    Pitfall 4 None-rejection lives in SqliteRunWriter.patch_stats, NOT in the
    builder. Empty-string sentinel '' is valid at builder level.
    """
    b = ReportStatsBuilder()
    b.set("size_guard_passed", False)
    b.set("skipped_reason", "")
    b.set("generated_at", "2026-05-10T14:30:00Z")
    assert b.delta["report.size_guard_passed"] is False
    assert b.delta["report.skipped_reason"] == ""
    assert b.delta["report.generated_at"] == "2026-05-10T14:30:00Z"
