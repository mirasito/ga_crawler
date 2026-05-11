---
phase: 05-reporter-excel-summary
plan: 02
subsystem: reporter
tags: [phase-05, reporter, builders, excel, summary, queries, conditional-formatting, russian-headers, formula-injection, wave-1]
date-completed: 2026-05-11
duration: ~10 min
tasks-completed: 3
deviations: 0
dependency-graph:
  requires:
    - matcher/strict_key.py (text(":rid") SQL constants pattern + thin engine.connect() reader style — mirror)
    - storage/sqlite.py (Match denormalized 13-col schema D-401 + Snapshot 18-col schema D-202 + Run schema for started_at)
    - tests/conftest.py synthetic_report_run fixture (in-memory SQLite + 1 Run + 3 viled snapshots + 8 goldapple snapshots + 3 matches with known price_delta_pct values)
    - tests/conftest.py openpyxl_workbook_reader fixture (bytes → openpyxl.Workbook callable)
    - tests/fixtures/reporter/expected-summary-text.txt (D-504 golden Telegram caption for week-1 baseline)
  provides:
    - ga_crawler.reporter.queries.PER_SKU_DELTAS_SQL (JOIN-back to snapshots for URLs per Pitfall 9; ORDER BY ABS(price_delta_pct) DESC per D-501)
    - ga_crawler.reporter.queries.ASSORTMENT_GAPS_SQL (NOT EXISTS subquery per Pitfall 8; symmetric D-402 filter on goldapple-side)
    - ga_crawler.reporter.queries.GOLDAPPLE_PROMOS_SQL (SQL-side discount_amount + discount_pct derivation per Pitfall 10)
    - ga_crawler.reporter.queries.TOP_N_DELTAS_SQL (SQL ABS LIMIT :n per Pattern 7)
    - ga_crawler.reporter.queries.RUN_STARTED_AT_SQL (D-512 ISO-week derivation input)
    - ga_crawler.reporter.queries.read_matches_for_run / read_gaps_for_run / read_promos_for_run / read_top_n_deltas / read_run_started_at (5 thin engine.connect() readers; all parameterized via :rid binds, T-05-sql-injection mitigated)
    - ga_crawler.reporter.excel_builder.PER_SKU_HEADERS_RU 11-col dict (D-503 verbatim Russian)
    - ga_crawler.reporter.excel_builder.GAPS_HEADERS_RU 6-col dict (D-503)
    - ga_crawler.reporter.excel_builder.PROMOS_HEADERS_RU 8-col dict (D-503 + Скидка, ₸/Скидка, % derived)
    - ga_crawler.reporter.excel_builder.build_workbook(matches_df, gaps_df, promos_df, summary_text) → bytes (4-sheet xlsx via pd.ExcelWriter engine='xlsxwriter' explicit per Pitfall 1; D-506 always 4 sheets)
    - ga_crawler.reporter.excel_builder._apply_sheet_chrome shared helper (freeze_panes(1,0) + autofilter + auto-width 50-char cap + optional 3-color CF mid_value=0)
    - ga_crawler.reporter.excel_builder._sanitize_cell + _sanitize_dataframe (T-05-injection guard prefixing single quote on =/+/-/@/\t/\r)
    - ga_crawler.reporter.excel_builder._format_for_column (Pitfall 2 US-locale: '#,##0 ₸' for KZT, '0.00' for percent)
    - ga_crawler.reporter.summary_builder.SUMMARY_TEMPLATE + TOP3_HEADER + TOP3_LINE module constants (D-504 source-locked)
    - ga_crawler.reporter.summary_builder.build_summary(*, stats, top3, gaps_count, promo_count, iso_week) → str (keyword-only; reads flat dotted stats per Pitfall 6; D-504 zero-match Top-3 omission)
  affects:
    - Plan 05-03 (archive.py consumes build_workbook() bytes via atomic write to disk)
    - Plan 05-04 (reporter_run.py orchestrator chains queries.* → build_workbook + build_summary in 7-step pipeline against synthetic_report_run)
    - Plan 05-05 (cli report-run subcommand wires ReportConfig + reporter_run)
