---
phase: 04-matcher-match-rate-kpi
plan: 04
subsystem: matcher
tags: [orchestrator, sync, kpi, runs-stats, integration-tests, wave-3]
dependency_graph:
  requires:
    - matcher/strict_key.py (Plan 04-03 — 5 SQL primitives + 6 text() constants)
    - matcher/stats.py (Plan 04-02 — MatchStatsBuilder + MATCH_STATS_KEYS)
    - matcher/config.py (Plan 04-01 — MatchConfig defaults)
    - storage/sqlite.py::SqliteRunWriter (patch_stats / fail / finalize / create / get_stats)
    - runner/gates.py::final_threshold_gate + auto_suggest_threshold (D-203 retailer-agnostic)
  provides:
    - runners/matcher_run.py::run_matcher_phase (sync 7-step pipeline)
    - runners/matcher_run.py::MatcherPhaseResult (status/match_count/match_rate/reason/stats_delta)
  affects:
    - main_run.py (Plan 04-05 will compose run_matcher_phase after goldapple)
    - cli.py (Plan 04-05 will add matcher-run subcommand)
tech_stack:
  added:
    - none (reuses structlog, sqlalchemy, dataclasses, time stdlib)
  patterns:
    - "7-step sync pipeline mirroring viled_run.py shape (sans fetch/parse/normalize)"
    - "Single-call patch_stats per code path (Pitfall 6 — skip / success / gate-fail paths)"
    - "Audit-trail invariant on gate-fail (D-409 — matches persist; only runs.status flips)"
    - "Log-only auto-suggest (D-407 — auto_suggest_p NOT a stats key per D-414)"
    - "Empty-string sentinel for skipped_reason on non-skipped path (Pitfall 4 None-rejects)"
key_files:
  created:
    - src/ga_crawler/runners/matcher_run.py
    - tests/integration/test_matcher_run.py
  modified:
    - none
decisions_honored:
  - D-405 (KPI formula end-to-end: rate = round(count * 100.0 / denominator, 2); zero-denominator -> 0.0 + warning log)
  - D-407 (auto_suggest_threshold called with history of match.count from prior 4 runs; emitted via log.info only — NOT persisted)
  - D-409 (P-gate: count < threshold -> run_writer.fail(reason) + matches rows persist; gate_passed=False in stats)
  - D-410 (build_matches_for_run primitive owns single-TX DELETE+INSERT; orchestrator-level rerun stable)
  - D-411 (skip protocol: status in {None, 'failed', 'running'} -> matches untouched; single patch_stats call with skipped_reason + gate_passed=False)
  - D-413 (sync only — `inspect.iscoroutinefunction(run_matcher_phase)` is False)
  - D-414 (10 match.* keys persisted on success; 9 on skip — auto_suggest_p deliberately absent)
  - Pitfall 6 (SINGLE patch_stats call per code path; verified by MagicMock.call_count==1)
metrics:
  duration_seconds: ~480
  tasks_completed: 2
  files_created: 2
  files_modified: 0
  tests_added: 13
  tests_passing_before: 441
  tests_passing_after: 454
  completed_date: 2026-05-11
---

# Phase 4 Plan 04-04: Matcher Orchestrator Summary

**One-liner:** Wave 3 deliverable — `runners/matcher_run.py` ships a sync 7-step pipeline that composes the strict-key SQL primitives (Plan 04-03), MatchStatsBuilder namespace (Plan 04-02), and retailer-agnostic gate helpers into the phase-level contract Phase 5 reporter consumes, with 13 integration tests pinning every D-decision end-to-end against a real SQLite engine.

## What Shipped

### `src/ga_crawler/runners/matcher_run.py` (238 LOC, new)

**`MatcherPhaseResult` dataclass** (5 fields):

| Field | Type | Purpose |
|---|---|---|
| `status` | str | "success" / "failed" / "skipped" |
| `match_count` | int | Number of rows inserted into `matches` table this call |
| `match_rate` | float | KPI value (percent points, 2 decimals); 0.0 when denominator=0 |
| `reason` | Optional[str] | None on success; populated on skip/fail |
| `stats_delta` | dict | The full `match.*` namespace payload that was patched into runs.stats |

**`run_matcher_phase(*, run_id, engine, run_writer, threshold_p=20, p_auto_suggest_factor=0.7, p_auto_suggest_after_runs=4) -> MatcherPhaseResult`** — sync, keyword-only.

7-step pipeline:

