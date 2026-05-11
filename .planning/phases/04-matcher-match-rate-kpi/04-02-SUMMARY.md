---
phase: 04-matcher-match-rate-kpi
plan: 02
subsystem: matcher/stats
tags: [stats, namespace, builder, phase-4, wave-1]
requires:
  - src/ga_crawler/runner/stats.py::StatsNamespaceError
  - src/ga_crawler/runner/stats.py::VILED_STATS_KEYS
  - src/ga_crawler/runner/stats.py::GOLDAPPLE_STATS_KEYS
provides:
  - src/ga_crawler/matcher/stats.py::MATCH_STATS_KEYS
  - src/ga_crawler/matcher/stats.py::MatchStatsBuilder
affects:
  - Phase 4 plan 04-04 (orchestrator will consume MatchStatsBuilder)
  - Phase 5 reporter (will read runs.stats[match.*] keys)
tech-stack:
  added: []
  patterns:
    - namespace-enforced stats builder (3rd instance after Viled + Goldapple)
    - StatsNamespaceError reuse across all three namespaces
key-files:
  created:
    - src/ga_crawler/matcher/stats.py
    - tests/unit/test_matcher_stats.py
  modified: []
decisions:
  - D-414: 10 canonical match.* keys frozen with week-1 baseline
  - "Defer NamespaceStatsBuilder base-class refactor to v2 (scope-contained 3rd copy now)"
metrics:
  duration_minutes: 4
  tasks_completed: 1
  files_created: 2
  files_modified: 0
  lines_added: 228
  tests_before: 401
  tests_after: 424
  tests_delta: 23
completed: 2026-05-11
---

# Phase 4 Plan 04-02: Match Stats Namespace + MatchStatsBuilder Summary

Phase 4 third-namespace stats builder shipped: `MATCH_STATS_KEYS` tuple (10 canonical keys per D-414) plus `MatchStatsBuilder` mirroring `ViledStatsBuilder` / `GoldappleStatsBuilder` line-for-line, reusing `StatsNamespaceError` from `runner/stats.py` — Phase 5 reporter can now safely read the frozen `runs.stats[match.*]` schema without join-back.

## What Was Built

### Canonical 10-key namespace (D-414)

`MATCH_STATS_KEYS` is a frozen tuple at `src/ga_crawler/matcher/stats.py`:

| Key | Type | Purpose |
|-----|------|---------|
| `match.count` | int | numerator — rows in matches WHERE run_id=:N |
| `match.rate` | REAL | percent points, 2 decimals (e.g. 42.31) |
| `match.numerator` | int | explicit dup of match.count for audit |
| `match.denominator` | int | comparable viled SKUs in brand-overlap (D-404) |
| `match.brand_overlap_count` | int | COUNT(DISTINCT brand_norm) ∩ |
| `match.viled_comparable_count` | int | viled after multipack/volume/DELISTED filter |
| `match.goldapple_comparable_count` | int | goldapple after same filter |
| `match.skipped_reason` | str | "failed_upstream" / "in_progress_upstream" / "" |
| `match.threshold_p` | int | applied P threshold (D-408) |
| `match.gate_passed` | bool | D-409 gate outcome |

### MatchStatsBuilder API parity

Verbatim copy of `ViledStatsBuilder` shape — same methods, same error semantics:

- `.set(bare_key, value)` — auto-prefixes bare keys (e.g. `set('count', 42)` → `{'match.count': 42}`)
- `.inc(bare_key, n=1)` — counter accumulator
- `.get(bare_key, default=None)` — read with fallback
- `.keys()` — iterable of namespaced keys
- `__len__` — delta size
- raises `StatsNamespaceError` on any key not in `MATCH_STATS_KEYS`

`StatsNamespaceError` is **imported** from `ga_crawler.runner.stats`, never redefined — single exception class across all three namespaces.

### 13 regression tests (23 with parametrize expansion)

`tests/unit/test_matcher_stats.py` covers:

1. `test_match_stats_keys_count` — exactly 10 keys
2. `test_all_keys_have_match_prefix` — prefix invariant
3. `test_each_required_key_present` — 10 parametrized presence checks
4. `test_set_resolves_bare_key` — bare → namespaced auto-prefix
5. `test_set_namespaced_key_passes` — namespaced direct write
6. `test_set_unknown_key_raises` — typo rejection
7. `test_set_viled_key_rejected` — cross-namespace pollution rejection (viled.\*)
8. `test_set_goldapple_key_rejected` — cross-namespace pollution rejection (goldapple.\*)
9. `test_inc_accumulates` — counter semantics
10. `test_inc_with_n` — `n=` argument
11. `test_get_default` — read with fallback
12. `test_three_way_namespaces_disjoint` — Pitfall 6 invariant (viled ∩ goldapple ∩ match = ∅)
13. `test_set_bool_and_str_and_null_values` — bool/str/empty-string pass-through (Pitfall 4 lives downstream in `patch_stats`)
14. `test_keys_and_len` — `.keys()` and `__len__` API

## Deviations from Plan

None — plan executed exactly as written. The plan's `<action>` block specified the file content verbatim, the test list was clear, and zero auto-fixes were needed.

## Three-Way Namespace Disjointness (Pitfall 6)

The plan flagged this as a critical invariant. Test 12 verifies:

```python
set(VILED_STATS_KEYS).isdisjoint(set(MATCH_STATS_KEYS))      # True
set(GOLDAPPLE_STATS_KEYS).isdisjoint(set(MATCH_STATS_KEYS))  # True
set(VILED_STATS_KEYS).isdisjoint(set(GOLDAPPLE_STATS_KEYS))  # True
```

All three pass. The `runs.stats` JSON column can now be safely patched by three independent `patch_stats(run_id, delta)` calls without key clobbering — exactly the property Pitfall 6 demands.

## TDD Gate Compliance

- **RED** (`d5b522e`): `test(04-02): add failing tests for MatchStatsBuilder + MATCH_STATS_KEYS` — collection error (`ModuleNotFoundError: No module named 'ga_crawler.matcher.stats'`)
- **GREEN** (`daef1cb`): `feat(04-02): ship MATCH_STATS_KEYS + MatchStatsBuilder (D-414)` — 23/23 tests pass
- **REFACTOR**: skipped by design — plan explicitly defers base-class refactor to v2

## Verification

- `uv run pytest tests/unit/test_matcher_stats.py -q` → **23 passed**
- `uv run pytest -q` → **424 passed, 1 skipped** (was 401/1 — exactly +23, no regression)
- Acceptance grep checks all pass:
  - file exists: yes
  - `class MatchStatsBuilder` count: 1
  - `"match.*"` literal keys: 10
  - `from ga_crawler.runner.stats import StatsNamespaceError`: 1
  - `class StatsNamespaceError` redefinition: 0
  - runtime smoke (`b.set('count', 1)` → `{'match.count': 1}`): OK

## Commits

| Phase | Hash | Message |
|-------|------|---------|
| RED | `d5b522e` | test(04-02): add failing tests for MatchStatsBuilder + MATCH_STATS_KEYS |
| GREEN | `daef1cb` | feat(04-02): ship MATCH_STATS_KEYS + MatchStatsBuilder (D-414) |

## What Phase 4 Plan 04-04 (Orchestrator) Gets

```python
from ga_crawler.matcher.stats import MatchStatsBuilder

builder = MatchStatsBuilder()
builder.set("count", match_count)
builder.set("rate", round(match_count * 100.0 / denominator, 2))
builder.set("numerator", match_count)
builder.set("denominator", denominator)
builder.set("brand_overlap_count", brand_overlap)
builder.set("viled_comparable_count", v_comparable)
builder.set("goldapple_comparable_count", g_comparable)
builder.set("skipped_reason", "")  # or "failed_upstream" if D-411 skip
builder.set("threshold_p", config.sanity_gate_p)
builder.set("gate_passed", match_count > config.sanity_gate_p)
run_writer.patch_stats(run_id, builder.delta)  # single atomic json_patch
```

Any typo (`builder.set("rat", ...)`) is caught at write-time, before silent KPI drift can corrupt the historical baseline.

## Self-Check: PASSED

- `src/ga_crawler/matcher/stats.py` — FOUND
- `tests/unit/test_matcher_stats.py` — FOUND
- Commit `d5b522e` — FOUND in git log
- Commit `daef1cb` — FOUND in git log
- Test count delta: 401 → 424 (+23 = exact match to file's 14 test functions × parametrize-expansion-of-test_each_required_key_present-to-10-cases = 13 base + 10 extra param cases = 23 collected)