tech-stack:
  added: []  # no new deps (pandas/xlsxwriter/openpyxl all installed in Plan 05-01)
  patterns:
    - text(":rid") SQL constant + thin engine.connect() reader (mirror matcher/strict_key.py)
    - SQL source-lock canary via str(SQL_CONST) substring assertions (mirror Phase 4 D-405 KPI canary)
    - Behavioral xlsx assertions via openpyxl read-back (NOT exact-hex per Pitfall 3) + source-inspection canaries for parameters not round-tripped through openpyxl (mid_value=0 for CF rule shape, engine='xlsxwriter' explicit)
    - Formula-injection guard via single-quote prefix on cells starting with =/+/-/@/\t/\r (T-05-injection mitigation)
    - SQL-side derivation of report columns (discount_amount + discount_pct in GOLDAPPLE_PROMOS_SQL, ORDER BY ABS in PER_SKU_DELTAS_SQL/TOP_N_DELTAS_SQL) so pandas consumer needs zero math
    - Keyword-only public function signature on build_summary (* sentinel) to prevent positional misordering
    - Golden-file byte-for-byte canary against tests/fixtures/reporter/expected-summary-text.txt (analog of week-1 KPI-rate-canary 6/5/3→60.0 in test_matcher_strict_key.py)
key-files:
  created:
    - src/ga_crawler/reporter/queries.py (~210 LOC — 5 SQL constants + 5 readers)
    - src/ga_crawler/reporter/excel_builder.py (~250 LOC — 3 header dicts + build_workbook + _apply_sheet_chrome + _format_for_column + _sanitize_cell + _sanitize_dataframe + _apply_3_color_scale)
    - src/ga_crawler/reporter/summary_builder.py (~105 LOC — SUMMARY_TEMPLATE + TOP3_HEADER + TOP3_LINE + build_summary)
    - tests/unit/test_reporter_queries.py (14 tests — 7 SQL source-lock canaries + 7 behavioral against synthetic_report_run)
    - tests/unit/test_excel_builder.py (23 tests — D-503 headers + 6 parametrize-expanded formula-injection cases + 2 num_format + 4-sheet order + freeze + autofilter + CF presence + injection round-trip + was_price NULL + 50-char width cap + 2 source-inspection canaries)
    - tests/unit/test_summary_builder.py (12 tests — 3 template source-lock + 1 golden file byte-for-byte canary + 6 branch coverage + 1 integration smoke with build_workbook)
  modified: []  # zero modifications — pure additive plan
decisions:
  - D-501 ORDER BY ABS(price_delta_pct) DESC enforced structurally in PER_SKU_DELTAS_SQL constant (source-locked test asserts substring "ORDER BY ABS")
  - D-502 NOT EXISTS gaps filter enforced structurally in ASSORTMENT_GAPS_SQL (Pitfall 8 — source-locked test asserts "NOT EXISTS" present AND "NOT IN" absent)
  - D-503 11 + 6 + 8 verbatim Russian header dict layouts source-locked in test_excel_builder.py::test_russian_headers_match_d503 (any drift fails immediately)
  - D-504 SUMMARY_TEMPLATE + TOP3_HEADER + TOP3_LINE module constants are the canonical source-of-truth for Telegram caption text; tests/fixtures/reporter/expected-summary-text.txt is the byte-for-byte regression canary
  - D-505 3-color CF mid_value=0 + mid_type='num' parity anchor source-locked via inspect.getsource canary (openpyxl does not round-trip xlsxwriter CF rule shape with full fidelity per Pitfall 3)
  - D-506 always-4-sheets-even-when-empty verified by openpyxl read-back of build_workbook(empty,empty,empty,'') → 4 named sheets
  - D-508 CF on Per-SKU deltas + Goldapple promos ONLY (NOT on Summary or Assortment gaps) verified via openpyxl colorScale rule introspection on each sheet
  - Pitfall 1 (engine='xlsxwriter' explicit, never default) enforced in build_workbook + source-inspection canary
  - Pitfall 2 (US-locale '#,##0 ₸' / '0.00' format strings) enforced in _format_for_column + unit tests reading fmt.num_format directly
  - Pitfall 6 (flat dotted stats keys: stats.get("match.count"), NOT nested) encoded in build_summary signature
  - Pitfall 9 (JOIN-back to snapshots for URLs because matches table is denormalized 13-col without url cols per D-401) enforced in PER_SKU_DELTAS_SQL JOIN structure
  - Pitfall 10 (SQL-side discount derivation in GOLDAPPLE_PROMOS_SQL — pandas consumer does no math) enforced via "discount_amount" / "discount_pct" columns assertions
  - T-05-injection (Excel formula injection) mitigated by _sanitize_cell prefixing single-quote on =/+/-/@/\t/\r in every object-dtype DataFrame column before write; end-to-end round-trip test confirms the prefix persists through openpyxl read-back
  - T-05-sql-injection (SQL injection via run_id) mitigated by exclusive use of text(":rid") parameterized binds; zero f-string interpolation reaches SQL text blocks (verified by canary test asserting ":rid" present in str() of every SQL constant)
