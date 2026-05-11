---
tags: [home, priorities, phase-3, phase-4, transition]
date: 2026-05-11
status: active
---

# Текущие приоритеты — Phase 3 closed окончательно, дальше Phase 4

## Контекст

Phase 3 закрыт 2026-05-11T11:18Z **во второй и финальный раз**. UAT Test 6 эмпирически подтверждён через 4 back-to-back cold-spawn invocations `scripts/uat3_live_run.py`. Plan 03-09 structural fix (warm-up navigation + retry-once safety net + CR-01 GATE_TITLE_MARKER hardening) валидирован на live goldapple.kz. Commit `3bbbc39` на master.

State of play:
- ROADMAP: Phases 1-3 complete; Phases 4-7 не starting yet
- v1 requirements: 27/48 closed (RECON ×4 + всё Phase 2 + CRAWL-02). 20 остались в Phases 4-7
- Open Warnings: 5 non-blocking из `03-REVIEW.md` (WR-01..05) — отдельный `/gsd-code-review 3 --fix` перед milestone close
- Phase 7 ops-playbook backlog: 3 items (Finding #2 gate-shell под нагрузкой, Windows framebuffer headless, SMOKE_URLS[2] intermittent stale)

## Что делать прямо сейчас

**Phase 4 — Matcher + Match-Rate KPI.** Заявленный goal: strict-key matches между viled/goldapple snapshots per `run_id`, match-rate KPI логируется с первой недели, sanity-gate `match_count > P` блокирует delivery на низком количестве. Requirements: MATCH-01..04 (4 штуки).

`/gsd-discuss-phase 4` — собирает context через adaptive questioning. Phase 4 ещё не имеет планов; нужен полный цикл discuss→plan→execute.

## Альтернативы (если откладываем Phase 4)

- `/gsd-code-review 3 --fix` — закрыть WR-01..05 перед началом Phase 4. Не блокирует, но проще не оставлять долг
- `/gsd-secure-phase 3` — retroactive security review (SECURITY.md ещё не существует для Phase 3)
- `/gsd-extract-learnings 3` — extract decisions/lessons/patterns из Phase 3 артефактов (полезно перед забыванием контекста)

## Чего НЕ делать

- Не лезть в SMOKE_URLS[2] ротацию — один occurrence; ждём второй before rotation per gates.py:33-35
- Не лезть в Headless Camoufox Windows fix — production Linux VPS unaffected; QA can run headed
- Не deeplink на конкретный Phase 4 plan — discuss-phase должен сначала зафиксировать D-401..D-4XX decisions

## Connections

- [[2026-05-11 — Phase 3 UAT Test 6 closed empirically, cold-start race fix validated на live KZ-laptop]] — последняя сессия
- [[Cold-start `Loading` race на первой навигации после Camoufox boot]] — resolved-empirically
- ~~[[Текущие приоритеты — Phase 3 plan 09 shipped, ждём operator UAT]]~~ — superseded
- [[.planning/ROADMAP|ROADMAP.md]] — Phase 4 success criteria + dependencies
- [[Match-rate — KPI с первой недели]] — Phase 4 core decision
- [[Strict-key матчинг вместо fuzzy в v1]] — Phase 4 matching strategy