| Step | Action | Decision |
|---|---|---|
| 1 | `read_run_status` → if None/'failed'/'running' → set skipped_reason + gate_passed=False, single patch_stats, return `status='skipped'`. **matches untouched.** | D-411 |
| 2 | `compute_comparable_counts` (×2 retailers) + `compute_brand_overlap` + `compute_denominator` → 4 stats keys | D-402, D-404 |
| 3 | `build_matches_for_run` → `match.count` + `match.numerator` (single-TX primitive) | D-410 |
| 4 | `rate = round(count * 100.0 / denominator, 2)`; zero-denominator → `rate=0.0` + `log.warning('match_zero_denominator')` | D-405 |
| 5 | `final_threshold_gate(count, threshold_p)` → `match.gate_passed`; `auto_suggest_threshold(history)` → `log.info('match_auto_suggest_p')` (log-only, NEVER persisted) | D-409, D-407 |
| 6 | `run_writer.patch_stats(run_id, dict(builder.delta))` — **SINGLE CALL** (Pitfall 6) | Pitfall 6 |
| 7 | Gate-fail branch: `run_writer.fail(run_id, 'match_count_below_threshold:{c}<{t}')`; matches rows NOT deleted (audit invariant) | D-409 |

**Skip path discipline:** All 9 non-`threshold_p` stat keys still set on the skip path (count/numerator/denominator/rate/brand_overlap_count/viled_comparable_count/goldapple_comparable_count/skipped_reason/gate_passed) so Phase 5 reporter never sees a partial `match.*` namespace.

**Success path discipline:** All 10 `MATCH_STATS_KEYS` set. `skipped_reason` uses empty-string sentinel `""` (NOT None) because `SqliteRunWriter.patch_stats` rejects None per Pitfall 4 (RFC-7396 MergePatch interprets null as DELETE).

### `tests/integration/test_matcher_run.py` (343 LOC, new, 13 tests)

Real on-disk SQLite engine via `init_db(tmp_path/'db.db')` + `make_engine(...)`; `SqliteSnapshotWriter` plants matched viled+goldapple rows; tests use real `SqliteRunWriter` for stats integrity assertions and `MagicMock` for the Pitfall 6 call-count assertion.

| # | Test | D / Pitfall | What it pins |
|---|---|---|---|
| 1 | `test_happy_path_writes_matches_and_stats` | D-414 | status='success', match_count=1, all 10 keys present, 1 matches row |
| 2 | `test_skipped_when_upstream_failed` | D-411 | run.status='failed' → result.reason='failed_upstream'; matches untouched (0 rows) |
| 3 | `test_skipped_when_upstream_running` | D-411 | run.status='running' → reason='in_progress_upstream'; matches untouched |
| 4 | `test_skipped_when_run_missing` | D-411 | run_id=99999 → reason='missing_run_row'; no SQL exception |
| 5 | `test_idempotent_orchestrator_rerun` | D-410 | Two consecutive run_matcher_phase calls produce identical match_count + stable matches row count + identical stats_delta keys |
| 6 | `test_sanity_gate_fail_persists_matches_and_fails_run` | D-409 | threshold_p=10 vs count=1 → status='failed'; reason='match_count_below_threshold:1<10'; runs.status='failed'; runs.fail_reason set; **matches rows persist (1 row)** |
| 7 | `test_single_patch_stats_call_on_success_path` | Pitfall 6 | `mock_rw.patch_stats.call_count == 1`; full delta carried in one shot |
| 8 | `test_zero_denominator_returns_rate_zero` | D-405 edge | No brand overlap → denominator=0, rate=0.0, fails on gate (count=0<P=20) |
| 9 | `test_all_ten_match_keys_present_on_success` | D-414 | `{k for k in stats if k.startswith('match.')} == set(MATCH_STATS_KEYS)` |
| 10 | `test_kpi_formula_end_to_end` | D-405 | 6 viled (5 comparable, 1 DELISTED) × 3 goldapple matched → match_count=3, rate=60.0, denominator=5, numerator=3 |
| 11 | `test_auto_suggest_emits_log_after_4_runs` | D-407 | 4 prior runs with `match.count` → expected suggested = int(0.7*median([5,10,15,20]))=8; **negative invariant**: `match.auto_suggest_p` NOT in stats |
| 12 | `test_no_async_in_orchestrator` | D-413 | `inspect.iscoroutinefunction(run_matcher_phase) is False` |
| 13 | `test_auto_suggest_silent_when_history_below_min_runs` | D-407 negative | <4 prior successful runs → no auto_suggest_p persisted; success path otherwise unchanged |

