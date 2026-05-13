---
tags: [pattern, planning, gsd-planner, wave-restructure, dependency-graph]
date: 2026-05-13
status: active
---

# Planner может legitimate-override CONTEXT.md decisions если найдёт implicit file-overlap

При `/gsd-plan-phase`, спавн `gsd-planner` агент имеет authority восстановить wave structure если CONTEXT.md `<decisions>` обещает parallel execution, но `files_modified` overlap делает её infeasible. Это не bug и не deviation — это **implicit-dependency rule** срабатывает.

## Concrete example (Phase 8, 2026-05-13)

CONTEXT.md D-809 локированно обещал:
> **W1 (parallel, 3 plans):** разные файлы, can run concurrent:
> - Plan 08-02 — PARSE-FIX-01 goldapple volume_raw
> - Plan 08-03 — PARSE-FIX-02 goldapple brand+name
> - Plan 08-04 — PARSE-FIX-03 viled volume_raw

Планировщик заметил: оба 08-02 и 08-03 модифицируют `src/ga_crawler/parsers/goldapple_microdata.py`. Concurrent execution → merge conflicts ИЛИ race на `parse_pdp` callsite. Restructured:

| Wave | Plans | Reason |
|---|---|---|
| 0 | 08-01 | spike (unchanged) |
| **1 ∥** | **08-02 ∥ 08-04** | disjoint files (goldapple_microdata.py ∥ viled_nextdata.py) |
| **2** | **08-03** | shared file с 08-02, sequenced |
| **3** | 08-05 | depends на W1+W2 (gate reads their stats) |

Override явно задокументирован в `## PLANNING COMPLETE` return + ROADMAP.md cross-cutting constraints.

## Why this is correct behavior

CONTEXT.md `<decisions>` describes **intent**. Планировщик derives **feasibility** через graph analysis на `files_modified`. Если intent и feasibility конфликтуют, planner picks feasibility и documents the override. Альтернатива — silent corruption во время execute (merge conflict при concurrent execution).

## When override is legitimate

- **`files_modified` overlap** между плановыми parallel plans → MUST sequence
- **Schema dependency**: Plan A creates table, Plan B reads it → MUST sequence
- **Stats key dependency**: Plan A writes stat, Plan B asserts on it → MUST sequence

## When override is NOT legitimate

- "Этот approach красивее" — нет, CONTEXT.md decisions locked
- "Я бы сделал по-другому" — нет, нет implicit-graph reason
- Override должен быть **structural**, не **aesthetic**

## Plan-checker validates the override

В Phase 8 plan-checker (`gsd-plan-checker`) явно проверил wave restructure и подтвердил: 08-02 + 08-04 fully disjoint files (`goldapple_microdata.py` ∥ `viled_nextdata.py`); 08-03 после 08-02 устраняет merge conflict. Dimension 3 (Dependency Correctness) — PASS.

## Connected

- `.planning/phases/08-parser-bug-fixes/08-CONTEXT.md` D-809 (overridden)
- `.planning/phases/08-parser-bug-fixes/08-01..05-PLAN.md` (new wave structure)
- `.planning/ROADMAP.md` § Phase 8 (cross-cutting constraints + wave dependency annotations)
- [[2026-05-13 — Phase 8 plan ready (5 plans, 4 waves) — wave restructure caught real file-overlap]] (session note)
