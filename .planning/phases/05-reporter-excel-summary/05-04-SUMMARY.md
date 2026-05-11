---
phase: 05-reporter-excel-summary
plan: 04
subsystem: reporter
tags: [phase-05, reporter, orchestrator, status-gate, patch-stats, integration, wave-3]
date-completed: 2026-05-12
duration: ~15 min
tasks-completed: 2
deviations: 0
dependency-graph:
  requires:
    - ga_crawler.matcher.strict_key.read_run_status (D-411 helper; D-507 REUSE — imported verbatim, never re-defined)
    - ga_crawler.reporter.config.ReportConfig (Plan 05-01 frozen dataclass — output_dir + size_limit_mb + top_n_deltas + timezone)
    - ga_crawler.reporter.stats.ReportStatsBuilder (Plan 05-01 — enforces 7-key D-514 namespace + reuses StatsNamespaceError)
    - ga_crawler.reporter.queries.{read_matches_for_run, read_gaps_for_run, read_promos_for_run, read_top_n_deltas, read_run_started_at} (Plan 05-02 — 5 thin engine.connect() readers; all parameterized via :rid)
    - ga_crawler.reporter.excel_builder.build_workbook (Plan 05-02 — 4-sheet xlsx bytes builder)
    - ga_crawler.reporter.summary_builder.build_summary (Plan 05-02 — D-504 Telegram caption builder; reads flat dotted stats per Pitfall 6)
    - ga_crawler.reporter.archive.{derive_filename, write_atomic, check_size_guard} (Plan 05-03 — D-512 ISO-week + D-510 atomic write + D-515 flag-only size guard)
    - ga_crawler.interfaces.RunWriterProtocol (Phase 2 contract — patch_stats / get_stats / fail)
    - tests/conftest.py synthetic_report_run (in-memory SQLite + 1 success Run + 3+8 paired snapshots + 3 matches + pre-populated viled.*/goldapple.*/match.* stats)
  provides:
    - ga_crawler.runners.reporter_run.run_reporter_phase (sync 7-step orchestrator; keyword-only signature; returns ReporterPhaseResult)
    - ga_crawler.runners.reporter_run.ReporterPhaseResult (dataclass — status / xlsx_path / xlsx_size_bytes / summary_text / sheet_row_counts / size_guard_passed / reason / stats_delta)
    - ga_crawler.runners.reporter_run._skip_path (private helper — D-507 skip-gate body; single patch_stats call; all 7 D-514 keys with skip-values)
  affects:
    - Plan 05-05 (main_run.py composition — wires run_reporter_phase AFTER run_matcher_phase per D-511; cli.py `report-run --run-id N` standalone D-412-style subcommand)
    - Plan 05-06 (REQUIREMENTS.md REPORT-01..06 closed + STATE.md cascade + ROADMAP.md plan list)
    - Phase 6 delivery (reads runs.stats.report.xlsx_path + report.summary_text + report.size_guard_passed; routes oversized → ops-chat alert)
    - Phase 7 cron + ops playbook (orphan *.xlsx.tmp glob-and-delete recovery from interrupted reporter_run mid-write crash)
tech-stack:
  added: []  # zero new deps — composes Wave 0..2 modules + matcher.strict_key.read_run_status REUSE
  patterns:
    - 7-step sync orchestrator mirror of runners/matcher_run.py shape (keyword-only signature, ReporterPhaseResult dataclass, single patch_stats per code path)
    - D-507 status-gate via REUSED matcher.strict_key.read_run_status — single source of truth across both derivation phases (matcher + reporter)
    - Pitfall 6 atomic patch_stats — SINGLE call per code path (success + skip both have exactly one); private _skip_path helper keeps the invariant structurally enforceable
    - Path-traversal containment check — target_path.relative_to(repo_root) raises ValueError before any disk write (defense-in-depth against malformed config.output_dir)
    - Defensive ValueError on NULL started_at for status='success' rows — DATA-05 invariant canary (would indicate Phase 2 data-integrity bug)
    - Reporter does NOT catch own exceptions — DATA-05 try/except boundary lives in main_run (Plan 05-05) per Plan 02-05 invariant; uncaught exceptions bubble up to outer caller
    - D-515 flag-only size guard — oversize logs warning + sets report.size_guard_passed=False but status='success' + xlsx persists (ARCHITECTURE.md "reporter independent of delivery")
