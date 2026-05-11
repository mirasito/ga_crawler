---
phase: 04-matcher-match-rate-kpi
plan: 03
subsystem: matcher
tags: [sql, strict-key, kpi, regression-canary, tdd, wave-2]
dependency_graph:
  requires:
    - storage/sqlite.py::Match (Plan 04-01 — Match SQLModel table)
    - storage/sqlite.py::Snapshot (Phase 2 — JOIN input)
    - storage/sqlite.py::Run (Phase 2 — FK target + status read)
    - storage/sqlite.py::make_engine, init_db, SqliteSnapshotWriter (Phase 2)
  provides:
    - matcher/strict_key.py::build_matches_for_run (DELETE+INSERT in one TX, D-410)
    - matcher/strict_key.py::compute_denominator (D-404 symmetric filter)
    - matcher/strict_key.py::compute_brand_overlap (intersection COUNT DISTINCT)
    - matcher/strict_key.py::compute_comparable_counts (per-retailer D-402 COUNT)
    - matcher/strict_key.py::read_run_status (D-411 skip-input)
    - matcher/strict_key.py::INSERT_MATCHES_SQL, DENOMINATOR_SQL, BRAND_OVERLAP_SQL,
      COMPARABLE_COUNT_SQL, DELETE_MATCHES_SQL, RUN_STATUS_SQL (module-level
      text() constants — source-locked by canary)
  affects:
    - runners/matcher_run.py (Plan 04-04 will consume all 5 primitives)
tech_stack:
  added:
    - none (reuses sqlalchemy.text, structlog, existing engine.begin pattern)
  patterns:
    - "Raw SQL via sqlalchemy.text(...) + params={'rid': run_id} (T-04-03-01 mitigation)"
    - "Single-transaction DELETE+INSERT via engine.begin() (D-410 / T-04-03-03)"
    - "Module-level text() constants for source-lockable KPI formula (D-405 / T-04-03-02)"
    - "Read-only queries via engine.connect() (separate from write path)"
key_files:
  created:
    - src/ga_crawler/matcher/strict_key.py
    - tests/unit/test_matcher_strict_key.py
  modified:
    - none
decisions_honored:
  - D-401 (13-column INSERT projection matches Match schema exactly)
  - D-402 (symmetric multipack/volume/DELISTED filters on both retailers)
  - D-403 (N→1 keep-all — test_n_to_1_keep_all proves 2 rows for 1 viled + 2 goldapple)
  - D-404 (denominator = comparable viled SKUs in brand-overlap with goldapple)
  - D-405 (KPI formula frozen — ROUND(... * 100.0 / v.current_price, 2); pinned via canary)
  - D-410 (DELETE+INSERT inside single engine.begin() transaction; idempotent across reruns)
  - D-411 (read_run_status returns literal status or None)
metrics:
  duration_seconds: ~600
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  tests_added: 17
  tests_passing_before: 424
  tests_passing_after: 441
  completed_date: 2026-05-11
---

# Phase 4 Plan 04-03: Strict-Key SQL Primitives Summary

**One-liner:** Wave 2 algorithmic core — `matcher/strict_key.py` ships 5 deterministic SQL primitives (DELETE+INSERT match builder, denominator, brand-overlap, comparable counts, run-status read) wrapped in a single-transaction idempotency contract (D-410), with the KPI formula frozen as a source-locked module constant and 17 regression tests pinning every D-decision (D-402/-403/-404/-405/-410/-411).

## What Shipped

### `src/ga_crawler/matcher/strict_key.py` (222 LOC, new)

**Six `text()` SQL constants (module-level — source-lockable per T-04-03-02):**