metrics:
  duration: ~10 min
  tasks: 3
  files-created: 6 (3 src + 3 unit tests)
  files-modified: 0
  tests-added: 49 (14 queries + 23 excel_builder + 12 summary_builder)
  tests-passing: 544 unit+integration (was 495 before plan, +49 from plan; 1 skipped carry-over)
  commits: 6 (3 RED + 3 GREEN; one TDD cycle per task)
---

# Phase 5 Plan 02: Reporter builders — queries.py + excel_builder.py + summary_builder.py Summary

Wave 1 pure builders ship: 5 SQL primitives (SELECT-only) reading matches + snapshots + runs; the 4-sheet xlsx workbook builder via xlsxwriter (D-503 Russian headers + D-505 3-color CF with mid_value=0 parity anchor + D-506 always-4-sheets + D-508 CF on 2 sheets only + T-05-injection sanitization); and the D-504 Telegram summary template with a byte-for-byte golden-file canary. All three modules are zero-side-effect transforms (no disk I/O, no orchestration) consumed by Plans 05-03 (archive) and 05-04 (reporter_run orchestrator) downstream.

## What changed

### Production code (3 new files, 0 modifications)

- **`src/ga_crawler/reporter/queries.py`** — 5 module-level `text(":rid")` SQL constants:
  - `PER_SKU_DELTAS_SQL` does the JOIN-back to snapshots for URLs (Pitfall 9; D-401 matches table is the denormalized 13-col shape without url columns), filters by `run_id = :rid`, orders by `ABS(price_delta_pct) DESC` (D-501).
  - `ASSORTMENT_GAPS_SQL` uses `NOT EXISTS` correlated subquery (Pitfall 8) instead of `NOT IN` (SQLite optimizer prefers the EXISTS shape; null-safe), plus the symmetric D-402 filter `multipack_flag = 0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'` on the goldapple side.
  - `GOLDAPPLE_PROMOS_SQL` derives `discount_amount` and `discount_pct` columns at the SQL layer (Pitfall 10) so the pandas consumer does no math; sort by `discount_pct DESC` for "most aggressive promo first" UX.
  - `TOP_N_DELTAS_SQL` uses SQL `ABS(...) DESC LIMIT :n` (Pattern 7) so reporter never materializes a 50k-row matches table into pandas just to pick 3.
  - `RUN_STARTED_AT_SQL` is the D-512 ISO-week derivation input. The `read_run_started_at` wrapper defensively handles both `datetime` (production path, SQLModel-managed row) and ISO `str` (test path, raw `text()` SELECT in synthetic_report_run) return types; missing run_id returns `None` (no exception).
  - 5 thin `engine.connect()` readers wrap each SQL constant: 3 return `pd.DataFrame`, 1 returns `list[dict]` (for direct top-N template substitution), 1 returns `Optional[datetime]`.
