---
phase: 05-reporter-excel-summary
plan: 05
subsystem: reporter
tags: [phase-05, reporter, main-run, cli, composition, data-05, report-run-subcommand, wave-4]
date-completed: 2026-05-12
duration: ~20 min
tasks-completed: 2
deviations: 1
dependency-graph:
  requires:
    - ga_crawler.runners.reporter_run.run_reporter_phase (Plan 05-04 — 7-step sync orchestrator; keyword-only signature; returns ReporterPhaseResult)
    - ga_crawler.reporter.config.ReportConfig (Plan 05-01 — frozen dataclass + from_pyproject loader)
    - ga_crawler.runners.matcher_run.run_matcher_phase (Plan 04-04 — matcher returns MatcherPhaseResult.status ∈ {success, failed, skipped})
    - ga_crawler.storage.sqlite.SqliteRunWriter (Phase 2 — patch_stats / get_stats / finalize / fail)
    - Plan 04-05 pre-finalize-before-matcher pattern (composition-layer invariant: pre-finalize so D-411 read_run_status sees 'success'; final idempotent finalize at the bottom is no-op via WHERE status='running' guard)
  provides:
    - ga_crawler.runners.main_run.run_weekly (composition extended with reporter step + 4 new D-514 MainRunResult fields surfaced to caller)
    - ga_crawler.runners.main_run.MainRunResult (dataclass with xlsx_path / xlsx_size_bytes / summary_text / size_guard_passed in addition to Plan 04-05 match_count + match_rate)
    - python -m ga_crawler report-run --run-id N [--output-dir DIR] [--db-path PATH] [--pyproject PATH] [--repo-root .] (D-509 standalone reporter recovery tool — exits 0/2; mirror of matcher-run shape; CLI JSON payload includes summary_text for ops debugging)
  affects:
    - Plan 05-06 (Wave 5 doc cascade — REQUIREMENTS.md REPORT-01..06 closed + STATE.md cascade + ROADMAP.md Phase 5 plan list + Progress 6/6)
    - Phase 6 delivery (reads runs.stats.report.xlsx_path + report.summary_text + report.size_guard_passed; weekly cron now produces a complete weekly artifact: viled + goldapple snapshots → matches → xlsx report on disk → 4-namespace stats)
    - Phase 7 cron entry (`python -m ga_crawler weekly-run` weekly Sunday produces reports/YYYY-WNN.xlsx with no extra invocation needed)
tech-stack:
  added: []  # zero new deps — composes Wave 0-3 modules + Plan 04-05 composition pattern
  patterns:
    - Reporter composition mirrors matcher composition (Plan 04-05) — inserted INSIDE if not viled_only and not goldapple_only branch, INSIDE the outer try/except so reporter exceptions bubble to existing Plan 02-05 DATA-05 lifecycle owner
    - Explicit gating on m_result.status == "success" — defensive layer above D-507 inside reporter_run (which would also skip on other statuses), keeps stats coherent (no report.* keys emitted when there were no matches)
    - Pre-initialized outcome variables scoped above try block — failure-return paths (viled-fail, goldapple-fail, matcher-fail, crash) all emit valid MainRunResult with sane defaults (None / 0 / "" / True)
    - size_guard_passed default True for no-reporter paths — semantically "no xlsx produced → no size violation possible" (Phase 6 DELIVER-03 reads this flag only when xlsx_path is non-empty)
    - report-run CLI: dataclasses.replace(cfg, output_dir=...) — frozen-safe override mirror of Plan 02-05 _config_with_overrides pattern for ViledConfig
    - report-run CLI: argparse type=int on --run-id — T-05-sql-injection mitigation at CLI boundary (non-integer rejected before SQL is touched)
    - report-run CLI: sys.stdout.buffer.write(payload.encode("utf-8")) — bypasses Windows cp1252 locale codec for Cyrillic + emoji in summary_text (Rule 1 auto-fix; print(json.dumps(..., ensure_ascii=False)) raised UnicodeEncodeError on Windows)
    - _extract_payload(stdout) test helper — splits structlog single-line log events from CLI handler indented (multi-line) JSON payload by searching for literal "{\n"