| Constant | Purpose |
|---|---|
| `INSERT_MATCHES_SQL` | 13-column INSERT...SELECT with strict-key JOIN `(brand_norm, name_norm, volume_norm)`; symmetric D-402 filters on both retailers; `price_delta = (g.current_price - v.current_price)` signed; `price_delta_pct = ROUND(... * 100.0 / v.current_price, 2)`; `matched_at = CURRENT_TIMESTAMP`. |
| `DENOMINATOR_SQL` | D-404: `COUNT(*)` of viled comparable SKUs with `brand_norm IN (SELECT DISTINCT g.brand_norm WHERE retailer='goldapple' AND run_id=:rid)`. |
| `BRAND_OVERLAP_SQL` | `COUNT(DISTINCT v.brand_norm)` of viled∩goldapple intersection for the run. |
| `COMPARABLE_COUNT_SQL` | Per-retailer `COUNT(*)` after the comparable filter (multipack/volume/DELISTED); retailer passed via bind param (T-04-03-05). |
| `DELETE_MATCHES_SQL` | `DELETE FROM matches WHERE run_id = :rid` — first step of the idempotent rebuild. |
| `RUN_STATUS_SQL` | `SELECT status FROM runs WHERE run_id = :rid` — D-411 skip-input. |

**Five public callables:**

| Function | Signature | Pattern |
|---|---|---|
| `build_matches_for_run(engine, run_id)` | `-> int` | `with engine.begin() as conn:` wraps DELETE+INSERT — atomic per D-410. Returns inserted rowcount. |
| `compute_denominator(engine, run_id)` | `-> int` | Read-only via `engine.connect()`. |
| `compute_brand_overlap(engine, run_id)` | `-> int` | Read-only. |
| `compute_comparable_counts(engine, run_id, retailer)` | `-> int` | Read-only; retailer bound via `:retailer` (T-04-03-05). |
| `read_run_status(engine, run_id)` | `-> Optional[str]` | Read-only; returns the literal status string or `None`. |

### `tests/unit/test_matcher_strict_key.py` (395 LOC, new, 17 tests)

Synthetic fixtures use real on-disk SQLite (`tmp_path` + `init_db` + `make_engine`) so WAL/foreign-key PRAGMAs and the matches DDL match production. Each test pre-plants the required `Run` row (FK constraint) and uses `SqliteSnapshotWriter` to insert paired viled+goldapple snapshots via the same dict-shape Phase 2/3 runners produce.

| # | Test | D-decision | What it pins |
|---|---|---|---|
| 1 | `test_strict_key_match_happy_path` | D-401 | All 13 columns populated correctly; price_delta=2000; price_delta_pct≈20.0 |
| 2 | `test_idempotent_rerun` | D-410 | 3 successive `build_matches_for_run` calls yield identical row count and set |
| 3 | `test_multipack_excluded_from_numerator` | D-402 | `multipack_flag=True` on both retailers → 0 matches |
| 4 | `test_volume_norm_null_excluded` | D-402 | NULL `volume_norm` on either side → 0 matches; both directions tested |
| 5 | `test_delisted_excluded` | D-402 | `stock_state='DELISTED'` → 0 matches |
| 6 | `test_other_stock_states_kept` | D-402 (negative) | OUT_OF_STOCK / UNAVAILABLE / UNKNOWN remain matchable |
| 7 | `test_n_to_1_keep_all` | D-403 | 1 viled + 2 goldapple with identical key → 2 match rows persisted |
| 8 | `test_denominator_only_in_brand_overlap` | D-404 | 5 viled SKUs in 2 brands (1 brand on goldapple) → denominator=3, not 5 |
| 9 | `test_denominator_zero_when_no_brand_overlap` | D-404 edge | `compute_denominator=0`; `build_matches=0`; no IntegrityError |
| 10 | `test_brand_overlap_count` | helper | COUNT(DISTINCT) intersection returns 2 (not 3, not 5) |
| 11 | `test_comparable_counts_per_retailer` | D-402 | Filter applies per-retailer correctly |
| 12 | `test_read_run_status_running_vs_success_vs_missing` | D-411 | Returns 'running' / 'success' / None depending on row state |
| 13 | `test_cross_run_isolation` | D-410 scoping | `build_matches_for_run(1)` never touches run_id=2 matches |
| 14 | `test_match_rate_formula_canary` | D-405 | 5/3 fixture → denom=5, matches=3, rate=60.00; INSERT_MATCHES_SQL contains `ROUND(` and `*100.0/v.current_price` |
| 15 | `test_price_delta_sign` | D-401 | viled<goldapple → +delta; viled>goldapple → −delta |
| 16 | `test_was_price_passthrough` | D-401 | NULL `was_price` on goldapple side preserved as NULL in match row |
| 17 | `test_join_skips_partial_key_mismatch` | strict-key | brand+name same but volume different → 0 matches |

