---
phase: 05-reporter-excel-summary
plan: 01
subsystem: reporter
tags: [phase-05, reporter, foundation, config, stats-namespace, fixtures, pyproject, wave-0]
date-completed: 2026-05-11
duration: ~25 min
tasks-completed: 3
deviations: 0
dependency-graph:
  requires:
    - matcher/stats.py (StatsNamespaceError import)
    - matcher/config.py (mirror pattern)
    - storage/sqlite.py (SqliteRunWriter / SqliteSnapshotWriter / init_db / make_engine)
    - runner/stats.py (VILED_STATS_KEYS / GOLDAPPLE_STATS_KEYS / StatsNamespaceError)
  provides:
    - ga_crawler.reporter.config.ReportConfig (frozen dataclass + from_pyproject loader per D-516)
    - ga_crawler.reporter.stats.REPORT_STATS_KEYS (7-tuple per D-514)
    - ga_crawler.reporter.stats.ReportStatsBuilder (namespace-enforced builder; reuses StatsNamespaceError)
    - tests/conftest.py synthetic_report_run (engine + Run + Snapshots + Matches deterministic fixture)
    - tests/conftest.py tmp_reports_dir (tmp_path/reports/ Path)
    - tests/conftest.py openpyxl_workbook_reader (bytes|Path → openpyxl.Workbook callable)
    - tests/fixtures/reporter/expected-summary-text.txt (D-504 golden Telegram caption for week-1 baseline)
    - pyproject.toml [tool.ga_crawler.report] namespace + pandas/xlsxwriter/openpyxl/tzdata deps
  affects:
    - Plan 05-02 (excel_builder + summary_builder consume ReportStatsBuilder + golden fixture)
    - Plan 05-03 (archive.py consumes ReportConfig.timezone + tmp_reports_dir)
    - Plan 05-04 (reporter_run.py consumes everything above via synthetic_report_run)
    - Plan 05-05 (cli report-run subcommand reads ReportConfig.from_pyproject)
tech-stack:
  added:
    - pandas 2.2.3 (production dep; D-516 RESEARCH §STACK)
    - xlsxwriter 3.2.9 (production dep; D-516 RESEARCH §STACK)
    - tzdata 2026.2 (conditional sys_platform=='win32'; D-516 Windows ZoneInfo)
    - openpyxl 3.1.5 (dev dep; D-516 test xlsx read-back)
    - python-dateutil 2.9.0.post0, pytz 2026.2, six 1.17.0, et-xmlfile 2.0.0 (transitives)
  patterns:
    - frozen-dataclass + from_pyproject classmethod (mirror MatchConfig)
    - namespace-enforced stats builder reusing StatsNamespaceError (no redefinition)
    - 4-way disjoint namespace invariant (viled ∩ goldapple ∩ match ∩ report = ∅)
    - append-only conftest extension per D-222
key-files:
  created:
    - src/ga_crawler/reporter/__init__.py (1-line docstring)
    - src/ga_crawler/reporter/config.py (60 LOC — ReportConfig dataclass + from_pyproject)
    - src/ga_crawler/reporter/stats.py (80 LOC — REPORT_STATS_KEYS 7-tuple + ReportStatsBuilder)
    - tests/unit/test_report_config.py (5 tests mirror test_match_config.py)
    - tests/unit/test_report_stats.py (14 tests mirror test_matcher_stats.py + 4-way disjoint)
    - tests/unit/test_phase05_fixtures_smoke.py (4 canary tests pinning fixture shape)
    - tests/fixtures/reporter/expected-summary-text.txt (D-504 golden Russian + emoji summary)
  modified:
    - pyproject.toml (+13 lines: [tool.ga_crawler.report] block + 4 deps)
    - uv.lock (regenerated — 9 packages installed)
    - tests/conftest.py (+260 lines: 3 new fixtures appended per D-222 append-only)