key-files:
  created:
    - src/ga_crawler/runners/reporter_run.py (~250 LOC — module docstring + ReporterPhaseResult dataclass + _skip_path private helper + run_reporter_phase 7-step entry point)
    - tests/integration/test_reporter_run.py (~470 LOC — 15 integration tests against real synthetic_report_run engine + real xlsx output via tmp_path-rooted repo_root)
  modified: []  # zero modifications — pure additive plan (Plan 05-05 will modify runners/main_run.py for D-511 composition)
decisions:
  - D-507 status-gate body lives in private _skip_path helper invoked once at Step 1; all 7 D-514 keys patched with skip-values (xlsx_path='', xlsx_size_bytes=0, summary_text='', sheet_row_counts={}, skipped_reason set, size_guard_passed=False, generated_at=now ISO 8601 UTC); skip-reason mapping is `failed→'failed_upstream' / running→'in_progress_upstream' / None→'missing_run_row' / other→'unexpected_upstream:<status>'`
  - Pitfall 6 single patch_stats invariant pinned by 2 tests — `test_single_patch_stats_call` (success path mock asserts call_count==1) + `test_single_patch_stats_call_on_skip_path` (skip path mock asserts call_count==1); these are the canaries that fail loudly on any future read-modify-write refactor
  - D-515 size guard is flag-only — `test_size_guard_flag_does_not_fail_run` confirms status='success' + xlsx persists on disk + report.size_guard_passed=False when check_size_guard returns (False, 99_999_999) via monkeypatch
  - D-405 KPI preservation — `test_d405_kpi_verbatim_in_summary` confirms summary_text contains "Совпало: 3 (60.0%)" verbatim from stats["match.rate"]=60.0 (no recomputation); summary_builder reads upstream flat dotted keys per Pitfall 6
  - D-510 idempotent overwrite — `test_filename_iso_week_and_overwrite` confirms second call to run_reporter_phase produces same xlsx_path + same sheet_row_counts (file overwritten cleanly via archive.write_atomic os.replace primitive); `test_idempotent_re_run_same_state` confirms xlsx_size_bytes within ±200 bytes between two calls (small drift OK due to xlsxwriter zip-metadata timestamps)
  - T-05-injection end-to-end — `test_formula_injection_sanitized_e2e` plants brand_norm='=cmd|/c calc' into both matches AND snapshots (Pitfall 9 JOIN-back consistency) then asserts the produced xlsx Per-SKU deltas A2 cell starts with leading single quote
  - DATA-05 exception-propagation invariant — `test_uncaught_exception_propagates` monkeypatches build_workbook to raise RuntimeError → run_reporter_phase does NOT catch; exception bubbles up to test (Plan 05-05 main_run owns try/except + run_writer.fail)
  - Path-traversal containment check — target_path.relative_to(repo_root.resolve()) raises ValueError BEFORE any disk write if config.output_dir escapes (e.g. '../../tmp' or absolute path); defense-in-depth above operator git-PR control on pyproject.toml
  - Defensive NULL started_at guard — `test_raises_on_null_started_at` mocks read_run_started_at→None and confirms ValueError("started_at") raised; the actual SQL schema enforces NOT NULL on runs.started_at, so this canary only triggers via test path or future schema regression
  - Adjustment from PLAN.md `<behavior>` Test 9: the plan suggested simulating NULL started_at via direct SQL UPDATE, but the storage/sqlite.py Run schema has NOT NULL on started_at (PRAGMA enforces); test adjusted to mock the reader function instead — same defensive surface, different injection vector
metrics:
  duration: ~15 min
  tasks: 2
  files-created: 2 (1 src + 1 integration test)
  files-modified: 0
  tests-added: 15 (3 D-507 skip + 3 success-path 4-sheet structure + 2 single-patch-stats canary + 1 D-515 flag-only + 1 D-405 KPI verbatim + 1 T-05-injection e2e + 1 D-510 idempotency + 1 defensive NULL started_at + 1 DATA-05 exception propagation + 1 stats namespace D-514)
  tests-passing: 594 unit+integration (was 579 before plan, +15 from plan; 1 skipped carry-over)
  commits: 2 (1 RED gate + 1 GREEN gate)
---

# Phase 5 Plan 04: Reporter orchestrator — runners/reporter_run.py Summary