key-files:
  created:
    - tests/integration/test_main_run_with_reporter.py (~370 LOC — 8 integration tests pinning D-511 composition rule + 4-namespace coexistence + Plan 04-05 pre-finalize pattern preserved + DATA-05 reporter-exception canary)
    - tests/integration/test_cli_report_subcommand.py (~280 LOC — 8 subprocess CLI tests covering help / required+optional flags / missing run-id / non-int run-id / non-existent run / success / --output-dir override / idempotent re-invocation)
    - .planning/phases/05-reporter-excel-summary/05-05-SUMMARY.md (this file)
  modified:
    - src/ga_crawler/runners/main_run.py (+63 LOC — 2 new imports + 4 new MainRunResult dataclass fields + pre-initialized outcome vars + reporter composition step inside try/both-retailers branch + success log + success return amended)
    - src/ga_crawler/cli.py (+126 LOC — docstring updated to 4-subcommand overview + Plan 05-05 additions block + _cmd_report handler + report-run subparser + dispatcher entry; -8 LOC for print→sys.stdout.buffer.write switch)
decisions:
  - Reporter composition placed AFTER matcher and explicit-gated on m_result.status == "success" (D-511) — the matcher-failed path early-returns BEFORE this block, the matcher-skipped path falls through to here but the explicit gate prevents reporter invocation when there were no matches to report; defensive layer over D-507 inside reporter_run for clarity (stats stay coherent — no half-namespace report.* keys emitted on matcher-skipped path)
  - 4 new MainRunResult fields (xlsx_path / xlsx_size_bytes / summary_text / size_guard_passed) placed BETWEEN existing norm06_path and stats_delta to preserve Python dataclass field-order rules (all non-default fields first, then defaults; the 4 new fields are scalar with defaults so they slot cleanly in)
  - Pre-initialized outcome variables (xlsx_path=None, xlsx_size_bytes=0, summary_text="", size_guard_passed=True) scoped above try block — every failure-return path (viled-fail, goldapple-fail, matcher-fail, outer crash) emits a valid MainRunResult with sane defaults instead of having to remember to set 4 None/0/""/True values in 4 different return statements; pre-init pattern was already used for match_count/match_rate (Plan 04-05) so this is the same idiom extended
  - size_guard_passed default = True for no-reporter paths (semantic: "no xlsx produced → no size violation could occur"); Phase 6 DELIVER-03 sanity-gate must read this flag only AFTER checking that xlsx_path is non-empty, otherwise the True default would mislead the delivery layer into thinking an oversized report passed when in fact no report was produced
  - report-run CLI exits 0 on success / 2 on skipped — matches matcher-run convention so ops monitoring scripts can use `exit_code != 0 → alert` uniformly across both standalone tools
  - JSON output includes 8 keys (status, run_id, xlsx_path, xlsx_size_bytes, summary_text, size_guard_passed, reason, stats_delta_keys) — summary_text in the JSON is the SAME string Phase 6 will read from runs.stats.report.summary_text for Telegram caption; CLI users can `python -m ga_crawler report-run --run-id N | jq -r .summary_text` to inspect the caption that would be sent (without actually sending)
  - Rule 1 auto-fix: print(json.dumps(..., ensure_ascii=False)) raised UnicodeEncodeError on Windows because summary_text contains Cyrillic (Cyrillic letters) + 📊 emoji (D-504 template) and default Windows stdout encoding is cp1252. Solution: sys.stdout.buffer.write(payload.encode("utf-8")) bypasses the locale codec entirely — portable across Linux/macOS/Windows. This pattern should propagate to _cmd_matcher and _cmd_weekly in a follow-up if they ever emit Cyrillic/emoji in their JSON payloads (currently they don't).
  - Plan 04-05 pre-finalize-before-matcher pattern preserved — spy test (test_pre_finalize_pattern_preserved) confirms exactly 2 finalize() calls on success path (1 pre-matcher + 1 final-idempotent via WHERE status='running' guard). Adding the reporter step did NOT introduce any new finalize() call; reporter does not own lifecycle management (DATA-05 boundary in main_run per Plan 05-04 invariant).
metrics:
  duration: ~20 min
  tasks: 2
  files-created: 3 (2 integration test files + this SUMMARY.md)
  files-modified: 2 (main_run.py + cli.py)
  tests-added: 16 (8 main_run composition + 8 CLI subprocess)
  tests-passing: 610 unit+integration (was 594 before plan, +16 from plan; 1 skipped carry-over from Plan 03-09)
  commits: 4 (1 RED Task 1 + 1 GREEN Task 1 + 1 RED Task 2 + 1 GREEN Task 2 with Rule 1 auto-fix bundled in same commit)
---

# Phase 5 Plan 05: main_run + CLI composition — wire reporter into production Summary

Wave 4 keystone lands: `run_reporter_phase` is now invoked from `runners/main_run.run_weekly` AFTER the matcher step BEFORE the final idempotent finalize, gated on `m_result.status == "success"` per D-511. `MainRunResult` extends with 4 new D-514 fields (`xlsx_path` / `xlsx_size_bytes` / `summary_text` / `size_guard_passed`) surfaced to the caller. CLI gets `report-run --run-id N` standalone D-509 recovery subcommand mirroring `matcher-run` shape. Plan 04-05 pre-finalize-before-matcher pattern preserved (spy test confirms exactly 2 finalize() calls on success path). DATA-05 reporter-exception canary green. 16 new integration tests; 610 passing (was 594), 0 regressions.

After this plan: `python -m ga_crawler weekly-run` produces a COMPLETE pipeline output in a single invocation — viled + goldapple snapshots → matches → xlsx report on disk → `runs.stats` carrying 4 namespaces (viled.* / goldapple.* / match.* / report.*). Phase 6 reads `runs.stats.report.xlsx_path` + `report.summary_text` + `report.size_guard_passed` and delivers via Telegram. Phase 5 reporter is now production-wired.

## What changed

### Production code (2 files modified, 0 new modules)

- **`src/ga_crawler/runners/main_run.py`** (+63 LOC) — 5 amendments per PLAN.md:
  1. **Imports** — `from ga_crawler.reporter.config import ReportConfig` + `from ga_crawler.runners.reporter_run import run_reporter_phase` added after the existing matcher_run import.
  2. **`MainRunResult` dataclass** — 4 new D-514 scalar default fields (`xlsx_path: Optional[str] = None`, `xlsx_size_bytes: int = 0`, `summary_text: str = ""`, `size_guard_passed: bool = True`) inserted between `norm06_path` and `stats_delta`. Field-order rules preserved (all non-default fields first, then defaults; `stats_delta: dict = field(default_factory=dict)` remains last).
  3. **Pre-initialized outcome vars** — `xlsx_path / xlsx_size_bytes / summary_text / size_guard_passed` initialized to `None / 0 / "" / True` above the try block so the failure-return paths (viled-fail, goldapple-fail, matcher-fail, outer crash) all emit valid `MainRunResult` objects with sane defaults without having to remember to set 4 values in 4 different return statements.
  4. **Reporter step** — inserted INSIDE the `if not viled_only and not goldapple_only:` block, AFTER the matcher's `elif m_result.status == "skipped":` clause but BEFORE the Norm06 + finalize path. Gated explicitly on `if m_result.status == "success":` — the matcher-failed path early-returns BEFORE reaching here, the matcher-skipped path falls through here but the explicit gate prevents reporter invocation. Inside the gate: `ReportConfig.from_pyproject(pyproject_path)` → `log.info("weekly_run_reporter_starting", ...)` → `r_result = run_reporter_phase(run_id, engine, run_writer, repo_root, config)` → copy 4 fields from `r_result` to local vars → `stats_delta_acc.update(r_result.stats_delta)` → if `r_result.status == "skipped"` log warning `weekly_run_reporter_skipped` and fall through (NOT a run-failure per Plan 05-04 invariant).
  5. **Success log + return** — `log.info("weekly_run_complete", ..., xlsx_path=..., xlsx_size_bytes=..., size_guard_passed=...)` and the success `return MainRunResult(...)` both extended with the 4 new reporter fields.

  **Critical invariant preserved:** The reporter call is INSIDE the existing `try:` block — so uncaught reporter exceptions are captured by the existing `except Exception as e:` (Plan 02-05 DATA-05 lifecycle owner) which calls `run_writer.fail(run_id, traceback)`. Reporter does NOT own its own try/except (Plan 05-04 invariant). The DATA-05 canary `test_data05_reporter_exception_finalizes` proves this end-to-end: monkeypatching `run_reporter_phase` to raise `RuntimeError("synthetic_reporter_explosion")` → run_weekly returns `MainRunResult(status='failed', reason=...)` → DB confirms `runs.status='failed'`.

  **Plan 04-05 pre-finalize pattern unchanged:** The 2-finalize-calls-per-success-run pattern (1 pre-matcher + 1 final-idempotent via `WHERE status='running'` guard) is preserved by `test_pre_finalize_pattern_preserved`. Adding the reporter step did NOT introduce any new finalize() call.

- **`src/ga_crawler/cli.py`** (+126 / -8 LOC) — 4 amendments per PLAN.md:
  1. **Module docstring** — updated overview to list 4 subcommands (was 3) and added Plan 05-05 additions bullet block.
  2. **`_cmd_report` handler** — placed right after `_cmd_matcher`. Mirrors `_cmd_matcher` shape exactly: `init_db(args.db_path)` → `make_engine(args.db_path)` → `SqliteRunWriter(engine)` → `Path(args.repo_root).resolve()` → `cfg = ReportConfig.from_pyproject(args.pyproject)` → if `args.output_dir is not None` then `cfg = dataclasses.replace(cfg, output_dir=args.output_dir)` (frozen-safe mirror of Plan 02-05 `_config_with_overrides` pattern) → `run_reporter_phase(...)` → 8-key JSON payload → `sys.stdout.buffer.write(payload.encode("utf-8"))` → return `0 if result.status == "success" else 2`.
  3. **`report-run` subparser** — `--run-id` (type=int, required=True — T-05-sql-injection mitigation at CLI boundary; argparse rejects non-integer at parse time) + `--output-dir` (default=None, override `[tool.ga_crawler.report].output_dir`) + `--db-path` (default=`prices.db`) + `--pyproject` (default=`pyproject.toml`) + `--repo-root` (default=`.`, resolved via `Path(...).resolve()` so CLI invocation from any cwd has a sensible default).
  4. **Dispatcher entry** — `if args.cmd == "report-run": return _cmd_report(args)` added after the `matcher-run` entry.

  **Rule 1 auto-fix bundled in Task 2:** The natural idiom `print(json.dumps(..., ensure_ascii=False))` raised `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4ca'` on Windows because the reporter's `summary_text` contains Cyrillic + 📊 emoji (D-504 template) and default Windows stdout encoding is cp1252. Fix: `payload = json.dumps(..., ensure_ascii=False, indent=2)` then `sys.stdout.buffer.write(payload.encode("utf-8"))` + `sys.stdout.buffer.write(b"\n")` + `sys.stdout.buffer.flush()`. Bypasses the locale codec entirely; portable across Linux/macOS/Windows. This pattern should propagate to `_cmd_matcher` and `_cmd_weekly` in a follow-up if they ever emit Cyrillic/emoji in JSON output (currently they don't, but they're at risk if anyone adds a reason-string in Russian).

### Test code (2 new integration test files)

- **`tests/integration/test_main_run_with_reporter.py`** (~370 LOC, 8 tests, all green):
  - `test_run_weekly_invokes_reporter_after_matcher` — full pipeline → reporter writes xlsx + MainRunResult populated + all 4 stats namespaces coexist (viled.* + goldapple.* + match.* + report.*) in `result.stats_delta`. The xlsx file exists on disk at `repo_root/result.xlsx_path` and `stat().st_size == xlsx_size_bytes`.
  - `test_run_weekly_viled_only_skips_reporter` — `viled_only=True` → matcher and reporter both skipped → `xlsx_path is None`, `xlsx_size_bytes == 0`, no `report.*` keys in stats_delta, `reports/` dir empty.
  - `test_run_weekly_goldapple_only_skips_reporter` — same for `goldapple_only=True`.
  - `test_run_weekly_matcher_failed_skips_reporter` — plant 1 match, set `sanity_gate_p=10` → matcher fails → main_run early-returns `status='failed'`; reporter NOT invoked; `match.*` keys present but no `report.*` keys.
  - `test_run_weekly_matcher_skipped_path_does_not_invoke_reporter` — patch `run_matcher_phase` to return `status='skipped'` → run still finalizes as success but reporter NOT invoked due to explicit `m_result.status == "success"` gate; no `report.*` keys.
  - `test_data05_reporter_exception_finalizes` — **CANARY** for Plan 02-05 DATA-05 invariant: monkeypatch `run_reporter_phase` to raise `RuntimeError("synthetic_reporter_explosion")` → outer try/except catches → `run_writer.fail` called → MainRunResult `status='failed'` + reason contains exception text; DB confirms `runs.status='failed'`.
  - `test_main_run_result_has_reporter_fields` — direct dataclass construction test for the 4 new fields with default values.
  - `test_pre_finalize_pattern_preserved` — **CANARY** for Plan 04-05 pre-finalize-before-matcher pattern: spy on `SqliteRunWriter.finalize` confirms exactly 2 calls on success path (1 pre-matcher + 1 final-idempotent via `WHERE status='running'` guard). Adding the reporter step did NOT introduce extra finalize calls.

- **`tests/integration/test_cli_report_subcommand.py`** (~280 LOC, 8 tests, all green):
  - `test_cli_help_lists_report_run` — top-level `--help` mentions `report-run`.
  - `test_report_run_help_lists_required_flags` — `report-run --help` lists `--run-id` / `--output-dir` / `--db-path` / `--pyproject`.
  - `test_report_run_missing_run_id_exits_2` — argparse rejects missing `--run-id` (non-zero exit).
  - `test_report_run_non_int_run_id_rejected` — **CANARY** for T-05-sql-injection mitigation: `--run-id abc` rejected by argparse `type=int` BEFORE reaching any SQL.
  - `test_report_run_nonexistent_run_exits_2` — run_id 99999 against empty DB → reporter D-507 skip-gate fires (`upstream_status is None` → `reason='missing_run_row'`) → JSON `status='skipped'` + exit code 2.
  - `test_report_run_success_writes_xlsx_and_exits_0` — planted successful run + matches + upstream stats → exit 0; JSON payload has `xlsx_path` ending in `.xlsx`, `xlsx_size_bytes > 0`, `size_guard_passed=True`, `summary_text` non-empty, `stats_delta_keys` contains `report.*` keys; xlsx file exists on disk at `tmp_path/payload['xlsx_path']` and size matches.
  - `test_report_run_output_dir_override` — `--output-dir custom_reports` → `xlsx_path` starts with `custom_reports/`; file exists at custom path. Verifies `dataclasses.replace(cfg, output_dir=...)` frozen-safe override path.
  - `test_report_run_idempotent_re_invocation` — **CANARY** for D-510: two consecutive subprocess invocations both exit 0; `xlsx_path` identical between runs (file overwritten via `write_atomic` `os.replace`).

  Test harness includes `_extract_payload(stdout)` helper that splits structlog single-line log events (emitted by `_configure_logging`'s `JSONRenderer`) from the CLI handler's indented multi-line JSON payload (via `json.dumps(indent=2)`) by searching for the literal `{\n` sentinel. Test fixture `planted_db` builds a complete minimal-but-realistic state: 1 finalized successful run + 1 viled snapshot + 1 goldapple snapshot + 1 match row + pre-populated upstream stats with `viled.fetch_count`, `goldapple.fetch_count`, `match.count`, `match.rate`, `match.denominator` (Pitfall 6 flat dotted keys).

## Acceptance Criteria

All success criteria from PLAN.md satisfied:

- [x] `src/ga_crawler/runners/main_run.py` amended with reporter step post-matcher; MainRunResult extended with 4 new D-514 fields
- [x] Pre-initialized outcome variables scoped above try block (None / 0 / "" / True defaults)
- [x] Reporter call inside both-retailers branch with explicit `if m_result.status == "success":` gate
- [x] Reporter exception bubbles to existing Plan 02-05 outer try/except (DATA-05 invariant; canary `test_data05_reporter_exception_finalizes` green)
- [x] `src/ga_crawler/cli.py` amended with `_cmd_report` + `report-run` subparser + dispatcher entry; --run-id type=int required; --output-dir override via `dataclasses.replace`
- [x] JSON output includes 8 keys (status, run_id, xlsx_path, xlsx_size_bytes, summary_text, size_guard_passed, reason, stats_delta_keys)
- [x] 16 integration tests green (8 main_run composition + 8 CLI subprocess) — exceeds plan's 10+ target
- [x] DATA-05 reporter-exception canary green
- [x] All 4 stats namespaces (viled.* / goldapple.* / match.* / report.*) coexist in MainRunResult.stats_delta on success path (Pitfall 6 atomic merge canary)
- [x] Zero regression: full `uv run pytest tests/unit tests/integration -x -q` exits 0 (610 passed, 1 skipped — was 594 baseline, +16 new tests)
- [x] `python -m ga_crawler --help` lists `report-run` alongside `goldapple-smoke`, `weekly-run`, `matcher-run`
- [x] `python -m ga_crawler report-run --help` shows all 5 flags

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UnicodeEncodeError on Windows when printing reporter summary_text via print(json.dumps(..., ensure_ascii=False))**
- **Found during:** Task 2 (CLI tests), specifically `test_report_run_success_writes_xlsx_and_exits_0` and downstream tests that parsed JSON output.
- **Issue:** The natural idiom `print(json.dumps({..., "summary_text": result.summary_text, ...}, ensure_ascii=False, indent=2))` raised `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4ca' in position 131: character maps to <undefined>` on Windows. Root cause: D-504 reporter summary template contains Cyrillic + 📊 emoji; Python's default `print()` writes to a stdout opened with the platform locale codec (`cp1252` on Windows EN-US), which cannot encode `\U0001f4ca`. `ensure_ascii=False` makes `json.dumps` emit the literal emoji bytes (correct for Linux/macOS where stdout is UTF-8) but Windows stdout cannot encode them.
- **Fix:** Replaced the `print(...)` call with `payload = json.dumps(...); sys.stdout.buffer.write(payload.encode("utf-8")); sys.stdout.buffer.write(b"\n"); sys.stdout.buffer.flush()`. Bypasses the locale codec entirely by writing UTF-8 bytes directly to the underlying binary stream. Portable across Linux/macOS/Windows.
- **Files modified:** `src/ga_crawler/cli.py` (`_cmd_report` only — left `_cmd_matcher` and `_cmd_weekly` untouched per scope boundary; they currently don't emit Cyrillic/emoji but they're at-risk if anyone ever adds Russian reason-strings).
- **Test:** `test_report_run_success_writes_xlsx_and_exits_0` exercises the fix end-to-end.
- **Commit:** Bundled into the Task 2 GREEN commit (`deb38ec`).

## Self-Check: PASSED

- File `src/ga_crawler/runners/main_run.py` exists and contains `run_reporter_phase(` (1 occurrence) and `xlsx_path:` (2 occurrences — dataclass field + outcome var).
- File `src/ga_crawler/cli.py` exists and contains `def _cmd_report` (1 occurrence) and `"report-run"` (2 quoted occurrences — `add_parser` + dispatcher) + 3 unquoted in docstring/comment (total 5 textual occurrences).
- File `tests/integration/test_main_run_with_reporter.py` exists (8 test functions).
- File `tests/integration/test_cli_report_subcommand.py` exists (8 test functions).
- Commit `f46abaf` (Task 1 RED) exists in git log.
- Commit `34abdd8` (Task 1 GREEN) exists in git log.
- Commit `e0f9c9d` (Task 2 RED) exists in git log.
- Commit `deb38ec` (Task 2 GREEN + Rule 1 auto-fix) exists in git log.
- `uv run pytest tests/unit tests/integration -x -q` → 610 passed, 1 skipped, 0 failures.
- `uv run pytest tests/integration/test_main_run_with_reporter.py tests/integration/test_cli_report_subcommand.py -q` → 16 passed.

## TDD Gate Compliance

- Task 1 RED commit `f46abaf` — `test(05-05): add failing tests for main_run reporter composition (Plan 05-05 Task 1 RED)` — RED gate verified: `AttributeError: 'MainRunResult' has no attribute 'xlsx_path'`.
- Task 1 GREEN commit `34abdd8` — `feat(05-05): wire run_reporter_phase into run_weekly + extend MainRunResult` — 8/8 new tests + 10/10 existing E2E tests pass.
- Task 2 RED commit `e0f9c9d` — `test(05-05): add failing tests for report-run CLI subcommand` — RED gate verified: top-level `--help` missing `report-run` subcommand entry.
- Task 2 GREEN commit `deb38ec` — `feat(05-05): add report-run CLI subcommand for D-509 standalone recovery` — 8/8 new CLI tests pass + full suite 610 passed / 1 skipped.

Both RED→GREEN cycles complete; both `test(...)` commits precede their respective `feat(...)` commits in git log.
