---
tags: [debugging, reporter, phase-5, phase-6, code-review, WR-01]
date: 2026-05-12
severity: warning
status: open-for-phase-6-consumer
---

# Skip-path ReporterPhaseResult — size_guard_passed расходится между DB и memory

## Симптом

Phase 5 reporter в skip-path (когда `runs.status != 'success'`) пишет в БД `report.size_guard_passed = False`, но возвращает `ReporterPhaseResult` с dataclass-default `True`. `main_run` затем пропагирует `True` в `MainRunResult.size_guard_passed` и логирует через `weekly_run_complete` event.

**БД и orchestrator return value расходятся** по флагу, который Phase 6 delivery gate должен читать.

## Где

- `src/ga_crawler/runners/reporter_run.py:97` — dataclass default
- `src/ga_crawler/runners/reporter_run.py:109-113` — skip-path patch_stats записывает `False` в `runs.stats.report.size_guard_passed`
- `src/ga_crawler/runners/main_run.py` — пропагирует `r_result.size_guard_passed` (in-memory) в `MainRunResult`

## Почему опасно (только для Phase 6+)

Phase 5 сам по себе не пользуется этим флагом downstream — Phase 5 пишет xlsx и финиширует. Но Phase 6 (Telegram Delivery + Ops/Business Split) спроектирована так, что **DELIVER-03 pre-send sanity-gate читает `size_guard_passed`** — `True` → business chat доставка; `False` → ops chat warning only.

Если Phase 6 берёт `size_guard_passed` из `MainRunResult` (in-memory) в skip-path — gate видит `True` и пытается доставить xlsx, которого нет (skip-path не создаёт файл). Результат: либо silent miss, либо delivery error в business chat вместо ops.

## Что делать

**Phase 6 ОБЯЗАН читать `size_guard_passed` из БД** через `run_writer.get_stats(run_id)["report.size_guard_passed"]`, НЕ из `MainRunResult.size_guard_passed`. БД — source of truth (Pitfall 6 atomic merge invariant).

Альтернатива (fix-at-source): в `reporter_run.py::_skip_path` явно установить `size_guard_passed=False` в возвращаемом `ReporterPhaseResult` — closes divergence на orchestrator-уровне. ≤5 LOC fix.

## Repro

```python
# synthetic skip case
engine, run_writer, run_id, _ = synthetic_report_run
run_writer.fail(run_id, "synthetic failure")  # status = 'failed' → reporter skips

result = run_reporter_phase(run_id=run_id, engine=engine, run_writer=run_writer, ...)
assert result.status == "skipped"
assert result.size_guard_passed is True  # in-memory dataclass default

stats = run_writer.get_stats(run_id)
assert stats["report.size_guard_passed"] is False  # DB truth
```

## Solutions

- **Сейчас:** `/gsd-code-review 5 --fix` (WR-01) — applies tha ≤5-LOC fix automatically
- **Phase 6 (если WR-01 не fix'нут раньше):** delivery-gate всегда читает из `run_writer.get_stats(run_id)`, не из result. Code review canary в Phase 6 PLAN.md: `grep "size_guard_passed" src/ga_crawler/runners/main_run.py` должен не находить `r_result.size_guard_passed` чтения в delivery-step.

## Связанные

- [[REPORT-06 size guard — delivery-time concern, не reporter-time]] *(D-515 рождение)*
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] *(D-514 — БД source-of-truth invariant)*
- [[Excel больше 45 MB — Telegram отбросит]] *(симптом, который size_guard защищает)*
- [[2026-05-12 — Phase 5 executed — reporter shipped через 6 waves]] *(когда WR-01 surfaced)*
