---
tags: [decision, phase-5, phase-6, reporter, telegram, size-guard, REPORT-06, D-515]
date: 2026-05-11
phase: 05-reporter-excel-summary
decision_ids: [D-515]
status: locked
cascades_to: phase-6
---

# REPORT-06 size guard — delivery-time concern, не reporter-time

## Решение

При xlsx_size_bytes > `size_limit_mb × 1024 × 1024` (default 45 MB per D-516):

- **structlog warning** event `report_size_exceeded` с size_bytes + threshold + run_id
- **`runs.stats.report.size_guard_passed = false`** через atomic `patch_stats` (Pitfall 6)
- **xlsx ПИШЕТСЯ на диск** в `reports/YYYY-WNN.xlsx` (REPORT-05 inviolate — файл всегда есть для manual recovery / split-and-send-later)
- **Run status остаётся `'success'`** — reporter НЕ вызывает `run_writer.fail`

REPORT-06 «явная ошибка» surface-ится **на delivery boundary** (Phase 6 DELIVER-03 sanity-gate), не в reporter:
- Phase 6 ОБЯЗАН прочитать `report.size_guard_passed` ДО `send_document`
- Если `false` → business-chat **skipped**, ops-chat **alert**: «xlsx too large for Telegram, run {rid} — manual delivery required»

## Зачем такое разделение

### Что REPORT-06 буквально говорит

> «Размер xlsx проверяется перед отправкой — если > 45 MB, ругается явной ошибкой (Telegram limit 50 MB).»

Ключевое слово — **«перед отправкой»**. Это delivery-time check, не reporter-time. Reporter создаёт артефакт; delivery решает что с ним делать.

### Почему НЕ raise + fail run

Альтернативы рассмотрены и отвергнуты:

| Alternative | Reason rejected |
|---|---|
| Raise ReportTooLargeError + run_writer.fail | Жесткая ошибка; **теряем data** (xlsx не пишется), потеряли run-data (был success из crawler позиции, теперь failed) |
| Auto-truncate top-N rows | Теряем информацию; xlsx становится «обрезанным произведением» вместо «слишком большим архивом»; REPORT-06 не про это |

Выбранный D-515 path: log warning + flag, xlsx persists, run остаётся success — оператор имеет xlsx файл на диске для:
1. Manual upload в Telegram self-hosted Bot API (raises limit до 2 GB)
2. Email-вложение (DELIVER-V2-01 в v2)
3. Split в несколько xlsx по brand/category + последовательная доставка

### Альянс с ARCHITECTURE.md

«Reporter is independent of delivery — file on disk first.» Reporter не должен знать о Telegram limit'е семантически — он знает только о `size_limit_mb` config-параметре, который случайно равен 45 (50 Telegram - 5 safety). Если завтра канал доставки сменится, изменится только `[tool.ga_crawler.report].size_limit_mb`.

## Что Phase 6 ОБЯЗАН реализовать

При `/gsd-discuss-phase 6`:

```python
# Phase 6 DELIVER-03 sanity-gate (pseudocode)
def deliver(run_id):
    stats = read_stats(run_id)
    if stats.get('runs.status') != 'success':
        ops_alert(...)
        return
    if not stats.get('report.size_guard_passed', True):
        ops_alert(
            f"xlsx too large for Telegram (size={stats['report.xlsx_size_bytes']} > 45MB), "
            f"run {run_id} — manual delivery required at {stats['report.xlsx_path']}"
        )
        # business-chat NOT touched
        return
    business_send(
        document=stats['report.xlsx_path'],
        caption=stats['report.summary_text'],  # verbatim per D-514
    )
```

Cascade Action Item **зафиксирован в `05-CONTEXT.md` Action Items L280-281** для Phase 6 CONTEXT при `/gsd-discuss-phase 6`.

## Pitfall mitigation

- **T-05-disk-full** (xlsx write fails mid-write на full disk) → atomic `*.xlsx.tmp + os.replace` гарантирует или completed файл, или ничего; insufficient disk → `OSError` → DATA-05 catches → `run_writer.fail(rid, traceback)`. Size guard срабатывает ПОСЛЕ write_atomic, так что состояние диска уже подтверждено.
- **T-05-partial-write** (process killed mid-xlsxwrite) — атомичность `os.replace` (Python 3.3+ cross-platform) защищает от corrupted partial xlsx. `report.size_guard_passed` reflects final committed file size, не in-progress.
- **REPORT-05 / D-510 overwrite** — если retry создаёт меньший xlsx (например, fewer matches), флаг переключается обратно `true`. Phase 6 reads current state, не historical.

## Caveats

- **xlsx_size_bytes vs filesystem block size** — `Path.stat().st_size` returns actual byte count, не disk-blocks. Безопасно для 45MB порога (далеко от inode-level concerns).
- **Telegram Bot API actual limit** — официально 50 MB для documents. 45MB threshold даёт 5MB safety margin (network overhead, multipart encoding, future Telegram limit changes). При смене на self-hosted server (`telegram-bot-api` daemon) — `size_limit_mb=2000` в pyproject; reporter unchanged.
- **Compressed xlsx** — xlsxwriter пишет ZIP-compressed XML. Текстово-тяжёлые рапорты (50k rows × 11 cols) обычно 3-15 MB. 45MB порог триггерится только при экстремальной cardinality (например, 200k+ rows). На v1 это unlikely — viled ~120 SKU, goldapple ~5-50k SKU.

## Связано

- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] (D-514 — `size_guard_passed` входит в 7-key namespace)
- [[Match-rate — KPI с первой недели]] (D-405 — `match.rate` not affected by size guard)
- [[Sanity-gate P — третий экземпляр паттерна auto-suggest 0.7×median]] (D-407..D-409 — этот pattern инвертирует: matcher FAILS run; reporter FLAGS run)

## Источник

- `.planning/REQUIREMENTS.md` REPORT-06
- `.planning/phases/05-reporter-excel-summary/05-CONTEXT.md` D-515 + D-516 (`size_limit_mb=45`)
- `.planning/phases/05-reporter-excel-summary/05-RESEARCH.md` §Pitfall 11 (size guard semantics)
- ARCHITECTURE.md §"Reporter is independent of delivery"
