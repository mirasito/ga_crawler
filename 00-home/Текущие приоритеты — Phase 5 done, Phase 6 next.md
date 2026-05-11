---
tags: [priority, phase-6, telegram, delivery, active]
date: 2026-05-12
status: active
---

# Текущие приоритеты — Phase 5 done, Phase 6 next

Phase 5 (Reporter — Excel + summary) закрыт `/gsd-execute-phase 5` 2026-05-12. 6 plans across 6 waves, 1 Rule 1 deviation (Windows cp1252 → `sys.stdout.buffer.write`), 472→610 tests, 0 regressions. Verifier 6/6 must-haves; 3 визуальных items в `05-HUMAN-UAT.md` для оператора.

## Прямо сейчас

`/clear` затем `/gsd-discuss-phase 6` (Telegram Delivery + Ops/Business Split).

Опции до Phase 6:
- `/gsd-code-review 5 --fix` — закрыть WR-01 (skip-path `size_guard_passed` divergence) + WR-02 (`check_size_guard` docstring vs `stat()` raise) до начала Phase 6
- `/gsd-secure-phase 5` — security gate ещё не закрыт (workflow.security_enforcement=true; SECURITY.md отсутствует)
- `uv run python -m ga_crawler weekly-run` (live) + `/gsd-verify-work 5` — resolve 3 HUMAN-UAT visual items с реальными данными

## Что осталось делать (если порядок Phase 6 → cleanup устраивает)

- WR-01 + WR-02 fold в Phase 6 polish — Phase 6 delivery-gate всё равно будет ловить `size_guard_passed`, можно закрыть divergence по ходу
- HUMAN-UAT items — resolve when первый weekly-run отгрузит real-data xlsx (synthetic фиктура byte-for-byte equivalent, но operator confidence выше с реальными prices)

## Phase 6 inputs готовы

- **`runs.stats.report.xlsx_path`** — relative path xlsx archive (D-514)
- **`runs.stats.report.summary_text`** — multi-line emoji Telegram caption (D-504 + D-514 source-of-truth)
- **`runs.stats.report.size_guard_passed`** — D-515 boolean flag для DELIVER-03 sanity-gate
- **`runs.stats.report.xlsx_size_bytes`** — int для pre-send check vs 50 MB Telegram limit
- **`runs.stats.report.generated_at`** — ISO 8601 UTC для caption staleness check

## Cascading invariants Phase 6 должна соблюдать

- **D-405 verbatim citation** — Phase 6 cite `runs.stats.match.rate` *(если включает KPI в delivery msg)* напрямую, не recompute
- **D-514 без regen** — Phase 6 НЕ строит свой caption; читает `report.summary_text` verbatim
- **D-515 size guard delivery-time** — DELIVER-03 sanity-gate отбрасывает xlsx с `size_guard_passed=false` в ops chat (warning), не business chat (silent)
- **Pitfall 6** — Phase 6 пишет `deliver.*` namespace (Phase 6 D-decisions определят keys) через single `patch_stats`
- **WR-01** — **читать `size_guard_passed` из `run_writer.get_stats(run_id)`**, НЕ из in-memory `MainRunResult` (skip-path расходится с DB)
- **Two-chat split** — ops chat (всё кроме success), business chat (только success + xlsx + caption); pre-send gate enforces boundary

## Frozen modules от Phase 5

Phase 6 не модифицирует:
- `src/ga_crawler/reporter/{config,stats,queries,excel_builder,summary_builder,archive}.py`
- `src/ga_crawler/runners/reporter_run.py`
- `src/ga_crawler/matcher/*`
- `src/ga_crawler/runner/{gates,stats}.py`
- Phase 3 `src/ga_crawler/{enumeration,fetchers,parsers}/goldapple_*.py`

`runners/main_run.py` + `cli.py` будут extended (как было в Plan 05-05 — composition + CLI subcommand mirror).

## State of play

- **ROADMAP**: phases 1-5 complete; phase 6 next (DELIVER-01..05); phase 7 (Scheduler + Observability) последняя
- **v1 requirements**: 37/48 → планируется **42/48** после Phase 6 (5 DELIVER- IDs)
- **Plans complete**: 39 (Phase 1=9 + Phase 2=6 + Phase 3=9 + Phase 4=6 + Phase 5=6 + Phase 1 skipped=3 не считаются)
- **Test suite**: 610 passed, 1 skipped
- **Branch**: `master`, clean modulo untracked

## Connected notes

- [[2026-05-12 — Phase 5 executed — reporter shipped через 6 waves]] *(итог Phase 5)*
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] *(D-514)*
- [[REPORT-06 size guard — delivery-time concern, не reporter-time]] *(D-515)*
- [[Skip-path ReporterPhaseResult — size_guard_passed расходится между DB и memory]] *(WR-01 — Phase 6 must read from DB)*
- [[CLI stdout UTF-8 на Windows — sys.stdout.buffer.write вместо print]] *(Plan 05-05 inheritance — Phase 6 `delivery-run` CLI должен следовать)*
- [[Telegram Bot API — канал доставки отчёта]] *(integration ref)*
- [[Excel больше 45 MB — Telegram отбросит]] *(D-515 рождение)*

## После Phase 6

Phase 7 (Scheduler + Observability Hardening) — финальный VPS setup + cron `CRON_TZ=Asia/Almaty` + Healthchecks.io dead-mans-switch + structlog deployment. Никаких feature-фаз после; v1 ship.

## Что НЕ делать

- Не строить второй summary template в Phase 6 — `report.summary_text` source-of-truth
- Не recompute size в delivery-gate — `report.size_guard_passed` + `report.xlsx_size_bytes` уже в БД
- Не использовать `print(json.dumps(..., ensure_ascii=False))` для CLI вывода — Windows cp1252 ломает (см. pattern)
- Не модифицировать reporter modules — frozen после Phase 5

## Git state

```
0688233 docs(phase-05): complete phase execution — verification + REVIEW + UAT close-out
94ebb3c test(05): persist human verification items as UAT
4ba89c7 docs(05-review): code review findings
2dd3627 docs(05-06): complete reporter-excel-summary phase plan 05-06
... (31 commits total за Phase 5)
```