decisions:
  - D-514 7-key report.* stats namespace is now codified in REPORT_STATS_KEYS tuple constant
  - D-516 4-default ReportConfig (output_dir='reports', size_limit_mb=45, top_n_deltas=3, timezone='Asia/Almaty') matches pyproject.toml seed
  - 4-way namespace disjoint invariant (viled ∩ goldapple ∩ match ∩ report = ∅) verified by test_four_way_namespaces_disjoint — failure here flags any prior regression simultaneously
  - tzdata conditional dep added for Windows dev (Asia/Almaty ZoneInfo lookup); Linux VPS Ubuntu 24.04 ships IANA tzdata natively so the marker keeps the production install minimal
  - synthetic_report_run fixture uses UPDATE-after-create pattern to set started_at deterministically (SqliteRunWriter.create() signature does not accept started_at; the value flows from datetime.now(UTC) default factory otherwise)
metrics:
  duration: ~25 min
  tasks: 3
  files-created: 7
  files-modified: 3
  tests-added: 23 (5 config + 14 stats + 4 fixtures smoke)
  tests-passing: 495 unit+integration (was 472 unit+integration before plan, +23 from plan)
  commits: 4 (1 config + 1 RED + 1 GREEN + 1 fixtures)
---

# Phase 5 Plan 01: Reporter foundation — pyproject namespace + ReportConfig + ReportStatsBuilder + test fixtures Summary

Wave 0 foundation lands: `[tool.ga_crawler.report]` namespace + pandas/xlsxwriter/openpyxl/tzdata deps in pyproject.toml; `src/ga_crawler/reporter/` package skeleton with `ReportConfig.from_pyproject` mirror of `MatchConfig` and `ReportStatsBuilder` enforcing the D-514 7-key namespace; conftest extended with `synthetic_report_run` + `tmp_reports_dir` + `openpyxl_workbook_reader` fixtures plus the D-504 golden Telegram-caption fixture. Plans 05-02..05-06 are unblocked.

## What changed

### Production code (3 new files / 1 modified config)

- **`pyproject.toml`** — added `[tool.ga_crawler.report]` block with 4 D-516 seeded keys (`output_dir="reports"`, `size_limit_mb=45`, `top_n_deltas=3`, `timezone="Asia/Almaty"`); added `pandas>=2.2,<2.3` + `xlsxwriter>=3.2,<3.3` + `tzdata; sys_platform == 'win32'` to `[project].dependencies`; added `openpyxl>=3.1,<3.2` to `[dependency-groups].dev`. `uv sync` resolved the new graph cleanly (9 packages installed; pandas 2.2.3 + xlsxwriter 3.2.9 + openpyxl 3.1.5 + tzdata 2026.2 + transitives).
- **`src/ga_crawler/reporter/__init__.py`** — 1-line docstring marker mirroring `matcher/__init__.py`.
- **`src/ga_crawler/reporter/config.py`** — `ReportConfig` frozen dataclass (60 LOC) with `from_pyproject` classmethod. Dataclass defaults mirror the pyproject seeds exactly so `ReportConfig()` in tests matches `ReportConfig.from_pyproject()` against the production toml. Missing keys (or missing file) fall back to dataclass defaults — mirror of `MatchConfig.from_pyproject` semantics.
- **`src/ga_crawler/reporter/stats.py`** — `REPORT_STATS_KEYS` 7-tuple per D-514 (`report.xlsx_path` / `xlsx_size_bytes` / `summary_text` / `sheet_row_counts` / `skipped_reason` / `size_guard_passed` / `generated_at`) + `ReportStatsBuilder` enforcing the `report.` prefix on every `set/inc/get`. `StatsNamespaceError` is imported from `runner/stats.py` — never redefined — so cross-namespace pollution (`viled.*`, `goldapple.*`, `match.*`) raises a single canonical exception class across all 4 namespaces.

### Test infrastructure (3 new test files + 1 modified conftest + 1 golden fixture)