Wave 3 keystone lands: `run_reporter_phase` 7-step sync orchestrator in `runners/reporter_run.py` composing Wave 0 (`ReportConfig` + `ReportStatsBuilder`) + Wave 1 (`queries.py` + `excel_builder.py` + `summary_builder.py`) + Wave 2 (`archive.py` 3 primitives) + Phase 4 D-411 helper (`matcher.strict_key.read_run_status` REUSED for D-507). 15 integration tests pin every D-507 / D-510 / D-514 / D-515 / D-405 invariant end-to-end against `synthetic_report_run` fixture. Single atomic `patch_stats` per code path (Pitfall 6) — both success and skip paths verified via `unittest.mock.patch.object` `call_count==1` canaries. D-515 size guard flag-only (oversize → status still 'success' + xlsx persists). Plan 05-05 is unblocked.

## What changed

### Production code (1 new file, 0 modifications)

- **`src/ga_crawler/runners/reporter_run.py`** (~250 LOC, sync) — three exports:
  - **`ReporterPhaseResult`** dataclass — 8 fields (status / xlsx_path / xlsx_size_bytes / summary_text / sheet_row_counts / size_guard_passed / reason / stats_delta); `default_factory=dict` on the two dict fields keeps the constructor zero-arg-friendly for skip paths.
  - **`_skip_path(*, run_id, upstream_status, run_writer)`** private helper — D-507 skip-gate body. Maps upstream_status → reason string (`failed_upstream` / `in_progress_upstream` / `missing_run_row` / `unexpected_upstream:<status>`), builds a `ReportStatsBuilder` with all 7 D-514 keys set to skip-values (`xlsx_path=''`, `xlsx_size_bytes=0`, `summary_text=''`, `sheet_row_counts={}`, `skipped_reason=reason`, `size_guard_passed=False`, `generated_at=now()` ISO 8601 UTC), makes the SINGLE atomic `run_writer.patch_stats` call, logs the `report_skipped_failed_run` warning event, returns `ReporterPhaseResult(status='skipped', reason, stats_delta)`. No xlsx written on this path.
  - **`run_reporter_phase(*, run_id, engine, run_writer, repo_root, config)`** main entry point — keyword-only signature (sentinel `*` first param) prevents positional misorder. Executes the 7 steps:
    1. **D-507 status-gate** — `read_run_status(engine, run_id)` IMPORTED verbatim from `matcher.strict_key` (Plan 04-03 D-411 helper; never re-implemented). Status `!= 'success'` triggers `_skip_path` and returns early.
    2. **Read upstream stats** — `run_writer.get_stats(run_id) or {}` returns flat dotted dict per Pitfall 6 (`viled.fetch_count` / `goldapple.fetch_count` / `match.count` / `match.rate`). Reporter never recomputes match.rate (D-405 KPI verbatim).
    3. **Read matches DataFrame** — `queries.read_matches_for_run(engine, run_id)` does the JOIN-back to snapshots for URLs per Pitfall 9 (matches table is denormalized 13-col without url columns).
    4. **Read gaps + promos + top-3 + started_at** — 4 thin reader calls. `started_at is None` triggers defensive `ValueError("started_at is NULL...")` raise (DATA-05 canary).
    5. **Pure builders** — `derive_filename(started_at, tz_name=config.timezone)` → ISO-week stem (e.g. `2026-W19`); `build_summary(stats=upstream_stats, top3=top3, gaps_count=len(gaps_df), promo_count=len(promos_df), iso_week=stem)` → multi-line emoji caption; `build_workbook(matches_df, gaps_df, promos_df, summary_text)` → xlsx bytes.
    6. **Archive** — `target_path = (repo_root / config.output_dir / filename).resolve()`; **path-traversal containment check** via `target_path.relative_to(repo_root.resolve())` raises `ValueError` BEFORE any disk write if `config.output_dir` escapes (defense-in-depth above operator git-PR control); `write_atomic(xlsx_bytes, target_path)` returns `size_bytes`; `check_size_guard(target_path, config.size_limit_mb)` returns `(passed, _)`; if `not passed` → log `report_size_exceeded` warning but DO NOT raise.
    7. **Atomic single-call patch_stats** — `ReportStatsBuilder` with all 7 D-514 keys (`xlsx_path=rel_path` with `\\` → `/` normalization for cross-platform consistency, `xlsx_size_bytes=int(size_bytes)`, `summary_text=summary_text`, `sheet_row_counts={summary,per_sku_deltas,assortment_gaps,goldapple_promos}`, `skipped_reason=''` empty sentinel per Pitfall 4 None-rejection, `size_guard_passed=bool(passed)`, `generated_at=now()` ISO 8601 UTC); SINGLE `run_writer.patch_stats(run_id, dict(builder.delta))` call (Pitfall 6); log `reporter_phase_complete` info event with timings + counts; return `ReporterPhaseResult(status='success', ...)`.

