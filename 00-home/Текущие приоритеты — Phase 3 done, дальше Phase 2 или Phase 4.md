---
tags: [priorities, phase-3-done, next-up]
date: 2026-05-06
---

# Текущие приоритеты — Phase 3 done, дальше Phase 2 или Phase 4

## Где мы

Phase 3 (Goldapple Crawl) **closed 2026-05-06**: 8 plans, 8 waves, 192/192 unit+integration тестов, status=passed (operator-approved). Production-код краулера goldapple готов: sitemap fetcher, microdata parser, Camoufox fetcher, smoke gate, final M-gate, stats namespace, orchestrator + CLI.

Live-verified hard data (run-43): brand-bucket fix дал `unmatched_viled_brands: 1` (было 2 в run-42). Givenchy сматчился. Truth 1 BLOCKER из 03-VERIFICATION.md закрыт структурно.

## Phase 7 ops backlog (открыт)

7 items captured в `.planning/phases/03-goldapple-crawl/03-07-SUMMARY.md`. Главное:

1. Cooldown ≥60 сек между manual smoke probe runs (anti-bot transient)
2. Smoke-URL rotation (URL[0] показывал landing fallback)
3. Cron alert if gate_shell_count/fetch_count > 5%
4. Camoufox upstream tracking
5. Orchestrator smoke probe warm-up wait
6. `jo_malone_london` unmatched investigation
7. **1-hour empirical live run** — deferred к первому production weekly cron

## Что дальше

Два независимых пути; recommend Phase 2 first потому что Phase 4 matcher без него не имеет 2-х сторон:

```
/gsd-discuss-phase 2     # viled crawl + storage skeleton
/gsd-discuss-phase 4     # matcher (паралл. discuss возможен)
```

Phase 2 строит viled-сторону + DB схему + shared NORM/PARSE модули, на которые Phase 3 уже запрограммирован через `interfaces.py` Protocols. Phase 4 даст match-rate KPI (зависит и от Phase 2 viled snapshot, и от Phase 3 goldapple snapshot).

## Что НЕ делать сейчас

- **Не запускать `/gsd-execute-phase 3` снова** — closed.
- **Не править D-305 ещё раз** — refined в commit `c662d72`, locked в текущей формулировке (longest-prefix-in-whitelist). Семантика покрыта тестами + AST gate.
- **Не делать 1-hour live run прямо сейчас** — anti-bot transient cooldown не позволит без долгих пауз. Production cron в Phase 7 покроет это естественно.

## Side-quest напоминание

`docs/viled-anti-bot-recommendations.html` (38 KB) — bonus-документ для viled-команды, рекомендации по защите viled.kz на основе того, как мы сами обходим goldapple. Не committed, на диске. Если хочется — `git add docs/ && git commit`.

## Connections

- [[2026-05-06 — Phase 3 closed через Wave 6 live-smoke + Wave 7 gap-closure]] — последний session note
- [[Brand-intersect через longest-prefix-in-whitelist, не exact-match]] — главный design-decision Phase 3 closure
- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] — ops backlog для Phase 7
- [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/STATE|STATE.md]]
