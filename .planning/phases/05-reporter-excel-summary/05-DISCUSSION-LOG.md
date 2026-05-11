# Phase 5: Reporter (Excel + summary) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 5-reporter-excel-summary
**Areas discussed:** Контракты листов + русские лейблы + шаблон сводки, Conditional formatting + zero-match edge cases, CLI + filename + main_run composition, Module layout + reporter stats namespace + REPORT-06 guard

---

## Area 1 — Контракты листов + русские лейблы + шаблон сводки

### Q1: Per-SKU deltas — как показывать N→1 дубликаты (D-403)?

| Option | Description | Selected |
|--------|-------------|----------|
| Показывать все строки как есть | 1 row на match-pair; D-403 N→1 keep-all сохраняется; pricing-менеджер фильтрует сам | ✓ |
| Dedup по min goldapple_price | Один row на viled_sku с наименьшей goldapple ценой; теряется variant-visibility | |
| Оба листа (full + dedup) | Per-SKU deltas + Per-SKU deltas (dedup); 5 листов в v1 | |

**User's choice:** Показывать все строки как есть (Recommended) → **D-501**

### Q2: Assortment gaps — уровень агрегации?

| Option | Description | Selected |
|--------|-------------|----------|
| SKU-level | Одна строка = один goldapple-SKU без viled-пары; колонки Бренд/Название/Объём/Цена goldapple/URL | ✓ |
| Brand-level | Одна строка = бренд + кол-во SKU; компактнее но менее детально | |
| Brand-level summary + SKU detail | Два листа gaps; 5 листов в v1 | |

**User's choice:** SKU-level (Recommended) → **D-502**
**Notes:** Brand-level gap по строгой интерпретации REPORT-01 = ∅ из-за CRAWL-02 (goldapple-crawl ограничен viled-brands). SKU-level — корректная семантика. Documented as REPORT-01 amend Action Item.

### Q3: Стиль русских заголовков?

| Option | Description | Selected |
|--------|-------------|----------|
| Формальный + lowercase brand names | "Бренд", "Цена viled, ₸", "Дельта, %"; brand-values как-есть в snapshots | ✓ |
| Локализованные retailer-имена | "Цена Вилед, ₸", "Цена Голд Эппл, ₸" | |
| URL/Brand разные по сайту + separate валюты | Дополнительные колонки Currency viled / Currency goldapple | |

**User's choice:** Формальный + lowercase бренды (Recommended) → **D-503**

### Q4: Литеральный шаблон текстовой сводки?

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-line блок с эмодзи | 📊 заголовок + строки по KPI + 🔝 топ-3 деltas; используется в Telegram caption И cell A1 Summary-листа | ✓ |
| Multi-line plain (без эмодзи) | То же, но без эмодзи; corporate vibe | |
| One-liner + Summary sheet раздельно | Одна строка, детали в xlsx-ячейках | |

**User's choice:** Multi-line блок с эмодзи (Recommended) → **D-504**

---

## Area 2 — Conditional formatting + zero-match edge cases

### Q5: Conditional formatting — какая колонка и тип?

| Option | Description | Selected |
|--------|-------------|----------|
| 3-color scale по Дельта, % | Green-white-red gradient на Per-SKU deltas; auto min/max; mid=0 | ✓ |
| Solid color по знаку + threshold | Простые cell rules: > 5% green, < -5% red | |
| Color-scale на обе дельты (₸ + %) | CF на обе колонки delta; визуальный шум | |

**User's choice:** 3-color scale по Дельта, % (Recommended) → **D-505**

### Q6: Zero-match и пустые подмножества?

| Option | Description | Selected |
|--------|-------------|----------|
| Строить все 4 листа всегда + headers без строк | Структура xlsx предсказуема; пустой лист = headers + frozen + autofilter | ✓ |
| Skip пустые листы, оставить Summary | Variable sheet-list; Phase 6 обрабатывает | |
| Fail run если match_count=0 | Дублирует MATCH-04 sanity-gate P | |

**User's choice:** Строить все 4 листа всегда + заголовки без строк (Recommended) → **D-506**

### Q7: Предусловие вызова reporter — runs.status gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Только runs.status='success' | Mirror D-411; skip с warning + report.skipped_reason | ✓ |
| status в ('success', 'partial') | Partial mode не выставляется сейчас | |
| Без status-gate: всегда генерировать | Phase 6 решает; противоречит SC#1 | |

**User's choice:** Только runs.status='success' (Recommended) → **D-507**

### Q8: Conditional formatting — на каких листах?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-SKU deltas + Goldapple promos | CF на Дельта,% + Скидка,% — обе значимые ранжируемые метрики | ✓ |
| Только Per-SKU deltas | Букве REPORT-02 (только дельты) | |
| Все числовые колонки | Перебор visual noise | |

**User's choice:** Per-SKU deltas + Goldapple promos (Recommended) → **D-508**

---

## Area 3 — CLI + filename + main_run composition

### Q9: Shape CLI для reporter?

| Option | Description | Selected |
|--------|-------------|----------|
| `report-run --run-id N` | Required flag; mirror D-412 matcher-run; explicit operator choice | ✓ |
| `report-run [--run-id N \| --last-success]` | Дополнительно last-success; два mode в argparse | |
| `report-run` (без обязательных) | Default = last-success; риск случайной перезаписи | |

**User's choice:** `report-run --run-id N` (Recommended) → **D-509**

### Q10: Filename collision policy?