**Critical contract**: `run_reporter_phase` does NOT catch its own exceptions. Per Plan 02-05 DATA-05 invariant, the outer try/except + `run_writer.fail()` lives in `main_run.run_weekly` (Plan 05-05). Reporter exception (e.g. xlsxwriter crash, disk-full from `write_atomic`, parameter-binding error from `queries.*`) propagates cleanly. This keeps the reporter testable as a pure transform + 1 atomic write surface.

### Test infrastructure (1 new file, 0 modifications)

- **`tests/integration/test_reporter_run.py`** (~470 LOC, 15 tests, `pytestmark = pytest.mark.integration`):

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_d507_skip_on_failed_run` | D-507 + D-514 — fail() upstream → skipped reason='failed_upstream'; all 7 keys patched; xlsx NOT written |
| 2 | `test_d507_skip_on_running_run` | D-507 — flip status back to 'running' → skipped reason='in_progress_upstream' |
| 3 | `test_d507_skip_on_missing_run` | D-507 — run_id=99999 → skipped reason='missing_run_row' |
| 4 | `test_xlsx_has_four_sheets_with_russian_headers` | REPORT-01 + REPORT-03 + D-503 — sheet order canary + D-503 verbatim Russian headers on Per-SKU deltas |
| 5 | `test_xlsx_cf_freeze_autofilter` | REPORT-02 + D-505 + D-508 — CF on Per-SKU deltas + Goldapple promos only; freeze_panes=="A2" + autofilter.ref non-empty on all 3 data sheets |
| 6 | `test_filename_iso_week_and_overwrite` | REPORT-05 + D-510 + D-512 — filename derives to 2026-W19; second call overwrites cleanly; xlsx_path + sheet_row_counts stable across calls |
| 7 | `test_report_stats_namespace_keys` | D-514 + Pitfall 6 atomic merge — all 7 report.* keys present + upstream viled.*/goldapple.*/match.* preserved; sheet_row_counts exact match |
| 8 | `test_single_patch_stats_call` | Pitfall 6 success-path canary — `patch.object(run_writer, 'patch_stats', wraps=...)` asserts call_count==1 |
| 9 | `test_single_patch_stats_call_on_skip_path` | Pitfall 6 skip-path canary — `_skip_path` makes exactly 1 patch_stats call |
| 10 | `test_size_guard_flag_does_not_fail_run` | D-515 + REPORT-06 + ARCHITECTURE.md — monkeypatch check_size_guard→(False,99_999_999); status='success' + xlsx persists + size_guard_passed=False |
| 11 | `test_d405_kpi_verbatim_in_summary` | D-405 KPI freeze — summary_text contains "Совпало: 3 (60.0%)" verbatim from stats['match.rate']=60.0 (no recompute) |
| 12 | `test_formula_injection_sanitized_e2e` | T-05-injection end-to-end — plant '=cmd\|/c calc' into matches AND snapshots (Pitfall 9 consistency); xlsx Per-SKU deltas A2 starts with "'=" |
| 13 | `test_idempotent_re_run_same_state` | D-510 + REPORT-05 — two calls produce same xlsx_path/summary_text/sheet_row_counts; size_bytes within ±200 |
| 14 | `test_raises_on_null_started_at` | Defensive NULL canary — mock read_run_started_at→None; ValueError("started_at") raised |
| 15 | `test_uncaught_exception_propagates` | DATA-05 boundary invariant — monkeypatch build_workbook to raise RuntimeError; reporter does NOT catch (Plan 05-05 main_run owns try/except) |

Each test uses a unique `output_dir` (e.g. `reports_t4`, `reports_t5`) so concurrent test execution never collides on the `2026-W19.xlsx` filename. All output is rooted at `synthetic_report_run`'s `tmp_path` (`repo_root` returned from fixture), which pytest auto-cleans.

## Why these decisions

- **D-507 status-gate REUSES `read_run_status` from `matcher.strict_key`** — single source of truth for "is upstream ready?" across both Phase 4 (matcher) and Phase 5 (reporter). If the gate semantics ever change (e.g. add 'partial' as acceptable), one helper updates and both phases stay in sync. Importing verbatim (`from ga_crawler.matcher.strict_key import read_run_status`) is the structural canary — any refactor that copies the helper into reporter would lose this coupling.
- **`_skip_path` private helper** — extracts the D-507 skip-gate body so the success path stays linear (the 7-step pipeline reads top-to-bottom without nested `if`s). Both code paths still satisfy the Pitfall 6 invariant: each `ReportStatsBuilder` is constructed fresh in its own scope so they cannot interleave deltas. Each ends with EXACTLY ONE `run_writer.patch_stats` call.
- **Path-traversal containment check** — `(repo_root / config.output_dir / filename).resolve().relative_to(repo_root.resolve())` raises `ValueError` if the resolved target escapes `repo_root`. This is defense-in-depth above the operator-git-PR control on `pyproject.toml`'s `output_dir`. A malicious or buggy edit setting `output_dir = "../../tmp"` is rejected BEFORE any bytes hit disk. The runtime cost is one `Path.relative_to` call (microseconds) once per `run_reporter_phase` invocation.
- **`cross-platform path normalization` via `str(...).replace("\\", "/")`** — Windows path separators are converted to forward slashes for `report.xlsx_path` storage. Phase 6 delivery reads this key as a `Path(report.xlsx_path)` and opens the file; forward slashes work uniformly on both Linux (production VPS) and Windows (dev machines). This matches how `git ls-files` reports paths.
- **D-515 size guard is flag-only** — the design rationale is in ARCHITECTURE.md "reporter independent of delivery" + D-515 "xlsx ВСЕГДА пишется на диск". If a report is 50 MB+ the operator wants the xlsx on disk so they can manually split, deliver, or move it; failing the run would force a full re-crawl. The flag (`report.size_guard_passed=False`) is consumed by Phase 6 DELIVER-03 sanity-gate to route oversized reports to ops-chat alert instead of business-chat. The `test_size_guard_flag_does_not_fail_run` canary is the structural lock.
- **Reporter does NOT catch own exceptions** — Plan 02-05 DATA-05 lifecycle owns the try/except + `run_writer.fail()` block in `main_run.run_weekly`. Keeping reporter exception-naive means: (a) the orchestrator stays thin and trivially unit-testable; (b) crashes always set runs.status='failed' via the outer block (no silent swallow); (c) the test `test_uncaught_exception_propagates` is a single source of truth for the DATA-05 boundary contract.
- **Defensive NULL `started_at` raise** — D-507 status-gate already filtered non-success runs. A `started_at IS NULL` on a `status='success'` row would indicate a Phase 2 invariant violation (the storage/sqlite.py Run schema enforces NOT NULL via SQLModel default_factory). The loud raise here is a canary that would fire on future schema-regression bugs before the reporter silently produces a garbled filename.
- **Test adjustment for `test_raises_on_null_started_at`** — the plan suggested `UPDATE runs SET started_at=NULL` to simulate the integrity bug, but the actual schema enforces NOT NULL (sqlite3.IntegrityError raised at UPDATE time). Switched to mocking `read_run_started_at` to return None — same defensive surface (reporter's own None-guard), different injection vector. Documented inline as a decision; the assertion `pytest.raises(ValueError, match="started_at")` is unchanged. This is the only adjustment from the PLAN.md `<behavior>` block.

## Deviations from Plan

**None — plan 05-04 executed exactly as written.** Two tasks landed on the first RED→GREEN cycle (no debugging iteration on production source after first commit). No Rule 1/2/3 auto-fixes triggered. No CLAUDE.md violations. No authentication gates encountered. No checkpoints reached.

One minor inline test adjustment: `test_raises_on_null_started_at` cannot use direct `UPDATE runs SET started_at=NULL` because the schema enforces NOT NULL (sqlite3.IntegrityError on UPDATE). Adjusted to mock `read_run_started_at` to return None. This is a test-mechanism adjustment, not a behavior deviation — the defensive `ValueError("started_at")` raise inside `run_reporter_phase` is unchanged. Captured in decisions above.

## Verification (per plan `<verification>` block)

```
$ uv run pytest tests/integration/test_reporter_run.py -x -q
15 passed in 1.42s