- **`src/ga_crawler/reporter/excel_builder.py`** — 3 D-503 verbatim Russian header dicts + `build_workbook(matches_df, gaps_df, promos_df, summary_text) → bytes` building the 4-sheet xlsx workbook via `pd.ExcelWriter(BytesIO, engine="xlsxwriter")` (Pitfall 1 explicit, never pandas default). Sheet order is Summary / Per-SKU deltas / Assortment gaps / Goldapple promos (D-506 always 4 sheets, even when all DataFrames empty). The shared `_apply_sheet_chrome` helper applies `freeze_panes(1,0)` + `autofilter` over the data range (or header-only for empty DataFrames) + auto-sized column widths with a 50-char `min(...,50)` cap + (optional) 3-color-scale CF on `Дельта, %` / `Скидка, %`. CF rule has `mid_type='num'` + `mid_value=0` (D-505 parity anchor — without this, a sheet of all-positive deltas would show red at the lowest positive, misleading the user). `_sanitize_cell` is the T-05-injection guard: any text cell whose first char is in `(=, +, -, @, \t, \r)` is prefixed with a single quote so Excel treats it as literal text. `_sanitize_dataframe` applies it to every object-dtype column before write; numeric columns pass through unchanged (defense-in-depth — pandas dtype check is the secondary layer). `_format_for_column` returns `'#,##0 ₸'` xlsxwriter Format for KZT-currency columns and `'0.00'` for percent columns (Pitfall 2 — US-locale storage; Excel renders per OS regional settings). Per D-405 the percent column is pre-scaled ×100, so the format string is `'0.00'` NOT `'0.00%'`. The Summary sheet's A1 cell gets `text_wrap=True` + row height 192 + col width 60 so the multi-line emoji caption renders as wrapped text instead of single-line concatenation (A5 assumption mitigation).
- **`src/ga_crawler/reporter/summary_builder.py`** — `SUMMARY_TEMPLATE` + `TOP3_HEADER` + `TOP3_LINE` module constants are the source-of-truth for the D-504 Telegram caption text. `build_summary(*, stats, top3, gaps_count, promo_count, iso_week) → str` is the pure function: keyword-only signature (sentinel `*`) to prevent positional misordering; reads flat dotted stats keys (`stats.get("match.count", 0)` / `stats.get("match.rate", 0.0)` — Pitfall 6) with default fallbacks so an empty stats dict produces a valid zero-match summary without KeyError. D-504 zero-match fallback: when `match_count == 0` (or `top3 == []`), the entire Top-3 block is OMITTED — no header line, no numbered rows, no leading blank line. When `match_count` is 1 or 2, the header is still emitted but only the rows that exist are listed. Top-3 list is sliced to `[:3]` defensively (caller is responsible for ABS DESC pre-sort; `build_summary` does NOT re-sort).

### Test infrastructure (3 new test files, 0 modifications)

- **`tests/unit/test_reporter_queries.py`** (14 tests) — 7 SQL source-lock canaries via `str(SQL_CONST)` substring assertions: JOIN-back-to-snapshots-for-URLs (Pitfall 9), `ORDER BY ABS(price_delta_pct) DESC` (D-501), `NOT EXISTS` present + `NOT IN` absent (Pitfall 8), D-402 symmetric filter clauses present in gaps SQL, SQL-derived discount columns + `was_price > current_price` clause + `ORDER BY discount_pct DESC` (Pitfall 10), `ABS LIMIT :n` for top-N (Pattern 7), `:rid` bind present in every SQL constant (T-05-sql-injection). Plus 7 behavioral tests against `synthetic_report_run` fixture: `read_matches_for_run` returns 3 rows in `creed > givenchy > dior` order (ABS DESC), 5-row gaps DataFrame with exact brand set `{chanel, armani, ysl, tom ford, givenchy}`, 2-row promos DataFrame with discount_pct ordering 20.0% > 16.67%, top-N returns `list[dict]` with the 4 required template keys, `n=1` LIMIT respected, tz-aware `started_at` returned, missing run_id returns `None`.
- **`tests/unit/test_excel_builder.py`** (23 tests) — D-503 verbatim header source-lock for all 3 dicts (per-SKU 11 cols, gaps 6 cols, promos 8 cols). 6 parametrize-expanded formula-injection cases (`=`, `+`, `-`, `@`, `\t`, `\r`) + normal-text-unchanged regression (`50000`, `None`, `""`, `"givenchy eau de parfum"`). Num-format assertions reading `fmt.num_format` directly (`#,##0 ₸` for KZT cols, `0.00` for percent, `None` for URL/brand). build_workbook returns bytes + 4-sheet name order canary + D-506 empty-DataFrames-still-produce-4-sheets + Summary A1 contains the multi-line emoji caption substring. `freeze_panes == "A2"` and `auto_filter.ref` non-empty on all 3 data sheets via openpyxl read-back. CF colorScale rule present on Per-SKU deltas + Goldapple promos, ABSENT on Summary + Assortment gaps (D-508). T-05-injection end-to-end persistence: a row with `brand_norm = "=cmd|/c calc"` round-trips through xlsx → openpyxl read-back with leading single-quote intact. `viled_was_price=None` / `goldapple_was_price=None` render as empty cell (not "None"/"0"/"—"). Source-inspection canaries (Pitfall 3) for `engine='xlsxwriter'` explicit, `mid_value=0` + `mid_type='num'`, and `min(...,50)` width cap — properties not round-tripped by openpyxl with full fidelity.
- **`tests/unit/test_summary_builder.py`** (12 tests) — 3 template source-lock asserts (`SUMMARY_TEMPLATE` contains each emoji-prefixed line, `TOP3_HEADER` equals `"\n🔝 Топ-3 дельты (viled vs goldapple):"` byte-for-byte, `TOP3_LINE` has all 5 placeholders). **The golden file canary**: `build_summary(synthetic_inputs)` output is compared byte-for-byte against `tests/fixtures/reporter/expected-summary-text.txt` (any drift fails with the full expected vs actual repr printed). D-504 zero-match fallback: `match_count=0` → no `🔝 Топ-3` substring in output. `match_count=1` with `top3=[1 row]` → Top-3 header present + 1 numbered row only (no rows 2 or 3). Top-3 order preservation (caller pre-sorts; builder does NOT re-sort). Empty stats dict defaults to 0 / 0.0 without KeyError. Pitfall 6 flat dotted keys regression. Defensive slice to 3 when caller passes 5 top rows. Integration smoke: summary text passes through `build_workbook` → cell A1 verbatim round-trip.

