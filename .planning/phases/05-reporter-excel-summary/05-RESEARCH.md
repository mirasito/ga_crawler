# Phase 5: Reporter (Excel + summary) — Research

**Researched:** 2026-05-11
**Domain:** DB-only multi-sheet xlsx reporter (pandas 2.2.x + xlsxwriter 3.2.x) с русскими заголовками, frozen panes, autofilter, 3-color-scale CF, ISO-week filename + atomic write, size-guard для Telegram boundary
**Confidence:** HIGH (стек жёстко локирован CLAUDE.md, все примитивы патент-проверены в Phase 4, единственная LOW-зона — поведение openpyxl при чтении CF-rules из xlsxwriter-сгенерированного файла; митигация задокументирована)

## Summary

Phase 5 — это **pure derivation phase**: ноль fetch/parse/network, только `SELECT … FROM matches/snapshots/runs WHERE run_id=:rid` + pandas-трансформация + xlsxwriter-запись + atomic disk write + один `patch_stats` call в `runs.stats.report.*`. Архитектурно это Phase 4 ещё раз, но с другим выходом (xlsx вместо matches-таблицы) — composition pattern, stats-namespace pattern, sync orchestrator pattern, скип-протокол `read_run_status`, idempotent CLI subcommand — всё уже зацементировано Plan 04-01..04-05 и просто **зеркалится в `report.*`-домен**. Стек локирован: pandas 2.2.x + xlsxwriter 3.2.x (CLAUDE.md §Tech Stack), pyproject уже понимает паттерн `[tool.ga_crawler.<domain>]`, conftest.py уже даёт реалистичные in-memory SQLite фикстуры — `Phase 5 не открывает архитектурных дискуссий, только реализует`.

**Ключевые риски, требующие осторожности в плане:** (1) Excel `num_format` строки **всегда хранятся в US-локали** в файле (`#,##0.00 ₸`, не `#,##0,00 ₸` — рендерится по OS-настройкам читателя; [VERIFIED: WebSearch HackerNoon + XlsxWriter Issue 137 cross-confirmed]); (2) openpyxl читает CF rules от xlsxwriter, но без гарантии семантической эквивалентности — тесты должны опираться на **поведенческие проверки** (cell value, sheet existence, freeze_panes coord, autofilter range) и проверять «есть CF в этом диапазоне» через `worksheet.conditional_formatting`-iterable rather than asserting exact `min_color` hex; (3) xlsxwriter `constant_memory=True` mode исключает `add_table()` + `merge_range()` ([CITED: xlsxwriter `working_with_memory.md`]) — для наших ~50k строк это **НЕ нужно включать**, обычный режим справляется; (4) `Path.replace` через `os.replace` — atomic cross-platform на Windows и POSIX; (5) `date.isocalendar()` корректно обрабатывает год-граничный случай по ISO 8601 — 2027-01-01 (Friday) попадёт в 2026-W53 ([CITED: docs.python.org/3/library/datetime + CalendarZ blog]).

**Primary recommendation:** реализовать пакет `src/ga_crawler/reporter/` (config.py + excel_builder.py + summary_builder.py + archive.py + stats.py) + `src/ga_crawler/runners/reporter_run.py` (sync 7-step orchestrator зеркалит matcher_run.py), amend main_run.py (вставить step ПОСЛЕ matcher до final finalize, идемпотентно по Plan 04-05 pattern), amend cli.py (новый subcommand `report-run --run-id N` зеркалит `matcher-run`), amend pyproject.toml (`[tool.ga_crawler.report]` + dev deps `pandas + xlsxwriter + openpyxl`). Идти Wave-by-Wave (Phase 4 5-wave shape): **Wave 0** (pyproject + deps + ReportConfig + ReportStatsBuilder + reporter/__init__.py skeleton + test fixtures), **Wave 1** (excel_builder.py + summary_builder.py — pure builders, no I/O), **Wave 2** (archive.py — ISO-week filename + atomic write + 45 MB size-guard), **Wave 3** (runners/reporter_run.py orchestrator + integration test), **Wave 4** (main_run amend + cli amend + integration test E2E), **Wave 5** (doc cascade — REQUIREMENTS.md REPORT-01..06 close + REPORT-01 amend per D-502 Action Item, STATE.md cascade per CONTEXT Action Items).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sheet contracts + N→1 duplicates (REPORT-01):**
- **D-501:** Per-SKU deltas — показывать все match-rows как есть (D-403 keep-all preserved). Reporter SELECT-ит `matches WHERE run_id=:rid ORDER BY ABS(price_delta_pct) DESC`, один row = одна match-pair. Dedup-логика **НЕ в reporter** — это commercial-signal D-403 preservation.
- **D-502:** Assortment gaps — SKU-level (одна строка = один goldapple-SKU без viled-пары). Источник: `snapshots WHERE retailer='goldapple' AND run_id=:rid AND multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED' AND (brand_norm, name_norm, volume_norm) NOT IN (SELECT brand_norm, name_norm, volume_norm FROM matches WHERE run_id=:rid)`. Колонки: Бренд / Название / Объём / Цена goldapple, ₸ / Старая цена goldapple, ₸ / URL goldapple.

  **Note re REPORT-01 wording:** REQUIREMENTS говорит «бренды на goldapple, отсутствующие на viled». SKU-level gap внутри overlap-брендов — более корректная интерпретация intent'а. Documented в Action Items для REPORT-01 amendment.

- **D-503:** Russian column headers — formal style + lowercase Latin для retailer-имён. Канонические заголовки: `Бренд`, `Название`, `Объём`, `Цена viled, ₸`, `Старая цена viled, ₸`, `URL viled`, `Цена goldapple, ₸`, `Старая цена goldapple, ₸`, `URL goldapple`, `Дельта, ₸`, `Дельта, %`, `Скидка, ₸`, `Скидка, %`. Источник истины — `reporter/excel_builder.py` константы.

- **D-504:** Text summary REPORT-04 — multi-line block с эмодзи. Используется в Telegram caption (Phase 6) И инсертится в cell A1 листа Summary. Канонический шаблон (week-1 baseline lock) указан в CONTEXT. Top-3 sort: `ABS(price_delta_pct) DESC`. Если match_count < 3 — top-N показывается с тем что есть. Если match_count=0 — заголовок строки "Топ-3 дельты" отсутствует.

**Conditional formatting + zero-match (REPORT-02 + edge cases):**
- **D-505:** 3-color scale (green-white-red) на колонку `Дельта, %` листа Per-SKU deltas. xlsxwriter `worksheet.conditional_format(range, {'type': '3_color_scale', 'min_color': '#F8696B', 'mid_color': '#FFEB84', 'max_color': '#63BE7B'})` с auto min/max и mid=0. Green (positive delta_pct) = goldapple дороже = viled дешевле.
- **D-506:** Reporter всегда строит все 4 листа даже при пустых подмножествах. Пустые листы имеют только headers + frozen pane (row 1) + autofilter, 0 строк данных.
- **D-507:** Reporter работает только на `runs.status='success'`. `runners/reporter_run.py` делает `SELECT status FROM runs WHERE run_id=:rid`. Если status ≠ 'success' — структурированный warning + `patch_stats({'report.skipped_reason': 'failed_upstream'})` + early return. Зеркалит D-411 matcher skip-protocol.
- **D-508:** Conditional formatting применяется к двум листам: `Per-SKU deltas` (колонка `Дельта, %`) + `Goldapple promos` (колонка `Скидка, %`). Все 4 листа имеют: frozen top row, autofilter на header-row, autosized column widths.

