---
tags: [priorities, phase-3, finding-1, plan-gaps, cold-start-race, next-up]
date: 2026-05-11
---

# Текущие приоритеты — Phase 3 Finding 1 → plan-gaps

## Где мы

**Phase 3** previously closed 2026-05-06 с UAT.md `status: partial` — Test 6 (1-hour live run) blocked-deferred к first production weekly cron. **Phase 2** closed 2026-05-07 (6/6 plans). Сегодня (2026-05-11) оператор открыл Test 6 досрочно через `/gsd-verify-work 3` — 5 sequential cold-spawn'ов через `scripts/uat3_live_run.py`, ни один не дошёл до run_loop.

**Главный результат:** Operational Finding #1 (cold-start `Loading` race на URL[0]) **повышен из ops-backlog в Phase 3 defect**. 4 cold-runs воспроизвели его 100% (а не "иногда") — это детерминированный bug, который ударит по production weekly cron каждое воскресенье.

UAT.md закрыт: 8 passed + 1 issue (Test 6, severity major). Partial fix применён (SMOKE_URLS[0] rotation, commit `fefed43`). Оставшийся gap — cold-start race — переходит в fix-plan.

## Что дальше

```
/clear
/gsd-plan-phase 3 --gaps
```

Planner прочитает `.planning/phases/03-goldapple-crawl/03-UAT.md` Gaps section и предложит PLAN.md для cold-start race fix. Затем plan-checker валидирует. **После approve:** `/gsd-execute-phase 3 --gaps-only` и я перезапускаю `scripts/uat3_live_run.py` для re-verification.

### Три направления fix (planner выберет/комбинирует)

| # | Подход | Trade-off |
|---|---|---|
| 1 | Warm-up navigation в `GoldappleFetcher.__aenter__` (goto homepage + networkidle + 1-2s) | Cleanest. +5-10s к каждому run. Warm-up сам может trigger device-check. |
| 2 | `wait_until="networkidle"` или `wait_for_selector('[itemprop="price"]')` в `fetch_one` | Per-fetch overhead. Риск timeout на slow PDP'ах. Не решает race на самой первой навигации (т.к. это эффект Camoufox bootstrap, не fetch_one). |
| 3 | Retry-once в `smoke_probe` если URL[0] failed | Самое узкое изменение. Маскирует, не решает root cause. Acceptable как fallback layer поверх (1). |

**Прогноз:** комбинация (1) для cleanest fix + (3) как safety net. (2) не трогаем без причины — может задеть production fetch rate.

## Что НЕ делать сейчас

- **Не двигаться к Phase 4** — открытый Finding #1 = production weekly cron в Phase 7 захромает каждое воскресенье → Phase 4 matcher не получит goldapple snapshot → match-rate KPI = 0 от недели 1. Сначала fix.
- **Не делать ещё один live run в этой сессии** — F.A.C.C.T. transient gate (Finding #2) уже активирован run-5; нужен ≥15 мин cooldown. Перезапуск после execute-phase будет уже cold.
- **Не запускать full auto-pipeline** (`/gsd-verify-work` → diagnose-issues spawn parallel debug agents → planner → checker) — root cause уже задокументирован в 03-UAT.md Gaps; повторная диагностика дублирует работу. Прямо в `/gsd-plan-phase 3 --gaps`.
- **Не убирать `headless=False`** в `scripts/uat3_live_run.py` — на Windows 11 локально Camoufox headless всё равно крашится (framebuffer); production VPS Linux не страдает.

## Open action items (что должно попасть в other docs после plan/execute)

- **`.planning/ROADMAP.md` Phase 3 row** — изменить с "Complete" на "Complete (re-opened 2026-05-11 для Finding #1 fix; closes Test 6)" пока fix не выполнен; вернуть в Complete после re-verification.
- **`.planning/STATE.md` accumulated decisions** — добавить D-3XX для cold-start fix-design (warm-up vs wait_until vs retry trade-offs).
- **Phase 7 ops-playbook backlog** — обновить: Finding #1 RESOLVED in Phase 3 fix; Finding #2 (back-to-back) и framebuffer-on-Windows остаются.

## Side-quest напоминание

- `docs/viled-anti-bot-recommendations.html` (38 KB) — всё ещё не committed.
- 4 untracked Obsidian-заметки от 2026-05-06/07 (sessions + knowledge + 00-home) — стоит закоммитить (`git add 00-home/ sessions/ knowledge/`) перед началом fix-plan.

## Connections

- [[2026-05-11 — Phase 3 UAT Test 6 re-opened, SMOKE_URLS rotation + cold-start race promoted]] — последний session note
- [[Cold-start `Loading` race на первой навигации после Camoufox boot]] — root cause + кандидаты fix (NEW)
- [[SMOKE_URLS rotation — операторская routine, не Phase 3 code defect]] — почему rotation коммитится отдельно (NEW)
- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] — обновлён с новыми empirical data (4 reproducible cold-runs)
- ~~[[Текущие приоритеты — Phase 2 ready для plan]]~~ — superseded (Phase 2 closed; узкое горлышко переместилось)
- [[.planning/phases/03-goldapple-crawl/03-UAT|03-UAT.md]] · [[scripts/uat3_live_run|scripts/uat3_live_run.py]]
- [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/STATE|STATE.md]]
