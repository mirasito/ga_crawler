---
phase: 05-reporter-excel-summary
plan: 03
subsystem: reporter
tags: [phase-05, reporter, archive, filesystem, atomic-write, iso-week, size-guard, wave-2]
date-completed: 2026-05-12
duration: ~15 min
tasks-completed: 3
deviations: 0
dependency-graph:
  requires:
    - src/ga_crawler/reporter/config.py (ReportConfig defaults — output_dir='reports', size_limit_mb=45, timezone='Asia/Almaty'; consumed by Plan 05-04 caller, NOT by archive.py itself)
    - zoneinfo stdlib (Python 3.12 native; tzdata wheel from Plan 05-01 covers Windows dev for Asia/Almaty lookup)
    - structlog>=25 (structured logging for report_overwritten audit event per D-510)
    - backups/.gitkeep precedent (Phase 2 D-219 — analog directory-tracking pattern for reports/)
  provides:
    - ga_crawler.reporter.archive.derive_filename(started_at, tz_name='Asia/Almaty') → str — D-512 ISO-week filename, rejects naive datetime
    - ga_crawler.reporter.archive.write_atomic(xlsx_bytes, target_path) → int — D-510 crash-safe write via *.xlsx.tmp + os.replace; returns st_size
    - ga_crawler.reporter.archive.check_size_guard(file_path, limit_mb) → tuple[bool, int] — D-515 / REPORT-06 flag-only guard; never raises
    - reports/.gitkeep — directory-tracking sentinel committed to git (mirror Phase 2 D-219)
    - .gitignore exclusions for reports/*.xlsx + reports/*.xlsx.tmp (final artifacts + orphan tmps)
  affects:
    - Plan 05-04 (runners/reporter_run.py orchestrator) — composes build_workbook() → write_atomic() → check_size_guard() → patch_stats; consumes ReportConfig.timezone for D-512 + size_limit_mb for D-515
    - Plan 05-05 (cli report-run subcommand) — wires archive primitives via reporter_run orchestrator
    - Phase 6 (delivery) — reads runs.stats.report.size_guard_passed flag (D-515) + report.xlsx_path; routes >45MB runs to ops-chat alert (DELIVER-03 sanity-gate)
    - Phase 7 (cron + ops playbook) — orphan *.xlsx.tmp cleanup glob (post-crash recovery)
tech-stack:
  added: []  # zero new deps — pure-stdlib (os.replace + datetime.isocalendar + zoneinfo) + structlog (already in tree)
  patterns:
    - tmp-file-sibling + os.replace atomic rename (POSIX + Windows NTFS guarantee; same-FS placement via .with_suffix(suffix + ".tmp"))
    - tz-aware datetime → ZoneInfo.astimezone → isocalendar (D-512 deterministic filename)
    - flag-only size guard (returns tuple, never raises; ARCHITECTURE.md "reporter independent of delivery")
    - directory-tracking via .gitkeep sentinel (mirror Phase 2 D-219 backups/.gitkeep)
    - sparse-file truncate(n) for O(1) large-file fixtures (1 GB test runs in <0.5s)
    - source-inspection canary for invariants not observable through public behavior (the .xlsx.tmp sibling + os.replace pattern is structural — if a future refactor swaps to shutil.move or tempfile.mkstemp on a different FS, atomic-rename crash safety silently breaks; the canary asserts the source code retains the right primitive)
key-files:
  created:
    - src/ga_crawler/reporter/archive.py (~180 LOC — 3 module-level callables + module docstring + structlog logger)
    - tests/unit/test_archive_smoke.py (5 smoke tests — RED gate for Task 1 + symbol-presence canaries)
    - tests/unit/test_archive_iso_week.py (10 tests — 5 parametrized year-boundary + 5 tz/format/return-type)
    - tests/unit/test_archive_atomic_write.py (12 tests — bytes round-trip + parent mkdir + overwrite + no-orphan-tmp + source-inspection + reports/.gitkeep + .gitignore canaries)
    - tests/integration/test_archive_size_guard.py (8 tests — under/exact/over limit + 45 MB D-516 default canary + file persists after check + never-raises on 1 GB + write_atomic combo + zero-byte)
    - reports/.gitkeep (directory-tracking sentinel)
  modified:
    - .gitignore (+6 lines — reports/*.xlsx + reports/*.xlsx.tmp exclusion block, placed after Phase 2 backups/ rules)
decisions:
  - D-510 atomic write is crash-safe via target.with_suffix(target.suffix + ".tmp") sibling + os.replace; the suffix-append pattern (instead of target.with_suffix(".xlsx.tmp")) keeps both .xlsx in the name so glob `reports/*.xlsx.tmp` reliably matches orphans for Phase 7 cleanup
  - D-510 overwrite policy is logged via structlog event report_overwritten with previous_size_bytes when target_path exists pre-write; ops-debugging audit trail without abort/backup behavior
  - D-512 ISO-week derivation is deterministic against re-run because runs.started_at is the input (not finished_at, not now()) — same input → same filename forever; verified by parametrize over 5 year-boundary cases (Pitfall 4)
  - D-515 size guard returns (passed, size_bytes) tuple — flag-only design enables ARCHITECTURE.md "reporter independent of delivery" invariant; xlsx persists on disk even at 1 GB so operator can manually split/recover
  - Inclusive boundary on size guard (`size_bytes <= limit_mb * 1024 * 1024`) pinned by test_size_guard_at_exact_limit_passes_inclusive — a 45 MB exact file passes; 45 MB + 1 byte trips
  - reports/.gitkeep tracked + reports/*.xlsx + reports/*.xlsx.tmp ignored — direct mirror of Phase 2 D-219 (backups/.gitkeep + backups/*.db); consistent directory-tracking convention across Phases 2 and 5
  - Sparse-file optimization (f.truncate(size_bytes)) for size-guard integration fixtures keeps the 1 GB never-raises test under 0.5s while exercising stat().st_size on a logically-large file
metrics:
  duration: ~15 min
  tasks: 3
  files-created: 6 (1 src + 4 tests + 1 reports/.gitkeep)
  files-modified: 1 (.gitignore)
  tests-added: 35 (5 smoke + 10 iso-week + 12 atomic-write + 8 size-guard)
  tests-passing: 579 unit+integration (was 544 before plan, +35 from plan; 1 skipped carry-over)
  commits: 4 (1 RED smoke + 1 GREEN archive.py + 1 feat directory+gitignore+tests + 1 test integration size-guard)
---

# Phase 5 Plan 03: Reporter archive — derive_filename + write_atomic + check_size_guard Summary

Wave 2 filesystem service lands: three pure-stdlib primitives in `reporter/archive.py` shipping ISO-week filename derivation from tz-aware `runs.started_at` (D-512 + Pitfall 4 year-boundary edge cases), crash-safe atomic disk write via `*.xlsx.tmp` sibling + `os.replace` (D-510 + Pitfall 5), and flag-only size guard returning `(passed, size_bytes)` without ever raising (D-515 / REPORT-06). Directory-tracking via `reports/.gitkeep` + `.gitignore` rules for `reports/*.xlsx` and `reports/*.xlsx.tmp` mirrors the Phase 2 D-219 `backups/` precedent. 35 new tests across 4 test files: 5 smoke canaries pinning the public surface, 10 unit tests covering all 5 Pitfall 4 year-boundary cases + tz override + format padding, 12 atomic-write tests including the no-orphan-tmp canary + source-inspection invariant, and 8 size-guard integration tests using sparse-file `truncate(n)` to keep the 1 GB never-raises case at O(1). Plan 05-04 orchestrator is unblocked.

## What changed

### Production code (1 new file)

- **`src/ga_crawler/reporter/archive.py`** — three module-level callables in ~180 LOC, pure-stdlib + structlog:
  - **`derive_filename(started_at, tz_name="Asia/Almaty") -> str`** — D-512 deterministic ISO-week filename. Rejects naive datetime with a `ValueError` that names the DATA-05 invariant for ops debugging. Converts the tz-aware UTC `runs.started_at` via `ZoneInfo(tz_name).astimezone()`, calls `isocalendar()` on the result, and formats `f"{iso_year}-W{iso_week:02d}.xlsx"` with zero-padded week. Default tz matches Phase 7 cron `CRON_TZ=Asia/Almaty` so cron-scheduled runs and `report-run --run-id N` recovery calls produce identical filenames for the same `started_at`.
  - **`write_atomic(xlsx_bytes, target_path) -> int`** — D-510 crash-safe disk write. Auto-creates `target_path.parent` via `mkdir(parents=True, exist_ok=True)`. Builds the tmp sibling via `target_path.with_suffix(target_path.suffix + ".tmp")` so the tmp lives in the same parent directory (same filesystem — required for `os.replace` atomicity per CPython docs on both POSIX and Windows NTFS). Writes bytes to the tmp, then `os.replace(tmp_path, target_path)` performs the atomic rename. Returns `target_path.stat().st_size` so callers don't re-stat. Emits a structlog `report_overwritten` event with `previous_size_bytes` when the target existed pre-write (D-510 overwrite audit trail).
  - **`check_size_guard(file_path, limit_mb) -> tuple[bool, int]`** — D-515 / REPORT-06 flag-only guard. Reads `stat().st_size`, compares against `limit_mb * 1024 * 1024` with **inclusive** boundary (`<=`), returns `(passed, size_bytes)`. Never raises. Callers (Plan 05-04 orchestrator) log `report_size_exceeded` warning and set `report.size_guard_passed=False` flag. xlsx persists on disk regardless — ARCHITECTURE.md "reporter independent of delivery" invariant.

### Test infrastructure (4 new test files)

- **`tests/unit/test_archive_smoke.py`** (5 tests) — RED gate for Task 1. Module import canary (`from ga_crawler.reporter import archive`), 3-callables-exposed assertion, D-512 W19 smoke (2026-05-10 14:00 UTC → 2026-W19), atomic round-trip smoke (bytes in → exact bytes out + correct st_size), size-guard tuple-return smoke. All 5 are exercised under `tmp_path` (pytest builtin) so the smoke file leaves zero artifacts.
- **`tests/unit/test_archive_iso_week.py`** (10 tests) — 5 parametrized year-boundary canaries pin Pitfall 4 (2027-01-01 UTC → 2026-W53; 2025-12-29 UTC → 2026-W01; 2026-05-10 14:00 → 2026-W19; 2026-01-04 18:00 → 2026-W01; 2026-12-31 23:00 → 2026-W53 after Almaty advances to 2027-01-01 04:00 Fri). Plus naive-datetime → ValueError, tz_name override (Almaty 2026-W02 vs UTC 2026-W01 for the same moment), Almaty day-boundary crossing (2026-05-10 22:30 UTC → 2026-W20 because Almaty advances to Monday 03:30), W01 zero-padding canary (`-W1.` substring absent), return-type-is-str canary.
- **`tests/unit/test_archive_atomic_write.py`** (12 tests) — bytes round-trip, return-equals-st_size, parent-dir auto-create on nested path, pre-existing-target overwrite-without-raise, **no-orphan-tmp-on-success canary** (the crash-safety design check — a leftover `*.xlsx.tmp` after a clean write would indicate `os.replace` silently failed), zero-byte payload handled, idempotent repeat-write, second-write-replaces-first (D-510 overwrite), **source-inspection canary** for `.xlsx.tmp` sibling pattern + `os.replace` primitive (Pitfall 3 — invariants not observable through public behavior; if a future refactor swaps to `shutil.move` or cross-FS `tempfile.mkstemp`, atomic-rename safety silently breaks), plus repo-level structural canaries `reports/.gitkeep` tracked + `.gitignore` excludes `reports/*.xlsx` + `reports/*.xlsx.tmp`.
- **`tests/integration/test_archive_size_guard.py`** (8 tests, marked `pytest.mark.integration`) — under-limit returns `(True, ...)`; **exact-limit inclusive boundary** (`size == limit_mb*1024*1024` → passed=True); limit+1 byte trips; 45 MB + 1 byte trips at `limit_mb=45` (D-516 default canary — if anyone tunes ReportConfig default below 45 this test catches the drift); **file-persists-after-check invariant** (ARCHITECTURE.md "reporter independent of delivery" + D-515 "xlsx ВСЕГДА пишется на диск"); **never-raises on 1 GB** (`f.truncate(1024*1024*1024)` makes this O(1) via sparse-file; runs in <0.5s); write_atomic + check_size_guard combination test (Plan 05-04 orchestrator call-sequence smoke — payload above 2 MB trips `limit_mb=2`, passes `limit_mb=3`); zero-byte file passes any positive limit.

### Configuration / directory tracking (1 new sentinel + 1 modified)

- **`reports/.gitkeep`** — empty file, git-tracked. Mirror of Phase 2 D-219 `backups/.gitkeep`. Ensures the `reports/` directory exists on every clone so the reporter's `mkdir(parents=True, exist_ok=True)` call is idempotent and structlog never logs a directory-creation event on first run.
- **`.gitignore`** — appended a 6-line block after the existing Phase 2 `backups/*.db` rules:
  ```
  # Phase 5 reporter artifacts (D-510 output_dir + D-516 namespace).
  # Directory tracked via reports/.gitkeep (mirror Phase 2 D-219 backups/ pattern);
  # xlsx outputs + orphan .xlsx.tmp from interrupted writes ignored.
  reports/*.xlsx
  reports/*.xlsx.tmp
  ```
  The `.xlsx.tmp` rule is the orphan-prevention canary — if a crash leaves a tmp sibling on disk, it won't accidentally land in git. Phase 7 ops playbook will own the glob-and-delete recovery step.

## Why these decisions

- **`target_path.with_suffix(target_path.suffix + ".tmp")` instead of `with_suffix(".xlsx.tmp")`** — `Path("reports/2026-W19.xlsx").with_suffix(".xlsx.tmp")` returns `reports/2026-W19.xlsx.tmp`, which is correct visually but conceptually wrong: `Path.with_suffix` replaces the final extension, not appends. Building the sibling via `suffix + ".tmp"` keeps the semantic clearer ("add `.tmp` to whatever the current suffix is") and stays robust if anyone ever passes a non-.xlsx target. Both approaches produce the same string for our use case, but the append style is the documented Phase 7 cleanup glob target (`reports/*.xlsx.tmp`).
- **`os.replace` over `shutil.move`** — CPython docs explicitly call out `os.replace` as the atomic primitive on both POSIX (single `rename(2)` syscall) and Windows NTFS (`MoveFileEx` with `MOVEFILE_REPLACE_EXISTING`). `shutil.move` falls back to copy-and-delete on cross-FS, which is not atomic. The same-FS guarantee comes from placing the tmp sibling in the target's parent directory, not in `/tmp` or `tempfile.gettempdir()`.
- **Source-inspection canary in `test_write_atomic_uses_xlsx_tmp_suffix_sibling`** — the atomic-rename invariant is structural, not behavioral: a refactor could theoretically write to `tempfile.NamedTemporaryFile()` (default location is `$TMPDIR`, possibly different FS) + `shutil.move`, and all public-behavior tests would still pass on a single-FS dev machine — but production crash-safety would silently break the first time `/tmp` and `reports/` lived on different mounts. The canary asserts `inspect.getsource(write_atomic)` retains the `.tmp` sibling pattern + `with_suffix` + `os.replace` substrings. Pitfall 3 pattern, mirror of the Plan 05-02 source-inspection canaries for `engine='xlsxwriter'` and `mid_value=0`.
- **Sparse-file `f.truncate(n)` for 1 GB test fixture** — `stat().st_size` returns the logical file size, which is what `check_size_guard` reads; the file's allocated blocks on disk can be sparse without affecting the test. This makes the 1 GB never-raises canary O(1) (~milliseconds) instead of writing actual gigabytes (~seconds and disk pressure). Tests stay fast (<2s for the whole integration file) and CI-friendly. Works on NTFS (Windows), ext4 (Linux), APFS (macOS) — all of which support sparse files.
- **Inclusive `<=` boundary on size guard** — D-516 default of 45 MB is "Telegram 50 MB limit minus 5 MB safety". A file at exactly 45 MB is safely deliverable; a file at 45 MB + 1 byte is not. The inclusive boundary makes the threshold exact rather than off-by-one. Pinned structurally by `test_size_guard_at_exact_limit_passes_inclusive` so any future refactor catching `<` instead of `<=` fails immediately.
- **Smoke file as RED gate for Task 1** — Plans 05-01 and 05-02 RED commits used the full test file (forcing collection error → ModuleNotFoundError); for Plan 05-03 the plan's `<action>` for Task 2 explicitly puts the full test files in a *later* task, so the natural RED gate for Task 1 is a smaller smoke file (5 tests) that pins the symbol surface. Task 2 then adds the comprehensive year-boundary parametrize + atomic-write coverage on top of a passing baseline. Same TDD discipline (RED-before-GREEN with `ModuleNotFoundError → ImportError` failure mode) without duplicating the full test-file content in two commits.

## Deviations from Plan

**None — plan 05-03 executed exactly as written.** All 3 tasks landed on the first RED → GREEN cycle (no debugging iteration). No Rule 1/2/3 auto-fixes triggered. No CLAUDE.md violations. No authentication gates encountered. No checkpoints reached.

Two minor inline implementation polish decisions made within the plan's stated `<action>` blocks:

1. **Added `test_archive_smoke.py` as the Task 1 RED gate** — the plan's task structure put all unit tests in Task 2 (with Task 1 owning only the production source). Adding a 5-test smoke file (subset of Task 2's coverage focused on import + 1-line behavior canaries) honors the `tdd="true"` Task 1 RED gate without duplicating the full test files. Tests run in <0.1s and pin the public surface that Tasks 2 / 3 extend.
2. **Added `test_size_guard_zero_byte_file` to Task 3** — defensive coverage for zero-byte path (passes any positive limit). Not in the plan's 7-test list but a natural pairing with `test_write_atomic_zero_bytes_handled` from Task 2 since the orchestrator could in theory hand `check_size_guard` an empty file (e.g. mid-flight failure leaves zero-byte target — albeit unreachable through the atomic-write path).
3. **Added `test_write_atomic_second_write_replaces_first` to Task 2** — explicit D-510 overwrite-policy regression beyond the `test_write_atomic_overwrites_existing` baseline. Distinct because it verifies that a *second* write with different-length payload fully replaces the first (no residual bytes from the larger file).

These adjustments add tests, they don't change the behavior contract or skip anything the plan specified.

## Verification (per plan `<verification>` block)

```
$ uv run pytest tests/unit/test_archive_iso_week.py tests/unit/test_archive_atomic_write.py \
                tests/unit/test_archive_smoke.py tests/integration/test_archive_size_guard.py -x -q
35 passed in 1.65s

$ uv run pytest tests/unit tests/integration -x -q
579 passed, 1 skipped, 53 warnings in 108.34s   ← +35 from baseline 544, 0 regressions

$ test -f reports/.gitkeep && \
  grep -q "reports/\*\.xlsx" .gitignore && \
  grep -q "reports/\*\.xlsx\.tmp" .gitignore && \
  git ls-files reports/.gitkeep | head -1
reports/.gitkeep

$ uv run python -c "<plan verification snippet>"
Wave 2 archive primitives OK
```

All `<success_criteria>` items satisfied:

- [x] `src/ga_crawler/reporter/archive.py` ships 3 module-level functions: `derive_filename`, `write_atomic`, `check_size_guard`
- [x] `reports/` directory tracked via `reports/.gitkeep` (verified `git ls-files reports/.gitkeep` returns 1 line)
- [x] `.gitignore` excludes `reports/*.xlsx` + `reports/*.xlsx.tmp` (both rules present in the appended Phase 5 block)
- [x] 35 tests green across 4 new test files (5 smoke + 10 ISO week + 12 atomic write + 8 size guard — exceeds the plan's 23+ target)
- [x] All ISO year-boundary edge cases per Pitfall 4 verified (2027-01-01 → W53; 2025-12-29 → W01; 2026-12-31 23:00 UTC → 2026-W53 after Almaty advances)
- [x] Atomic write crash-safety verified via `test_write_atomic_no_orphan_tmp_on_success` canary
- [x] Size guard returns tuple, never raises (`test_size_guard_never_raises_on_oversize` with 1 GB sparse file); xlsx persists after over-limit check (`test_size_guard_file_persists_after_check`)
- [x] Inclusive boundary (`<=`) on size guard pinned by `test_size_guard_at_exact_limit_passes_inclusive`
- [x] Zero regression: full `uv run pytest tests/unit tests/integration -x -q` exits 0 (579 passed, 1 skipped carry-over)

## Commits

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | `0732bdd` | test | add failing smoke test for reporter.archive (RED gate) |
| 2 | `7a6bef1` | feat | implement reporter.archive primitives (GREEN gate) |
| 3 | `0c6c098` | feat | add reports/ dir tracking + ISO-week + atomic-write unit tests |
| 4 | `e117910` | test | add size-guard integration tests (D-515 / REPORT-06) |

## TDD Gate Compliance

| Task | RED commit | GREEN commit | REFACTOR | Notes |
|------|-----------|--------------|----------|-------|
| 1 (archive.py) | `0732bdd` (smoke RED) | `7a6bef1` (archive.py GREEN) | — | ImportError on archive submodule absence confirmed RED; 5 smoke tests GREEN on first shot |
| 2 (reports/ + unit tests) | — | `0c6c098` | — | Tests written against existing archive.py (post-Task-1) and pass on creation; commit is `feat` for the directory/.gitignore additions plus the test-deepening. The RED canary for the behaviors here was already captured by Task 1's smoke file |
| 3 (size-guard integration) | — | `e117910` | — | Integration tests written against existing archive.py and pass on creation; commit is `test` (test-only addition). The flag-only invariant was already smoke-gated by Task 1 |

Task 1 follows the canonical RED → GREEN cycle. Tasks 2 and 3 are test-deepening + structural additions on top of a passing baseline; the public-surface RED gate was discharged by Task 1's smoke file. No REFACTOR commits needed.

## What unblocked downstream

- **Plan 05-04** (Wave 3 orchestrator) — `runners/reporter_run.py` 7-step pipeline can now compose `queries.read_run_started_at` → `derive_filename` → `build_workbook` → `write_atomic` → `check_size_guard` → `patch_stats`. The 3 archive primitives are pure-stdlib (no pandas/xlsxwriter dependency at this layer) so the orchestrator can be unit-tested independently of the Excel builder. The `report.xlsx_path` / `report.xlsx_size_bytes` / `report.size_guard_passed` keys (D-514 namespace) all map 1-to-1 to the archive return values.
- **Plan 05-05** (Wave 4 composition + CLI) — `cli.py` `_cmd_report` wires `ReportConfig.timezone` (Plan 05-01) → `derive_filename(tz_name=...)` for operator-tunable timezone (defensive overkill since D-512 mandates Asia/Almaty, but operator-overridable for cross-region recovery scenarios).
- **Phase 6 delivery** — reads `runs.stats.report.size_guard_passed` (set by Plan 05-04 from `check_size_guard` return value). DELIVER-03 sanity-gate routes `False` runs to ops-chat alert instead of business-chat; `True` runs proceed with `send_document` against `report.xlsx_path`.
- **Phase 7 cron + ops playbook** — orphan `*.xlsx.tmp` glob-and-delete is the recovery step for partial writes after a process crash; `.gitignore` rule ensures these never accidentally land in git.

## Self-Check: PASSED

- File existence:
  - `src/ga_crawler/reporter/archive.py` — FOUND
  - `tests/unit/test_archive_smoke.py` — FOUND
  - `tests/unit/test_archive_iso_week.py` — FOUND
  - `tests/unit/test_archive_atomic_write.py` — FOUND
  - `tests/integration/test_archive_size_guard.py` — FOUND
  - `reports/.gitkeep` — FOUND (tracked: `git ls-files reports/.gitkeep` returns the path)
  - `.gitignore` — modified (+6 lines for `reports/*.xlsx` + `reports/*.xlsx.tmp`)
- Commit hashes verified via `git log --oneline -5`:
  - `0732bdd` — FOUND (RED smoke)
  - `7a6bef1` — FOUND (GREEN archive.py)
  - `0c6c098` — FOUND (tests + dir + gitignore)
  - `e117910` — FOUND (integration size-guard)
- Test counts verified: 5 + 10 + 12 + 8 = 35 new tests; pytest run produces 579 passed (+35 from 544 baseline; 1 skipped carryover from Plan 02-05).