## Why these decisions

- **`text(":rid")` SQL constants + thin engine.connect() readers** — mirror of `matcher/strict_key.py` SQL style. Module-level constants are source-lockable via `str(SQL).substring` canaries (one canary per D-decision), so any future drift in an `ORDER BY` clause or filter predicate fails the exact regression test that pins the D-decision. No f-string interpolation reaches the SQL text block — only `:rid` / `:n` parameterized binds — so T-05-sql-injection cannot reach SQLite via this layer.
- **JOIN-back to snapshots for URLs (Pitfall 9)** — D-401 matches table is the denormalized 13-col shape and intentionally has NO url columns (URLs change across runs even when SKU keys are stable). The presentation-time JOIN to both retailer-side snapshots reconstructs `viled_url` and `goldapple_url` columns at read time without violating the matches-table schema invariant. This is the most surprising design choice in queries.py and is documented in `read_matches_for_run`'s docstring.
- **NOT EXISTS over NOT IN for gaps (Pitfall 8)** — three reasons stacked: (1) SQLite optimizer prefers `NOT EXISTS` for correlated subqueries with composite keys; (2) `NOT IN` is null-unsafe (if any row in the subquery has NULL, the entire predicate evaluates UNKNOWN and excludes everything); (3) the symmetric D-402 filter naturally lives in the outer SELECT WHERE clause without requiring a CTE.
- **SQL-side discount derivation (Pitfall 10)** — keeping `discount_amount = was_price - current_price` and `discount_pct = ROUND((was_price - current_price) * 100.0 / was_price, 2)` in the SQL layer means: (a) the pandas DataFrame already has the columns the Excel header dict expects, (b) the `ROUND(..., 2)` precision is consistent with Phase 4's `price_delta_pct` precision (both are 2 decimal places), (c) the consumer in excel_builder doesn't need any computation logic — it just renames columns and applies the CF rule.
- **`mid_value=0` + `mid_type='num'` on the 3-color CF rule (D-505)** — without `mid_value=0`, xlsxwriter's default is `percentile=50` which anchors yellow at the median of the data range. On a sheet of all-positive deltas (viled cheaper than goldapple across the board), this would paint the lowest positive value red — misleading. The parity anchor at 0 makes red mean "viled more expensive" universally regardless of the row distribution, which is the correct semantic for a price-comparison report.
- **Formula-injection sanitization on every text cell (T-05-injection)** — Excel formula injection is the only practical attack on a xlsx file consumed by a non-technical user. The defense is universal: every object-dtype DataFrame column gets `_sanitize_cell` applied before write; cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` are prefixed with a single quote (`'`). Numeric columns are safe by construction (Excel sees an int, not a formula). The `dtype == object` check is the secondary defense — if pandas auto-coerces `=1+1` to int (unlikely but possible), Excel sees `1+1=2` already evaluated, not a formula. The parametrize over all 6 trigger chars + end-to-end round-trip test through openpyxl guarantee the prefix persists through the xlsxwriter → openpyxl reader → cell value path.
- **Golden file byte-for-byte canary** — the D-504 Telegram caption text is the structural source-of-truth for Phase 6 delivery (Plan 06 will read `runs.stats.report.summary_text` verbatim and pass it as the `caption` argument to `aiogram.bot.send_document`). Any drift between the template constants in `summary_builder.py` and the operator-facing text in the Telegram message is a contractual break. The golden file is the single artifact both sides reference; if either drifts, the test fails immediately. The synthetic_report_run fixture is the canonical week-1 baseline (3/8 fetch counts, 60% match rate, creed > givenchy > dior top-3) — operator can run `uv run python -c "from ga_crawler.reporter.summary_builder import build_summary; ..." > tests/fixtures/reporter/expected-summary-text.txt` to regenerate after an intentional D-504 update.
- **Source-inspection canaries (Pitfall 3)** — `mid_value=0`, `mid_type='num'`, and the 50-char width cap are properties of the xlsxwriter CF rule and `set_column` call that openpyxl does not round-trip with full fidelity (openpyxl exposes `colorScale.cfvo[1].val` as a string `'0'` but the type marker round-trip is fragile across xlsxwriter/openpyxl version pairs). Asserting via `inspect.getsource(eb._apply_sheet_chrome)` substring match against the source code is the deterministic regression canary. Same pattern for `engine="xlsxwriter"` explicit (Pitfall 1) — if a future refactor accidentally drops the kwarg and pandas swaps to openpyxl as default, no behavioral test in the suite would catch it.