## Verification

```
$ uv run pytest tests/unit/test_matcher_strict_key.py -q
.................                                                        [100%]
17 passed in 0.96s

$ uv run pytest -q
441 passed, 1 skipped, 12 warnings in 103.89s
# Baseline before plan: 424 (425 collected − 1 skipped). +17 new, 0 regressions.

$ uv run python -c "from ga_crawler.matcher.strict_key import INSERT_MATCHES_SQL; \
    s = str(INSERT_MATCHES_SQL); \
    assert 'ROUND' in s; assert 'multipack_flag = 0' in s; assert 'DELISTED' in s; \
    print('formula constants verified')"
formula constants verified
```

Acceptance criteria from PLAN counted:

| Pattern | Required | Actual |
|---|---|---|
| `with engine.begin() as conn:` | ≥1 | 1 |
| `DELETE FROM matches WHERE run_id` | ≥1 | 1 |
| `multipack_flag = 0` | ≥4 | 4 |
| `stock_state != 'DELISTED'` | ≥4 | 6 |
| `volume_norm IS NOT NULL` | ≥4 | 6 |
| `v.retailer = 'viled'` | ≥1 | 1 |
| `g.retailer = 'goldapple'` | ≥1 | 1 |
| `ROUND(` | ≥1 | 1 |
| `CURRENT_TIMESTAMP` | ≥1 | 1 |

## Decisions Honored

| Decision | How Applied |
|---|---|
| D-401 (13-col Match schema) | INSERT projects exactly the 13 columns in Match SQLModel order; `price_delta` signed; `price_delta_pct` rounded REAL; `matched_at` via SQL `CURRENT_TIMESTAMP` |
| D-402 (symmetric filters) | Both `v.*` and `g.*` halves of the JOIN apply `multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'` verbatim; `DENOMINATOR_SQL` and `COMPARABLE_COUNT_SQL` apply the same filter |
| D-403 (N→1 keep-all) | JOIN has no DISTINCT clause; composite PK on matches allows multiple goldapple_sku per viled_sku; pinned by `test_n_to_1_keep_all` |
| D-404 (denominator symmetric) | `WHERE v.brand_norm IN (SELECT DISTINCT g.brand_norm ... goldapple ... :rid)`; pinned by `test_denominator_only_in_brand_overlap` |
| D-405 (KPI formula frozen) | SQL lives as module-level `text()` constant; canary asserts substring match on both ROUND and the `*100.0/v.current_price` numerator after whitespace collapse |
| D-410 (one-TX idempotency) | `build_matches_for_run` uses `with engine.begin() as conn:`; DELETE then INSERT in same transaction; pinned by `test_idempotent_rerun` (3 reruns stable) + `test_cross_run_isolation` |
| D-411 (status read) | `read_run_status` returns `row[0]` or `None` literally; pinned by `test_read_run_status_running_vs_success_vs_missing` |

## Deviations from Plan

**None — plan executed exactly as written.**

