# Phase 5: Reporter (Excel + summary) - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 строит **DB-only reporter**: для успешного `run_id` производит multi-sheet xlsx (`reports/YYYY-WNN.xlsx`) с русскими заголовками + multi-line emoji текстовую сводку, и заархивирует на диск. Reporter **полностью независим от Telegram** (ARCHITECTURE.md — file-on-disk-first); Phase 6 — тонкая обёртка, читающая результаты из `runs.stats.report.*` + xlsx с диска. Reporter консьюмит исключительно БД: `matches` таблица (Phase 4 D-401 13-колонок денормализованная — никаких JOIN-back), `snapshots` для assortment gaps и goldapple promos, `runs.stats.match.*` (Phase 4 D-414) для текстовой сводки. KPI формула frozen с week 1 baseline (D-405) — reporter цитирует `runs.stats.match.rate` напрямую. Reporter **работает только на `runs.status='success'`** (mirror D-411 matcher skip-protocol); failed/partial runs пропускаются с structured-log warning. Pre-send 45 MB size guard (REPORT-06) — log-warning + `report.size_guard_passed=false` flag для Phase 6 DELIVER-03 sanity-gate, **не fail run**. Phase 5 НЕ доставляет в Telegram (Phase 6), НЕ деплоит cron (Phase 7), НЕ меняет схему `runs`/`snapshots`/`matches` (frozen Phase 2..4).

</domain>

<decisions>
## Implementation Decisions

### Sheet contracts + N→1 duplicates (REPORT-01)

- **D-501:** **Per-SKU deltas — показывать все match-rows как есть (D-403 keep-all preserved).** Reporter SELECT-ит все строки из `matches WHERE run_id=:rid` (отсортировано по `ABS(price_delta_pct) DESC` для actionability), один row = одна match-pair. Один viled_sku может встретиться N раз (по одной строке на каждый goldapple-вариант, D-403). Pricing-менеджер фильтрует в Excel autofilter сам. Dedup-логика **НЕ в reporter** — это commercial-signal D-403 preservation.

- **D-502:** **Assortment gaps — SKU-level (одна строка = один goldapple-SKU без viled-пары).** Источник: `snapshots WHERE retailer='goldapple' AND run_id=:rid AND multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED' AND (brand_norm, name_norm, volume_norm) NOT IN (SELECT brand_norm, name_norm, volume_norm FROM matches WHERE run_id=:rid)`. Колонки: Бренд / Название / Объём / Цена goldapple, ₸ / Старая цена goldapple, ₸ / URL goldapple. Use case — закупщики viled видят конкретные варианты к завозу.

  **Note re REPORT-01 wording:** REQUIREMENTS говорит «бренды на goldapple, отсутствующие на viled». Но CRAWL-02 ограничивает goldapple-crawl брендами viled — pure brand-gap = ∅ by construction. SKU-level gap внутри overlap-брендов = более корректная интерпретация intent'а (виледд знает бренд, но не везёт конкретный SKU). Документировано в Action Items для REPORT-01 amendment.

- **D-503:** **Russian column headers — formal style + lowercase Latin для retailer-имён.** Канонические заголовки:
  - `Бренд`, `Название`, `Объём` — общие
  - `Цена viled, ₸`, `Старая цена viled, ₸`, `URL viled` — viled-side
  - `Цена goldapple, ₸`, `Старая цена goldapple, ₸`, `URL goldapple` — goldapple-side
  - `Дельта, ₸`, `Дельта, %` — Per-SKU deltas-only
  - `Скидка, ₸`, `Скидка, %` — Goldapple promos-only
  - Brand-values в самих строках — как записаны в snapshots (Cyrillic + Latin mix, NO localization).

  Источник истины этих лейблов — `reporter/excel_builder.py` константы (НЕ pyproject); изменение требует PR.