## Deviations from Plan

**None — plan 05-02 executed exactly as written.** All 3 tasks landed on the first RED→GREEN cycle (no debugging iteration). No Rule 1/2/3 auto-fixes triggered. No CLAUDE.md violations. No authentication gates encountered. No checkpoints reached.

A few minor inline implementation polish decisions made within the plan's stated `<action>` blocks:

1. **`read_run_started_at` tz-aware guarantee** — the plan's source code returned `val` directly when it was already a `datetime`. Added a defensive `if val.tzinfo is None: val = val.replace(tzinfo=timezone.utc)` line so the function's return contract is "tz-aware datetime or None" unconditionally. This is a docstring-tightening, not a behavior change for the synthetic_report_run fixture (which stores the run with explicit tz).
2. **Test file naming** — created `tests/unit/test_reporter_queries.py` as a dedicated file rather than embedding queries-related tests in `test_excel_builder.py` as the plan's Task 1 `<behavior>` block allowed ("placed in test_excel_builder.py for now or a new test_queries.py — your choice"). Dedicated file keeps the test-to-source mapping 1:1 with the matcher pattern (`test_matcher_strict_key.py` ↔ `matcher/strict_key.py`).
3. **`test_build_summary_slices_top3_to_three_when_more_provided` added** — defensive coverage for the `top3[:3]` slice in build_summary; not in the plan's 10-test list but a natural pairing with the existing `match_count_less_than_3` branch coverage.

## Verification (per plan `<verification>` block)

```
$ uv run pytest tests/unit/test_excel_builder.py tests/unit/test_summary_builder.py -x -q
35 passed in 0.74s

$ uv run pytest tests/unit/test_report_config.py tests/unit/test_report_stats.py -x -q
26 passed in 0.07s   ← Wave 0 still green, no regression

$ uv run pytest tests/unit tests/integration -x -q
544 passed, 1 skipped, 53 warnings in 106.55s   ← +49 from baseline 495, 0 regressions

$ uv run python -c "<plan end-to-end snippet>"
Builders OK: summary=324 chars, xlsx=7238 bytes
queries.py invariants OK
```

All `<success_criteria>` items satisfied:

- [x] `src/ga_crawler/reporter/queries.py` ships 5 SQL constants + 5 readers, all parameterized via `:rid` binds
- [x] `src/ga_crawler/reporter/excel_builder.py` ships 3 Russian header dicts (D-503 verbatim), `build_workbook()` returning xlsx bytes via `engine='xlsxwriter'`, `_apply_sheet_chrome` shared helper, formula-injection sanitization
- [x] `src/ga_crawler/reporter/summary_builder.py` ships D-504 canonical template constants + `build_summary()` pure function
- [x] 49 unit tests green across 3 new test files (14 queries + 23 excel_builder + 12 summary_builder)
- [x] Golden file canary in `test_summary_builder.py::test_build_summary_golden_file_canary` passes byte-for-byte against `tests/fixtures/reporter/expected-summary-text.txt`
- [x] Sheet order is `Summary, Per-SKU deltas, Assortment gaps, Goldapple promos` (D-506)
- [x] CF rules only on `Per-SKU deltas` + `Goldapple promos` with `mid_value=0` anchor (D-505 + D-508)
- [x] All formula-injection trigger chars (`=`, `+`, `-`, `@`, `\t`, `\r`) sanitized via single-quote prefix; round-trip verified through openpyxl
- [x] Zero regression: full `uv run pytest tests/unit tests/integration -x -q` exits 0 (544 passed, 1 skipped carry-over)

