"""GoldappleStatsBuilder + GOLDAPPLE_STATS_KEYS tests (Pitfall 6 + RESEARCH §Q4)."""

from __future__ import annotations

import pytest

from ga_crawler.runner.stats import (
    GOLDAPPLE_STATS_KEYS,
    GoldappleStatsBuilder,
    StatsNamespaceError,
)


def test_namespace_has_16_keys() -> None:
    """RESEARCH §Q4 lines 1051-1066: 13 keys at v1.0; v1.1 Phase 8 PARSE-FIX-04
    appends 3 keys (volume_null_rate, brand_null_rate, parser_drift_failure_reason)
    per 08-CONTEXT.md D-815; 08-PATTERNS.md Pattern 2."""
    assert len(GOLDAPPLE_STATS_KEYS) == 16


def test_all_keys_have_goldapple_prefix() -> None:
    for key in GOLDAPPLE_STATS_KEYS:
        assert key.startswith("goldapple."), f"key {key!r} missing namespace prefix"


@pytest.mark.parametrize("expected_key", [
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
    "goldapple.volume_null_rate",
    "goldapple.brand_null_rate",
    "goldapple.parser_drift_failure_reason",
])
def test_each_required_key_present(expected_key: str) -> None:
    assert expected_key in GOLDAPPLE_STATS_KEYS


def test_builder_starts_empty() -> None:
    b = GoldappleStatsBuilder()
    assert b.delta == {}
    assert len(b) == 0


def test_builder_set_auto_prefixes() -> None:
    b = GoldappleStatsBuilder()
    b.set("fetch_count", 100)
    assert b.delta == {"goldapple.fetch_count": 100}


def test_builder_set_accepts_full_namespace() -> None:
    b = GoldappleStatsBuilder()
    b.set("goldapple.fetch_count", 100)
    assert b.delta == {"goldapple.fetch_count": 100}


def test_builder_inc_accumulates() -> None:
    b = GoldappleStatsBuilder()
    b.inc("fetch_failures")
    b.inc("fetch_failures")
    assert b.delta["goldapple.fetch_failures"] == 2


def test_builder_inc_with_n() -> None:
    b = GoldappleStatsBuilder()
    b.inc("fetch_failures", n=5)
    b.inc("fetch_failures", n=2)
    assert b.delta["goldapple.fetch_failures"] == 7


def test_builder_set_bool_value() -> None:
    b = GoldappleStatsBuilder()
    b.set("smoke_pass", True)
    assert b.delta["goldapple.smoke_pass"] is True


def test_builder_set_dict_value() -> None:
    b = GoldappleStatsBuilder()
    diagnostics = {"camoufox_version": "135", "responses": [{"url": "x", "status": 200}]}
    b.set("smoke_diagnostics", diagnostics)
    assert b.delta["goldapple.smoke_diagnostics"]["camoufox_version"] == "135"
    assert len(b.delta["goldapple.smoke_diagnostics"]["responses"]) == 1


def test_builder_set_list_value() -> None:
    b = GoldappleStatsBuilder()
    b.set("unmatched_viled_brands", 7)  # numeric counter; list allowed for review queue
    b.set("unmatched_goldapple_slugs_new", 23)
    assert b.delta["goldapple.unmatched_viled_brands"] == 7
    assert b.delta["goldapple.unmatched_goldapple_slugs_new"] == 23


def test_builder_unknown_key_raises() -> None:
    b = GoldappleStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.set("foobar", 1)


def test_builder_unknown_key_inc_raises() -> None:
    b = GoldappleStatsBuilder()
    with pytest.raises(StatsNamespaceError):
        b.inc("nonsense")


def test_builder_from_run_loop_stats() -> None:
    """run_loop emits {fetch_count, fetch_failures, gate_shell_count}; bulk import."""
    b = GoldappleStatsBuilder()
    b.from_run_loop_stats({
        "fetch_count": 100,
        "fetch_failures": 2,
        "gate_shell_count": 0,
        "stale_count": 5,
    })
    assert b.delta["goldapple.fetch_count"] == 100
    assert b.delta["goldapple.fetch_failures"] == 2
    assert b.delta["goldapple.gate_shell_count"] == 0
    assert b.delta["goldapple.stale_count"] == 5


def test_builder_from_run_loop_ignores_unknown_keys() -> None:
    """Defensive: future run_loop adds keys that aren't in namespace; ignore."""
    b = GoldappleStatsBuilder()
    b.from_run_loop_stats({"fetch_count": 50, "future_key_we_dont_have": 999})
    assert b.delta == {"goldapple.fetch_count": 50}


def test_builder_get_default() -> None:
    b = GoldappleStatsBuilder()
    assert b.get("fetch_count", default=0) == 0
    b.set("fetch_count", 42)
    assert b.get("fetch_count") == 42