**CLI shape + filename + main_run composition (REPORT-05 + SC#3 + integration):**
- **D-509:** CLI shape — standalone subcommand `python -m ga_crawler report-run --run-id N` (required flag). Mirror Phase 4 D-412. Дополнительные flags: `--output-dir`, `--db-path`, `--pyproject`.
- **D-510:** Filename `reports/YYYY-WNN.xlsx` с overwrite policy. Второй вызов перезаписывает первый xlsx без backup. Структурированный лог-event `report_overwritten` если файл существовал.
- **D-511:** main_run composition — reporter вызывается AFTER matcher BEFORE final finalize в `run_weekly`. Pre-finalize matcher pattern Plan 04-05 mirror — `run_writer.finalize(rid, 'success')` до reporter, повторный `finalize` после.
- **D-512:** ISO week derives from `runs.started_at` in Asia/Almaty timezone. Asia/Almaty синхронизирован с Phase 7 cron `CRON_TZ=Asia/Almaty`.

**Module structure + reporter stats namespace + REPORT-06 guard:**
- **D-513:** Module layout — `reporter/` package split + `runners/reporter_run.py` orchestrator. Mirror Phase 4 D-413.
- **D-514:** Stats namespace `report.*` — full keys: xlsx_path / xlsx_size_bytes / summary_text / sheet_row_counts / skipped_reason / size_guard_passed / generated_at (7 keys).
- **D-515:** REPORT-06 size guard — log warning + `report.size_guard_passed=false`, NOT fail run. xlsx ПИШЕТСЯ на диск всегда (для manual recovery). Phase 6 DELIVER-03 sanity-gate ОБЯЗАН читать `report.size_guard_passed`.
- **D-516:** `[tool.ga_crawler.report]` namespace в pyproject.toml — minimal: output_dir / size_limit_mb / top_n_deltas / timezone.

### Claude's Discretion

- **`reports/` directory tracking:** auto-`mkdir(parents=True, exist_ok=True)`; tracked в git via `.gitkeep`; `.gitignore` excludes `reports/*.xlsx`. Mirror Phase 2 D-219 `backups/` pattern.
- **Atomic write:** xlsxwriter пишет к `*.xlsx.tmp` затем `Path.replace`. Planner проверяет xlsxwriter Workbook close-flush semantics.
- **Number formatting:** `'#,##0 ₸'` для цен (KZT тысячи), `'0.00'` для процентов, `'YYYY-MM-DD HH:MM'` для timestamps. Planner проверяет совпадает ли xlsxwriter format с Russian locale ожиданиями.
- **Column widths:** auto-calc на основе longest header + 1-2 char padding; max width 50 chars.
- **`was_price IS NULL` rendering:** пустая ячейка (Excel-friendly).
- **Goldapple promos filter:** `WHERE retailer='goldapple' AND run_id=:rid AND was_price IS NOT NULL AND was_price > current_price AND multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'`. Sort by `Скидка, % DESC`.
- **Test infra:** real on-disk SQLite + real xlsx output + openpyxl-read-back assertions. Synthetic matches fixture с известным delta_pct для CF verification. Phase 5 не пишет live-tests (mirror Phase 4 — no `-m live`).
- **Historical re-run support:** SC#3 `report-run --run-id 17` работает поскольку schema frozen Phase 2..4.
- **Per-brand match-rate в Summary:** v2 territory.
- **Sheet ordering:** Summary первый, затем Per-SKU deltas, Assortment gaps, Goldapple promos.

### Deferred Ideas (OUT OF SCOPE)

- Per-brand match-rate sheet (v2 REPORT-V2-02)
- Week-over-week delta column (v2 REPORT-V2-01)
- New/disappeared SKU sheet (v2 REPORT-V2-03)
- Match-rate degradation alert (v2 REPORT-V2-04)
- Promo-frequency view (v2 REPORT-V2-05)
- PDF-вариант сводки (v2 DELIVER-V2-01)
- Web dashboard для исторических трендов (v2 INFRA-V2-03)
- `report-run --last-success` auto-pick (отвергнуто D-509)
- `reports/` retention rotation (не нужно)
- xlsx encryption / password protection
- Auto-truncate top-N rows при size > 45 MB (отвергнуто D-515)
- Reporter в weekly-run optional flag `--with-report=false` (отвергнуто D-511)
- Multi-language headers (EN + RU)
- Sheet ordering customization через config
- Excel pivot tables / charts
- Live tests против real БД на Hetzner

</user_constraints>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **REPORT-01** | Excel с 4 листами: Summary, Per-SKU deltas, Assortment gaps, Goldapple promos | §"Pattern 1: ExcelWriter multi-sheet + writer.book/writer.sheets" (D-501..D-503) + §"Pattern 4: Sheet contracts (column lists)" |
| **REPORT-02** | CF: подсветка дельт (зелёный — viled дешевле, красный — viled дороже), frozen panes, autofilter | §"Pattern 2: xlsxwriter 3-color scale" (D-505 verbatim API) + §"Pattern 3: freeze_panes + autofilter" |
| **REPORT-03** | Заголовки колонок и текст сводки — на русском | §"Pattern 4: Russian column headers" (D-503 verbatim) + §"Pattern 5: xlsxwriter UTF-8 / `write_string` для emoji-cell A1" |
| **REPORT-04** | Текстовая сводка: viled_count, goldapple_count, match_count, match_rate %, gap_size, top-3 deltas, promo_count | §"Pattern 6: Summary builder reads `runs.stats.match.*` directly" + §"Pattern 7: Top-N via SQL `ORDER BY ABS(price_delta_pct) DESC LIMIT 3`" |
| **REPORT-05** | xlsx записывается на диск в `reports/YYYY-WNN.xlsx` до отправки | §"Pattern 8: ISO-week filename derivation" (D-512) + §"Pattern 9: Atomic write via `*.xlsx.tmp` + `os.replace`" |
| **REPORT-06** | Размер xlsx > 45 MB → явная ошибка, Telegram limit 50 MB | §"Pattern 10: Size-guard (D-515 — log+flag, NOT fail)" + §"Don't Hand-Roll: don't truncate, just signal" |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Read run status + stats | Storage (SQLAlchemy/sqlmodel) | Backend (read_run_status helper) | Pure SQL SELECT; mirror Phase 4 read_run_status() |
| Per-SKU SQL queries (matches/snapshots) | Storage (SQLAlchemy text+bind) | Backend (excel_builder consumes DataFrames) | Same pattern Phase 4 strict_key.py — `text("SELECT … :rid")` + `engine.connect()` |
| DataFrame transformation | Backend (pure pandas) | — | `pd.read_sql + df.sort_values + df.rename` — no I/O |
| xlsx file build | Backend (pandas+xlsxwriter via ExcelWriter) | Filesystem (atomic write) | pandas DataFrame → xlsxwriter via `pd.ExcelWriter(engine='xlsxwriter')`; D-513 owns excel_builder.py |
| Conditional formatting / freeze_panes / autofilter | xlsxwriter (worksheet methods после to_excel) | — | Post-write через `writer.sheets['X']` access |
| Text summary build | Backend (pure string template) | — | Template constants + f-string + reads `runs.stats.match.*` |
| ISO week filename derivation | Backend (Python stdlib `date.isocalendar()` + `ZoneInfo`) | — | Pure function; no third-party tz lib needed (Python 3.12 stdlib) |
| Atomic file write | Filesystem (`os.replace`) | Backend (Path) | Cross-platform atomic; `Path.replace` wraps `os.replace` |
| Size-guard | Backend (Path.stat().st_size) | — | Pure stat; D-515 just logs+flags |
| `runs.stats.report.*` write | Storage (SqliteRunWriter.patch_stats) | Backend (ReportStatsBuilder) | Atomic json_patch — Pitfall 6 invariant reused |
| Orchestration | Backend (runners/reporter_run.py — sync) | — | Mirror Phase 4 matcher_run.py 7-step shape |
| CLI subcommand | Controller (cli.py argparse) | Backend (delegates to reporter_run) | Mirror `matcher-run` exactly |

## Standard Stack

### Core (LOCKED — from CLAUDE.md §Tech Stack, do not relitigate)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Python** | 3.12.x | Runtime | LOCKED `pyproject.toml requires-python = ">=3.12"` [VERIFIED: pyproject.toml line 5] |
| **pandas** | 2.2.x | DataFrame + ExcelWriter | LOCKED CLAUDE.md §Stack. Latest pandas 2.2.3 released 2024-09-20, Python ≥3.9. [VERIFIED: pypi.org/project/pandas/2.2.3]. Pandas 3.0.2 is current latest stable but CLAUDE.md locks the 2.2.x line. Pin: `pandas>=2.2,<2.3`. |
| **xlsxwriter** | 3.2.x | Excel writer engine | LOCKED CLAUDE.md §Stack. Latest 3.2.9. [VERIFIED: pypi.org/project/xlsxwriter]. Pin: `xlsxwriter>=3.2,<3.3`. Pandas 2.2.x auto-detects xlsxwriter engine when `engine='xlsxwriter'` passed to `pd.ExcelWriter`. [CITED: github.com/jmcnamara/xlsxwriter `working_with_pandas.md`]. |
| **openpyxl** | 3.1.x | xlsx READ-back для unit tests | TEST-ONLY (dev dep). Latest stable 3.1.5 (2024-06-28). [VERIFIED: pypi.org/project/openpyxl]. Used to open xlsxwriter-generated files and assert structure. NOT used to write — xlsxwriter is the canonical write engine per CLAUDE.md. |
| **SQLAlchemy 2.x** | (via sqlmodel) | Raw `text()` SQL execution | Already in pyproject via `sqlmodel>=0.0.24,<0.1`. Phase 5 uses `engine.connect()` + `conn.execute(text("SELECT …"), {"rid": run_id})` per Phase 4 strict_key.py pattern [VERIFIED: src/ga_crawler/matcher/strict_key.py]. |
| **structlog** | 25.x | Structured logging | Already in pyproject. Phase 5 uses for `report_skipped_failed_run` / `report_size_exceeded` / `report_overwritten` events. |
| **stdlib `zoneinfo`** | Python 3.12 builtin | ISO-week tz conversion | `from zoneinfo import ZoneInfo; ZoneInfo("Asia/Almaty")`. No third-party tz lib needed. [VERIFIED: docs.python.org/3/library/zoneinfo + Python 3.12 stdlib]. |
| **stdlib `os`/`pathlib`** | builtin | Atomic write via `os.replace` | Cross-platform atomic since Python 3.3 [CITED: docs.python.org/3/library/os.html#os.replace]. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **tomllib** | Python 3.11+ stdlib | Read `[tool.ga_crawler.report]` | `import tomllib` — used by `ReportConfig.from_pyproject` mirror of `MatchConfig.from_pyproject` (matcher/config.py:12) [VERIFIED: src/ga_crawler/matcher/config.py]. |
| **dataclasses (frozen=True)** | stdlib | `ReportConfig` dataclass | Mirror `MatchConfig` (matcher/config.py:17) [VERIFIED]. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pandas+xlsxwriter | **openpyxl write mode** | Slower, less polished formatting API for conditional_format + 3_color_scale. Pandas 2.2.x defaults to openpyxl when present; we **must explicitly pass `engine='xlsxwriter'`**. CLAUDE.md §"What NOT to use" line 408 locks: «openpyxl для write-heavy reports — slower, less polished». |
| pandas | **polars** | At ~50k row scale polars adds API to learn for tiny perf win. CLAUDE.md §"What NOT to use" line 406 locks rejection. |
| xlsxwriter `constant_memory=True` | xlsxwriter default mode | constant_memory **disables `add_table()` + `merge_range()`** [CITED: working_with_memory.md]. Default memory mode is fine for our scale (~50k rows × 11 cols ≈ 550k cells, ~5-15 MB peak RAM). Не включать без необходимости. |
| Atomic write via `*.xlsx.tmp` + `Path.replace` | Direct write to final path | Direct write race-fragile при crash — half-written file remains. `os.replace` is atomic cross-platform per Python docs. **Use atomic write.** |
| `Path.replace` | `shutil.move` | `shutil.move` is NOT atomic when crossing filesystem boundaries (falls back to copy+delete). `os.replace`/`Path.replace` is atomic when src+dst on same FS (our case — both in repo_root). **Use `Path.replace`.** |
| ISO week via `started_at.isocalendar()` | week derivation by hand | Stdlib handles year-boundary case correctly: 2027-01-01 (Friday) → ISO 2026-W53 [CITED: CalendarZ blog "ISO Week Numbers Explained"]. **Use stdlib.** |
| `runs.stats.match.rate` source | recompute formula locally in reporter | D-405 KPI formula frozen with week-1 baseline. Reporter **MUST cite verbatim** to avoid drift. **Read, never recompute.** |

**Installation:**
```bash
# Production deps (add to pyproject.toml [project].dependencies)
uv add pandas>=2.2,<2.3 xlsxwriter>=3.2,<3.3

# Dev/test deps (add to [dependency-groups].dev)
uv add --dev openpyxl>=3.1,<3.2
```

**Version verification:** [VERIFIED: pypi.org 2026-05-11] pandas 2.2.3 (2024-09-20, Python ≥3.9) + xlsxwriter 3.2.9 (current, Python ≥3.8) + openpyxl 3.1.5 (2024-06-28, Python ≥3.8). All compatible with our Python 3.12 floor.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  CLI subcommand `report-run --run-id N`           │
│                  OR weekly-run composition step                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│   runners/reporter_run.py — `run_reporter_phase(run_id, ...)`     │
│   Step 1: read_run_status(engine, rid) ──── D-507 skip-gate       │
│           ↓ if status != 'success' → patch_stats skip; return     │
│   Step 2: read runs.stats → extract match.* keys for summary      │
│   Step 3: SELECT * FROM matches WHERE run_id=:rid                 │
│           ORDER BY ABS(price_delta_pct) DESC                      │
│   Step 4: SELECT … FROM snapshots (gaps + promos queries)         │
│   Step 5: Pure builders:                                          │
│           summary_builder.build(stats, matches, gaps, promos)     │
│                ↓ returns multi-line emoji text                    │
│           excel_builder.build(matches, gaps, promos, summary_txt) │
│                ↓ returns BytesIO OR Path                          │
│   Step 6: archive.write_atomic(xlsx_bytes, repo_root, started_at) │
│           ↓ derives reports/YYYY-WNN.xlsx via ISO week (D-512)    │
│           ↓ writes to *.xlsx.tmp then os.replace                  │
│           ↓ stat size → size_guard_passed bool                    │
│   Step 7: ReportStatsBuilder.set(xlsx_path/size/summary_text/…)   │
│           → run_writer.patch_stats(rid, builder.delta)            │
│           → return ReporterPhaseResult                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│             reports/2026-W19.xlsx (4 sheets)                      │
│             + runs.stats.report.* (7 keys)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    Phase 6 (DELIVER) — reads
                    report.xlsx_path + .summary_text
                    + .size_guard_passed (DELIVER-03 gate)
```

### Recommended Project Structure

```
src/ga_crawler/
├── reporter/                  # NEW package (D-513 — mirror matcher/)
│   ├── __init__.py            # 1-line docstring (mirror runner/__init__.py)
│   ├── config.py              # ReportConfig.from_pyproject (mirror matcher/config.py)
│   ├── stats.py               # ReportStatsBuilder + REPORT_STATS_KEYS (D-514 — mirror matcher/stats.py)
│   ├── excel_builder.py       # build_workbook(matches_df, gaps_df, promos_df, summary_text) → bytes/Path
│   ├── summary_builder.py     # build_summary(stats_dict, top3_rows, gaps_count) → str (D-504 template)
│   ├── archive.py             # derive_filename(started_at, tz) + write_atomic(bytes, path) + size_guard
│   └── queries.py             # SQL constants + helpers (mirror matcher/strict_key.py SQL constants)
└── runners/
    ├── reporter_run.py        # NEW — sync 7-step orchestrator (mirror matcher_run.py shape exactly)
    └── main_run.py            # AMEND — insert run_reporter_phase step after matcher (D-511)
cli.py                          # AMEND — add `report-run` subcommand (D-509, mirror `matcher-run`)

reports/                        # NEW dir, .gitkeep tracked, *.xlsx in .gitignore (mirror backups/ D-219)

tests/
├── unit/
│   ├── test_report_config.py        # ReportConfig.from_pyproject (mirror test_match_config.py)
│   ├── test_report_stats.py         # ReportStatsBuilder namespace enforcement (mirror test_matcher_stats.py)
│   ├── test_summary_builder.py      # multi-line template + top-3 ABS sort + zero-match fallback
│   ├── test_excel_builder.py        # in-memory BytesIO + openpyxl read-back assertions
│   └── test_archive_iso_week.py     # isocalendar boundary cases + atomic write atomicity sim
└── integration/
    ├── test_reporter_run.py         # real on-disk SQLite + run_reporter_phase + xlsx assertions
    ├── test_cli_report_subcommand.py  # subprocess `python -m ga_crawler report-run --run-id N`
    └── test_main_run_with_reporter.py  # E2E: weekly-run → reporter step → xlsx exists + stats populated

pyproject.toml                  # AMEND — add [tool.ga_crawler.report] (D-516), pandas+xlsxwriter+openpyxl
```

### Pattern 1: ExcelWriter multi-sheet + `writer.book` / `writer.sheets`

**What:** pandas DataFrame → multi-sheet xlsx через `pd.ExcelWriter(engine='xlsxwriter')`. После `df.to_excel(writer, sheet_name='X')` доступ к нативным xlsxwriter workbook+worksheet через `writer.book` + `writer.sheets[sheet_name]` — оттуда любые xlsxwriter calls (conditional_format, freeze_panes, autofilter, set_column, write_string).

**When to use:** Все 4 листа Phase 5. Это **единственный паттерн** для combining pandas table-write + xlsxwriter cell-level formatting.

**Source:** [CITED: github.com/jmcnamara/xlsxwriter `example_pandas_column_formats.md` + `example_pandas_multiple.md` via Context7].

**Example:**
```python
# Source: xlsxwriter docs working_with_pandas.md + example_pandas_column_formats.md
import io
import pandas as pd

def build_workbook(
    matches_df: pd.DataFrame,
    gaps_df: pd.DataFrame,
    promos_df: pd.DataFrame,
    summary_text: str,
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # ---- Sheet 1: Summary (text in A1 + KPI block below) ----
        # Empty DataFrame to anchor the sheet; we write everything cell-by-cell.
        pd.DataFrame().to_excel(writer, sheet_name="Summary", index=False, header=False)
        workbook = writer.book
        ws_summary = writer.sheets["Summary"]
        ws_summary.write_string(0, 0, summary_text)  # cell A1
        # KPI block at A3..B9 (label / value)
        # ws_summary.write(2, 0, "viled_count"); ws_summary.write(2, 1, viled_count); …

        # ---- Sheet 2: Per-SKU deltas (matches table) ----
        # Rename to Russian headers BEFORE to_excel (D-503).
        matches_ru = matches_df.rename(columns=PER_SKU_HEADERS_RU)
        matches_ru.to_excel(writer, sheet_name="Per-SKU deltas", index=False)
        ws_deltas = writer.sheets["Per-SKU deltas"]
        _apply_sheet_chrome(ws_deltas, workbook, matches_ru, conditional_col="Дельта, %")

        # ---- Sheet 3: Assortment gaps ----
        gaps_ru = gaps_df.rename(columns=GAPS_HEADERS_RU)
        gaps_ru.to_excel(writer, sheet_name="Assortment gaps", index=False)
        _apply_sheet_chrome(writer.sheets["Assortment gaps"], workbook, gaps_ru)

        # ---- Sheet 4: Goldapple promos ----
        promos_ru = promos_df.rename(columns=PROMOS_HEADERS_RU)
        promos_ru.to_excel(writer, sheet_name="Goldapple promos", index=False)
        _apply_sheet_chrome(
            writer.sheets["Goldapple promos"], workbook, promos_ru, conditional_col="Скидка, %"
        )
    return buffer.getvalue()
```

### Pattern 2: xlsxwriter 3-color scale conditional formatting (D-505)

**What:** Apply green-white-red gradient на колонку `Дельта, %` (или `Скидка, %` для promos) с auto-min, mid=0, auto-max.

**When to use:** Two sheets only per D-508: `Per-SKU deltas.Дельта, %` + `Goldapple promos.Скидка, %`. NOT on Summary or Assortment gaps.

**Source:** [CITED: github.com/jmcnamara/xlsxwriter `working_with_conditional_formats.md` + `example_conditional_format.md` via Context7].

**Example:**
```python
# Source: xlsxwriter docs example_conditional_format.md
# D-505 colors: green = positive delta_pct (viled cheaper), red = negative (viled more expensive)

# Find the column index of "Дельта, %" in the renamed DataFrame
delta_col_idx = list(df_ru.columns).index("Дельта, %")
n_rows = len(df_ru)

# Excel range = data rows only (skip header row 0); A1-notation form is convenient
# Column letter from index: chr(ord('A') + idx) works only up to col 26 — use xl_col_to_name for safety
from xlsxwriter.utility import xl_col_to_name
col_letter = xl_col_to_name(delta_col_idx)
first_data_row = 2  # row 1 is header (1-indexed for A1 notation)
last_data_row = 1 + n_rows  # 1 header + n_rows data
cf_range = f"{col_letter}{first_data_row}:{col_letter}{last_data_row}"

worksheet.conditional_format(cf_range, {
    "type": "3_color_scale",
    "min_color": "#F8696B",   # red — viled more expensive
    "mid_color": "#FFEB84",   # yellow — near-parity
    "max_color": "#63BE7B",   # green — viled cheaper
    # min_type/max_type defaults to 'min'/'max' (auto data range)
    # mid_type='num', mid_value=0 anchors mid at zero — IMPORTANT
    "mid_type": "num",
    "mid_value": 0,
})
```

**Critical detail re D-505:** Auto-min/auto-max + `mid_type='num', mid_value=0` anchors the midpoint at 0 regardless of data range. Without `mid_value=0`, mid defaults to `percentile=50`, which means a sheet where all values are positive would still show red at the lowest positive value — misleading. **Anchor mid at 0** для семантики «zero=parity, green=viled win, red=viled lose».

### Pattern 3: freeze_panes + autofilter + autosized column widths

**What:** Frozen top row + autofilter on header row + per-column width sized to content.

**When to use:** All 4 sheets per D-508 (including empty sheets per D-506 — header-only sheet still gets frozen pane + autofilter, just zero data rows).

**Source:** [CITED: xlsxwriter `worksheet.md` freeze_panes + autofilter + set_column via Context7].

**Example:**
```python
def _apply_sheet_chrome(worksheet, workbook, df_ru, conditional_col=None):
    """Apply frozen panes + autofilter + column widths + (optional) CF + number formats."""
    n_rows, n_cols = df_ru.shape

    # 1. Freeze top row — A1 notation 'A2' OR (1, 0) form
    worksheet.freeze_panes(1, 0)

    # 2. Autofilter — full data range including header
    if n_rows > 0:
        worksheet.autofilter(0, 0, n_rows, n_cols - 1)
    else:
        # D-506 empty sheet: autofilter on header row only (range 0,0,0,n_cols-1)
        worksheet.autofilter(0, 0, 0, n_cols - 1)

    # 3. Auto column widths (header-content based; cap at 50 chars per Claude's Discretion)
    for col_idx, col_name in enumerate(df_ru.columns):
        col_data = df_ru[col_name].astype(str) if n_rows > 0 else pd.Series([], dtype=str)
        max_content = max(
            [len(str(col_name))] + [len(v) for v in col_data]
        )
        width = min(max_content + 2, 50)  # padding + cap
        # Apply per-column number format for price/percent columns
        fmt = _format_for_column(col_name, workbook)  # see Pattern 5
        worksheet.set_column(col_idx, col_idx, width, fmt)

    # 4. Apply CF if requested
    if conditional_col and conditional_col in df_ru.columns and n_rows > 0:
        _apply_3_color_scale(worksheet, df_ru, conditional_col)
```

### Pattern 4: Russian column headers + sheet contracts (D-503 verbatim)

**What:** Module-level constants in `excel_builder.py` defining header maps per sheet.

**When to use:** Renaming SQL-result DataFrames before `df.to_excel(…)`. Source-of-truth lives in code, not pyproject — changing headers requires PR (mirror D-405 KPI formula freeze pattern).

**Example:**
```python
# src/ga_crawler/reporter/excel_builder.py — D-503 source-locked headers

PER_SKU_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "viled_price": "Цена viled, ₸",
    "viled_was_price": "Старая цена viled, ₸",
    "viled_url": "URL viled",                 # NOTE: matches table has no url cols — see Open Q1
    "goldapple_price": "Цена goldapple, ₸",
    "goldapple_was_price": "Старая цена goldapple, ₸",
    "goldapple_url": "URL goldapple",         # NOTE: see Open Q1
    "price_delta": "Дельта, ₸",
    "price_delta_pct": "Дельта, %",
}

GAPS_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "current_price": "Цена goldapple, ₸",
    "was_price": "Старая цена goldapple, ₸",
    "url": "URL goldapple",
}

PROMOS_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "current_price": "Цена goldapple, ₸",
    "was_price": "Старая цена goldapple, ₸",
    "discount_amount": "Скидка, ₸",
    "discount_pct": "Скидка, %",
    "url": "URL goldapple",
}
```

### Pattern 5: xlsxwriter number formats + Russian locale rendering

**What:** `num_format` strings always stored in **US locale** (`#,##0.00`, comma=thousands, dot=decimal) in the xlsx file. Excel renders per OS regional settings of the reader — Russian Windows shows `5 990,00`, English Windows shows `5,990.00`. Don't try to localize the format string itself.

