---
tags: [decision, phase-5, reporter, telegram, caption, single-source-of-truth, D-514]
date: 2026-05-11
phase: 05-reporter-excel-summary
decision_ids: [D-514]
status: locked
---

# Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text

## Решение

В Phase 5 `reporter_run.py` пишет multi-line emoji summary string (D-504 template) ОДНОВРЕМЕННО:
1. В **cell A1 листа Summary** xlsx-файла
2. В **`runs.stats.report.summary_text`** (атомарно через `patch_stats`, mirror Pitfall 6)

Phase 6 (Telegram Delivery) **читает `report.summary_text` дословно** для `send_document(caption=...)` без regen, без повторной БД-выборки, без повторного computation top-3 deltas.

## Зачем

Защита от drift между:
- cell A1 в xlsx, который оператор открывает
- Telegram caption, который команда видит в бизнес-чате
- любой ad-hoc summary при операторском recovery

Если Phase 6 имел бы собственную summary-логику, любое будущее изменение D-504 template требовало бы синхронного edit'а в двух местах. Risk silent divergence — Telegram caption отстаёт от Excel cell на новые поля (например, если week-over-week delta появится в v2).

## Что D-514 fixes структурно

7-key namespace `report.*` записывается reporter'ом одним atomic `patch_stats({json_patch})`:

| Key | Type | Purpose |
|---|---|---|
| `report.xlsx_path` | str | Phase 6 reads для `send_document(document=open(path, 'rb'))` |
| `report.xlsx_size_bytes` | int | Sanity check / monitoring |
| `report.summary_text` | str | **THIS DECISION** — Phase 6 reads для caption verbatim |
| `report.sheet_row_counts` | dict | Audit (e.g. `{"per_sku_deltas": 47, "gaps": 8385, "promos": 1247}`) |
| `report.skipped_reason` | str OR null | "failed_upstream" если D-507 trip, null иначе |
| `report.size_guard_passed` | bool | REPORT-06 — Phase 6 DELIVER-03 gate (see [[REPORT-06 size guard — delivery-time concern, не reporter-time]]) |
| `report.generated_at` | str | ISO 8601 timestamp (audit + observability) |

## Pattern Mirror

Этот pattern — третий экземпляр в проекте «producer пишет в `runs.stats.<domain>.*`, consumer READS, не recomputes»:

| Phase | Producer | Consumer | Frozen Key |
|---|---|---|---|
| 2 | `viled_run.py` | matcher, reporter | `viled.*` (9 keys) |
| 3 | `goldapple_run.py` | matcher, reporter | `goldapple.*` (13 keys) |
| 4 | `matcher_run.py` | reporter | `match.*` (10 keys, D-414) |
| **5** | `reporter_run.py` | **Phase 6 delivery** | **`report.*` (7 keys, D-514)** |

4-way disjoint invariant: `viled.* ∩ goldapple.* ∩ match.* ∩ report.* = ∅`. Тестируется в `tests/unit/test_report_stats.py::test_four_way_namespaces_disjoint`.

## Pitfall mitigation

- **Pitfall 6 (atomic patch_stats)** — reporter вызывает `run_writer.patch_stats(rid, delta_dict)` ОДИН РАЗ per code path. Никакого read-modify-write. SQL `UPDATE runs SET stats = json_patch(stats, :delta)` атомарен на уровне SQLite execution.
- **Pitfall 4 (RFC-7396 null deletes)** — `ReportStatsBuilder` rejects None values; sentinels для absent — `""` (empty string для skipped_reason), `False` для bool, `{}` для dict, `-1`/`0` для int.

## Caveats / edge cases

- **D-507 skip path** — если `runs.status != 'success'`, reporter пишет ТОЛЬКО `report.skipped_reason='failed_upstream'`; остальные 6 keys остаются absent. Phase 6 проверяет `skipped_reason` ДО чтения `summary_text`.
- **REPORT-06 size guard fail** — если xlsx > 45MB, `report.size_guard_passed=false` но `summary_text` ВСЁ РАВНО пишется (xlsx тоже пишется на диск). Phase 6 решает routing: business-chat skip + ops-chat alert. См. [[REPORT-06 size guard — delivery-time concern, не reporter-time]].

## Связано

- [[Match-rate — KPI с первой недели]] (Phase 4 D-405 — `match.rate` consumed verbatim в `summary_text`)
- [[REPORT-06 size guard — delivery-time concern, не reporter-time]] (D-515)
- [[Matches table — денормализованная, N→1 keep-all]] (D-401 — input для summary)

## Источник

- `.planning/phases/05-reporter-excel-summary/05-CONTEXT.md` D-514 + D-504
- `.planning/phases/05-reporter-excel-summary/05-RESEARCH.md` §"Pattern: atomic stats writing"
- 04-CONTEXT.md D-414 (pattern source)
- STATE.md row "patch_stats MUST use single-call SQL"
