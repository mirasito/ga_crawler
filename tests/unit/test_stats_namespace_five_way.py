"""Plan 06-02 (Wave 1) — 5-way namespace disjoint canary.

Extends Phase 5's 4-way (``tests/unit/test_report_stats.py::test_four_way_namespaces_disjoint``).
D-607 + Pitfall 7 source-lock invariant: each of the 5 stats namespaces
({viled, goldapple, match, report, deliver}) is fully disjoint from the
other four.
"""

from __future__ import annotations

from ga_crawler.delivery.stats import DELIVER_STATS_KEYS
from ga_crawler.matcher.stats import MATCH_STATS_KEYS
from ga_crawler.reporter.stats import REPORT_STATS_KEYS
from ga_crawler.runner.stats import GOLDAPPLE_STATS_KEYS, VILED_STATS_KEYS


def test_five_way_namespaces_disjoint():
    sets = {
        "viled":     set(VILED_STATS_KEYS),
        "goldapple": set(GOLDAPPLE_STATS_KEYS),
        "match":     set(MATCH_STATS_KEYS),
        "report":    set(REPORT_STATS_KEYS),
        "deliver":   set(DELIVER_STATS_KEYS),
    }
    names = list(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert sets[a].isdisjoint(sets[b]), (
                f"{a}.* ∩ {b}.* must be empty; overlap: {sets[a] & sets[b]}"
            )


def test_deliver_keys_all_have_prefix():
    for k in DELIVER_STATS_KEYS:
        assert k.startswith("deliver."), f"{k!r} missing deliver. prefix"