**When to use:** Price columns (`#,##0 ₸` for integer KZT), percent columns (`0.00` plain decimal — NOT `0%` since data are already `*100`-scaled per D-401 `price_delta_pct = ROUND(… * 100.0 / …)`).

**Source:** [VERIFIED: github.com/jmcnamara/XlsxWriter Issue #137 + HackerNoon "How to Specify Data Format in Excel with Python" cross-confirmed].

**Example:**
```python
def _format_for_column(col_name: str, workbook) -> object | None:
    """Map Russian header → xlsxwriter Format object."""
    if col_name in (
        "Цена viled, ₸", "Старая цена viled, ₸",
        "Цена goldapple, ₸", "Старая цена goldapple, ₸",
        "Дельта, ₸", "Скидка, ₸",
    ):
        # KZT integer with thousands separator + ₸ suffix.
        # NOTE: US-locale format string — renders as '5 990 ₸' on Russian Windows, '5,990 ₸' on English.
        return workbook.add_format({"num_format": "#,##0 ₸"})
    if col_name in ("Дельта, %", "Скидка, %"):
        # Percent already pre-scaled (×100) per D-405 formula. Use '0.00' not '0.00%'.
        return workbook.add_format({"num_format": "0.00"})
    if col_name in ("URL viled", "URL goldapple"):
        # Optional: blue underline + url type (xlsxwriter write_url) — see Open Q2
        return None
    return None  # default (Excel auto-format)
```

**Cross-checked:** xlsxwriter handles emoji + Cyrillic + ₸ natively as UTF-8 inside the xlsx zip; **no font configuration needed** [CITED: xlsxwriter `working_with_data.md` "Writing unicode data"]. Python source MUST be UTF-8 (already the default in Python 3.x).

### Pattern 6: Summary builder reads `runs.stats.match.*` directly (D-504 template)

**What:** `summary_builder.build_summary(stats: dict, top3: list, gaps_count: int, promo_count: int, iso_week: str) -> str`.

**When to use:** Called by orchestrator AFTER reading `runs.stats` via `run_writer.get_stats(run_id)` (existing helper, [VERIFIED: src/ga_crawler/storage/sqlite.py:235 `SqliteRunWriter.get_stats`]). Returns the canonical D-504 template string.

**Source:** Mirror Phase 4 patterns + D-504 verbatim template. Reads keys per [VERIFIED: src/ga_crawler/matcher/stats.py:21-32 MATCH_STATS_KEYS — `match.count`, `match.rate`, `match.viled_comparable_count`, `match.goldapple_comparable_count`].

**Example:**
```python
# src/ga_crawler/reporter/summary_builder.py
SUMMARY_TEMPLATE = """\
📊 Неделя {iso_week} — viled vs goldapple

📦 viled: {viled_count} SKU  •  goldapple: {goldapple_count} SKU
🎯 Совпало: {match_count} ({match_rate}%)
🆕 Гэпы: {gaps_count} SKU у goldapple без viled-пары
💸 Промо у goldapple: {promo_count} SKU
"""

TOP3_HEADER = "\n🔝 Топ-3 дельты (viled vs goldapple):"
TOP3_LINE = " {n}. {brand} {name} {volume}: {delta_pct}%"

def build_summary(
    stats: dict,
    top3: list[dict],
    gaps_count: int,
    promo_count: int,
    iso_week: str,
) -> str:
    """D-504 canonical template — week-1 baseline locked."""
    viled_count = stats.get("viled.fetch_count", 0)
    goldapple_count = stats.get("goldapple.fetch_count", 0)
    match_count = stats.get("match.count", 0)
    match_rate = stats.get("match.rate", 0.0)

    body = SUMMARY_TEMPLATE.format(
        iso_week=iso_week,
        viled_count=viled_count,
        goldapple_count=goldapple_count,
        match_count=match_count,
        match_rate=match_rate,
        gaps_count=gaps_count,
        promo_count=promo_count,
    )

    # D-504: omit Top-3 header entirely if match_count == 0
    if match_count > 0 and top3:
        body += TOP3_HEADER + "\n"
        for n, row in enumerate(top3[:3], start=1):
            body += TOP3_LINE.format(
                n=n,
                brand=row["brand_norm"],
                name=row["name_norm"],
                volume=row["volume_norm"],
                delta_pct=row["price_delta_pct"],
            ) + "\n"
    return body
```

### Pattern 7: Top-N via SQL `ORDER BY ABS(price_delta_pct) DESC LIMIT 3`

**What:** SQLite has native `ABS()`. Use it in the matches query, not Python sort, so reporter scales to 50k+ matches without materializing all rows just to pick 3.

**Example:**
```python
# src/ga_crawler/reporter/queries.py — mirror matcher/strict_key.py SQL constants style

TOP_N_DELTAS_SQL = text(
    """
    SELECT brand_norm, name_norm, volume_norm, price_delta_pct
    FROM matches
    WHERE run_id = :rid
    ORDER BY ABS(price_delta_pct) DESC
    LIMIT :n
    """
)

def read_top_n_deltas(engine, run_id: int, n: int = 3) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(TOP_N_DELTAS_SQL, {"rid": run_id, "n": n}).fetchall()
    return [dict(zip(["brand_norm", "name_norm", "volume_norm", "price_delta_pct"], r)) for r in rows]
```

### Pattern 8: ISO-week filename derivation (D-512)

**What:** Asia/Almaty tz-aware → `started_at.isocalendar()` → `(iso_year, iso_week, iso_weekday)` → `f"{iso_year}-W{iso_week:02d}.xlsx"`.

**Edge case verified:** ISO 8601 specifies week 1 contains the first Thursday of the year. 2027-01-01 (Friday) → ISO `(2026, 53, 5)` because the week containing Jan 1-3, 2027 has its Thursday (Dec 31) in 2026. [CITED: docs.python.org/3/library/datetime + CalendarZ blog "ISO Week Numbers Explained"]. Python's `date.isocalendar()` handles this natively since Python 3.8.

**Example:**
```python
# src/ga_crawler/reporter/archive.py
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def derive_filename(started_at: datetime, tz_name: str = "Asia/Almaty") -> str:
    """D-512 deterministic ISO-week filename from runs.started_at.

    started_at MUST be timezone-aware UTC (SQLModel default_factory uses datetime.now(timezone.utc)).
    Converts to Asia/Almaty local, then takes ISO calendar.

    Edge cases (verified via stdlib isocalendar — ISO 8601 Thursday rule):
      - 2027-01-01 (Fri) → 2026-W53
      - 2025-12-29 (Mon) → 2026-W01
    """
    if started_at.tzinfo is None:
        raise ValueError("started_at must be timezone-aware (DATA-05 invariant)")
    local = started_at.astimezone(ZoneInfo(tz_name))
    iso_year, iso_week, _ = local.isocalendar()
    return f"{iso_year}-W{iso_week:02d}.xlsx"
```

### Pattern 9: Atomic write via `*.xlsx.tmp` + `os.replace` (Claude's Discretion → recommend)

**What:** xlsxwriter `workbook.close()` (or `pd.ExcelWriter.__exit__`) writes the final xlsx bytes synchronously. To make this resilient to process-crash mid-write, build into a tmp file, then atomically rename.

**Source:** [CITED: docs.python.org/3/library/os.html#os.replace — "If dst exists, it will be replaced silently if the user has permission. The operation may fail if src and dst are on different filesystems. If successful, the renaming will be an atomic operation"].

**Example:**
```python
# src/ga_crawler/reporter/archive.py
import os
from pathlib import Path

def write_atomic(xlsx_bytes: bytes, target_path: Path) -> int:
    """Atomic write via temp file + os.replace. Returns final file size in bytes.

    On crash mid-write, the *.xlsx.tmp file may remain (a separate cleanup-on-startup
    step in run_weekly could handle stale tmp files, but not required for v1 — Path.glob
    in Phase 7 ops playbook is sufficient).
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)  # auto-mkdir per Claude's Discretion
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_bytes(xlsx_bytes)
    # os.replace is atomic on same FS, cross-platform (Windows + POSIX)
    os.replace(tmp_path, target_path)
    return target_path.stat().st_size
```

### Pattern 10: Size-guard (D-515 — log + flag, NOT fail)

**What:** After `write_atomic`, compare `file.stat().st_size` against `config.size_limit_mb × 1024 × 1024`. If exceeded: structlog warning event + `report.size_guard_passed = False`. **xlsx remains on disk.** Run status stays `success`. Phase 6 reads the flag and routes to ops-chat.

**Source:** PITFALLS.md Pitfall 11 "Telegram 50MB hard limit" + D-515 verbatim.

**Example:**
```python
def check_size_guard(file_path: Path, limit_mb: int) -> tuple[bool, int]:
    """Returns (passed, size_bytes). passed=True if file <= limit; False if exceeds."""
    size_bytes = file_path.stat().st_size
    limit_bytes = limit_mb * 1024 * 1024
    return (size_bytes <= limit_bytes, size_bytes)

# In orchestrator (Step 6 after write_atomic):
passed, size_bytes = check_size_guard(xlsx_path, config.size_limit_mb)
if not passed:
    log.warning(
        "report_size_exceeded",
        run_id=run_id,
        size_bytes=size_bytes,
        size_limit_mb=config.size_limit_mb,
    )
builder.set("size_guard_passed", passed)
builder.set("xlsx_size_bytes", size_bytes)
```

### Anti-Patterns to Avoid

- **Recomputing match-rate в reporter.** D-405 freezes the formula at `runs.stats.match.rate`. Reading the stat is correct; recomputing locally drifts. Already covered in Phase 4 `test_match_rate_formula_canary` source-lock.
- **Storing the canonical summary template in pyproject.toml.** D-504 mandates source-of-truth lives in `summary_builder.py` as a module constant. Mirror D-405 KPI formula freeze pattern.
- **Calling `pd.ExcelWriter(…)` without explicit `engine='xlsxwriter'`.** pandas 2.2.x defaults to openpyxl when both are installed. We **must** pass `engine='xlsxwriter'` explicitly — CLAUDE.md §"What NOT to use" rejects openpyxl write mode.
- **Per-fetch `patch_stats` calls.** Pitfall 6 invariant: one atomic `patch_stats` per phase. Reporter accumulates in `ReportStatsBuilder.delta` and writes ONCE in Step 7.
- **Auto-truncating top-N rows when xlsx > 45 MB.** Rejected per D-515 Deferred Ideas. Information loss; size-guard is a flag, not a fix.
- **`shutil.move` for atomic rename.** Not atomic when crossing filesystems. Use `os.replace` / `Path.replace`.
- **Using `df.iterrows()` или Python-side sort для top-N.** Pattern 7 mandates SQL `ORDER BY ABS(…) LIMIT 3` — scales to 50k+ rows without RAM pressure.
- **`if file.endswith('.xlsx'): pass` без full path resolution.** Always work with `pathlib.Path` resolved via `repo_root.joinpath(config.output_dir, filename)` to avoid cwd ambiguity in CLI invocations.
- **Per-cell `worksheet.write(row, col, value)` loop.** `df.to_excel(writer, sheet_name=…)` is 10-100x faster for table writes. Only use `write_string(0, 0, summary)` for cell A1 of Summary sheet.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-sheet xlsx write | Custom xml/zip builder | `pd.ExcelWriter(engine='xlsxwriter')` | Standard library combo; handles row/col indexing, autosize, encoding |
| Russian/emoji cell text | Custom UTF-8 wrapper | xlsxwriter `worksheet.write_string(0, 0, summary_text)` | Native UTF-8 inside xlsx zip; no font config needed [CITED: working_with_data.md] |
| 3-color gradient | Manual cell coloring via Format objects | xlsxwriter `conditional_format(range, {'type': '3_color_scale', …})` | Excel-native CF rule; renders in Excel regardless of who reads |
| ISO week from date | Manual `(year, week) = …` | `date.isocalendar()` stdlib | Handles Thursday-rule year boundary correctly per ISO 8601 |
| Asia/Almaty tz conversion | hand-coded UTC offset (+5h) | `ZoneInfo("Asia/Almaty")` | IANA tzdata via Python 3.12 stdlib; no third-party tz lib |
| Atomic file rename | manual `try/except` around shutil | `os.replace` / `Path.replace` | Atomic cross-platform per Python docs |
| Top-N by abs() | `df.assign(abs=…).sort_values()…head(3)` | SQL `ORDER BY ABS(price_delta_pct) DESC LIMIT 3` | SQLite native; doesn't materialize 50k rows into pandas |
| Stats namespace JSON merge | read-modify-write on `runs.stats` | `SqliteRunWriter.patch_stats(rid, delta)` | Atomic `json_patch` SQL — Pitfall 6 invariant [VERIFIED: storage/sqlite.py:232] |
| File size check | `len(file.read())` (loads all bytes) | `file.stat().st_size` | O(1) stat call vs O(N) read |
| TOML config read | manual ConfigParser/INI parse | `import tomllib` (Python 3.11+ stdlib) | Mirror `MatchConfig.from_pyproject` [VERIFIED: matcher/config.py:12] |
| auto-`mkdir` semantics | `if not p.exists(): p.mkdir()` race | `p.mkdir(parents=True, exist_ok=True)` | Standard idiom; no TOCTOU |

**Key insight:** Phase 5 is **derivation phase, not feature phase**. Every problem above has an established stdlib or already-locked-stack answer. The work is wiring, not invention.

## Runtime State Inventory

> Phase 5 is **greenfield** — no rename, refactor, or migration. New module/files only.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 5 is read-only over Phase 2..4 schemas; writes only to `runs.stats.report.*` (new keys in existing column) and `reports/*.xlsx` (new directory) | None |
| Live service config | None — no external SaaS/API; Telegram is Phase 6 | None |
| OS-registered state | None — no Task Scheduler / systemd / cron involvement (Phase 7 owns cron) | None |
| Secrets/env vars | None — no new secrets; reporter reads `runs.stats` and writes local files | None |
| Build artifacts | New deps (pandas + xlsxwriter + openpyxl-dev) — fresh `uv sync` after pyproject amend will pull them. Verify `uv.lock` updates committed. | Wave 0 plan must run `uv sync` and commit lockfile delta |

**Nothing found in category:** All five — verified by inspection of CONTEXT, REQUIREMENTS, and STATE (no rename/migration triggers; pure additive phase).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | runtime | ✓ (assumed — locked in pyproject) | 3.12.x | — |
| pandas 2.2.x | excel_builder | ✗ (not yet in pyproject; add Wave 0) | — | None — required by CLAUDE.md |
| xlsxwriter 3.2.x | excel_builder | ✗ (not yet in pyproject; add Wave 0) | — | None — required by CLAUDE.md |
| openpyxl 3.1.x | tests (read-back) | ✗ (not yet in pyproject; add Wave 0 as dev dep) | — | Could test via raw zipfile + xml parse, but openpyxl is standard test pattern |
| stdlib `zoneinfo` | archive.py | ✓ (Python 3.12 builtin) | builtin | — |
| stdlib `tomllib` | config.py | ✓ (Python 3.11+ builtin) | builtin | — |
| `Asia/Almaty` tzdata | ZoneInfo lookup | ✓ on most Linux/macOS; ⚠ Windows needs `tzdata` package | system | `pip install tzdata` if `ZoneInfoNotFoundError` raised on Windows VPS |
| Disk space for `reports/` | archive.py write | ✓ (Hetzner CX22 — 40 GB SSD per CLAUDE.md §Stack) | — | — |

**Missing dependencies with no fallback:**
- pandas 2.2.x, xlsxwriter 3.2.x — must be added Wave 0; both required by CLAUDE.md lock.

**Missing dependencies with fallback:**
- openpyxl is test-only; if not added, tests must use lower-level zipfile/xml inspection (more brittle). Recommend adding as dev dep.

**Windows tzdata note:** Phase 7 cron runs on Linux VPS (Hetzner Ubuntu 24.04 LTS per CLAUDE.md §Hosting) which ships full IANA tzdata. Local dev on Windows may need `pip install tzdata`. Wave 0 plan should document this for dev-environment setup or add `tzdata` as conditional dep (`tzdata; sys_platform == 'win32'`).

## Common Pitfalls

### Pitfall 1: pandas defaults to openpyxl when both are installed

**What goes wrong:** `pd.ExcelWriter("out.xlsx")` without `engine=…` picks openpyxl when openpyxl is in the environment (it's the pandas default fallback). Our code expects xlsxwriter (CF API differs subtly).

**Why it happens:** pandas 2.2 priority: `xlsxwriter > openpyxl` for `.xlsx`, but only if both installed at writer-construction time. If dev env adds openpyxl as test dep first, then xlsxwriter, the order works. But fragile.

**How to avoid:** **Always pass `engine='xlsxwriter'` explicitly.** Codified test: `test_excel_builder_uses_xlsxwriter_engine` reads back the xlsx and asserts `writer._engine.__class__.__name__ == 'XlsxWriter'` (or assert via tested behavior — `worksheet.conditional_format` is xlsxwriter-only attr).

**Warning signs:** CF rules don't render correctly when opened in Excel. `writer.book` is `openpyxl.Workbook` not `xlsxwriter.Workbook`.

### Pitfall 2: Excel `num_format` strings are NOT localized

**What goes wrong:** Developer writes `'#,##0,00 ₸'` (European-style comma decimal) expecting Russian Excel to render commas. The format string is rejected or misparsed; cells display garbage.

**Why it happens:** Excel stores `num_format` strings in **US locale internally**, regardless of the reader's OS regional settings. Comma is reserved as thousands separator. Dot is decimal. Renderer translates at display time.

**How to avoid:** Always use US-locale format strings: `'#,##0.00'`, `'#,##0 ₸'`. Document this in `_format_for_column` docstring. Don't try to localize.

**Source:** [VERIFIED: github.com/jmcnamara/XlsxWriter Issue #137]: "Excel stores the number format in the file format in the US locale, but renders it according to the regional settings of the host OS."

**Warning signs:** Cells show `#####` or text-like rendering of numbers.

### Pitfall 3: openpyxl `worksheet.conditional_formatting` may not preserve xlsxwriter rules byte-for-byte

**What goes wrong:** Integration test asserts `assert ws['F2'].fill.fgColor.rgb == 'FF63BE7B'` (the green hex). openpyxl reads CF rules from xlsxwriter-written files, but the rule may be normalized differently or stored on a different level.

**Why it happens:** xlsxwriter writes Excel-2007-CF-XML; openpyxl parses it. Round-trip is generally lossless for **3_color_scale** (well-supported on both sides), but exact internal representation differs.

**How to avoid:** Tests should **assert behavioral structure**, not exact internal representation:
- `assert "Per-SKU deltas" in workbook.sheetnames` (sheet exists)
- `assert ws.freeze_panes == "A2"` (frozen pane coordinate — openpyxl returns A1 notation as string)
- `assert ws.auto_filter.ref == "A1:K47"` (autofilter range — openpyxl readable)
- `assert any(cf.type == "colorScale" for cf in ws.conditional_formatting._cf_rules)` — confirm a color-scale rule exists on the expected range, without asserting exact color hexes

**Confidence:** MEDIUM — openpyxl reading xlsxwriter-CF rules works for our needs (3_color_scale is well-documented on both sides) but planner should write **one Wave 1 smoke test** verifying the assertion above against a tiny synthetic xlsx, then commit the assertion shape before scaling out tests.

### Pitfall 4: ISO week year boundary — filename may "jump back" a year

**What goes wrong:** Run executes 2027-01-01 in Asia/Almaty. Operator expects `2027-W01.xlsx`. Reporter writes `2026-W53.xlsx`. Operator thinks the report is missing.

**Why it happens:** ISO 8601 week numbering: 2027-01-01 (Friday) → ISO `(2026, 53, 5)` because the Thursday of that week (2026-12-31) falls in 2026. **Correct behavior** — but unexpected if operator doesn't know ISO 8601.

**How to avoid:** Document this in `archive.derive_filename` docstring (already shown in Pattern 8). Add a regression test `test_derive_filename_year_boundary` with explicit cases:
```python
assert derive_filename(datetime(2027, 1, 1, 12, tzinfo=timezone.utc), tz_name="Asia/Almaty") == "2026-W53.xlsx"
assert derive_filename(datetime(2025, 12, 29, 12, tzinfo=timezone.utc), tz_name="Asia/Almaty") == "2026-W01.xlsx"
```

**Source:** [CITED: docs.python.org/3/library/datetime#date.isocalendar + CalendarZ "ISO Week Numbers Explained"].

### Pitfall 5: BytesIO write vs disk write — atomic semantics differ

**What goes wrong:** Developer uses `pd.ExcelWriter("reports/2026-W19.xlsx", engine="xlsxwriter")` directly to disk. Process crashes mid-write. File is partial / corrupt.

**Why it happens:** xlsxwriter writes the zip stream in chunks during `workbook.close()`. A crash before close leaves a half-written file at the target path.

**How to avoid:** Build into `io.BytesIO()` first (in-memory); only after the workbook is closed do we have a complete byte string. Then `write_atomic(bytes, target_path)` (Pattern 9). Crash mid-build leaves NO file at target path; only the orphan `*.xlsx.tmp` remains.

**Note:** For very large xlsx (>500 MB) this would force everything into RAM. At our scale (~5-15 MB) this is the simplest correct pattern. If we ever hit memory pressure → switch to direct-to-disk write + post-write rename of completed file.

### Pitfall 6: `runs.stats` JSON read pattern — `get_stats` returns flat dict, NOT nested

**What goes wrong:** Reporter reads `stats["match"]["rate"]` expecting nested dict. Returns KeyError because keys are dotted-flat: `stats["match.rate"]`.

**Why it happens:** Phase 4 `MatchStatsBuilder` writes keys with literal `match.` prefix as dict keys, then `patch_stats` json-merges them at the top level. The resulting JSON is `{"match.rate": 42.31, "match.count": 47, …}` — flat dict with dotted-string keys, not nested objects.

**How to avoid:** Read flat: `stats.get("match.rate", 0.0)`. Verified pattern from [VERIFIED: src/ga_crawler/runners/matcher_run.py:73 `stats.get("match.count")`].

### Pitfall 7: `runs.stats` namespace collision — three-way disjoint invariant

**What goes wrong:** Phase 5 introduces a key like `report.count` that clashes with hypothetical future Phase X. Multiple builders writing same key during one run causes Pitfall 6 silent overwrite.

**Why it happens:** patch_stats uses RFC-7396 json_patch — last writer wins for a given key.

**How to avoid:** Phase 5 `REPORT_STATS_KEYS` constants are all prefixed `report.` and `ReportStatsBuilder._resolve` raises `StatsNamespaceError` on any non-`report.*` write attempt. Cross-builder test (mirror tests/unit/test_matcher_stats.py three-way disjoint invariant): `assert VILED_STATS_KEYS.isdisjoint(GOLDAPPLE_STATS_KEYS).isdisjoint(MATCH_STATS_KEYS).isdisjoint(REPORT_STATS_KEYS)` (4-way now).

### Pitfall 8: `assortment gaps` SQL — NOT EXISTS vs LEFT JOIN performance

**What goes wrong:** D-502 uses `NOT IN (SELECT … FROM matches …)`. At 50k snapshots × 50k matches, this is O(N×M) on SQLite without optimizer help.

**Why it happens:** SQLite optimizer is good but not magical. `NOT IN` with correlated subquery may be slow.

**How to avoid:** Use `NOT EXISTS` or `LEFT JOIN … WHERE matches.viled_sku IS NULL`. For 50k×50k these are typically <1s on SQLite with WAL. Add a covering index `(run_id, brand_norm, name_norm, volume_norm)` on snapshots if benchmarks show slowness — but planner shouldn't preemptively add the index; measure first.

**Recommended phrasing:**
```sql
SELECT s.brand_norm, s.name_norm, s.volume_norm, s.current_price, s.was_price, s.url
FROM snapshots s
WHERE s.retailer = 'goldapple'
  AND s.run_id = :rid
  AND s.multipack_flag = 0
  AND s.volume_norm IS NOT NULL
  AND s.stock_state != 'DELISTED'
  AND NOT EXISTS (
      SELECT 1 FROM matches m
      WHERE m.run_id = :rid
        AND m.brand_norm = s.brand_norm
        AND m.name_norm = s.name_norm
        AND m.volume_norm = s.volume_norm
  )
ORDER BY s.brand_norm, s.name_norm
```

### Pitfall 9: `matches` table lacks URL columns — Per-SKU deltas can't show URLs without JOIN

**What goes wrong:** D-503 mandates `URL viled` and `URL goldapple` columns on Per-SKU deltas sheet. But [VERIFIED: src/ga_crawler/storage/sqlite.py:90-116 Match SQLModel] has 13 columns — none of them `viled_url` or `goldapple_url`.

**Why it happens:** D-401 froze matches to 13 cols. URLs are in `snapshots` table. Reporter SELECT must JOIN back to snapshots to get URLs.

**How to avoid:** Reporter SQL JOINs matches → snapshots (both sides) to fetch URLs:

```sql
SELECT
  m.brand_norm, m.name_norm, m.volume_norm,
  m.viled_price, m.viled_was_price, vs.url AS viled_url,
  m.goldapple_price, m.goldapple_was_price, gs.url AS goldapple_url,
  m.price_delta, m.price_delta_pct
FROM matches m
JOIN snapshots vs
  ON vs.run_id = m.run_id AND vs.retailer = 'viled' AND vs.sku_id = m.viled_sku
JOIN snapshots gs
  ON gs.run_id = m.run_id AND gs.retailer = 'goldapple' AND gs.sku_id = m.goldapple_sku
WHERE m.run_id = :rid
ORDER BY ABS(m.price_delta_pct) DESC
```

This is **NOT a violation of D-401** (matches schema stays 13 cols — derivation table immutable). It's a JOIN at read-time for presentation. Note 04-CONTEXT D-401 statement «reporter SELECT * directly … без JOIN-back» referred to avoiding joining for *prices and deltas* (those denormalized for speed). URLs are presentation-only and not in the denormalized set.

**Surface as Open Question 1** — planner should confirm with user whether (a) accept JOIN-at-read, OR (b) extend D-401 matches schema (denormalize URLs too), OR (c) drop URL columns from Per-SKU deltas (commercial-team UX loss).

### Pitfall 10: Goldapple promos sheet — `discount_amount` and `discount_pct` derived in SQL not in pandas

**What goes wrong:** Computing `was - current = discount_amount` and `discount_amount / was * 100 = discount_pct` in pandas after SELECT — adds two pandas-side transformations, harder to assert.

**Why it happens:** Phase tests want to assert the discount values; doing math in SQL puts the values in the result set directly.

**How to avoid:** Derive in SQL:

```sql
SELECT
  brand_norm, name_norm, volume_norm,
  current_price, was_price,
  (was_price - current_price) AS discount_amount,
  ROUND((was_price - current_price) * 100.0 / was_price, 2) AS discount_pct,
  url
FROM snapshots
WHERE retailer = 'goldapple'
  AND run_id = :rid
  AND was_price IS NOT NULL
  AND was_price > current_price
  AND multipack_flag = 0
  AND volume_norm IS NOT NULL
  AND stock_state != 'DELISTED'
ORDER BY discount_pct DESC
```

### Pitfall 11: Empty match-rate (denominator=0) — summary shows "0.0%" not crash

**What goes wrong:** Week-1 baseline at hand: `match.rate` could be 0.0 if zero brand-overlap. Summary template displays "Совпало: 0 (0.0%)" — correct, but tests must cover.

**Why it happens:** D-405 zero-denominator guard already in `matcher_run.py:159` — rate=0.0 + log warning. Reporter just reads the stat.

**How to avoid:** Mirror `match_zero_denominator` warning in reporter if `match_count == 0` → don't emit Top-3 header (D-504). Test `test_summary_zero_match` confirms structure.

## Code Examples

### Reading SQL into pandas DataFrame (matcher reuse style)

```python
# src/ga_crawler/reporter/queries.py
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

MATCHES_WITH_URLS_SQL = text("""
    SELECT
      m.brand_norm, m.name_norm, m.volume_norm,
      m.viled_price, m.viled_was_price, vs.url AS viled_url,
      m.goldapple_price, m.goldapple_was_price, gs.url AS goldapple_url,
      m.price_delta, m.price_delta_pct
    FROM matches m
    JOIN snapshots vs
      ON vs.run_id = m.run_id AND vs.retailer = 'viled' AND vs.sku_id = m.viled_sku
    JOIN snapshots gs
      ON gs.run_id = m.run_id AND gs.retailer = 'goldapple' AND gs.sku_id = m.goldapple_sku
    WHERE m.run_id = :rid
    ORDER BY ABS(m.price_delta_pct) DESC
""")

def read_matches_for_run(engine: Engine, run_id: int) -> pd.DataFrame:
    """Phase 5 input. Joins matches to snapshots for URLs (Pitfall 9)."""
    with engine.connect() as conn:
        return pd.read_sql(MATCHES_WITH_URLS_SQL, conn, params={"rid": run_id})
```

### ReportConfig.from_pyproject (mirror MatchConfig)

```python
# src/ga_crawler/reporter/config.py — mirror of src/ga_crawler/matcher/config.py
from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ReportConfig:
    output_dir: str = "reports"
    size_limit_mb: int = 45
    top_n_deltas: int = 3
    timezone: str = "Asia/Almaty"

    @classmethod
    def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "ReportConfig":
        path = Path(pyproject_path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        report = data.get("tool", {}).get("ga_crawler", {}).get("report", {})
        return cls(
            output_dir=str(report.get("output_dir", cls.output_dir)),
            size_limit_mb=int(report.get("size_limit_mb", cls.size_limit_mb)),
            top_n_deltas=int(report.get("top_n_deltas", cls.top_n_deltas)),
            timezone=str(report.get("timezone", cls.timezone)),
        )
```

### ReportStatsBuilder (mirror MatchStatsBuilder)

```python
# src/ga_crawler/reporter/stats.py — mirror of src/ga_crawler/matcher/stats.py
from __future__ import annotations
from typing import Any, Iterable
from ga_crawler.runner.stats import StatsNamespaceError

REPORT_STATS_KEYS: tuple[str, ...] = (
    "report.xlsx_path",          # str — relative path from repo_root
    "report.xlsx_size_bytes",    # int
    "report.summary_text",       # str — multi-line emoji (D-504 template)
    "report.sheet_row_counts",   # dict[str, int]
    "report.skipped_reason",     # str OR "" if ran
    "report.size_guard_passed",  # bool
    "report.generated_at",       # str — ISO 8601 UTC
)

_BARE_TO_NAMESPACED: dict[str, str] = {k.split(".", 1)[1]: k for k in REPORT_STATS_KEYS}

class ReportStatsBuilder:
    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _BARE_TO_NAMESPACED:
            return _BARE_TO_NAMESPACED[bare_key]
        if bare_key in REPORT_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in REPORT_STATS_KEYS; allowed: {sorted(REPORT_STATS_KEYS)}"
        )

    def set(self, bare_key: str, value: Any) -> None:
        self.delta[self._resolve(bare_key)] = value
```

### reporter_run.py orchestrator (mirror matcher_run.py 7-step shape)

```python
# src/ga_crawler/runners/reporter_run.py
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import text

from ga_crawler.interfaces import RunWriterProtocol
from ga_crawler.matcher.strict_key import read_run_status  # D-507 reuse
from ga_crawler.reporter.archive import (
    derive_filename, write_atomic, check_size_guard,
)
from ga_crawler.reporter.config import ReportConfig
from ga_crawler.reporter.excel_builder import build_workbook
from ga_crawler.reporter.queries import (
    read_matches_for_run, read_gaps_for_run, read_promos_for_run,
    read_top_n_deltas, read_run_started_at,
)
from ga_crawler.reporter.stats import ReportStatsBuilder
from ga_crawler.reporter.summary_builder import build_summary

log = structlog.get_logger(__name__)


@dataclass
class ReporterPhaseResult:
    status: str  # "success" | "skipped"
    xlsx_path: Optional[str] = None
    xlsx_size_bytes: int = 0
    summary_text: Optional[str] = None
    sheet_row_counts: dict = field(default_factory=dict)
    size_guard_passed: bool = True
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)


def run_reporter_phase(
    *,
    run_id: int,
    engine,
    run_writer: RunWriterProtocol,
    repo_root: Path,
    config: ReportConfig,
) -> ReporterPhaseResult:
    started = time.perf_counter()
    builder = ReportStatsBuilder()

    # ---- Step 1: D-507 status-gate ----
    status = read_run_status(engine, run_id)
    if status != "success":
        reason = (
            "failed_upstream" if status == "failed"
            else "in_progress_upstream" if status == "running"
            else "missing_run_row"
        )
        builder.set("skipped_reason", reason)
        builder.set("xlsx_path", "")
        builder.set("xlsx_size_bytes", 0)
        builder.set("summary_text", "")
        builder.set("sheet_row_counts", {})
        builder.set("size_guard_passed", False)
        builder.set("generated_at", datetime.now(timezone.utc).isoformat())
        run_writer.patch_stats(run_id, dict(builder.delta))
        log.warning("report_skipped_failed_run", run_id=run_id, upstream_status=status)
        return ReporterPhaseResult(
            status="skipped", reason=reason, stats_delta=dict(builder.delta)
        )

    # ---- Step 2: read upstream stats for summary ----
    upstream_stats = run_writer.get_stats(run_id)

    # ---- Step 3: read matches (with JOIN-back for URLs per Pitfall 9) ----
    matches_df = read_matches_for_run(engine, run_id)

    # ---- Step 4: read gaps + promos ----
    gaps_df = read_gaps_for_run(engine, run_id)
    promos_df = read_promos_for_run(engine, run_id)

    # ---- Step 5: pure builders ----
    top3 = read_top_n_deltas(engine, run_id, n=config.top_n_deltas)
    started_at = read_run_started_at(engine, run_id)
    iso_week_str = derive_filename(started_at, tz_name=config.timezone).removesuffix(".xlsx")
    summary_text = build_summary(
        stats=upstream_stats,
        top3=top3,
        gaps_count=len(gaps_df),
        promo_count=len(promos_df),
        iso_week=iso_week_str,
    )
    xlsx_bytes = build_workbook(matches_df, gaps_df, promos_df, summary_text)

    # ---- Step 6: atomic write + size guard ----
    filename = derive_filename(started_at, tz_name=config.timezone)
    target_path = repo_root / config.output_dir / filename
    if target_path.exists():
        prev_size = target_path.stat().st_size
        log.info("report_overwritten", run_id=run_id, previous_size_bytes=prev_size, path=str(target_path))
    size_bytes = write_atomic(xlsx_bytes, target_path)
    size_passed, _ = check_size_guard(target_path, config.size_limit_mb)
    if not size_passed:
        log.warning(
            "report_size_exceeded",
            run_id=run_id, size_bytes=size_bytes, size_limit_mb=config.size_limit_mb,
        )

    # ---- Step 7: Atomic single-call patch_stats (Pitfall 6) ----
    rel_path = str(target_path.relative_to(repo_root)).replace("\\", "/")
    sheet_row_counts = {
        "summary": 1,
        "per_sku_deltas": len(matches_df),
        "assortment_gaps": len(gaps_df),
        "goldapple_promos": len(promos_df),
    }
    builder.set("xlsx_path", rel_path)
    builder.set("xlsx_size_bytes", size_bytes)
    builder.set("summary_text", summary_text)
    builder.set("sheet_row_counts", sheet_row_counts)
    builder.set("size_guard_passed", size_passed)
    builder.set("skipped_reason", "")
    builder.set("generated_at", datetime.now(timezone.utc).isoformat())
    run_writer.patch_stats(run_id, dict(builder.delta))

    elapsed = time.perf_counter() - started
    log.info(
        "reporter_phase_complete",
        run_id=run_id, xlsx_path=rel_path, xlsx_size_bytes=size_bytes,
        size_guard_passed=size_passed, sheet_row_counts=sheet_row_counts,
        duration_s=round(elapsed, 3),
    )
    return ReporterPhaseResult(
        status="success",
        xlsx_path=rel_path,
        xlsx_size_bytes=size_bytes,
        summary_text=summary_text,
        sheet_row_counts=sheet_row_counts,
        size_guard_passed=size_passed,
        stats_delta=dict(builder.delta),
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openpyxl write-only flow | xlsxwriter write + openpyxl read-back | 2024+ | xlsxwriter dominates write-heavy use cases (faster, richer CF API); openpyxl still the read engine of choice |
| pandas `.xlsx` engine=auto | Explicit `engine='xlsxwriter'` | pandas 2.0+ | pandas 2.x defaults shifted; we MUST be explicit |
| `pytz` for tz | `zoneinfo` stdlib (Python 3.9+) | Python 3.9 | No third-party tz dep needed |
| Manual `tempfile + rename` | `os.replace` (atomic since 3.3) | Python 3.3 | Cleaner, fewer error paths |

**Deprecated/outdated:**
- **`pytz`** — replaced by stdlib `zoneinfo`. Don't add as dep.
- **`xlrd`** — was the old `.xls` reader; deprecated for `.xlsx`. We don't need it (write-only path + openpyxl-read for tests).
- **Pandas `df.to_excel(path, engine_kwargs={...})` legacy form** — current pandas uses `pd.ExcelWriter(…) as writer` context manager + `df.to_excel(writer, …)`. Use the context-manager form.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio + pytest-mock (already in `[dependency-groups].dev` per pyproject.toml line 27-33) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (line 42-48) — `asyncio_mode=auto`, testpaths=["tests"] |
| Quick run command | `uv run pytest tests/unit -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REPORT-01 | 4 sheets, correct names, correct column orders (D-503) | integration | `uv run pytest tests/integration/test_reporter_run.py::test_xlsx_has_four_sheets_with_russian_headers -x` | ❌ Wave 3 |
| REPORT-02 | 3-color CF on Дельта, % + freeze_panes + autofilter | integration | `uv run pytest tests/integration/test_reporter_run.py::test_xlsx_cf_freeze_autofilter -x` | ❌ Wave 3 |
| REPORT-03 | Russian column headers verbatim from D-503 + UTF-8 emoji A1 | unit | `uv run pytest tests/unit/test_excel_builder.py::test_russian_headers_match_d503 -x` | ❌ Wave 1 |
| REPORT-04 | Summary text matches D-504 template + top-3 ABS sort + zero-match fallback | unit | `uv run pytest tests/unit/test_summary_builder.py -x` | ❌ Wave 1 |
| REPORT-05 | xlsx written to `reports/YYYY-WNN.xlsx`; idempotent re-run overwrites | integration | `uv run pytest tests/integration/test_reporter_run.py::test_filename_iso_week_and_overwrite -x` | ❌ Wave 3 |
| REPORT-06 | Synthetic >45MB xlsx → `report.size_guard_passed=False` + warning, xlsx persists | integration | `uv run pytest tests/integration/test_reporter_run.py::test_size_guard_flag_does_not_fail_run -x` | ❌ Wave 2/3 |
| D-507 | Failed/running run skips reporter + correct `report.skipped_reason` | integration | `uv run pytest tests/integration/test_reporter_run.py::test_d507_skip_on_failed_run -x` | ❌ Wave 3 |
| D-511 | weekly-run composition writes xlsx after matcher | integration | `uv run pytest tests/integration/test_main_run_with_reporter.py -x` | ❌ Wave 4 |
| D-509 | CLI `report-run --run-id N` produces xlsx + 0 exit | integration | `uv run pytest tests/integration/test_cli_report_subcommand.py -x` | ❌ Wave 4 |
| D-512 | ISO week edge cases (2027-01-01 → 2026-W53; 2025-12-29 → 2026-W01) | unit | `uv run pytest tests/unit/test_archive_iso_week.py -x` | ❌ Wave 2 |
| D-514 | `report.*` namespace enforcement (StatsNamespaceError on bad key) + 4-way disjoint | unit | `uv run pytest tests/unit/test_report_stats.py -x` | ❌ Wave 0 |
| D-516 | `ReportConfig.from_pyproject` defaults + override | unit | `uv run pytest tests/unit/test_report_config.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_<changed_module>.py -x` (sub-second)
- **Per wave merge:** `uv run pytest -x -q` (~2-3 min for full suite at current 380+ test count + new ~25 Phase 5 tests)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_report_config.py` — ReportConfig.from_pyproject defaults + override (mirror tests/unit/test_match_config.py exactly)
- [ ] `tests/unit/test_report_stats.py` — ReportStatsBuilder namespace + 4-way disjoint invariant (mirror tests/unit/test_matcher_stats.py)
- [ ] `tests/conftest.py` extension — `synthetic_report_run` fixture (Run + Snapshots + Matches populated end-to-end), `tmp_reports_dir` (tmp_path-based output_dir), `openpyxl_workbook_reader` helper
- [ ] Test fixtures: `tests/fixtures/reporter/expected-summary-text.txt` — golden D-504 output for week-1 baseline matched run

*(No framework install needed — pytest/pytest-asyncio/pytest-mock already in `[dependency-groups].dev`.)*

## Security Domain

> `security_enforcement: true` and `security_asvs_level: 1` per `.planning/config.json` line 40-41. Phase 5 scope is **read-only over DB + write to local filesystem + write JSON to runs.stats** — minimal attack surface, but a few items to document.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Reporter has no user-facing auth surface; runs in same process as cron |
| V3 Session Management | no | No sessions — single-process batch job |
| V4 Access Control | no | No multi-tenant; single deployment, single operator |
| V5 Input Validation | **yes (low risk)** | SQL params via SQLAlchemy `text(":rid")` bind-param (Phase 4 T-04-03-01 pattern reuse) — no f-string interpolation reaches SQL. `--run-id` CLI arg via argparse `type=int` validates type at parse time. |
| V6 Cryptography | no | No secrets, no encryption in scope |
| V12 File Handling | **yes (Excel-injection risk)** | PITFALLS Security Mistake row 6 — malicious product name `=cmd|...` in a cell can trigger CSV/Excel formula injection. Mitigation below. |

### Known Threat Patterns for {pandas + xlsxwriter}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **Excel formula injection** (product name starts with `=`, `+`, `-`, `@`, `\t`, `\r` → executes formula in Excel) | Tampering | Sanitize all text cells written from DB — prefix any value starting with these chars with a single quote `'`. Apply in `excel_builder._sanitize_cell(v)` to ALL non-numeric cell values from `matches.brand_norm`, `matches.name_norm`, `snapshots.url`, `snapshots.name`. Test `test_excel_injection_prefix` confirms `=SUM(A1)` written becomes `'=SUM(A1)` in xlsx cell. Source: [VERIFIED: PITFALLS.md Security Mistake row 6]. |
| **SQL injection via run_id** | Tampering | All SQL uses `text("… :rid …")` + `params={"rid": run_id}`. argparse `type=int` validates before reaching SQL. Mirror Phase 4 T-04-03-01. |
| **Path traversal via output_dir config** | Tampering | `ReportConfig.output_dir` is operator-edited via git PR (not external input). Phase 5 doesn't accept output_dir from untrusted sources. Still: `target_path = (repo_root / config.output_dir / filename).resolve()` + assert `repo_root.resolve() in target_path.parents` to defense-in-depth. |
| **`json_patch` key collision via report.* values** | Tampering | `ReportStatsBuilder._resolve` enforces `report.*` prefix; arbitrary key writes raise `StatsNamespaceError`. Pitfall 6 invariant preserved. |
| **Sensitive data leak in xlsx** | Information Disclosure | xlsx is internal-team artifact (PROJECT.md §"Internal tool of one team"). No PII (only product names + prices + URLs). Acceptable. |
| **xlsx unzip-bomb on read-back tests** | DoS (via test fixture only) | Tests open xlsx files we just wrote — bounded by `size_limit_mb=45` (D-516). Acceptable. |

**Note re Excel-injection:** The current Phase 2/3 parsers extract `name`/`brand`/`url` from real retailer HTML. A malicious actor could in theory edit a product name on goldapple.kz to `=cmd|'/c calc'!A1`. After our scraper persists it to snapshots, the reporter would render it into xlsx and an Excel user opening the file could see a formula-prompt. Mitigation = single-quote prefix on any cell starting with formula-trigger chars. Trivial to implement in excel_builder; planner should include this as a Wave 1 task.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | openpyxl 3.1.x reads xlsxwriter-3.2.x conditional_format rules sufficiently to assert `rule.type == 'colorScale'` | Pitfall 3 + Pattern 11 test guidance | Tests may need stricter assertions (zip inspection); planner should write one smoke test Wave 1 to validate the assertion style before scaling | [ASSUMED — needs Wave 1 smoke verification] |
| A2 | xlsxwriter Workbook close inside `with pd.ExcelWriter(io.BytesIO(), engine='xlsxwriter') as writer:` block writes COMPLETE xlsx bytes to the BytesIO at `__exit__` — no `.seek(0)` needed | Pattern 1 + Pattern 9 | Bytes may be 0-length / truncated at BytesIO write; planner should write `test_buffer_is_complete_after_close` in Wave 1 | [ASSUMED — typical pandas/xlsxwriter usage but worth one explicit test] |
| A3 | `runs.stats` JSON column is small enough that reading the whole blob via `get_stats(run_id)` is O(1) practically (typical 30-100 keys) | Pattern 6 summary read | At 100+ runs × ~30 keys it's still <10 KB JSON — no risk | Verified via Phase 4 stats key counts (9 viled + 13 goldapple + 10 match = 32 keys today; +7 report = 39 in Phase 5) |
| A4 | At 50k row scale, pandas DataFrame holds ~50 MB peak RAM during xlsx build; well under VPS 4GB | Standard Stack + Pattern 1 | Hetzner CX22 has 4 GB RAM (CLAUDE.md §Hosting). Camoufox at goldapple-phase peak likely ~1 GB. Reporter ~50 MB peak is fine | [ASSUMED — typical pandas memory; verify with synthetic 50k-row test in Wave 1] |
| A5 | xlsxwriter `worksheet.write_string(0, 0, summary_text)` accepts multi-line strings with `\n` and renders as wrapped text in Excel (with row height auto-adjust OR explicit wrap format) | Pattern 1 Summary sheet | Multi-line may render as single-line concatenated; planner may need `workbook.add_format({"text_wrap": True})` + `worksheet.set_row(0, height)` | [ASSUMED — Context7 docs show write_string accepts UTF-8 but don't confirm \n wrap behavior. Wave 1 smoke test needed.] |
| A6 | `runs.stats` JSON for an existing successful run contains `goldapple.fetch_count` AND `viled.fetch_count` keys (per Phase 2/3 stats builders) | Pattern 6 summary fields | Summary may show 0/0 if keys absent — planner can default-via-`.get(…, 0)` and add log warning if absent | Verified via [src/ga_crawler/runner/stats.py:142 + :17] |
| A7 | `Path.replace` is atomic on Windows NTFS — confirmed Python docs but Windows file locking from Excel-open-on-developer-machine may break the test | Pitfall 5 / Pattern 9 | If Excel has `reports/2026-W19.xlsx` open during dev test, `os.replace` raises PermissionError. Tests use `tmp_path` so this shouldn't manifest | [ASSUMED — typical Windows behavior; tmp_path mitigates] |

**If user confirms or rejects any assumption, surface to planner via `/gsd-discuss-phase` follow-up.**

## Open Questions

1. **URL columns on Per-SKU deltas sheet require JOIN-back to snapshots** (Pitfall 9).
   - What we know: D-503 lists `URL viled` + `URL goldapple` as headers. Matches table has no URL columns (D-401 13-col denormalized).
   - What's unclear: whether to (a) accept JOIN-back at reporter read-time, (b) extend matches schema to include URLs (D-401 amendment), (c) drop URL columns from Per-SKU deltas.
   - Recommendation: **option (a) JOIN at read** — keeps D-401 invariant. URLs are presentation-only; "no JOIN-back" referred to prices/deltas (denormalized for the 50k×50k JOIN speed). Surface to planner Wave 1; cheap to flip later if user prefers (b).

2. **Hyperlink cells for URL columns** — write as plain text or as xlsxwriter hyperlinks?
   - What we know: xlsxwriter has `worksheet.write_url(row, col, url, fmt)` rendering as clickable hyperlink.
   - What's unclear: D-503 doesn't specify; Claude's Discretion. Hyperlink UX is better but adds complexity (format object, 255-char limit per cell per Excel).
   - Recommendation: **Wave 1 default = plain text** (matches the "minimal-API surface" Wave shape). Defer hyperlink-cell to Wave 2 if user requests.

3. **Sheet name in Russian or English?**
   - What we know: D-503 specifies Russian column headers but not sheet tab names. CONTEXT examples show "Summary / Per-SKU deltas / Assortment gaps / Goldapple promos" in English.
   - What's unclear: whether sheet tabs should be `Сводка / Дельты / Гэпы / Промо`.
   - Recommendation: **stick with English sheet names** as in CONTEXT (D-509 file path naming uses English; consistent with overall codebase + makes Phase 6 caption "См. лист 'Per-SKU deltas'" parseable). Flag to planner; user can flip in 1 commit if desired.

4. **Summary sheet — what's below cell A1?**
   - What we know: D-504 says cell A1 holds the multi-line emoji block. CONTEXT mentions "KPI labels" below but no explicit list.
   - What's unclear: structure of `Summary` sheet rows 3+ (KPI label/value pairs?).
   - Recommendation: **Minimal KPI block at rows 3-9** with label/value pairs mirroring the summary template fields (viled_count, goldapple_count, match_count, match_rate, gaps_count, promo_count, generated_at). Provides BI-tooling-friendly cell references. Flag to planner; trivial to extend.

5. **`reports/.gitkeep` vs `reports/` initialization** — should Wave 0 create the directory artifact?
   - What we know: D-219 backups/ pattern uses `.gitkeep` + `.gitignore *.db`. Mirror suggests `.gitkeep` + `.gitignore reports/*.xlsx`.
   - What's unclear: whether to auto-create `reports/` in `archive.write_atomic` (via `parent.mkdir(parents=True, exist_ok=True)`) — yes, already in Pattern 9.
   - Recommendation: **both** — Wave 0 commits `reports/.gitkeep` + `.gitignore` entry; `write_atomic` also auto-mkdir as defense-in-depth (handles fresh checkout).

## Sources

### Primary (HIGH confidence)
- **Context7 `/jmcnamara/xlsxwriter`** — fetched 2026-05-11 for: `conditional_format 3_color_scale`, `freeze_panes`, `autofilter`, `set_column`, `num_format`, `ExcelWriter pandas multiple sheets`, `constant_memory`, `Workbook close exceptions`, `write_string unicode`. All examples verbatim from official xlsxwriter docs.
- **`pypi.org/project/pandas/2.2.3`** — confirmed pandas 2.2.3 release date (2024-09-20), Python ≥3.9 requirement.
- **`pypi.org/project/xlsxwriter`** — confirmed xlsxwriter 3.2.9 current; 3.2.x matches CLAUDE.md lock.
- **`pypi.org/project/openpyxl`** — confirmed openpyxl 3.1.5 (2024-06-28).
- **CLAUDE.md §Technology Stack** — pandas 2.2.x + xlsxwriter 3.2.x LOCK (Polars/openpyxl-write rejected).
- **`docs.python.org/3/library/zoneinfo`** — `ZoneInfo("Asia/Almaty")` stdlib usage.
- **`docs.python.org/3/library/datetime#date.isocalendar`** — ISO week year boundary handling.
- **`docs.python.org/3/library/os.html#os.replace`** — atomic cross-platform rename.

### Codebase (HIGH — VERIFIED via Read)
- `src/ga_crawler/storage/sqlite.py` — Run/Snapshot/Match SQLModel + SqliteRunWriter.patch_stats atomic json_patch
- `src/ga_crawler/matcher/strict_key.py` — SQL constants pattern + `read_run_status` D-411 helper to reuse for D-507
- `src/ga_crawler/matcher/config.py` — `MatchConfig.from_pyproject` template to mirror for `ReportConfig`
- `src/ga_crawler/matcher/stats.py` — `MatchStatsBuilder` + `MATCH_STATS_KEYS` template to mirror for `ReportStatsBuilder`
- `src/ga_crawler/runners/matcher_run.py` — 7-step orchestrator template
- `src/ga_crawler/runners/main_run.py` — composition step pattern + pre-finalize Plan 04-05
- `src/ga_crawler/cli.py` — `_cmd_matcher` argparse template
- `pyproject.toml` — `[tool.ga_crawler.match]` template for `[tool.ga_crawler.report]`

### Secondary (MEDIUM confidence)
- **github.com/jmcnamara/XlsxWriter Issue #137** (via WebSearch) — "Excel stores num_format in US locale, renders per OS regional" verified statement
- **CalendarZ blog "ISO Week Numbers Explained"** (via WebSearch) — 2016-01-01 → 2015-W53 confirms year-boundary case
- **HackerNoon "How to Specify Data Format in Excel with Python"** (via WebSearch) — num_format examples cross-confirmed

### Tertiary (LOW confidence — needs Wave 1 verification)
- **openpyxl reading xlsxwriter CF rules exactly** — assertion-shape Wave 1 smoke test needed (Assumption A1)
- **`write_string` multi-line wrap behavior** — Wave 1 smoke test needed (Assumption A5)
- **Memory footprint at 50k-row scale** — Wave 1 synthetic load test needed (Assumption A4)

## Project Constraints (from CLAUDE.md)

The following CLAUDE.md directives constrain Phase 5 planning. Planner MUST verify compliance.

| Directive | Source | Application to Phase 5 |
|-----------|--------|-----------------------|
| **pandas 2.2.x + xlsxwriter 3.2.x LOCKED** | CLAUDE.md §Stack | Wave 0 adds these as production deps with version pins; never Polars; never openpyxl-write |
| **Python 3.12 LOCKED** | CLAUDE.md §Stack | All code targets `py312`; stdlib `tomllib` + `zoneinfo` available; no backport shims |
| **uv as project manager** | CLAUDE.md §Stack | `uv add pandas xlsxwriter`; `uv sync` after pyproject amend; lockfile committed |
| **structlog for all logging** | CLAUDE.md §Stack | Reporter uses `log = structlog.get_logger(__name__)` mirror of matcher_run.py:40 |
| **xlsxwriter (not openpyxl) for write-heavy reports** | CLAUDE.md §"What NOT to use" line 408 | `engine='xlsxwriter'` explicit on every `pd.ExcelWriter()` call |
| **KZT-only (no multi-currency)** | CLAUDE.md §Project | All price columns are integer KZT (`#,##0 ₸` format); no currency-conversion logic |
| **Excel-injection prevention** | CLAUDE.md inherits PITFALLS Security Mistake row 6 | `excel_builder` sanitizes cell values starting with `=`, `+`, `-`, `@`, tab, CR with single-quote prefix |
| **append-only schema; no alembic on v1** | CLAUDE.md §SQLite | Phase 5 makes NO schema changes — only adds to runs.stats JSON column (atomic via patch_stats) |
| **DATA-05 try/except lifecycle** | CLAUDE.md inherits | Reporter exception → handled by main_run.py outer try/except → `run_writer.fail(rid, traceback)` |
| **Per-domain split convention** | CLAUDE.md §"emerging patterns" + Phase 4 D-413 mirror | `reporter/` package + `runners/reporter_run.py` mirrors `matcher/` + `runners/matcher_run.py` exactly |
| **Namespace-enforced stats builders** | CLAUDE.md §Phase 4 patterns | `ReportStatsBuilder("report.*")` + `StatsNamespaceError` raise on bad keys |
| **GSD Workflow Enforcement** | CLAUDE.md §"GSD Workflow Enforcement" | All Phase 5 code edits go through `/gsd-execute-phase`, not direct edits |
| **Russian-first user interface** | CLAUDE.md §Project (commercial team is Russian-speaking) | Excel headers in Russian (D-503); summary template in Russian (D-504); log events in English (operator-facing) |

## Metadata

**Confidence breakdown:**
- Standard Stack: **HIGH** — versions pin-locked in CLAUDE.md, verified against pypi.org 2026-05-11
- Architecture: **HIGH** — every primitive (orchestrator, stats namespace, config loader, CLI subcommand, runs.stats merge, atomic write, status-gate) already exists in Phase 4 codebase as ready-to-mirror template
- xlsxwriter API specifics (CF / freeze_panes / autofilter / num_format): **HIGH** — Context7 fetched verbatim from `/jmcnamara/xlsxwriter`
- pandas+xlsxwriter integration: **HIGH** — multiple official examples via Context7
- ISO-week + tz handling: **HIGH** — Python stdlib + ISO 8601 standard
- Atomic file write: **HIGH** — os.replace documented atomic since Python 3.3
- Russian header rendering: **MEDIUM-HIGH** — Cyrillic is UTF-8-native in xlsxwriter, but Wave 1 smoke verification recommended for multi-line cell A1 wrap
- openpyxl test read-back: **MEDIUM** — works for sheet/freeze/autofilter assertions; exact CF rule preservation needs one Wave 1 smoke test (Assumption A1)
- Pitfalls (Excel-injection, num_format locale, year boundary, BytesIO atomicity): **HIGH** — multi-source verified

**Research date:** 2026-05-11
**Valid until:** 2026-06-11 (pandas/xlsxwriter ecosystem is stable; ~30 days). Re-validate version pins at Wave 0 plan creation.

---

*Research for: GA Crawler Phase 5 Reporter (Excel + summary)*
*Researched: 2026-05-11*
*Confidence: HIGH overall; 7 assumptions logged for planner verification (A1..A7)*