- **D-504:** **Text summary REPORT-04 — multi-line block с эмодзи. Используется в Telegram caption (Phase 6) И инсертится в cell A1 листа Summary.** Канонический шаблон (week-1 baseline lock):
  ```
  📊 Неделя {YYYY-WNN} — viled vs goldapple

  📦 viled: {viled_count} SKU  •  goldapple: {goldapple_count} SKU
  🎯 Совпало: {match_count} ({match_rate}%)
  🆕 Гэпы: {gaps_count} SKU у goldapple без viled-пары
  💸 Промо у goldapple: {promo_count} SKU

  🔝 Топ-3 дельты (viled vs goldapple):
   1. {brand} {name} {volume}: {delta_pct}%
   2. ...
   3. ...
  ```
  Top-3 sort: `ABS(price_delta_pct) DESC` (наибольший абсолютный сдвиг — наиболее actionable). Если match_count < 3 — top-N показывается с тем что есть (1 или 2 строки), но строка "🔝 Топ-3 дельты" остаётся. Если match_count=0 — заголовок строки "Топ-3 дельты" отсутствует, остальные строки сохраняют structure ("Совпало: 0 (0.0%)").

### Conditional formatting + zero-match (REPORT-02 + edge cases)

- **D-505:** **3-color scale (green-white-red) на колонку `Дельта, %` листа Per-SKU deltas.** xlsxwriter `worksheet.conditional_format(range, {'type': '3_color_scale', 'min_color': '#F8696B', 'mid_color': '#FFEB84', 'max_color': '#63BE7B'})` с auto min/max и mid=0. Green (positive delta_pct) = goldapple дороже = viled дешевле — позитив для viled commercial team. Red (negative delta_pct) = viled дороже — сигнал к снижению цены.

- **D-506:** **Reporter всегда строит все 4 листа** (Summary / Per-SKU deltas / Assortment gaps / Goldapple promos) даже при пустых подмножествах. Пустые листы имеют только headers + frozen pane (row 1) + autofilter, 0 строк данных. Text summary явно говорит "Совпало: 0 (match-rate 0.0%)" при match_count=0. Структура xlsx предсказуема: Phase 6 всегда отправляет один файл с 4 листами, downstream BI-инструменты могут анализировать week-over-week без обработки переменного sheet-list.

- **D-507:** **Reporter работает только на `runs.status='success'`.** В начале orchestrator (`runners/reporter_run.py`) делает `SELECT status FROM runs WHERE run_id=:rid`. Если status ≠ 'success' (любой из 'running'/'failed'/'partial') — структурированный warning `report_skipped_failed_run` + `run_writer.patch_stats(rid, {'report.skipped_reason': 'failed_upstream'})` + early return. Зеркалит D-411 matcher skip-protocol — один invariant по всем downstream phase-orchestrator'ам, единообразный pattern для Phase 6/7.

  **Composition layer note:** В `runners/main_run.run_weekly` reporter вызывается ПОСЛЕ pre-finalize (Plan 04-05 pattern: `run_writer.finalize(rid, 'success')` до downstream-step которая читает status). Зеркалит D-411 contract gap fix для composition layer.

- **D-508:** **Conditional formatting применяется к двум листам:** `Per-SKU deltas` (колонка `Дельта, %`) + `Goldapple promos` (колонка `Скидка, %`). Summary и Assortment gaps — без CF (нечего ранжировать визуально). Все 4 листа имеют: frozen top row, autofilter на header-row, autosized column widths (xlsxwriter `set_column_pixels` based on max-content-length).

### CLI shape + filename + main_run composition (REPORT-05 + SC#3 + integration)

