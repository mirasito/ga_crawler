---
tags: [home, priorities, phase-4, execute, matcher, kpi]
date: 2026-05-11
status: active
---

# Текущие приоритеты — Phase 4 plan ready, execute next

## Контекст

Phase 3 окончательно закрыт по двум осям 2026-05-11:
- **UAT Test 6** (cold-start Loading race) — pass через 4/4 cold-spawn invocations на live KZ-laptop (утро)
- **Security re-audit** (`94989bc`) — 35/35 closed, plans 03-08/03-09 surface re-verified, никаких регрессий (день)

Phase 4 теперь полностью спланирован:
- CONTEXT.md — 15 решений D-401..D-415 (`a16f0e1`)
- PATTERNS.md — 11/11 analogs mapped к existing codebase
- 6 PLAN.md across 5 waves — verified by gsd-plan-checker, 0 blockers (`fdbd229`)

State of play:
- ROADMAP: Phases 1-3 complete; Phase 4 **planned & verified**, ready to execute; Phases 5-7 untouched
- v1 requirements: 27/48 closed → 31/48 после Phase 4 execution (MATCH-01..04)
- Open Warnings: 5 non-blocking из `03-REVIEW.md` + 1 новая WARN-1 в Phase 4 plans (gate boundary `>` vs `>=` inherited from Phase 2/3 D-203 precedent)
- Phase 7 ops-playbook backlog: 3 items неизменно

## Что делать прямо сейчас

**`/gsd-execute-phase 4`** — план готов, контекст плотный (D-401..D-415 покрывают всю серую зону), pattern-mapper уже отработал, plan-checker passed. Wave structure линейная (1→2→3→4→5), 04-01 и 04-02 могут параллелиться в Wave 1.

Ожидаемый объём изменений: **7 новых файлов** + **4 amended** + ~80 unit/integration тестов. Самые load-bearing инварианты для executor'а:

1. **D-405 KPI freeze** — формула фиксируется с week 1; source-locked canary `test_match_rate_formula_canary` (04-03 Test 14) + end-to-end `test_kpi_formula_end_to_end` (04-04 Test 10). НЕ изменять без обновления fixture.
2. **D-402/-404 symmetric filters** — `multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'` применяется к **обеим** сторонам JOIN (viled + goldapple) в numerator И denominator. Asymmetric = silent KPI corruption.
3. **D-410 idempotency** — DELETE+INSERT в одной `with engine.begin() as conn:` транзакции; tests re-run 3× и asserting stable count.
4. **D-411 skip protocol** — viled OR goldapple status='failed'/'in_progress' → matcher skip (structured-log warning, НЕ touch matches table, НЕ write zero-match row).
5. **D-414 stats namespace strict** — 10-key allowlist в `MatchStatsBuilder`; `StatsNamespaceError` на anything else.
6. **D-409 gate-fail audit invariant** — `match_count <= P` → `run_writer.fail` AFTER matches rows committed; matches **persist** для audit-trail.

## Альтернативы (если откладываем execute)

- `/gsd-code-review 4` — predict-review plans перед execution (cross-AI feedback). Если нужна вторая пара глаз.
- `/gsd-code-review 3 --fix` — закрыть WR-01..05 из Phase 3 REVIEW.md перед началом Phase 4. Не блокирует.
- Optional: добавить `test_gate_boundary_match_count_equals_p` для WARN-1 alignment — если хочется strict `>` boundary вместо inherited `>=`.

## Чего НЕ делать

- НЕ менять D-405 формулу `matches / viled_skus_with_brand_in_goldapple_brands × 100%` — она frozen с week 1 как исторический baseline.
- НЕ async-ить matcher — sync transaction по D-413 Claude's Discretion; assertion `grep -c 'async def' src/ga_crawler/runners/matcher_run.py == 0`.
- НЕ refactor-ить `NamespaceStatsBuilder` base class в Phase 4 — explicitly deferred per CONTEXT D-414 line 119 "Claude's Discretion"; v2 territory.
- НЕ trogать `interfaces.py` Protocols — frozen с Wave 0 Phase 3.

## Connections

- [[2026-05-11 — Phase 3 security re-audit + Phase 4 discuss и plan готовы]] — последняя сессия
- ~~[[Текущие приоритеты — Phase 3 closed окончательно, дальше Phase 4]]~~ — superseded
- [[Match-rate — KPI с первой недели]] — формула теперь frozen + source-locked
- [[Matches table — денормализованная, N→1 keep-all]] — новое решение Phase 4
- [[Sanity-gate P — третий экземпляр паттерна auto-suggest 0.7×median]] — новое решение Phase 4
- [[Strict-key матчинг вместо fuzzy в v1]] — core matching strategy
- [[.planning/ROADMAP|ROADMAP.md]] — Phase 4 success criteria
- `.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT.md` — D-401..D-415 locked decisions
- `.planning/phases/04-matcher-match-rate-kpi/04-0{1..6}-PLAN.md` — executable plans