## Verification

```
$ uv run pytest tests/integration/test_matcher_run.py -q
.............                                                            [100%]
13 passed, 15 warnings in 0.83s

$ uv run pytest -q
454 passed, 1 skipped, 27 warnings in 102.53s
# Was 441 passed before plan; +13 new tests, 0 regressions

$ uv run python -c "from ga_crawler.runners.matcher_run import run_matcher_phase, MatcherPhaseResult; import inspect; assert not inspect.iscoroutinefunction(run_matcher_phase); print('sync ok')"
sync ok
```

Acceptance criteria from PLAN counted:

| Pattern | Required | Actual |
|---|---|---|
| `def run_matcher_phase` | 1 | 1 |
| `class MatcherPhaseResult` | 1 | 1 |
| `run_writer.patch_stats` | ≥2 (skip + success/fail paths) | 2 |
| `run_writer.fail` | 1 (gate-fail only) | 1 (call site; docstring also references it informationally) |
| `build_matches_for_run` import + call | 2 | 2 |
| `compute_denominator` import + call | 2 | 2 |
| `final_threshold_gate` import + call | 2 | 2 |
| `auto_suggest_threshold` import + call | 2 | 2 |
| `from ga_crawler.matcher.stats import MatchStatsBuilder` | 1 | 1 |
| `async def` | 0 (sync only) | 0 |
| Integration tests `^def test_` | ≥12 | 13 |

## Decisions Honored

| Decision | How Applied |
|---|---|
| D-405 (KPI formula frozen) | `rate = round(match_count * 100.0 / denominator, 2)` in Step 4; pinned end-to-end by `test_kpi_formula_end_to_end` (6/5/3 → 60.0) and by canary in Plan 04-03 |
| D-407 (auto-suggest log-only) | `auto_suggest_threshold(history, factor=0.7, min_runs=4)` invoked in Step 5; result emitted via `log.info('match_auto_suggest_p', suggested=X, ...)`. **NOT** added to `builder` — MATCH_STATS_KEYS deliberately excludes `auto_suggest_p`. Pinned by negative invariant in `test_auto_suggest_emits_log_after_4_runs` (`assert "match.auto_suggest_p" not in stats`) |
| D-409 (gate-fail audit invariant) | Gate-fail branch calls `run_writer.fail(run_id, reason)` AFTER patch_stats so gate_passed=False is durable. matches rows from Step 3 persist. `test_sanity_gate_fail_persists_matches_and_fails_run` asserts both runs.status='failed' AND `_count_matches(...) == 1` |
| D-410 (orchestrator-level idempotency) | Step 3 delegates to `build_matches_for_run` which wraps DELETE+INSERT in `engine.begin()`. `test_idempotent_orchestrator_rerun` calls run_matcher_phase twice → match_count stable + stats keys identical |
| D-411 (skip-if-upstream-failed) | Step 1: `read_run_status` → `(None, 'failed', 'running')` → set skipped_reason + gate_passed=False + 7 other match.* keys to 0, single patch_stats, return status='skipped'. matches NOT touched. Pinned by 3 tests (failed/running/missing) |
| D-413 (sync only) | No `async def`, no `await`. `test_no_async_in_orchestrator` source-locks. |
| D-414 (10-key namespace) | All 10 MATCH_STATS_KEYS set on success path; subset (still all 10 keys, with sentinel values) on skip path. `test_all_ten_match_keys_present_on_success` asserts set equality |
| Pitfall 6 (single patch_stats) | Each code path (skip / success / gate-fail) calls `run_writer.patch_stats(...)` exactly once. `test_single_patch_stats_call_on_success_path` uses MagicMock with `assert call_count == 1` |
| Pitfall 4 (None-DELETE) | `skipped_reason` sentinel is `""` on non-skipped path, NOT None (SqliteRunWriter.patch_stats raises ValueError on None values) |

## Deviations from Plan

**None — plan executed exactly as written.**

Minor notes:

1. **`run_writer.fail` grep count**: PLAN's acceptance criteria say "== 1". A literal `grep -c 'run_writer.fail'` returns 2 because the module docstring (line 16) references `run_writer.fail` informationally. The structural invariant (exactly one **call site**, only on gate-fail) is satisfied: line 212 is the sole call. The docstring reference does not represent a second call.