$ uv run pytest tests/unit tests/integration -x -q
594 passed, 1 skipped, 85 warnings in 112.42s   ← +15 from baseline 579, 0 regressions

$ uv run python -c "<plan signature snippet>"
reporter_run signature OK

$ uv run python -c "<plan dataclass field snippet>"
reporter_run orchestrator OK
```

All `<acceptance_criteria>` items satisfied:

- [x] `grep -c "def run_reporter_phase"` → 1
- [x] `grep -c "class ReporterPhaseResult"` → 1
- [x] `grep -c "from ga_crawler.matcher.strict_key import read_run_status"` → 1 (D-507 REUSE)
- [x] `grep -c "run_writer.patch_stats"` → 2 (one in `_skip_path`, one in `run_reporter_phase`; both atomic per Pitfall 6)
- [x] `grep -c "write_atomic\|check_size_guard\|derive_filename"` → 10 (well above ≥3)
- [x] `grep -c "build_summary\|build_workbook"` → 6 (well above ≥2)
- [x] `grep -c "size_guard_passed"` → 5 (≥3)
- [x] `grep -c "report_skipped_failed_run\|report_size_exceeded\|reporter_phase_complete"` → 3 (≥3)
- [x] `uv run python -c "from ga_crawler.runners.reporter_run import run_reporter_phase; print('importable')"` exits 0

All `<success_criteria>` items satisfied:

- [x] `src/ga_crawler/runners/reporter_run.py` ships `run_reporter_phase` (sync 7-step) + `ReporterPhaseResult` dataclass + `_skip_path` helper
- [x] `read_run_status` IMPORTED from `matcher.strict_key` (D-507 REUSE — not redefined)
- [x] SINGLE `run_writer.patch_stats` call per code path (Pitfall 6); both success and skip paths verified via `test_single_patch_stats_call` + `test_single_patch_stats_call_on_skip_path`
- [x] All 7 D-514 stats keys patched on both success and skip paths
- [x] D-515 size guard is flag-only — `test_size_guard_flag_does_not_fail_run` confirms `status='success'` + `xlsx persists` even when `passed=False`
- [x] D-405 KPI verbatim — summary text contains `match.rate` from upstream stats, never recomputed (`test_d405_kpi_verbatim_in_summary`)
- [x] 15 integration tests green covering REPORT-01..06 + D-507 (3 skip cases) + D-510 (idempotency + overwrite) + D-514 (namespace + atomic merge) + D-515 (flag-only) + T-05-injection e2e
- [x] Path-traversal containment check enforced (`target_path.relative_to(repo_root)` raises ValueError)
- [x] Zero regression: full `uv run pytest tests/unit tests/integration -x -q` exits 0 (594 passed, 1 skipped carry-over)

## Commits

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | `9ed8ad4` | test | add failing tests for reporter_run orchestrator (RED gate) |
| 2 | `c18862a` | feat | implement reporter_run orchestrator (GREEN gate) |

## TDD Gate Compliance

| Task | RED commit | GREEN commit | REFACTOR | Notes |
|------|-----------|--------------|----------|-------|
| 1 (reporter_run.py) | `9ed8ad4` (full test file) | `c18862a` | — | ModuleNotFoundError on `ga_crawler.runners.reporter_run` import confirmed RED at collection time; GREEN produced 13/15 first-shot. The 2 initially-failing tests were a single test (`test_raises_on_null_started_at`) that hit a schema NOT NULL constraint at UPDATE time (caught at fail-fast — 14 pass + 1 fail); adjusted the test mechanism (mock the reader function instead of UPDATE NULL) in the same GREEN commit. No production-code change needed. |
| 2 (test_reporter_run.py) | — | (folded into GREEN of Task 1) | — | The plan separated Task 1 (production code) and Task 2 (tests) but the TDD discipline naturally folds them: Task 2's test file IS the RED gate for Task 1 (no production code = ImportError = RED). The two tasks committed atomically as RED then GREEN per the plan's `tdd="true"` directive. |

## Imports demonstrating D-507 reuse + Plan 05-02/03 composition

```python
# D-507 REUSE (Plan 04-03 D-411 helper — never re-defined here)
from ga_crawler.matcher.strict_key import read_run_status

