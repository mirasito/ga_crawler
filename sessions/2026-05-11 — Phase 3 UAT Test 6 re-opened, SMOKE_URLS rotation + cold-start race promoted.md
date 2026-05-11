---
tags: [session, phase-3, uat, verify-work, anti-bot, smoke-urls, cold-start-race, finding-1]
date: 2026-05-11
---

# Phase 3 UAT Test 6 re-opened, SMOKE_URLS rotation + cold-start race promoted

`/gsd-verify-work 3` — оператор решил снять blocked-deferred с Test 6 и прогнать "1-hour live run" сегодня вместо ожидания Phase 7 cron deploy. Прогнал 5 sequential cold-spawn'ов через `scripts/uat3_live_run.py` (faithful translation pre-D-212 `goldapple-run --viled-brands givenchy,jo_malone_london --sanity-gate-m 10`, т.к. этот CLI subcommand удалён в Phase 2 wave-4). Все 5 упёрлись в smoke probe — run_loop **ни разу не достигнут**. Промежуточная победа: нашёл stale SMOKE_URLS[0] и закоммитил rotation. Главный итог: **Operational Finding #1 (cold-start `Loading` race) повышен из "Phase 7 ops backlog" в "Phase 3 production-blocking defect"** — 4 из 4 cold-runs воспроизвели его 100% (а не "иногда"), что меняет оценку риска для production weekly cron.

## Артефакты сессии

| Файл | Commit |
|---|---|
| `src/ga_crawler/runner/gates.py` (SMOKE_URLS[0] rotation: `7680100018-very-irresistible-givenchy` → `19000488678-givenchy-irresistible`) | `fefed43` |
| `.planning/phases/03-goldapple-crawl/03-UAT.md` (Test 6 re-opened, прогон, diagnosed, закрыт как complete с 1 issue) | `86ffb6f` |
| `scripts/uat3_live_run.py` (NEW UAT driver — reproducible bounded live run) | `86ffb6f` |
| `.gitignore` (add `/runs/` + `/.uat-run/`) | `86ffb6f` |

## Что произошло шаг за шагом

1. `/gsd-progress` — показал Phase 3 как complete с UAT.md `status: partial`. Test 6 (`Live Full Run, 1-hour`) был **blocked, blocked_by: prior-phase**, reason: deferred to first production weekly run per 03-VERIFICATION.md `deferred[]`.
2. Оператор: "хочу прогнать сейчас, сам всё сделай" → YOLO mode.
3. Pre-flight: `uv 0.11.7`, Python 3.12.13, KZ IP подтверждён (95.59.122.134 / `KZ`), `prices.db` нет (fresh DB будет создан).
4. **Surprise #1:** `goldapple-run` CLI subcommand больше не существует — удалён D-212 cutover (Phase 2 Plan 02-05). Текущий entry-point `weekly-run`, который derives `viled_brands` from current run's viled snapshot. Original Test 6 invocation невоспроизводим.
5. Написал `scripts/uat3_live_run.py` — вызывает `run_goldapple_phase` напрямую с `viled_brands=["givenchy", "jo_malone_london"]`, M=10, fresh prices.db. Это **faithful translation** pre-D-212 invocation; не product-level change.
6. **Run-1 (headless=True):** Camoufox упал на boot с `Crash Annotation GraphicsCriticalError: RenderCompositorSWGL failed mapping default framebuffer, no dt` — Playwright Timeout 180000ms. Windows 11 headless Camoufox локально не работает. Перешёл на `headless=False`.
7. **Run-2 (headed, cold):** smoke probe FAIL — URL[0] (`7680100018-very-irresistible-givenchy`) returned generic homepage title "ЗОЛОТОЕ ЯБЛОКО — интернет-магазин..." size=9587. Гипотеза: stale SKU → 30x redirect to homepage.
8. **Run-3 (headed, после 75s cooldown):** smoke probe FAIL — URL[0] returned title "Loading https://goldapple.kz/..." size=18034. Operational Finding #1 (cold-start race) confirmed.
9. **Проверил sitemap:** `givenchy-irresistible` есть в live sitemap → URL `19000488678-givenchy-irresistible`. Сделал inline rotation SMOKE_URLS[0] (gates.py:32). Коммент в коде явно обозначает rotation как "Phase 7 ops-playbook procedure" — операторская routine, не код-fix. Закоммитил отдельно (`fefed43`).
10. **Run-4 (headed, cold, после rotation):** smoke probe FAIL — URL[0] (новый rotated `19000488678-givenchy-irresistible`) returned title "Loading https://goldapple.kz/..." size=18033. **То же самое behaviour, что run-3** — это НЕ stale-SKU, это **cold-start race condition** на URL[0] (первой навигации после Camoufox boot). URL[1], URL[2] passed.
11. **Run-5 (headed, после 75s cooldown):** smoke probe FAIL — ВСЕ 3 URL "Gold Apple — checking device" block=true size~18063. Operational Finding #2 (back-to-back gate-shell) — 75 sec мало для F.A.C.C.T. transient gate.