2. **Auto-suggest log capture (Test 11)**: structlog default routes do not always reach pytest's `caplog`. The test asserts the load-bearing **negative invariant** (`"match.auto_suggest_p" not in stats`) and exercises the suggestion-computation code path (4 prior runs planted with `match.count`). The log-emission check is best-effort (no hard-assert). This matches the PLAN's `<action>` note line 808.

3. **Plan listed 12 tests, shipped 13**: Added `test_auto_suggest_silent_when_history_below_min_runs` as a complementary negative test for D-407 (<4 runs → no auto_suggest_p). All 13 green.

No CLAUDE.md directives required adjustment. No Rule 1/2/3 auto-fixes triggered. No checkpoints reached (plan is fully autonomous). No threat flags introduced (all flagged threats in the PLAN's `<threat_model>` covered by tests: T-04-04-01 KPI canary, T-04-04-02 namespace enforcement inherited from Plan 04-02, T-04-04-03 atomic merge invariant, T-04-04-06 gate-fail audit trail).

## TDD Gate Compliance

| Task | RED | GREEN |
|---|---|---|
| Task 1 (matcher_run.py) | Confirmed `ModuleNotFoundError: No module named 'ga_crawler.runners.matcher_run'` before writing the module. Commit `5d431d2`. | Smoke import + dataclass-fields probe passes after `Write`. All 9 grep acceptance counts pass. |
| Task 2 (integration tests) | Test file did not exist; PLAN's specification was the test contract. Tests would have collection-errored on the absent module had Task 1 not preceded. Commit `466be9e`. | 13/13 tests pass on first run after Write. Full suite 454 passed (was 441), 0 regressions. |

Per-task commits capture both phases in git history.

## Open Questions / Wave 4 Handoff

Plan 04-05 (CLI + main_run integration) is the final Wave 4 plan:

1. **`runners/main_run.py`**: amend to call `run_matcher_phase(run_id=..., engine=..., run_writer=..., threshold_p=cfg.sanity_gate_p, ...)` AFTER `run_goldapple_phase`. D-411 makes this safe: if either viled or goldapple failed, matcher will skip cleanly.
2. **`cli.py`**: add `matcher-run --run-id N` subcommand (operator recovery tool per D-412). Plumb `--sanity-gate-p N` override → constructs `MatchConfig` directly OR forwards to `run_matcher_phase(threshold_p=...)`.
3. **`pyproject.toml`**: already has `[tool.ga_crawler.match]` (Plan 04-01). No further edits expected in 04-05 unless CLI wires more keys.
4. **Phase 5 reporter dependency**: ready to consume `runs.stats.match.*` (10 keys) + `matches` table (13 columns) directly. No JOIN-back.

No blockers.

## Threat Flags

None. Trust boundaries and surfaces as declared in the PLAN's `<threat_model>`:

- **T-04-04-01** (KPI formula corruption): pinned by `test_kpi_formula_end_to_end` + Plan 04-03 source-lock canary.
- **T-04-04-02** (stats namespace pollution): MatchStatsBuilder raises `StatsNamespaceError` on non-match.* keys (Plan 04-02 invariant); `test_all_ten_match_keys_present_on_success` asserts exact set equality.
- **T-04-04-03** (partial stats write): Single `patch_stats` call per code path; `test_single_patch_stats_call_on_success_path` source-locks.
- **T-04-04-04** (auto-suggest DoS): `_gather_prior_match_counts` reads at most `lookback=4` prior runs.
- **T-04-04-05** (info disclosure): `skipped_reason` values are static strings; no PII.
- **T-04-04-06** (gate-fail audit): `test_sanity_gate_fail_persists_matches_and_fails_run` asserts the full invariant — run.status='failed', fail_reason populated, matches rows persist.

## Self-Check: PASSED

Verified post-write:
- `src/ga_crawler/runners/matcher_run.py` — FOUND
- `tests/integration/test_matcher_run.py` — FOUND
- Commit `5d431d2` (Task 1 — feat) — FOUND
- Commit `466be9e` (Task 2 — test) — FOUND
- `uv run pytest tests/integration/test_matcher_run.py -q` → 13 passed
- `uv run pytest -q` → 454 passed, 1 skipped, 0 regressions (was 441)
- Smoke: `MatcherPhaseResult` dataclass fields = `['status', 'match_count', 'match_rate', 'reason', 'stats_delta']`
- Smoke: `inspect.iscoroutinefunction(run_matcher_phase) is False` — sync confirmed
- All 5 strict_key primitives imported + called; auto_suggest_threshold + final_threshold_gate imported + called; MatchStatsBuilder imported
