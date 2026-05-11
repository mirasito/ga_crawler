---
phase: 04-matcher-match-rate-kpi
plan: 05
subsystem: composition-cli
tags: [orchestrator, cli, composition, wave-4, integration-tests]
dependency_graph:
  requires:
    - runners/matcher_run.py::run_matcher_phase (Plan 04-04)
    - matcher/config.py::MatchConfig.from_pyproject (Plan 04-01)
    - storage/sqlite.py::SqliteRunWriter (existing — finalize/fail/patch_stats lifecycle)
    - runners/goldapple_run.py::PhaseResult (existing — composed-after by matcher)
  provides:
    - runners/main_run.py::run_weekly with matcher composition + sanity_gate_p kwarg
    - runners/main_run.py::MainRunResult.match_count + match_rate fields
    - cli.py::_cmd_matcher (D-412 standalone matcher-run subcommand)
    - cli.py::weekly-run --sanity-gate-p flag
  affects:
    - Phase 5 reporter (will consume runs.stats.match.* keys end-to-end through weekly-run)
    - Phase 7 ops (cron weekly-run will produce match-rate KPI; matcher-run for recovery)
tech_stack:
  added:
    - none (reuses argparse, subprocess for tests, MatchConfig/run_matcher_phase from earlier plans)
  patterns:
    - "Composition layer pre-finalizes runs row BEFORE matcher so D-411 read_run_status sees 'success'; D-409 fail() flips back on gate-trip"
    - "Matcher composition skipped in *_only modes (matcher needs both retailer datasets)"
    - "Idempotent finalize via WHERE status='running' guard — safe to call twice (pre-matcher + post-matcher) on success path"
    - "CLI subprocess integration test pattern: invoke via `sys.executable -m ga_crawler ...`, capture stdout/stderr, assert substring + returncode"
    - "argparse type=int as defence-in-depth on --run-id (T-04-05-01 SQL injection class)"
key_files:
  created:
    - tests/integration/test_cli_matcher_subcommand.py
  modified:
    - src/ga_crawler/runners/main_run.py
    - src/ga_crawler/cli.py
    - tests/integration/test_main_run_e2e.py