| Option | Description | Selected |
|--------|-------------|----------|
| Overwrite | Перезапись `reports/YYYY-WNN.xlsx`; история в БД (DATA-03); log `report_overwritten` event | ✓ |
| Run-id suffix `2026-W19-run42.xlsx` | Никогда collision; отклонение от REPORT-05 literal format | |
| Overwrite + .bak | Backup-rotate; избыточная логика | |

**User's choice:** Overwrite (Recommended) → **D-510**

### Q11: Вызов reporter в main_run pipeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Да, в main_run после matcher перед finalize | viled → goldapple → matcher → reporter → finalize; xlsx готов к Phase 6 | ✓ |
| Нет, только standalone + Phase 6 | weekly-run не self-contained | |
| Через флаг `--with-report` | Optional; production cron всё равно включит | |

**User's choice:** Да, в main_run после matcher перед finalize (Recommended) → **D-511**

### Q12: ISO week source для filename?

| Option | Description | Selected |
|--------|-------------|----------|
| ISO week от `runs.started_at` (Asia/Almaty) | Детерминированно: повтор всегда дает тот же filename | ✓ |
| ISO week от `runs.finished_at` | Опасно при ран через полночь воскресенья | |
| ISO week от `datetime.now()` при вызове | Не детерминированно при re-run | |

**User's choice:** ISO week от `runs.started_at` (Recommended) → **D-512**

---

## Area 4 — Module layout + reporter stats namespace + REPORT-06 guard

### Q13: Структура `reporter/` package?

| Option | Description | Selected |
|--------|-------------|----------|
| Split: excel + summary + archive | Mirror D-413; reporter/ package с 4 файлами + runners/reporter_run.py | ✓ |
| Flat: reporter.py + runners/reporter_run.py | Один файл ~400-600 LOC; отличается от matcher pattern | |
| Sub-modules без orchestrator | Без runners/reporter_run.py; orchestration в main_run/cli напрямую | |

**User's choice:** Split: excel + summary + archive (Recommended) → **D-513**

### Q14: Stats namespace `report.*` — что пишет reporter?

| Option | Description | Selected |
|--------|-------------|----------|
| Full namespace: path + size + summary + counts | 7 keys; Phase 6 читает без файл-IO + без regen | ✓ |
| Minimal: path + size + skipped_reason | Phase 6 дублирует summary-логику | |
| No stats — return dict from runner | Phase 6 в отдельном процессе не видит dict | |

**User's choice:** Full namespace: path + size + summary + counts (Recommended) → **D-514**

### Q15: REPORT-06 при xlsx > 45 MB?

| Option | Description | Selected |
|--------|-------------|----------|
| Log warning + size_guard_passed=false | xlsx пишется на диск; флаг для Phase 6; не fail run | ✓ |
| Raise ReportTooLargeError + fail run | Жесткая ошибка; теряем data | |
| Auto-truncate top-N rows | Теряем информацию; overkill для v1 | |

**User's choice:** Log warning + size_guard_passed=false (Recommended) → **D-515**
**Notes:** «Явная ошибка» в REPORT-06 surface-ится на delivery boundary (Phase 6 reads `report.size_guard_passed` и роутит >45MB в ops-chat alert). Reporter остаётся delivery-independent per ARCHITECTURE.md.

### Q16: `[tool.ga_crawler.report]` namespace?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: output_dir + size_limit_mb + top_n + timezone | 4 keys; mirror MatchConfig pattern | ✓ |
| Empty (всё в коде как constants) | Теряется operator-PR рычаг | |
| Maximal: + headers + emoji on/off | Дублирует логику; risk divergence | |

**User's choice:** Minimal (Recommended) → **D-516**

---

## Claude's Discretion

User explicitly delegated следующие детали Claude после 4 вопросов в каждой зоне ("Перейти к next area"):

- **Area 1:** точные колонки каждого листа (Per-SKU deltas sort by ABS(delta_pct) DESC; full column-list из D-503 канона; Goldapple promos filter `was_price > current_price`); Summary sheet layout (cell A1 = D-504 текстовая сводка, KPI-блок ниже).
- **Area 2:** 3-color scale auto min/max (xlsxwriter default), frozen top row + autofilter на всех 4 листах, number format `'#,##0 ₸'` / `'0.00'`, was_price NULL = пустая ячейка.
- **Area 3:** flags `--output-dir`/`--db-path`/`--pyproject` для report-run, exit code 0/2 для success/failure, structured log events (report_started / report_xlsx_written / report_summary_built / report_overwritten / report_size_exceeded), `reports/` directory auto-mkdir + .gitkeep + .gitignore exclude *.xlsx.
- **Area 4:** atomic xlsx write через `*.xlsx.tmp` + `Path.replace`, test infra (real on-disk SQLite + openpyxl-read-back assertions + synthetic_report_run fixture), historical re-run graceful с future column additions, sheet ordering Summary→Per-SKU→Gaps→Promos.

## Deferred Ideas

Documented в CONTEXT.md `<deferred>` section. Highlights:

- Per-brand match-rate sheet (REPORT-V2-02)
- Week-over-week delta column (REPORT-V2-01)
- New/disappeared SKU sheet (REPORT-V2-03)
- Match-rate degradation alert (REPORT-V2-04)
- Promo-frequency view (REPORT-V2-05)
- PDF/Email channel (DELIVER-V2-01)
- Web dashboard (INFRA-V2-03)
- `--last-success` auto-pick (отвергнуто per D-509 explicit-operator-choice)
- `reports/` retention rotation (не нужно — ISO-week file per run естественно)
- Auto-truncate при > 45 MB (отвергнуто D-515)
- Multi-language headers (out of scope; команда полностью русскоязычная)
- Excel pivot tables / charts (v2 territory)