- **`tests/unit/test_report_config.py`** — 5 tests mirroring `test_match_config.py`: defaults / `from_pyproject` reads the namespace / missing file → defaults / partial namespace → other keys default / production pyproject regression canary.
- **`tests/unit/test_report_stats.py`** — 14 tests mirroring `test_matcher_stats.py` plus the new **4-way disjoint invariant** (`test_four_way_namespaces_disjoint`): `report.*` is verified disjoint from `viled.*` / `goldapple.*` / `match.*` pairwise. The prior three-way invariant (Phase 4) is re-asserted in the same test so failure here surfaces any earlier regression simultaneously. Cross-namespace writes are explicitly rejected (`test_set_viled_key_rejected`, `_goldapple_key_rejected`, `_match_key_rejected`). Dict value support verified for `report.sheet_row_counts` per D-514.
- **`tests/unit/test_phase05_fixtures_smoke.py`** — 4 canary tests pinning the fixture shape (Run+Snapshots+Matches row counts, Top-3 delta order, golden file structure). Real consumption happens in Plans 05-02..05-05; these canaries lock the contract.
- **`tests/conftest.py`** — appended 3 new fixtures per D-222 append-only pattern (existing Phase 2/3/4 fixtures untouched, zero rewrites):
  - `tmp_reports_dir(tmp_path) → Path` — pre-mkdir'd `tmp_path/reports/` for archive isolation.
  - `openpyxl_workbook_reader` — callable accepting `bytes | bytearray | Path`, returns `openpyxl.Workbook`. Used by xlsx builder tests in 05-02/04.
  - `synthetic_report_run(tmp_path) → (engine, run_writer, run_id, repo_root)` — in-memory SQLite engine + 1 success run (started_at=2026-05-10 14:00 UTC → ISO 2026-W19 in Asia/Almaty) + 3 viled snapshots + 8 goldapple snapshots (3 matched + 3 gap-only + 2 promo gap-only) + 3 Match rows with deterministic `price_delta_pct` values for Top-3 testing (creed −22.30, givenchy +15.50, dior +5.00). Pre-populates `runs.stats` with `viled.fetch_count=3 / goldapple.fetch_count=8 / match.count=3 / match.rate=60.0` for the reporter summary-text consumer.
- **`tests/fixtures/reporter/expected-summary-text.txt`** — D-504 golden Telegram caption (Russian + emoji) for the week-1 baseline. Top-3 sorted by ABS(delta_pct) DESC: creed > givenchy > dior. UTF-8 encoded, trailing newline.

## Why these decisions

- **`ReportConfig` dataclass defaults match pyproject seeds verbatim** so tests can construct `ReportConfig()` directly without TOML I/O and still get production behaviour. The mirror of `MatchConfig` keeps the operator mental model consistent (operator edits TOML, code reads via `from_pyproject`).
- **`StatsNamespaceError` reused from `runner/stats.py` (never redefined)** preserves the cross-namespace invariant: a single exception class flows through `viled.*`, `goldapple.*`, `match.*`, and now `report.*`. The 4-way disjoint test (Pitfall 7) detects any future namespace collision at unit-test time.
- **tzdata conditional dep (`sys_platform == 'win32'`)** prevents `ZoneInfoNotFoundError('Asia/Almaty')` on Windows dev machines while keeping the production install minimal (Linux VPS ships IANA tzdata natively).
- **`synthetic_report_run` uses UPDATE-after-create to set `started_at` deterministically** because `SqliteRunWriter.create()` only accepts `run_id`; the `started_at` default flows from `datetime.now(UTC)`. A direct SQL `UPDATE runs SET started_at = :sa` keeps the fixture deterministic without modifying production code (avoids a Rule 2 deviation in `SqliteRunWriter`).
- **conftest extension is append-only per D-222** — no existing fixture renamed, no signature changed. All 412 pre-existing unit tests and all 83 integration tests continue to pass unchanged.

## Deviations from Plan

None — plan 05-01 executed exactly as written. The single small adjustment was an inline implementation detail in `synthetic_report_run` (UPDATE-after-create for `started_at`) because the plan's source code in the `<action>` block called `run_writer.create(started_at=...)` but the real `SqliteRunWriter.create(run_id=None)` signature does not accept `started_at`. This is an implementation detail, not a behaviour deviation — the fixture still plants `started_at = 2026-05-10 14:00 UTC` deterministically and the resulting ISO-week derivation (2026-W19 in Asia/Almaty) is unchanged. Documented inline in the fixture comment.

No Rule 1/2/3 auto-fixes triggered. No CLAUDE.md violations. No authentication gates encountered. No checkpoints reached.