decisions_honored:
  - D-411 (skip-protocol delegated to matcher; composition layer does NOT pre-gate on upstream status)
  - D-412 (CLI shape: standalone matcher-run --run-id N for recovery + weekly-run composition)
  - D-409 (gate-fail audit-trail: matcher fail() flips runs.status to 'failed'; matches rows persist; MainRunResult(status='failed') returned)
  - D-410 (idempotency: matcher-run against same run_id twice is stable — DELETE+INSERT in single TX inside primitive)
  - D-405/-407/-414 (matcher's own invariants inherited unchanged from Plan 04-04)
metrics:
  duration_seconds: ~720
  tasks_completed: 2
  files_created: 1
  files_modified: 3
  tests_added: 11
  tests_passing_before: 454
  tests_passing_after: 465
  completed_date: 2026-05-11
---

# Phase 4 Plan 04-05: Matcher Composition + CLI Subcommand Summary

**One-liner:** Wave 4 closer — composes `run_matcher_phase` into `run_weekly` after the goldapple phase (with D-411-aware pre-finalize), extends `MainRunResult` with match_count/match_rate, and ships the `matcher-run --run-id N [--sanity-gate-p P]` standalone CLI (D-412 recovery tool) plus a new `--sanity-gate-p` flag on `weekly-run`, validated by 11 new integration tests against real SQLite + subprocess CLI invocations.

## What Shipped

### `src/ga_crawler/runners/main_run.py` (amended; +52/-1 LOC)

**`MainRunResult` dataclass — 2 new fields:**

| Field | Type | Default | Purpose |
|---|---|---|---|
| `match_count` | int | 0 | Plan 04-05 — matches table row count for the run |
| `match_rate` | float | 0.0 | Plan 04-05 — match-rate percent (numerator/denominator × 100, 2 decimals) |

**`run_weekly` signature — 1 new kwarg:**

```python
def run_weekly(
    repo_root: Path | str,
    *,
    db_path: str | Path = "prices.db",
    headless: bool = True,
    viled_only: bool = False,
    goldapple_only: bool = False,
    sanity_gate_n: Optional[int] = None,
    sanity_gate_m: Optional[int] = None,
    sanity_gate_p: Optional[int] = None,  # NEW — Plan 04-05 P-gate override
    aliases_path: Optional[Path | str] = None,
    pyproject_path: Path | str = "pyproject.toml",
) -> MainRunResult: ...
```

**Composition step (new block after goldapple, before Norm06):**

1. Skipped entirely in `viled_only` / `goldapple_only` modes (matcher needs both retailer datasets).
2. **Pre-finalize** `run_writer.finalize(run_id, status='success')` so `read_run_status` returns `'success'` instead of `'running'`. Without this, D-411 would skip the matcher inside every composed run (the run is mid-flight when matcher is invoked).
3. Resolve `effective_p = sanity_gate_p or MatchConfig.from_pyproject(pyproject_path).sanity_gate_p`.
4. Call `run_matcher_phase(...)`; accumulate `m_result.stats_delta` into `stats_delta_acc`; capture `match_count` + `match_rate`.
5. Branch on `m_result.status`:
   - `'failed'` → write Norm06 ledger, log `weekly_run_matcher_failed`, **early-return** `MainRunResult(status='failed', reason=...)`. `run_writer.fail` was already called by the matcher (D-409); `fail()` has no status guard so it overrides the earlier pre-finalize cleanly.
   - `'skipped'` → log `weekly_run_matcher_skipped`, fall through to Norm06 + final `finalize` (skip is NOT a run-failure; mirrors Phase 3 "representative run" semantics).
   - `'success'` (implicit) → fall through to Norm06 + final `finalize`.
6. Final `run_writer.finalize(run_id, status='success')` at the bottom is **idempotent** thanks to the `WHERE status='running'` guard — on the composed path, finalize was already done pre-matcher; this call is a no-op. In `*_only` modes (no matcher), this is the canonical close.

**Architectural note (Rule 1 fix):** The plan's `<truths>` block stated "matcher's skip-protocol (D-411) handles upstream-failure on its own — the composition layer does NOT pre-gate." But D-411's `read_run_status` accepts ONLY `'success'`/`'partial'` and treats `'running'` as a skip condition. Inside `run_weekly`, the runs row is always `'running'` at the matcher's call site (finalize has not happened yet). Without intervention, every composed matcher call would skip silently and produce 0 matches in production. The pre-finalize-before-matcher pattern resolves this contract gap while preserving D-409 (gate-fail flips back via `fail()`). Documented inline; pinned by `test_run_weekly_composes_matcher_step` end-to-end. See Deviations section below.

### `src/ga_crawler/cli.py` (amended; +113/-5 LOC)

**`_cmd_matcher` handler (new, ~50 LOC):** D-412 standalone recovery tool. Reads existing snapshots for `--run-id N`, invokes `run_matcher_phase`, prints JSON status payload, exits 0/2 based on result.status.

**`matcher-run` subparser (new):**

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--run-id` | int | required | runs.run_id of existing run to (re-)match |
| `--db-path` | str | `prices.db` | SQLite database file path |
| `--sanity-gate-p` | int | None (→ pyproject default 20) | Override P-threshold |
| `--pyproject` | str | `pyproject.toml` | Path to pyproject.toml for [tool.ga_crawler.match] |

**`weekly-run` subparser — new flag:**

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--sanity-gate-p` | int | None (→ pyproject default) | Plan 04-05: matcher P-threshold override |

**`weekly-run` JSON output extended with `match_count` + `match_rate` fields.**

### `tests/integration/test_main_run_e2e.py` (amended; +265/-2 LOC)

5 new Plan 04-05 tests added:

| # | Test | What it pins |
|---|---|---|
| 1 | `test_run_weekly_composes_matcher_step` | matcher step runs after goldapple; `match.*` keys present in stats; `match.count` in DB matches `result.match_count` |
| 2 | `test_run_weekly_matcher_gate_fail_returns_failed` | matcher P-gate trip → `MainRunResult(status='failed', reason='match_count_below_threshold:1<10')`; matches row persists (D-409 audit invariant); `runs.status='failed'` |
| 3 | `test_run_weekly_matcher_skip_still_finalizes_success` | matcher status='skipped' → composition continues; final run.status='success'; Norm06 ledger written; match.* keys from stub matcher delta merged into stats_delta |
| 4 | `test_run_weekly_only_flag_skips_matcher` | `viled_only=True` → matcher NOT invoked at all (not just D-411 skip); `match.*` keys absent from stats |
| 5 | `test_main_run_result_has_match_count_field` | `MainRunResult(status='success', run_id=1).match_count == 0` (dataclass default); explicit construction works |

Pre-existing 5 tests untouched and still green.

### `tests/integration/test_cli_matcher_subcommand.py` (new, 6 tests, ~155 LOC)

| # | Test | What it pins |
|---|---|---|
| 1 | `test_cli_help_lists_matcher_run` | top-level `--help` advertises the `matcher-run` subcommand |
| 2 | `test_cli_matcher_run_success` | `matcher-run --run-id N --sanity-gate-p 1` against planted snapshots → exit 0, JSON contains `"status": "success"` + `"match_count": 1` |
| 3 | `test_cli_matcher_run_gate_fail_exits_2` | `--sanity-gate-p 99` vs 1 match → exit 2, JSON shows `"status": "failed"` + `match_count_below_threshold` |
| 4 | `test_cli_matcher_run_skipped_when_upstream_failed` | run.status='failed' → matcher skips → exit 2, JSON shows `"status": "skipped"` + `failed_upstream` |
| 5 | `test_cli_matcher_run_requires_run_id` | argparse rejects missing `--run-id` (non-zero exit, mention of `--run-id` in stderr) |
| 6 | `test_cli_weekly_run_help_lists_sanity_gate_p` | `weekly-run --help` shows `--sanity-gate-p` flag |

All tests invoke CLI via `subprocess.run([sys.executable, '-m', 'ga_crawler', ...])` — true CLI smoke tests, not in-process mock calls.

## Verification

```
$ uv run pytest tests/integration/test_main_run_e2e.py tests/integration/test_cli_matcher_subcommand.py -q
................                                                         [100%]
16 passed in 2.91s

$ uv run pytest -q
465 passed, 1 skipped, 37 warnings in 107.16s
# Was 454 passed before this plan; +11 new tests, 0 regressions.

$ uv run python -m ga_crawler --help        # shows {goldapple-smoke, weekly-run, matcher-run}
$ uv run python -m ga_crawler matcher-run --help  # shows --run-id, --db-path, --sanity-gate-p, --pyproject
$ uv run python -m ga_crawler weekly-run --help   # shows --sanity-gate-p among existing flags
```

Acceptance criteria from PLAN:

| Pattern | Required | Actual |
|---|---|---|
| `from ga_crawler.runners.matcher_run import run_matcher_phase` in main_run.py | 1 | 1 |
| `from ga_crawler.matcher.config import MatchConfig` in main_run.py | 1 | 1 |
| `match_count: int = 0` in main_run.py | 1 | 1 |
| `match_rate: float = 0.0` in main_run.py | 1 | 1 |
| `run_matcher_phase(` call in main_run.py | ≥ 1 | 1 |
| `sanity_gate_p` references in main_run.py | ≥ 2 | 6 |
| `weekly_run_matcher_skipped` log key | 1 | 1 |
| `weekly_run_matcher_failed` log key | 1 | 1 |
| `def _cmd_matcher` in cli.py | 1 | 1 |
| `"matcher-run"` literal in cli.py | ≥ 2 | 2 |
| `"--sanity-gate-p"` in cli.py | ≥ 2 | 2 |
| `args.cmd == "matcher-run"` dispatch | 1 | 1 |
| `tests/integration/test_cli_matcher_subcommand.py` file | exists | yes |
| `^def test_cli_` count | ≥ 6 | 6 |

## Decisions Honored

| Decision | How Applied |
|---|---|
| D-411 (skip-protocol delegation) | `run_weekly` does NOT pre-gate on upstream phase status — it always invokes `run_matcher_phase`, which internally reads `runs.status` and decides skip vs proceed. The pre-finalize-before-matcher pattern ensures the matcher sees `'success'` (the run completed both retailer phases without phase-level failure return) so it proceeds. If the matcher would have skipped on a real `'failed'` upstream (which never happens in composition because we early-return on phase fail), the skip path still works — tested by `test_run_weekly_matcher_skip_still_finalizes_success` via stub matcher. |
| D-412 (CLI shape) | Two CLI surfaces: `matcher-run --run-id N` standalone (D-412 recovery tool) + `weekly-run` (composition; matcher always invoked). Mirror Phase 3 `goldapple-smoke` / `goldapple-run` subcommand pattern. |
| D-409 (gate-fail audit invariant) | When matcher returns `status='failed'`, `run_weekly` returns `MainRunResult(status='failed')` WITHOUT calling `run_writer.finalize` (matcher already called `fail()`). matches rows persist (verified by `test_run_weekly_matcher_gate_fail_returns_failed` counting matches WHERE run_id=N). `runs.status='failed'` confirmed via direct DB read. |
| D-410 (idempotency at composition) | `matcher-run` CLI subcommand against same run_id is idempotent via Plan 04-03 `build_matches_for_run` DELETE+INSERT-in-one-TX inside the primitive (verified upstream in Plan 04-04 test_idempotent_orchestrator_rerun; transitively inherited here). |
| Plan truths "When matcher returns status='skipped'... composition continues to Norm06 + finalize as success" | `test_run_weekly_matcher_skip_still_finalizes_success` pins this exact semantics via stubbed matcher returning `MatcherPhaseResult(status='skipped')`. |

## Deviations from Plan

### Rule 3 — Blocking issue fixed: pre-finalize before matcher

**Found during:** Task 1, first GREEN test run (`test_run_weekly_composes_matcher_step` failed with `match_count == 0` when expecting `>= 1`).

**Issue:** Plan's `<truths>` block stated "matcher's skip-protocol (D-411) handles upstream-failure on its own — the composition layer does NOT pre-gate." This assumes matcher would proceed when invoked inside `run_weekly`. But D-411's `read_run_status` (Plan 04-04 frozen primitive) treats `'running'` as a skip condition — and inside `run_weekly`, the `runs` row is ALWAYS in `'running'` state at the matcher's call site (finalize happens last, after Norm06). The matcher would silently skip EVERY composed call, never producing matches in production. The plan's intended composition semantics contradicted matcher_run.py's actual D-411 implementation.

**Fix:** Insert `run_writer.finalize(run_id, status='success')` BEFORE invoking `run_matcher_phase` so D-411 sees `'success'` and proceeds. On D-409 gate-fail, the matcher's own `run_writer.fail(...)` flips status back to `'failed'` — `fail()` has no status guard (DATA-05 idempotency invariant). On success or skip paths, the final `finalize()` call at the bottom of `run_weekly` is a no-op thanks to its `WHERE status='running'` guard.

**Files modified:** `src/ga_crawler/runners/main_run.py` (added pre-finalize call; documented inline with rationale comment).

**Commit:** `26a1248` (GREEN commit for Task 1).

**Why Rule 3 and not Rule 4:** The fix is local to the composition layer (no changes to matcher_run.py, no changes to D-411 semantics for standalone `matcher-run --run-id N` recovery — which DOES want to read the finalized status of a completed run). No architectural restructure; just one extra `finalize()` call. Standalone CLI semantics unchanged.

**Alternative considered:** Change matcher_run.py to accept an `allow_running=True` flag for inline composition. Rejected — would dilute D-411's safety invariant for the standalone recovery use case (which is the canonical D-412 motivation). The pre-finalize approach keeps the matcher API single-purpose.

### Minor: PhaseResult name (Plan referred to `GoldappleRunResult`)

The plan's test action snippet referenced `GoldappleRunResult`, but the actual dataclass in `runners/goldapple_run.py` is named `PhaseResult`. Tests adjusted with `from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult` alias for clarity. No functional impact.

### No auth gates, no checkpoints, no architectural changes.

## TDD Gate Compliance

| Task | RED | GREEN |
|---|---|---|
| Task 1 (main_run.py + tests) | Confirmed 5 tests fail with `AttributeError: 'MainRunResult' object has no attribute 'match_count'` and `module ... does not have the attribute 'run_matcher_phase'`. Commit `52ce0bc`. | After implementing composition + dataclass extension, all 5 new + 5 existing tests green. Then full-suite ran 459/0 regressions. Commit `26a1248`. |
| Task 2 (cli.py + tests) | Confirmed 6 tests fail (matcher-run subcommand not registered; weekly-run lacks --sanity-gate-p flag). Commit `f9df9b3`. | After implementing _cmd_matcher + subparser + weekly's new flag, all 6 CLI tests green. Full suite 465/0 regressions. Commit `ba3d965`. |

Both RED commits explicitly `test(...)` typed; both GREEN commits explicitly `feat(...)` typed. Per-task commits capture the cycle.

## Stats Namespace Surface

After Plan 04-05, a successful `weekly-run` populates `runs.stats` with the full three-namespace union:

- **`viled.*`** keys (Phase 2 — viled crawl stats; ~10 keys)
- **`goldapple.*`** keys (Phase 3 — goldapple crawl stats; ~15 keys)
- **`match.*`** keys (Phase 4 — matcher stats; 10 keys, all of MATCH_STATS_KEYS)

Phase 5 reporter reads from this union directly without any JOIN-back.

## Threat Flags

None. The plan's `<threat_model>` register accounted for all surfaces:

- **T-04-05-01** (SQL injection via --run-id): `argparse type=int` rejects non-numeric input (defence-in-depth over Plan 04-03's parameterized SQL). Tested transitively via `test_cli_matcher_run_requires_run_id` (argparse parser invariant).
- **T-04-05-02** (--sanity-gate-p out-of-range): accepted; documented in --help; operator-friendly forced-pass via negative P is a feature, not a bug.
- **T-04-05-03** (info disclosure): JSON output exposes only `runs.stats` columns already in DB.
- **T-04-05-04** (DoS via matcher-run on huge snapshot set): SQL JOIN scoped to single run_id (Plan 04-03 indexed); operator-local DB.
- **T-04-05-05** (silent matcher skip in weekly-run): `weekly_run_matcher_skipped` log + `match.skipped_reason` in stats. Operator can audit.

No new threat surfaces introduced.

## Open Questions / Phase 5 Handoff

Plan 04-05 closes Wave 4 of Phase 4. Final phase-level success criteria check:

| Criterion | Status |
|---|---|
| `matches` table exists, schema per D-401 | ✅ (Plan 04-01) |
| `matcher` module reads `v_current_snapshots`, writes `matches` per D-402 | ✅ (Plan 04-03) |
| match-rate KPI formula per MATCH-03 + D-405 | ✅ (Plan 04-03/-04, frozen with canary) |
| `match.*` stats namespace per D-414 | ✅ (Plan 04-02/-04) |
| Sanity gate P + auto-suggest per D-406..-409 | ✅ (Plan 04-04) |
| Idempotency per D-410 | ✅ (Plan 04-03/-04 transitively) |
| Failed-crawl skip protocol per D-411 | ✅ (Plan 04-04 + composition-layer pre-finalize here) |
| `python -m ga_crawler matcher-run --run-id N` works per D-412 | ✅ (this plan) |
| `python -m ga_crawler weekly-run` produces full match.* stats namespace | ✅ (this plan) |

**Phase 5 reporter ready to start.** Inputs available:
- `matches` table (13 columns, denormalized — no JOIN-back needed)
- `runs.stats.match.*` (10 keys: count, rate, numerator, denominator, brand_overlap_count, viled_comparable_count, goldapple_comparable_count, skipped_reason, threshold_p, gate_passed)
- `runs.status`, `runs.fail_reason`, `runs.finished_at` for delivery-time gating (Phase 6)

No blockers.

## Self-Check: PASSED

Verified post-write:
- `tests/integration/test_cli_matcher_subcommand.py` — FOUND
- `src/ga_crawler/runners/main_run.py` (modified) — diff applied, imports + dataclass + signature + composition block all present
- `src/ga_crawler/cli.py` (modified) — _cmd_matcher + matcher-run subparser + weekly's --sanity-gate-p all present
- `tests/integration/test_main_run_e2e.py` (modified) — 5 new tests appended
- Commit `52ce0bc` (Task 1 RED) — FOUND
- Commit `26a1248` (Task 1 GREEN) — FOUND
- Commit `f9df9b3` (Task 2 RED) — FOUND
- Commit `ba3d965` (Task 2 GREEN) — FOUND
- `uv run pytest tests/integration/test_main_run_e2e.py tests/integration/test_cli_matcher_subcommand.py -q` → 16 passed
- `uv run pytest -q` → 465 passed, 1 skipped, 0 regressions (was 454)
- Manual: `uv run python -m ga_crawler --help` shows `matcher-run` subcommand
- Manual: `uv run python -m ga_crawler matcher-run --help` shows --run-id, --db-path, --sanity-gate-p, --pyproject
- Manual: `uv run python -m ga_crawler weekly-run --help` shows --sanity-gate-p
