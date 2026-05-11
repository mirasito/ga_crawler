---
phase: 5
slug: reporter-excel-summary
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 05-RESEARCH.md §Validation Architecture (committed `c808a12`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio + pytest-mock (already in `[dependency-groups].dev` — pyproject.toml L27-33) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (L42-48) — `asyncio_mode=auto`, `testpaths=["tests"]` |
| **Quick run command** | `uv run pytest tests/unit -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~2-3 min (full ≈380 baseline tests + new ≈25 Phase 5 tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_<changed_module>.py -x` (sub-second)
- **After every plan wave:** Run `uv run pytest -x -q` (~2-3 min)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~3 seconds for unit tests; ~3 min for full suite

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | D-516 | — | ReportConfig.from_pyproject defaults + override | unit | `uv run pytest tests/unit/test_report_config.py -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 0 | D-514 | — | `report.*` namespace enforcement (StatsNamespaceError) + 4-way disjoint | unit | `uv run pytest tests/unit/test_report_stats.py -x` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | REPORT-03 | — | Russian column headers verbatim from D-503 | unit | `uv run pytest tests/unit/test_excel_builder.py::test_russian_headers_match_d503 -x` | ❌ W1 | ⬜ pending |
| 5-02-02 | 02 | 1 | REPORT-04 | — | Summary text matches D-504 template + top-3 ABS sort + zero-match fallback | unit | `uv run pytest tests/unit/test_summary_builder.py -x` | ❌ W1 | ⬜ pending |
| 5-02-03 | 02 | 1 | REPORT-03 | T-05-injection | Excel formula injection sanitization (cells starting with `=+-@` prefixed with `'`) | unit | `uv run pytest tests/unit/test_excel_builder.py::test_formula_injection_sanitized -x` | ❌ W1 | ⬜ pending |
| 5-03-01 | 03 | 2 | D-512 | — | ISO week edge cases (2027-01-01 → 2026-W53; 2025-12-29 → 2026-W01) | unit | `uv run pytest tests/unit/test_archive_iso_week.py -x` | ❌ W2 | ⬜ pending |
| 5-03-02 | 03 | 2 | REPORT-06 | T-05-disk-full | Synthetic >45MB xlsx → `report.size_guard_passed=False` + warning, xlsx persists | unit/integration | `uv run pytest tests/integration/test_archive_size_guard.py -x` | ❌ W2 | ⬜ pending |
| 5-03-03 | 03 | 2 | REPORT-05 | T-05-partial-write | Atomic write via `*.xlsx.tmp` + `os.replace` (crash mid-write leaves no partial file) | unit | `uv run pytest tests/unit/test_archive_atomic_write.py -x` | ❌ W2 | ⬜ pending |
| 5-04-01 | 04 | 3 | REPORT-01 | — | 4 sheets with correct names + column orders (D-503) | integration | `uv run pytest tests/integration/test_reporter_run.py::test_xlsx_has_four_sheets -x` | ❌ W3 | ⬜ pending |
| 5-04-02 | 04 | 3 | REPORT-02 | — | 3-color CF on Дельта,% + freeze_panes + autofilter present | integration | `uv run pytest tests/integration/test_reporter_run.py::test_xlsx_cf_freeze_autofilter -x` | ❌ W3 | ⬜ pending |
| 5-04-03 | 04 | 3 | D-507 | T-05-status-bypass | Failed/running run skips reporter + correct `report.skipped_reason` | integration | `uv run pytest tests/integration/test_reporter_run.py::test_d507_skip_on_failed_run -x` | ❌ W3 | ⬜ pending |
| 5-04-04 | 04 | 3 | REPORT-05 | — | xlsx written to `reports/YYYY-WNN.xlsx`; idempotent re-run overwrites | integration | `uv run pytest tests/integration/test_reporter_run.py::test_filename_iso_week_and_overwrite -x` | ❌ W3 | ⬜ pending |
| 5-04-05 | 04 | 3 | D-514 | — | `report.*` keys 7-key namespace patched via patch_stats (Pitfall 6 atomic) | integration | `uv run pytest tests/integration/test_reporter_run.py::test_report_stats_namespace_keys -x` | ❌ W3 | ⬜ pending |
| 5-05-01 | 05 | 4 | D-511 | — | weekly-run composition writes xlsx after matcher + pre-finalize pattern | integration | `uv run pytest tests/integration/test_main_run_with_reporter.py -x` | ❌ W4 | ⬜ pending |
| 5-05-02 | 05 | 4 | D-509 | — | CLI `report-run --run-id N` produces xlsx + 0 exit; required flag enforced | integration | `uv run pytest tests/integration/test_cli_report_subcommand.py -x` | ❌ W4 | ⬜ pending |
| 5-05-03 | 05 | 4 | DATA-05 | — | reporter exception → run_writer.fail via outer try/except (Plan 02-05 invariant) | integration | `uv run pytest tests/integration/test_main_run_with_reporter.py::test_data05_reporter_exception_finalizes -x` | ❌ W4 | ⬜ pending |
| 5-06-01 | 06 | 5 | REPORT-01..06 | — | Doc cascade — REQUIREMENTS.md REPORT-01..06 closed + REPORT-01 amend per D-502 + STATE.md cascade + pyproject [tool.ga_crawler.report] namespace | docs-only | `git diff --stat HEAD~1 -- .planning/REQUIREMENTS.md .planning/STATE.md .planning/ROADMAP.md pyproject.toml` shows expected lines | ❌ W5 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_report_config.py` — `ReportConfig.from_pyproject` defaults + override (mirror `tests/unit/test_match_config.py` exactly)
- [ ] `tests/unit/test_report_stats.py` — `ReportStatsBuilder` namespace + 4-way disjoint invariant `match.* ∩ viled.* ∩ goldapple.* ∩ report.* = ∅` (mirror `tests/unit/test_matcher_stats.py`)
- [ ] `tests/conftest.py` extension — `synthetic_report_run` fixture (Run + Snapshots + Matches populated end-to-end with paired viled+goldapple rows + 3 matches with known deltas + 2 promos), `tmp_reports_dir` (tmp_path-based output_dir), `openpyxl_workbook_reader` helper (`open xlsx → assert sheets/headers/freeze_panes/autofilter/cf_rules`)
- [ ] `tests/fixtures/reporter/expected-summary-text.txt` — golden D-504 output for week-1 baseline matched run (regression-canary for D-504 template freeze; mirror `test_match_rate_formula_canary` source-lock pattern)

*(No framework install needed — pytest/pytest-asyncio/pytest-mock already in `[dependency-groups].dev`.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Conditional formatting **visually** renders green-white-red gradient in MS Excel / LibreOffice | REPORT-02 | xlsxwriter writes the CF rule into the xlsx XML; the actual color rendering happens at open-time in the spreadsheet application. openpyxl can read back the rule definition but cannot render colors. | Manual: open generated `reports/2026-W19.xlsx` in MS Excel, verify Per-SKU deltas tab — Дельта,% column shows gradient with negative = red, 0 ≈ white, positive = green. Repeat in LibreOffice Calc. Document any rendering quirks in 05-VERIFICATION.md. |
| Russian emoji rendering in Summary sheet cell A1 | REPORT-04 | Emoji codepoints (📊 📦 🎯 🆕 💸 🔝) render based on system font availability. xlsxwriter writes UTF-8 codepoints correctly; rendering depends on opener's font stack (Calibri default falls back to system emoji on Windows 11 / macOS / Linux). | Manual: open xlsx in MS Excel 365, MS Excel 2019, LibreOffice 7+, Google Sheets. Verify emoji visible (not boxes/question marks). Document fallback behavior. |
| ₸ (Kazakhstani Tenge) symbol rendering in number_format `'#,##0 ₸'` | REPORT-03 | ₸ codepoint U+20B8 must be in the cell's number_format string; Excel reads via XLSX's `numFmtId` table. Rendering depends on opener's font availability for U+20B8 (Calibri has it since 2013). | Manual: open xlsx in MS Excel 2013+, LibreOffice 5+, Google Sheets. Verify ₸ shows as "₸" not "□" or "₽" (Russian Ruble confusion). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 3 seconds for unit tests
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