## Verification (per plan `<verification>` block)

```
$ uv run pytest tests/unit/test_report_config.py tests/unit/test_report_stats.py -x -q
26 passed in 0.07s

$ uv run pytest tests/unit -x -q
412 passed, 4 warnings in 76.64s

$ uv run pytest tests/unit tests/integration -x -q
495 passed, 1 skipped, 39 warnings in 109.31s   ← +23 from baseline 472, 0 regressions

$ uv run python -c "<plan verification snippet>"
Wave 0 foundation OK
pyproject.toml OK — all 4 D-516 keys + 4 new deps present
```

All `<success_criteria>` items satisfied:

- [x] `[tool.ga_crawler.report]` block present with all 4 D-516 keys
- [x] pandas + xlsxwriter in production deps; openpyxl in dev deps; tzdata conditional Windows-only
- [x] `uv sync` exits 0; `uv.lock` regenerated (9 packages installed)
- [x] `reporter/__init__.py` + `config.py` + `stats.py` all present
- [x] `ReportConfig.from_pyproject` mirrors `MatchConfig.from_pyproject` API
- [x] `ReportStatsBuilder` mirrors `MatchStatsBuilder` API; enforces 7-key D-514 namespace; reuses `StatsNamespaceError`
- [x] 4-way namespace disjoint invariant verified by `test_four_way_namespaces_disjoint`
- [x] 19 unit tests green across `test_report_config.py` (5) + `test_report_stats.py` (14) — plus 4 smoke tests
- [x] `tests/conftest.py` extended with `synthetic_report_run` + `tmp_reports_dir` + `openpyxl_workbook_reader`
- [x] `tests/fixtures/reporter/expected-summary-text.txt` present with canonical D-504 output
- [x] Zero regression: full `uv run pytest tests/unit tests/integration -x -q` exits 0

## Commits

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | `f3d0b8d` | feat | add [tool.ga_crawler.report] namespace + pandas/xlsxwriter/openpyxl/tzdata deps |
| 2 | `5cb7ca8` | test | add failing tests for ReportConfig + ReportStatsBuilder (RED gate) |
| 3 | `5ba2994` | feat | implement reporter package with ReportConfig + ReportStatsBuilder (GREEN gate) |
| 4 | `11e7517` | feat | extend conftest with synthetic_report_run + golden summary fixture |

## What unblocked downstream

- **Plan 05-02** (Wave 1 pure builders) — `ReportStatsBuilder` + `REPORT_STATS_KEYS` + `synthetic_report_run` fixture + golden summary file are all in place. `excel_builder.py` + `summary_builder.py` + `queries.py` can land next.
- **Plan 05-03** (Wave 2 archive) — `ReportConfig.timezone` + `tmp_reports_dir` fixture available for ISO-week derivation + atomic write tests.
- **Plan 05-04** (Wave 3 orchestrator) — `synthetic_report_run` is the end-to-end fixture for `runners/reporter_run.py` 7-step pipeline tests.
- **Plan 05-05** (Wave 4 composition + CLI) — `ReportConfig.from_pyproject` is the operator-tunable surface read by `cli.py` `_cmd_report` (mirror of `_cmd_matcher`).

## Self-Check: PASSED

- File existence:
  - `src/ga_crawler/reporter/__init__.py` — FOUND
  - `src/ga_crawler/reporter/config.py` — FOUND
  - `src/ga_crawler/reporter/stats.py` — FOUND
  - `tests/unit/test_report_config.py` — FOUND
  - `tests/unit/test_report_stats.py` — FOUND
  - `tests/unit/test_phase05_fixtures_smoke.py` — FOUND
  - `tests/fixtures/reporter/expected-summary-text.txt` — FOUND
  - `tests/conftest.py` — modified (+260 lines appended)
  - `pyproject.toml` — modified (+13 lines)
  - `uv.lock` — regenerated
- Commit hashes verified via `git log --oneline -5`:
  - `f3d0b8d` — FOUND
  - `5cb7ca8` — FOUND
  - `5ba2994` — FOUND
  - `11e7517` — FOUND