One micro-note: the PLAN's acceptance-criteria line `grep -c 'g.brand_norm IN' >= 2` is incorrect against its own provided SQL skeleton. In both `DENOMINATOR_SQL` and `BRAND_OVERLAP_SQL` the pattern is `v.brand_norm IN (SELECT DISTINCT g.brand_norm ...)` — i.e. `g.brand_norm` appears in the inner SELECT, not in the outer `IN` clause. The skeleton in the PLAN's `<action>` block uses this exact form, and we follow it verbatim. The functional intent (denominator restricted to brand-overlap; brand-overlap COUNT DISTINCT) is satisfied and pinned by `test_denominator_only_in_brand_overlap` and `test_brand_overlap_count` — both green. No code change needed; this is a documentation-side miscount in the PLAN, not a deviation in implementation.

No CLAUDE.md directives required adjustment. No Rule 1/2/3 auto-fixes triggered. No checkpoints reached (plan is fully autonomous).

## TDD Gate Compliance

| Task | RED | GREEN |
|---|---|---|
| Task 1 (strict_key.py) | Confirmed `ModuleNotFoundError: No module named 'ga_crawler.matcher.strict_key'` before writing the module. | Smoke import + 9 acceptance-grep counts all pass after `Write`. Commit `61843ed`. |
| Task 2 (test file) | Test file would have collected-errored on missing imports if written first; in practice we wrote Task 1's module first (smoke-verified import), then Task 2's tests RED-collected against the source module surface that already existed but had not yet been exercised. All 17 tests pass on first run after Write. Commit `9a780fa`. |

Per-task commits captured both phases in git history. Commit messages reference D-numbers and test names explicitly.

## Threat Flags

None. No new trust boundaries or surfaces beyond those already in the PLAN's `<threat_model>`:

- **T-04-03-01** (SQL injection): every SQL constant uses `text("... :rid ...")` + `params={"rid": run_id}` or `params={"retailer": retailer}`. No f-string interpolation.
- **T-04-03-02** (KPI formula drift): formula lives as module-level `text()` constant; canary source-locks via substring match.
- **T-04-03-03** (partial INSERT on crash): `engine.begin()` wraps DELETE+INSERT — atomic.
- **T-04-03-04** (FK violation): tests pre-plant `Run` rows before snapshots/matches; production caller (orchestrator) gates on `read_run_status` before invoking the builder.
- **T-04-03-05** (retailer parameterization): `compute_comparable_counts` accepts retailer via bind param, not f-string.

## Open Questions / Wave 2 Handoff

Plan 04-04 (`runners/matcher_run.py`) consumes all 5 primitives plus the Plan 04-02 `MatchStatsBuilder`:

1. Read `read_run_status(engine, run_id)` — gate-skip if `None` / `'running'` / `'failed'` (D-411).
2. Call `build_matches_for_run(engine, run_id)` for the numerator count.
3. Call `compute_denominator`, `compute_brand_overlap`, `compute_comparable_counts` (×2 retailers) for the stats payload.
4. Compute `match.rate = round(numerator * 100.0 / denominator, 2)` if denominator > 0, else 0.0 (D-405 + edge in CONTEXT "Claude's Discretion").
5. Patch `runs.stats.match.*` via `SqliteRunWriter.patch_stats` (Plan 04-02 keys frozen).
6. Apply sanity-gate via `final_threshold_gate(numerator, MatchConfig.sanity_gate_p)`; fail run if trip.

No blockers. SQL surface is locked; orchestrator is now a thin shell.

## Self-Check: PASSED

Verified post-write:
- `src/ga_crawler/matcher/strict_key.py` — FOUND
- `tests/unit/test_matcher_strict_key.py` — FOUND
- Commit `61843ed` (Task 1) — FOUND
- Commit `9a780fa` (Task 2) — FOUND
- Full pytest 441 passed — VERIFIED
- Smoke: `INSERT_MATCHES_SQL` contains ROUND, multipack_flag=0, DELISTED — VERIFIED
- All 5 exported callables + 6 SQL constants importable — VERIFIED