## Commits

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | `307b84d` | test | add failing tests for reporter.queries SQL primitives (RED gate) |
| 2 | `da1af51` | feat | implement reporter.queries SQL primitives (GREEN gate) |
| 3 | `0c432e1` | test | add failing tests for reporter.excel_builder (RED gate) |
| 4 | `55a789d` | feat | implement reporter.excel_builder (GREEN gate) |
| 5 | `6c21917` | test | add failing tests for reporter.summary_builder (RED gate) |
| 6 | `833a244` | feat | implement reporter.summary_builder (GREEN gate) |

## TDD Gate Compliance

| Task | RED commit | GREEN commit | REFACTOR | Notes |
|------|-----------|--------------|----------|-------|
| 1 (queries.py) | `307b84d` | `da1af51` | — | Test collection error → ModuleNotFoundError confirmed RED; GREEN produced 14/14 first-shot |
| 2 (excel_builder.py) | `0c432e1` | `55a789d` | — | Test collection error → ModuleNotFoundError confirmed RED; GREEN produced 23/23 first-shot |
| 3 (summary_builder.py) | `6c21917` | `833a244` | — | Test collection error → ModuleNotFoundError confirmed RED; GREEN produced 12/12 first-shot incl. byte-for-byte golden canary |

All 3 tasks: clean RED → GREEN cycle. No REFACTOR commits needed (production code is at the abstraction level the tests require; further refactoring is YAGNI until Plan 05-04 reveals duplication with the orchestrator).

## What unblocked downstream

- **Plan 05-03** (Wave 2 archive) — `build_workbook()` returns `bytes`, ready to be consumed by `archive.write_atomic(path, bytes)` for the disk-write step. The archive module owns the temp-file-rename pattern + size-guard check; this plan deliberately ships no filesystem I/O so the two concerns stay isolated.
- **Plan 05-04** (Wave 3 orchestrator) — `queries.read_matches_for_run` / `read_gaps_for_run` / `read_promos_for_run` / `read_top_n_deltas` / `read_run_started_at` are the 5 read primitives the 7-step pipeline composes; `build_workbook` + `build_summary` are the 2 transform primitives. The orchestrator's only new logic will be: ISO-week derivation from `started_at` (D-512), atomic single `patch_stats` call to write the 7 `report.*` keys, and the D-507 status-gate check + D-515 size-guard wiring.
- **Plan 05-05** (Wave 4 CLI) — the `report-run` subcommand wires `ReportConfig.from_pyproject` (Plan 05-01) + the orchestrator from Plan 05-04 + the builders from this plan. No new public surface needed here.
- **Plan 06** (Wave 5 Telegram delivery) — reads `runs.stats.report.summary_text` verbatim from the runs JSON column and passes it as the `caption` argument to `aiogram.bot.send_document`. Because `summary_text` is written from this plan's `build_summary` and the golden-file canary pins the template shape, there is zero possibility of drift between the Excel A1 cell, the Telegram caption, and the operator-facing fixture.

## Self-Check: PASSED

- File existence:
  - `src/ga_crawler/reporter/queries.py` — FOUND
  - `src/ga_crawler/reporter/excel_builder.py` — FOUND
  - `src/ga_crawler/reporter/summary_builder.py` — FOUND
  - `tests/unit/test_reporter_queries.py` — FOUND
  - `tests/unit/test_excel_builder.py` — FOUND
  - `tests/unit/test_summary_builder.py` — FOUND
- Commit hashes verified via `git log --oneline -10`:
  - `307b84d` — FOUND (RED queries)
  - `da1af51` — FOUND (GREEN queries)
  - `0c432e1` — FOUND (RED excel_builder)
  - `55a789d` — FOUND (GREEN excel_builder)
  - `6c21917` — FOUND (RED summary_builder)
  - `833a244` — FOUND (GREEN summary_builder)
- Test counts verified: 14 + 23 + 12 = 49 new tests; pytest run produces 544 passed (+49 from 495 baseline; 1 skipped carryover from Plan 02-05).