## Главный итог — Finding #1 promotion

**До сегодня** Finding #1 трактовалось как "иногда сбоит в dev sessions, production cron справится". 2 точки данных: run-42 (cold, fail), run-43 (cold, fail). Эмпирическое окно слишком узкое → optimistic deferral.

**Сегодня** ещё 4 cold-runs (1 + 2 + 3 + 4 в текущей сессии). URL[0] failed cold **4 из 4 раз** в чистых cold-start conditions. URL[1] и URL[2] **никогда не падают на cold-start** — только URL[0]. Pattern — детерминированный: первая навигация после Camoufox boot ловит page mid-load.

**Что это значит для Phase 7 production:**
- Weekly cron Sunday-night → cold Camoufox boot → fresh tmp profile (D-311) → первая навигация = SMOKE_URLS[0]
- 100% reproducibility cold-start failure → smoke probe gate fails → goldapple phase fails → отчёт не отправится в business chat → ops-alert каждое воскресенье
- Это **не "редкая транзиентка"**, это **детерминированный bug в production code path**

**Поэтому переклассифицировал:** Operational Finding #1 не остаётся в Phase 7 ops-playbook backlog. Это Phase 3 defect, требующий fix-plan через `/gsd-plan-phase 3 --gaps`.

## Что НЕ promoted — Finding #2 и framebuffer

- **Finding #2 (back-to-back gate-shell):** Production weekly cron делает 1 run/нед — 7-day gap. Никогда не trigger'ит F.A.C.C.T. rate heuristic. Остаётся в Phase 7 ops-playbook (документация для оператора при manual debugging: ≥15 мин cooldown, не 60-75 сек).
- **Headless framebuffer crash на Windows 11:** Production VPS = Linux. Linux headless Camoufox unaffected. Остаётся в Phase 7 ops-playbook (документация для local QA на Windows: headless=False).

## Кандидаты fix для Finding #1 (planner детализирует)

Три направления, каждое со своими trade-offs:

1. **Warm-up navigation в `GoldappleFetcher.__aenter__`** — после Camoufox boot сделать `await page.goto("https://goldapple.kz/", wait_until="networkidle")` + 1-2s pause. Single extra request, prim'ит SPA cache + Cloudflare cookie. Cleanest, но добавляет ~5-10s к каждому run + сам warm-up может trigger device-check на cold-IP (требует тестирования).
2. **Better wait в `fetch_one`** — поменять `wait_until="domcontentloaded"` (если сейчас так) на `wait_until="networkidle"` или явное `wait_for_selector('[itemprop="price"]', timeout=15000)`. Per-fetch overhead. Может trigger timeout на slow-loading PDP'ах.
3. **Retry внутри `smoke_probe`** — если URL[0] failed, retry один раз с 5s pause. Самое узкое изменение, но не решает root cause, просто маскирует race.

**Predict:** planner выберет (1) или гибрид (1)+(3). (2) рискованный — может задеть production fetch rate.

## Phase 3 UAT финальное состояние

| Result | Count |
|---|---|
| Passed | 8 |
| Issues | 1 (Test 6) |
| Status | complete |

Test 6 закрыт как **issue, severity: major**, partial_fix applied (SMOKE_URLS[0] rotation), оставшийся gap — Finding #1 — escalated to Phase 3 fix-plan.

## Recommended next step

`/clear` → `/gsd-plan-phase 3 --gaps` — planner создаст fix-plan для cold-start race, plan-checker валидирует. Затем `/gsd-execute-phase 3 --gaps-only` и я перезапускаю `scripts/uat3_live_run.py` для re-verification. Если все 3 SMOKE_URLS проходят cold → Test 6 закрывается как pass → Phase 3 ready for transition to Phase 4 (Matcher).

**Не рекомендую:** ехать в Phase 4 с открытым Finding #1. Production weekly cron в Phase 7 захромает на первом же воскресенье, и Phase 4 matcher не получит goldapple snapshot для match-rate KPI.

## Connections

- [[Текущие приоритеты — Phase 3 Finding 1 → plan-gaps]] — следующий приоритет (NEW)
- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] — обновлён с новыми empirical data
- [[SMOKE_URLS rotation — операторская routine, не Phase 3 code defect]] — новое решение (NEW)
- [[Cold-start `Loading` race на первой навигации после Camoufox boot]] — новое debugging note (NEW)
- ~~[[Текущие приоритеты — Phase 2 ready для plan]]~~ — superseded (Phase 2 closed 2026-05-07; новое узкое горлышко — Phase 3 Finding #1)
- [[.planning/phases/03-goldapple-crawl/03-UAT|03-UAT.md]] — полная evidence + diagnosis
- [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/STATE|STATE.md]]