- **D-509:** **CLI shape — standalone subcommand `python -m ga_crawler report-run --run-id N`** (required flag, обязательный). Mirror Phase 4 D-412 `matcher-run --run-id N`. Дополнительные flags: `--output-dir reports/` (override `[tool.ga_crawler.report].output_dir`), `--db-path ./prices.db`, `--pyproject ./pyproject.toml`. Use case: оператор фиксит баг в reporter и регенерирует xlsx для существующего `run_id` без перекраула 4ч (SC#3). Idempotent — повторный вызов перезаписывает свой же xlsx.

- **D-510:** **Filename `reports/YYYY-WNN.xlsx` с overwrite policy.** Если 2 успешных run в одну ISO неделю (manual recovery + cron — оба success) — второй вызов перезаписывает первый xlsx без backup. Истина в БД (`runs` table immutable per DATA-03 + matches denormalized). Каждый вызов структурно log-ит событие `report_overwritten` (с previous_size_bytes, current_size_bytes, previous_run_id если читается из xlsx metadata) если файл существовал. Path resolved as `Path(config.output_dir).joinpath(f"{iso_year}-W{iso_week:02d}.xlsx")` относительно `repo_root`.

- **D-511:** **main_run composition — reporter вызывается AFTER matcher BEFORE final finalize в `run_weekly`.** Pipeline:
  ```
  runs.create()
    → run_viled_phase()
    → run_goldapple_phase()
    → Norm06Writer.persist()
    → run_writer.finalize('success')      # pre-finalize per Plan 04-05 pattern
    → run_matcher_phase()                  # читает status='success' per D-411
    → run_reporter_phase()                 # NEW — читает status='success' per D-507
    → run_writer.finalize('success')       # idempotent re-finalize per Plan 04-05
  ```
  Reporter — single SYNCHRONOUS phase (sync `engine.connect()`, sync pandas, sync xlsxwriter, sync file write). Внутри одного try/except DATA-05 lifecycle (Plan 02-05 invariant): любая uncaught exception в reporter триггерит `run_writer.fail(rid, traceback)` через outer except. xlsx-файл на диске после exception может быть partial/corrupted — `archive.py` использует atomic write (xlsxwriter writes к `*.xlsx.tmp` затем `os.replace`).

- **D-512:** **ISO week derives from `runs.started_at` in Asia/Almaty timezone.** Деривация:
  ```python
  almaty_tz = ZoneInfo("Asia/Almaty")
  started_at_local = run.started_at.astimezone(almaty_tz)
  iso_year, iso_week, _ = started_at_local.isocalendar()
  filename = f"{iso_year}-W{iso_week:02d}.xlsx"
  ```
  Детерминированно: повторный вызов `report-run --run-id 42` всегда производит тот же filename. Asia/Almaty синхронизирован с Phase 7 cron `CRON_TZ=Asia/Almaty` invariant (no UTC drift между cron-scheduling и reporter-filenaming).

### Module structure + reporter stats namespace + REPORT-06 guard

- **D-513:** **Module layout — `reporter/` package split + `runners/reporter_run.py` orchestrator.** Mirror Phase 4 D-413 + ARCHITECTURE.md L112-116:
  ```
  src/ga_crawler/
    reporter/
      __init__.py
      config.py             # ReportConfig.from_pyproject — mirror MatchConfig
      excel_builder.py      # 4 sheets + CF + frozen panes + autofilter + Russian headers (D-503)
      summary_builder.py    # multi-line emoji template (D-504) + top-3 deltas
      archive.py            # filename derivation (D-512) + atomic write + REPORT-06 size guard
    runners/
      reporter_run.py       # orchestrator: status-gate D-507 → build → archive → patch_stats → return
      main_run.py           # AMEND: добавить run_reporter_phase step после matcher (D-511)
  ```
  Phase 4 matcher.* и goldapple/viled stats builders НЕ затрагиваются. `runner/stats.py` — добавляется `ReportStatsBuilder("report.*")` (используя существующий `NamespaceStatsBuilder` base если есть; иначе copy-paste pattern Phase 4 не успел внести base refactor).

- **D-514:** **Stats namespace `report.*` — full keys (mirror D-414 pattern).** Reporter пишет в `runs.stats` через atomic `patch_stats` (Pitfall 6 invariant):
  - `report.xlsx_path` — str, relative path from repo_root (e.g. `"reports/2026-W19.xlsx"`)
  - `report.xlsx_size_bytes` — int
  - `report.summary_text` — str, multi-line emoji caption (D-504 канонический шаблон, готов к Telegram caption без regen)
  - `report.sheet_row_counts` — dict[str, int] (e.g. `{"summary": 1, "per_sku_deltas": 47, "assortment_gaps": 8385, "goldapple_promos": 1247}`)
  - `report.skipped_reason` — str OR null ("failed_upstream" если D-507 trip, null иначе)
  - `report.size_guard_passed` — bool (false при xlsx > size_limit_mb per D-515)
  - `report.generated_at` — ISO 8601 timestamp string (UTC)

  Phase 6 читает `report.xlsx_path` + `report.summary_text` + `report.size_guard_passed` из stats без файл-IO и без regen. Reporter-это-source-of-truth для caption.

- **D-515:** **REPORT-06 size guard — log warning + `report.size_guard_passed=false`, NOT fail run.** При `xlsx_size_bytes > size_limit_mb × 1024 × 1024` (default 45 MB):
  - structlog warning event `report_size_exceeded` с size_bytes + size_limit_mb + run_id
  - `report.size_guard_passed=false` в stats
  - **xlsx ПИШЕТСЯ на диск** (для manual recovery / split-and-send-later) — reporter не разрушает свой output
  - Run status остаётся `success` (REPORT-06 — это delivery-time concern; ARCHITECTURE.md «reporter independent of delivery» удерживается)
  - **Phase 6 (DELIVER-03 sanity-gate) ОБЯЗАН читать `report.size_guard_passed`**: если false → business-chat skipped, ops-chat alert «xlsx too large for Telegram, run {rid} — manual delivery required». Этот invariant фиксируется в Phase 5 CONTEXT и cascade-копируется в Phase 6 CONTEXT при /gsd-discuss-phase 6.

- **D-516:** **`[tool.ga_crawler.report]` namespace в pyproject.toml — minimal:**
  ```toml
  [tool.ga_crawler.report]
  output_dir = "reports"            # relative to repo_root
  size_limit_mb = 45                # REPORT-06 threshold (50 MB Telegram - 5 MB safety)
  top_n_deltas = 3                  # REPORT-04 summary top-N
  timezone = "Asia/Almaty"          # ISO-week derivation tz (D-512)
  ```
  `ReportConfig.from_pyproject` loader зеркалит `MatchConfig.from_pyproject` (Plan 04-01) и `ViledConfig.from_pyproject` (Plan 02-04). Operator меняет через git PR — same pattern that D-407/D-310 sanity-gate auto-suggest tuning.

### Claude's Discretion

- **`reports/` directory tracking:** auto-`mkdir(parents=True, exist_ok=True)` при первом запуске; tracked в git via `.gitkeep`; `.gitignore` excludes `reports/*.xlsx`. Mirror Phase 2 D-219 `backups/` pattern.
- **Atomic write:** xlsxwriter пишет к `*.xlsx.tmp` затем `Path.replace` — защита от partial write при crash. Planner проверяет xlsxwriter Workbook close-flush semantics.
- **Number formatting:** `'#,##0 ₸'` для цен (KZT тысячи), `'0.00'` для процентов (D-505), `'YYYY-MM-DD HH:MM'` для timestamps. Planner проверяет совпадает ли xlsxwriter format с Russian locale ожиданиями.
- **Column widths:** auto-calc на основе longest header + 1-2 char padding; max width 50 chars (для длинных названий товаров — wrap или truncate display? Planner выберет — default truncate с full text в cell value).
- **`was_price IS NULL` rendering:** пустая ячейка (Excel-friendly) НЕ `—`/`N/A`/`0`. CF на NULL не реагирует.
- **Goldapple promos filter:** `WHERE retailer='goldapple' AND run_id=:rid AND was_price IS NOT NULL AND was_price > current_price AND multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'`. Sort by `Скидка, % DESC` (наиболее интересное промо вверху).
- **Test infra:** real on-disk SQLite + real xlsx output + openpyxl-read-back assertions (verify header text + frozen pane state + autofilter range + conditional format rules + sheet row counts). Synthetic matches fixture с известным delta_pct для CF verification. Phase 5 не пишет live-tests (mirror Phase 4 — no `-m live`).
- **Historical re-run support:** SC#3 `report-run --run-id 17` для past run работает поскольку schema frozen Phase 2..4. Если когда-нибудь matches column добавится — reporter graceful с `SELECT * FROM matches` через SQLModel + nullable новых колонок.
- **Per-brand match-rate в Summary:** v2 territory (REPORT-V2-02). Phase 5 показывает только overall match_rate из `runs.stats.match.rate`.
- **Sheet ordering:** в xlsx первый лист — Summary (open-on-default), затем Per-SKU deltas, затем Assortment gaps, затем Goldapple promos. xlsxwriter `add_worksheet` order сохраняет порядок.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value (weekly viled vs goldapple report для commercial team), constraints §Delivery channel (Telegram + Excel — выбран на v1)
- `.planning/REQUIREMENTS.md` §Report (REPORT-01..06 active), §Match (MATCH-01..04 frozen — reporter consumes `matches` + `runs.stats.match.*`), §Data (DATA-03 immutable history — reporter regenerates from БД)
- `.planning/ROADMAP.md` §"Phase 5: Reporter (Excel + summary)" — phase goal + 4 success criteria (SC#1..4)

### Prior phase context (decisions cascade)
- `.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT.md` — Phase 4 frozen: D-401 matches schema 13-col денормализованная (reporter reads directly, NO JOIN-back); D-403 N→1 keep-all (Phase 5 D-501 preserves at render); D-405 KPI formula frozen week-1 baseline (reporter cites `runs.stats.match.rate` verbatim); D-411 skip-protocol (Phase 5 D-507 mirrors); D-413 module split + runners/*_run.py pattern; D-414 stats namespace (Phase 5 D-514 mirrors with `report.*`); D-412 standalone subcommand pattern (Phase 5 D-509 mirrors with `report-run`)
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md` — Phase 2 frozen: D-203 retailer-agnostic gate helpers (Phase 5 не использует gates напрямую — только status read); D-218 gate-fail-but-data-persists invariant (Phase 5 D-515 mirrors REPORT-06 — xlsx persists on size-exceed); D-219 atomic backup pattern (Phase 5 atomic xlsx write inspired); D-220 no alembic (Phase 5 D-516 inherits — no migration); D-221 v_current_snapshots VIEW (Phase 5 NOT used — explicit run_id read instead, since reporter может работать с historical runs)
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` — supplementary; Phase 3 ships goldapple snapshots which Phase 5 reads for Assortment gaps + Goldapple promos sheets

### Research foundation
- `.planning/research/ARCHITECTURE.md` §"Major components" — pandas + openpyxl/xlsxwriter pattern; §"Build Order" — reporter (Phase 3 пункт в research order = current Phase 5); §"Key boundary principle" — Crawler-Parser-Normalizer-Matcher = pure pipelines; Storage/Reporter/Delivery = side-effects only
- `.planning/research/PITFALLS.md` — Pitfall 6 (atomic merge in runs.stats — Phase 5 D-514 reuses via patch_stats)
- `.planning/research/STACK.md` (если есть) или CLAUDE.md §Tech Stack — pandas 2.2.x + xlsxwriter 3.2.x locked

### Frozen infrastructure (Phase 5 inputs — READ-ONLY for reporter)
- `src/ga_crawler/storage/sqlite.py` — `Run` + `Snapshot` + `Match` SQLModel tables, `make_engine` WAL + PRAGMA, `init_db` idempotent schema, `SqliteRunWriter.patch_stats(run_id, delta)` atomic json_patch (Phase 5 calls для `report.*` keys), `SqliteRunWriter.fail`/`finalize` lifecycle
- `src/ga_crawler/matcher/strict_key.py` — INSERT_MATCHES_SQL формулу не трогать (D-405 frozen); reporter читает результаты JOIN через `SELECT * FROM matches WHERE run_id=:rid`
- `src/ga_crawler/matcher/stats.py` — `MatchStatsBuilder` enforces `match.` prefix; reporter ЧИТАЕТ `match.*` keys из stats but не пишет
- `src/ga_crawler/runner/stats.py` — `StatsNamespaceError` + Goldapple/Viled/Match builders; Phase 5 добавит `ReportStatsBuilder("report.*")` mirror
- `src/ga_crawler/runners/main_run.py` — current orchestrator (viled + goldapple + matcher); Phase 5 amend через `run_reporter_phase` после matcher per D-511
- `src/ga_crawler/cli.py` — current 3 subcommands (`goldapple-smoke`, `weekly-run`, `matcher-run`); Phase 5 amends добавлением `report-run --run-id N` per D-509
- `pyproject.toml` — current namespaces `[tool.ga_crawler.crawl.{retailer}]` + `[tool.ga_crawler.match]`; Phase 5 adds `[tool.ga_crawler.report]` per D-516

### Test infrastructure (inherited)
- `tests/conftest.py` — 11+ fixtures (mock_run_writer + in_memory_sqlite_session + Phase 4 synthetic_matched_snapshots); Phase 5 adds `synthetic_report_run` (Run + Snapshots + Matches populated for end-to-end xlsx-build test) + `tmp_reports_dir` (tmp_path-based output_dir для archive tests) + `openpyxl_workbook_reader` helper (open xlsx and assert headers/CF/frozen pane)
- `tests/integration/` — pattern from Phase 4 tests/integration/test_matcher_run.py: real on-disk SQLite + run pipeline + assert state

### Project conventions
- `CLAUDE.md` §Tech Stack — pandas 2.2.x + xlsxwriter 3.2.x (locked, no Polars/openpyxl-write); §Storage SQLite vs Postgres (matcher + reporter SQL well within SQLite envelope)

### Project state & accumulated decisions
- `.planning/STATE.md` — Accumulated Key Decisions row "Reporter is independent of delivery" (Phase 5 D-507 + D-515 + ARCHITECTURE.md alignment); "D-405 KPI formula freeze" row (Phase 5 cites `runs.stats.match.rate` verbatim); "patch_stats single-call invariant" row (Phase 5 D-514 inherits Pitfall 6)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`storage/sqlite.py::SqliteRunWriter.patch_stats(run_id, delta)`** — atomic json_patch для `report.*` keys (Pitfall 6 invariant). Zero дополнительной работы.
- **`storage/sqlite.py::Match` SQLModel + 13-col schema (D-401)** — denormalized; reporter `SELECT * FROM matches WHERE run_id=:rid ORDER BY ABS(price_delta_pct) DESC` без JOIN-back.
- **`storage/sqlite.py::Snapshot` SQLModel** — для Assortment gaps + Goldapple promos sheets; `SELECT WHERE retailer='goldapple' AND NOT EXISTS (matches subselect)` для D-502.
- **`runs.stats.match.*` namespace (D-414)** — `match.count` + `match.rate` + `match.denominator` etc. читаются напрямую для text summary (D-504): `📦 viled: ... • goldapple: ... • Совпало: {match.count} ({match.rate}%)`.
- **`runner/stats.py::StatsNamespaceError` + `GoldappleStatsBuilder`/`ViledStatsBuilder`/`MatchStatsBuilder`** — паттерн namespace-enforced stats builder. Phase 5 копирует в `ReportStatsBuilder("report.*")` либо рефакторит в `NamespaceStatsBuilder(prefix)` base (low-risk, побочный продукт).
- **`cli.py::_cmd_matcher` shape (Plan 04-05)** — argparse mirror для `report-run --run-id N` (D-509).
- **`runners/main_run.run_weekly` composition pattern (Plan 04-05)** — pre-finalize-before-downstream-step pattern; Phase 5 reporter step повторяет (status='success' set до reporter call).
- **`runners/matcher_run.read_run_status(engine, run_id)`** — D-411 helper, переиспользуется в `runners/reporter_run.py` для D-507 status-gate.
- **`pyproject.toml [tool.ga_crawler.match]` config namespace** (Plan 04-01) — pattern для D-516 `[tool.ga_crawler.report]`.
- **xlsxwriter 3.2.x** — locked в pyproject (CLAUDE.md §Stack) — already-available; not a new dep.

### Established Patterns
- **Per-domain split** (D-213 retailer-split + D-413 matcher-split) → Phase 5 mirrors как reporter-domain split (`reporter/` + `runners/reporter_run.py`). Симметрия.
- **Append-only + immutable** (DATA-03 inherits): reporter — read-only, никогда не пишет в `runs`/`snapshots`/`matches` (только `runs.stats.report.*` через `patch_stats`).
- **`runs` lifecycle extension** (DATA-05): reporter НЕ создаёт runs row — она уже есть. Только `patch_stats` для `report.*` keys. Mirror Phase 3 D-309 + Phase 4 «extends runs row, не создаёт».
- **Stats namespace enforcement** (D-211/D-414): Phase 5 `ReportStatsBuilder` enforces `report.` prefix. Прямой `runs.stats[key]` write через builder, не bare dict.
- **CLI subcommands** (Phase 3 + Phase 4): `report-run --run-id N` standalone + `weekly-run` composition. Phase 6/7 продолжат паттерн (`delivery-run`, possibly `health-check`).
- **DATA-05 try/except DATA-05 lifecycle** (Plan 02-05): `run_weekly` wraps body in try/except; reporter exception → `run_writer.fail(rid, traceback)` через outer except.
- **Atomic SQL stats merge via patch_stats** (Pitfall 6): single-call `UPDATE runs SET stats = json_patch(stats, :delta)` — Phase 5 reuses без read-modify-write.
- **Frozen schema, no migrations** (D-220): Phase 5 не меняет `runs`/`snapshots`/`matches`; reporter — read-only consumer.
- **Tests use real on-disk SQLite + assert state** (Plan 04-04 integration test pattern): Phase 5 integration tests open generated xlsx with openpyxl and assert structure.

### Integration Points
- **Input ← `matches` table** (Phase 4 D-401, denormalized 13-col): full row-per-match read, ORDER BY abs(price_delta_pct) DESC.
- **Input ← `snapshots` table** (Phase 2 D-202, 18-col): для Assortment gaps + Goldapple promos, filtered by retailer + multipack/volume/stock_state.
- **Input ← `runs` table** (Phase 2 D-201): `status` (D-507 gate read), `started_at` (D-512 ISO week derivation), `stats.match.*` (D-414 reads for text summary).
- **Input ← `pyproject.toml [tool.ga_crawler.report]`** (D-516 new namespace): output_dir + size_limit_mb + top_n_deltas + timezone.
- **Output → `reports/YYYY-WNN.xlsx`** (D-510 atomic write): 4-sheet workbook with Russian headers + CF + frozen panes + autofilter.
- **Output → `runs.stats.report.*` keys** через `patch_stats` (D-514 7 keys): xlsx_path / xlsx_size_bytes / summary_text / sheet_row_counts / skipped_reason / size_guard_passed / generated_at.
- **Output → Phase 6 delivery** consumes `report.xlsx_path` (file location) + `report.summary_text` (Telegram caption) + `report.size_guard_passed` (DELIVER-03 sanity-gate input). Phase 6 НЕ regenerates summary, НЕ re-reads БД для caption.
- **Output → CLI integration**: `cli.py` добавляется `report-run` subcommand (Plan 05-XX); `weekly-run` уже work — main_run.py amends.

### Open dependencies
None — Phase 5 fully unblocked. Phase 4 closed (matches + match.* stats ship). Phase 2/3 closed (snapshots ship). Phase 5 — pure data-derivation + file-output phase, без новых fetcher/parser зависимостей. xlsxwriter 3.2.x уже в pyproject (CLAUDE.md §Stack).

</code_context>

<specifics>
## Specific Ideas

- **«Reporter — это source-of-truth для caption»** (D-514): Phase 6 НЕ дублирует summary-логику. xlsx + `summary_text` пишутся одновременно reporter'ом → Phase 6 читает `runs.stats.report.summary_text` дословно для Telegram caption. Защита от drift между summary в xlsx cell A1 и Telegram caption.
- **«REPORT-06 — это delivery-time concern, не reporter-time»** (D-515): xlsx пишется на диск ВСЕГДА (если status=success); size-guard поднимает флаг для Phase 6 DELIVER-03; xlsx остаётся для manual recovery / split-and-send. ARCHITECTURE.md «reporter independent of delivery» удерживается.
- **«ISO week из started_at, не finished_at, не now()»** (D-512): детерминированно для re-run. report-run --run-id 42 во вторник для воскресной runs.started_at — всегда тот же filename, что и cron-вызов в воскресенье.
- **«D-403 N→1 не дедуплицируется в reporter»** (D-501): commercial-signal preservation. Excel autofilter — задача оператора. Reporter — нейтральный transformer.
- **«CF green = goldapple дороже = viled cheaper»** (D-505): семантика выбрана от потребителя отчёта (pricing-менеджер viled). Положительная дельта = позитивный сигнал «viled конкурентен».
- **«Текстовая сводка — фиксирован шаблон с week-1 baseline»** (D-504): шаблон зафиксирован в `summary_builder.py` константами. Изменение — git PR с обновлением regression test. Mirror D-405 KPI freeze pattern.
- **«Топ-3 дельты по ABS(price_delta_pct)»** (D-504 + Claude's Discretion): наибольший абсолютный сдвиг — наиболее actionable, независимо от знака (узнать о голдэппловской глубокой скидке так же важно, как о их завышенной цене).

</specifics>

<deferred>
## Deferred Ideas

- **Per-brand match-rate sheet** — v2 (REPORT-V2-02 Brand-level aggregate). On-demand SQL aggregation; Phase 5 — overall rate only из `runs.stats.match.rate`.
- **Week-over-week delta column в Per-SKU deltas** — v2 (REPORT-V2-01). Phase 5 — single-run snapshot; cross-run сравнение требует join по предыдущему run_id, отдельный feature.
- **New/disappeared SKU sheet** — v2 (REPORT-V2-03). Аналогично требует prev-run join.
- **Match-rate degradation alert (>10% drop from 4-week-avg)** — v2 (REPORT-V2-04). Phase 5 — baseline only; alert — отдельная phase.
- **Promo-frequency view (как часто goldapple ставит скидку на бренд)** — v2 (REPORT-V2-05). Требует cross-run history aggregation.
- **PDF-вариант сводки** — out of scope для v1 (xlsx + Telegram caption достаточно per PROJECT.md). v2 territory (DELIVER-V2-01 Email channel).
- **Web dashboard для исторических трендов** — v2 (INFRA-V2-03). Phase 5 — xlsx-only.
- **`report-run --last-success` auto-pick** — отвергнуто D-509: оператор должен явно выбирать run_id для recovery. Уменьшает риск случайной перезаписи.
- **`reports/` retention rotation** (mirror backups/ 4-rotate) — не нужно: один файл на ISO week, история накапливается естественно. Если 5 лет × 52 недели × ~5 MB = ~1.3 GB через 5 лет — приемлемо для VPS.
- **xlsx encryption / password protection** — out of scope; внутренний инструмент команды viled.
- **Auto-truncate top-N rows при size > 45 MB** — отвергнуто D-515: теряем информацию. Phase 6 решает (manual delivery / Bot API self-hosted server для 2 GB limit).
- **Reporter в weekly-run optional flag `--with-report=false`** — отвергнуто D-511: reporter — обязательная часть weekly pipeline (без него Phase 6 нечего отправлять). Skip управляется через D-507 status-gate.
- **Multi-language headers (EN + RU)** — out of scope; команда viled полностью русскоязычная per PROJECT.md.
- **Sheet ordering customization через config** — отвергнуто; Summary всегда первый, остальные fixed order для UX-consistency.
- **Excel pivot tables / charts** — out of scope для v1; данные в plain rows + conditional formatting + autofilter достаточно. v2 territory если потребуется.
- **Live tests против real БД on Hetzner** — out of scope для Phase 5; mirror Phase 4 (no `-m live`). Synthetic fixtures + integration tests достаточны.

### Reviewed Todos (not folded)
`todo match-phase 5` returned 0 matches — todos infrastructure не задействована для Phase 5 specifically.

</deferred>

---

*Phase: 5-reporter-excel-summary*
*Context gathered: 2026-05-11*
*Decisions: D-501..D-516 (16 decisions). 4 areas discussed; все recommended-варианты приняты пользователем.*

## Action Items for Other Documents

The following changes propagate to other artifacts at next opportunity:

- **`.planning/REQUIREMENTS.md` REPORT-01**: amend «бренды на goldapple, отсутствующие на viled» → «SKU на goldapple, отсутствующие на viled по strict-key (brand_norm, name_norm, volume_norm), в пределах brand-overlap (CRAWL-02 scope)» per D-502. Brand-level gap = ∅ by CRAWL-02 construction; SKU-level — корректная интерпретация intent'а. Surface at Plan 05-XX Wave 0 verifies + amends.
- **`.planning/STATE.md`**: add to "Accumulated Key Decisions" — "Phase 5 reporter — source-of-truth for Telegram caption (D-514): `runs.stats.report.summary_text` пишется reporter'ом, Phase 6 читает дословно. Защита от summary-drift между xlsx cell A1 и Telegram caption" — surface at next phase transition.
- **`.planning/STATE.md`**: add — "Phase 5 REPORT-06 size-guard (D-515) — log warning + `report.size_guard_passed=false` flag в stats; xlsx ВСЕГДА пишется на диск. Phase 6 DELIVER-03 sanity-gate ОБЯЗАН читать `report.size_guard_passed` и роутить >45MB runs в ops-chat alert вместо business-chat" — surface at next phase transition (cascade in Phase 6 CONTEXT).
- **`pyproject.toml`**: add `[tool.ga_crawler.report]` namespace per D-516 (output_dir / size_limit_mb / top_n_deltas / timezone) — surface at Plan 05-XX Wave 0.
