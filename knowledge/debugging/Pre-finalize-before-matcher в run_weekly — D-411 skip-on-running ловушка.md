---
tags: [debugging, phase-4, matcher, composition, gotcha]
date: 2026-05-11
phase: 04-matcher-match-rate-kpi
plan: 04-05
severity: blocking-if-missed
status: resolved
---

# Pre-finalize-before-matcher в run_weekly — D-411 skip-on-running ловушка

## Симптом

В composed `run_weekly()` matcher **всегда** возвращал `status='skipped'` с `match.skipped_reason='in_progress_upstream'`, даже когда viled и goldapple отработали успешно. matches table оставалась пустой, KPI=0.0, weekly run выглядел успешным, но без отчёта.

## Root cause

D-411 skip-protocol matcher'а проверяет `runs.status` ДО построения matches:

```python
status = read_run_status(engine, run_id)
if status in ('failed', 'running', None):
    return MatcherPhaseResult(status='skipped', ...)
```

Внутри `run_weekly` runs row создаётся в начале как `status='running'` и финализируется ТОЛЬКО в самом конце. Matcher вызывается **между** crawl-phases и `finalize()` → видит `'running'` → скипает. По спецификации D-411 это корректно для standalone `matcher-run` (там run уже завершён), но в composition ломает pipeline.

Plan 04-05 явно говорил «matcher D-411 handles upstream-failure on its own» — что справедливо только для standalone случая.

## Решение

В `run_weekly` финализировать run как `'success'` ДО вызова matcher:

```python
# viled + goldapple completed
run_writer.finalize(run_id, 'success')   # matcher теперь видит 'success'
matcher_result = run_matcher_phase(...)
if matcher_result.status == 'failed':
    # matcher.fail() уже флипнул status обратно на 'failed'
    return MainRunResult(status='failed', ...)
# финальный finalize() ниже идемпотентен через WHERE status='running' guard
```

Matcher's `run_writer.fail(...)` НЕ имеет status-guard'а → перезаписывает `'success'` обратно на `'failed'` при D-409 gate-fail. Финальный `finalize()` в конце `run_weekly` ловит только `'running'` (идемпотентен) → не перетрёт корректный failed/success.

## Структурная защита

- Тест в `tests/integration/test_main_run_e2e.py` фиксирует: matcher НЕ возвращает status='skipped' в composed path при здоровых crawls
- Standalone `matcher-run` semantics не затронуты — там status уже финален

## Generalization

Когда какой-либо protocol-step внутри pipeline проверяет shared mutable state (типа `runs.status`), убедись что upstream-stages фиксируют то состояние, на которое downstream-step ожидает реагировать. **Skip-protocol полезен для standalone recovery, но в composition требует явного state-handshake.**

## Connections

- [[2026-05-11 — Phase 4 executed — matcher + KPI shipped через 5 waves]] — где обнаружилось
- [[Matches table — денормализованная, N→1 keep-all]] — таблица была бы пустой без фикса
- [[Run-level sanity-gate перед доставкой]] — D-409 P-gate работает корректно благодаря этому фиксу