# Plan 05-01 — config + stats namespace
from ga_crawler.reporter.config import ReportConfig
from ga_crawler.reporter.stats import ReportStatsBuilder

# Plan 05-02 — 5 SQL primitives + 2 pure builders
from ga_crawler.reporter.queries import (
    read_gaps_for_run, read_matches_for_run, read_promos_for_run,
    read_run_started_at, read_top_n_deltas,
)
from ga_crawler.reporter.excel_builder import build_workbook
from ga_crawler.reporter.summary_builder import build_summary

# Plan 05-03 — 3 archive primitives
from ga_crawler.reporter.archive import (
    check_size_guard, derive_filename, write_atomic,
)

# Phase 2 contract Protocol — patch_stats / get_stats / fail
from ga_crawler.interfaces import RunWriterProtocol
```

These 12 imports (across 6 modules) are the structural canary for "reporter_run is pure composition of Wave 0..2 outputs + matcher D-411 helper" — any future refactor that copies a primitive's logic inline rather than importing would break this contract. Plan 05-05's `main_run.py` composition will be a similar single-file import block.

## Integration test count by category

| Category | Count | Tests |
|----------|-------|-------|
| D-507 skip-gate | 3 | failed_upstream, in_progress_upstream, missing_run_row |
| Success path (REPORT-01..03) | 2 | 4-sheet + Russian headers, CF + freeze + autofilter |
| Stats namespace (D-514) | 1 | all 7 report.* keys + upstream namespace co-existence |
| Pitfall 6 single patch_stats | 2 | success path + skip path canaries |
| D-515 size guard flag-only | 1 | oversize → status='success' + xlsx persists |
| D-405 KPI preservation | 1 | "Совпало: 3 (60.0%)" verbatim |
| T-05-injection end-to-end | 1 | brand_norm='=cmd|/c calc' → leading single quote |
| D-510 idempotency | 2 | filename + overwrite, full state stability across two calls |
| Defensive guards | 2 | NULL started_at, exception propagation |
| **Total** | **15** | |

## What unblocked downstream

- **Plan 05-05** (Wave 4 main_run + CLI) — `runners/main_run.py` `run_weekly` composition can now call `run_reporter_phase` AFTER `run_matcher_phase` per D-511 invariant (`runs.create → run_viled_phase → run_goldapple_phase → Norm06Writer.persist → run_writer.finalize('success') → run_matcher_phase → run_reporter_phase → run_writer.finalize('success')`). The pre-finalize-before-matcher pattern from Plan 04-05 carries through identically (D-411 + D-507 both require `status='success'`). `cli.py` will gain a `report-run --run-id N` standalone D-412-style recovery subcommand mirroring `matcher-run`.
- **Plan 05-06** (Wave 5 doc cascade) — REQUIREMENTS.md REPORT-01..06 can be closed once Plan 05-05 ships the CLI surface; STATE.md accumulates the D-507 / D-510 / D-514 / D-515 decisions as Phase 5 invariants; ROADMAP.md Phase 5 progress moves to 4/6 → 6/6 after 05-06.
- **Phase 6 delivery** — reads `runs.stats.report.xlsx_path` + `runs.stats.report.summary_text` + `runs.stats.report.size_guard_passed`; the size-guard flag drives DELIVER-03 routing (`False` → ops-chat alert + manual handoff; `True` → business-chat `send_document`). All 7 D-514 keys are now written by this plan's `_skip_path` + `run_reporter_phase` Step 7 atomic patch.
- **Phase 7 cron + ops playbook** — orphan `*.xlsx.tmp` cleanup glob (post-crash recovery) is unchanged from Plan 05-03; the Plan 05-04 orchestrator does not create the tmp file directly (delegated to `archive.write_atomic`), so the recovery surface is the same.

## Self-Check: PASSED

- File existence:
  - `src/ga_crawler/runners/reporter_run.py` — FOUND
  - `tests/integration/test_reporter_run.py` — FOUND
- Commit hashes verified via `git log --oneline -5`:
  - `9ed8ad4` — FOUND (RED gate)
  - `c18862a` — FOUND (GREEN gate)
- Test counts verified: 15 new integration tests; pytest run produces 594 passed (+15 from 579 baseline; 1 skipped carryover from Plan 02-05).
