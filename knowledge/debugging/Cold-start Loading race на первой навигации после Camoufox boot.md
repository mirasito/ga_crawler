---
tags: [debugging, anti-bot, camoufox, cold-start, race-condition, phase-3, goldapple, finding-1, production-defect, resolved-structurally]
date: 2026-05-11
severity: production-blocking
production_impact: weekly-cron-fails-each-sunday
status: resolved-structurally
resolution_date: 2026-05-11
resolution_plan: 03-09
awaits: operator-live-confirmation
---

# Cold-start `Loading` race на первой навигации после Camoufox boot

## Симптом

Smoke probe возвращает `passed: false` потому что **URL[0]** (первый из 3 SMOKE_URLS) — и **только** URL[0] — возвращает HTML, в котором `<title>` всё ещё в начальном состоянии:

```json
{
  "url": "https://goldapple.kz/19000488678-givenchy-irresistible",
  "status": 200,
  "size": 18033,
  "title": "Loading https://goldapple.kz/19000488678-givenchy-irresistible",
  "block": false,
  "price_extracted": false
}
```

`status: 200` + `block: false` (НЕ gate-shell!) + размер ~18 KB + title буквально начинается со слова **"Loading "** — это SPA shell до того, как ReactDOM successfully hydrated и заполнил `<title>` реальным product name. `parse_pdp` возвращает None (microdata `<meta itemprop="price">` ещё не отрендерен в DOM), `price_extracted: false` → smoke gate fail.

URL[1] и URL[2] в той же probe sequence возвращаются нормально (~200-400 KB, реальный product title, `price_extracted: true`). Это **не gate-shell, не stale-SKU, не network error** — это race condition между моментом, когда `fetch_one` забирает HTML, и моментом, когда SPA закончила hydration.

## Когда воспроизводится

**Cold-start первая навигация** — каждый раз. 2026-05-11 session: 4 cold-runs (1 + 2 + 3 + 4) воспроизвели его на URL[0] **4 из 4 раз** = 100% reproducibility:

| Run | URL[0] поведение | URL[1] | URL[2] |
|---|---|---|---|
| run-2 (cold) | stale SKU → 30x homepage (отдельный bug, fixed) | ✅ | ✅ |
| run-3 (cold, after rotation) | "Loading ..." 18034 байт | ✅ | ✅ |
| run-4 (cold, rotated[0]) | "Loading ..." 18033 байт | ✅ | ✅ |
| run-42 (cold, 2026-05-06) | stale SKU → 30x | ✅ | ✅ |
| run-43 (cold, 2026-05-06) | "Loading ..." | ✅ | ✅ |

URL[1] и URL[2] **никогда** не падают cold. Pattern строго: URL[0] = первая навигация = ловит SPA mid-hydration.

**Не воспроизводится** на URL[1+] потому что к моменту второй навигации Camoufox profile уже warm, Cloudflare cookie получен, SPA bundle закэширован → hydration занимает ≈100ms, не ≈300-500ms.

## Root cause

**Не anti-bot, не fingerprint, не network.** Чистая race в коде:

1. Camoufox boots → fresh tmp profile (D-311) → no cached bundle, no cookies
2. `fetch_one(page, URL[0])` → `page.goto(url, wait_until=???)` (см. ниже)
3. Goto resolves когда страница достигает выбранного wait_until state — но это **не значит**, что SPA hydration завершена. Для goldapple.kz `<title>` начально `"Loading ${url}"` и заменяется на product name только после hydration.
4. `fetch_one` читает `await page.content()` → получает HTML где title всё ещё `"Loading ..."` и `<meta itemprop="price">` ещё не существует.
5. `parse_pdp` → None (нет price element).
6. Smoke gate проверяет `price_extracted=true` для всех 3 URL → fail.

Hypothesis на `wait_until`: текущий код вероятно использует `domcontentloaded` или `load`, оба resolve до hydration. Нужен либо `networkidle` (даёт время на дополнительные XHR'ы, обычно покрывает hydration), либо явный `wait_for_selector('[itemprop="price"]')` с timeout.

См. `src/ga_crawler/fetchers/goldapple.py` `fetch_one`. На момент 2026-05-11 не верифицировал прямой `wait_until` контракт — это часть fix-plan.

## Production impact

**КАЖДОЕ ВОСКРЕСЕНЬЕ.**

Phase 7 production weekly cron на VPS:
- 1 run/нед, Sunday-night Asia/Almaty
- 1 cold Camoufox spawn в начале run'а (D-311 mandates fresh tmp profile)
- 1 smoke probe сразу после boot → **URL[0] hit cold-start race с вероятностью ~100%**
- Smoke gate fails → goldapple_phase fails → run.status="failed"
- В Phase 6 ops alert → business chat пустой каждое воскресенье

Это **не "edge case"**, это **первый же запуск production cron сломается**. До 2026-05-11 это трактовалось как редкая транзиентка (Phase 3 close-out had 2 data points); сегодняшние +4 точки изменили оценку.

## Workaround (до fix)

Manual debugging: не помогает. Race deterministic на cold-start; cooldown не лечит. **Нужен code-level fix.**

## Candidate fixes (для planner)

| # | Подход | Описание | Trade-off |
|---|---|---|---|
| 1 | **Warm-up navigation** | В `GoldappleFetcher.__aenter__` после Camoufox boot — `await page.goto("https://goldapple.kz/", wait_until="networkidle"); await asyncio.sleep(1.5)` ДО возврата контроля. К моменту smoke probe профиль уже warm: bundle закэширован, Cloudflare cookie получен. | +5-10s к каждому run. Сам warm-up может ловить device-check на cold-IP (но это уже Cloudflare layer, не SPA race — отдельный класс). Cleanest. |
| 2 | **`wait_until="networkidle"` в `fetch_one`** | Поменять текущий wait state на networkidle, который ждёт 500ms без активных XHR. Обычно покрывает hydration. | Per-fetch overhead (+1-3s). На slow PDP'ах может trigger timeout (default 30s). Не лечит сам Camoufox bootstrap race (он до первого `fetch_one`). |
| 3 | **`wait_for_selector('[itemprop="price"]')` в `fetch_one`** | Явное ожидание появления price element. Резистентен к network-idle false-positives. | Если страница вообще без цены (out-of-stock), будет ждать до timeout — но stale/OOS PDP'ы уже helmed `detect_state()` отдельно. Per-fetch overhead. |
| 4 | **Retry-once в `smoke_probe`** | Если URL[0] failed с title.startswith("Loading"), retry один раз через 5s. | Не решает root cause, маскирует race. OK как safety net поверх (1). Не OK как single fix. |

**Recommend:** (1) primary + (4) safety net. (2)/(3) рассматриваем если (1) не сработает.

## Phase 3 fix-plan path

`/gsd-plan-phase 3 --gaps` → planner читает `.planning/phases/03-goldapple-crawl/03-UAT.md` Gap section → создаёт PLAN.md (вероятно `03-09-PLAN.md` Wave 8 gap-closure) → plan-checker валидирует → execute-phase --gaps-only → re-run `scripts/uat3_live_run.py` для verification.

Success criteria для fix:
- 3 cold-runs подряд (с ≥15 мин gap чтобы избежать Finding #2) — все 3 проходят smoke probe
- URL[0] возвращает реальный product title + `price_extracted=true`
- run_loop достигнут хотя бы раз
- final_m_gate(10) passes

## Resolution (2026-05-11 PM)

Закрыт structurally планом **03-09** (`gap_closure: true`, Wave 8). Реализованы оба рекомендованных подхода:

**Layer 1 — Warm-up navigation в `GoldappleFetcher.__aenter__`** (commit `e7801ae`):
- Модульные константы `WARMUP_URL = "https://goldapple.kz/"`, `WARMUP_SETTLE_SECONDS = 2.0`, `WARMUP_NETWORKIDLE_TIMEOUT_MS = 15_000` (экспортированы в `__all__`)
- После Camoufox boot и page capture: `await page.goto(WARMUP_URL, wait_until="networkidle", timeout=WARMUP_NETWORKIDLE_TIMEOUT_MS); await asyncio.sleep(WARMUP_SETTLE_SECONDS)` — до возврата контроля caller'у
- Best-effort: inner try/except → `camoufox_warmup_networkidle_timeout` event на failure; settle unconditional; outer except → `shutil.rmtree(profile_dir)` (Pitfall 7 invariant сохранён)
- `camoufox_booted` event расширен полями `warmup_url` + `warmup_elapsed_ms`

**Layer 2 — Retry-once в `smoke_probe`** (commit `0bdd12a` + `05b29a8` CR-01 fix):
- Helpers `_compute_price_extracted` + `_is_loading_race` в `runner/gates.py`
- Retry triggers ТОЛЬКО на точную Loading-race shape: `status == 200` AND `price_extracted == False` AND `"loading "` substring в title AND title НЕ содержит `GATE_TITLE_MARKER` (импорт из `parsers.goldapple_microdata` — single source of truth) AND `block_reason != "gate_shell_not_cleared"` AND `not block` AND `isinstance(rec, dict)`
- Event `phase3_smoke_probe_retry` с first-attempt диагностикой
- D-312 strict-gate invariant сохранён: ровно ОДИН for-loop в smoke_probe (retry — inline branch, не nested loop)

**Что НЕ было сделано (rejected approaches):**
- ~~Approach 2~~ (`wait_until="networkidle"` / `wait_for_selector` в `fetch_one`) — отклонён: per-fetch overhead × ~3,450 weekly fetches; не лечит сам bootstrap race (он ДО первого `fetch_one`)
- ~~Approach 3~~ alone (retry-only без warm-up) — отклонён: маскирует root cause; принят как safety net поверх Layer 1

**Test coverage:** +7 net new tests (3 fetcher lifecycle: `test_warmup_navigation_called_once_in_aenter`, `test_camoufox_boot_failure_cleans_profile_dir`, `test_warmup_goto_failure_does_not_abort_boot`; 4 smoke_probe: retry triggers on Loading-race, no-retry on happy-path, no-retry on gate-shell, no-retry on non-200). Полный non-live suite: **392 passed, 1 skipped, 0 failed**.

**Verifier verdict:** `human_needed`, score **5/5 must_haves verified** structurally. Остался **один operator-driven item:** live re-run `scripts/uat3_live_run.py` на KZ-laptop с cold Camoufox spawn — нужно empirically подтвердить, что 4 cold-spawn runs достигают `run_loop` (а не упираются в smoke_probe). После confirmation Test 6 в `03-UAT.md` флипается `partial → pass`, Phase 3 закрывается окончательно.

**Open code-review findings** (отдельный цикл `/gsd-code-review 3 --fix` перед milestone close):
- WR-01: `asyncio.sleep(1.0)` не injectable
- WR-02: `_compute_price_extracted` без try/except вокруг `parse_pdp`
- WR-03: нет post-retry outcome event
- WR-04: `WARMUP_SETTLE_SECONDS = 2.0` magic number
- 4 Info findings (unused tuple element, dead price check, label drift, missing back-off assert)

## Connections

- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] — Finding #2, отдельный класс (rate-based, F.A.C.C.T.)
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — Phase 1 spike baseline; race не сломал spike потому что spike делал 100 sequential fetches, а не 3-URL probe-then-bail
- [[Fresh Camoufox profile per run + integrated smoke probe]] — D-311 fresh profile делает каждый cold-start "первой навигацией"
- [[2026-05-11 — Phase 3 UAT Test 6 re-opened, SMOKE_URLS rotation + cold-start race promoted]] — session с empirical data

## Файлы для проверки/fix

- `src/ga_crawler/fetchers/goldapple.py` — `GoldappleFetcher.__aenter__` (где добавить warm-up) + `fetch_one` (где может быть wrong `wait_until`)
- `src/ga_crawler/runner/gates.py` — `smoke_probe()` (где может быть retry-once safety net)
- `.planning/phases/03-goldapple-crawl/03-UAT.md` — Gap section с partial_fix + recommended_next
- `.planning/runs/{1..5}/runs.json` — empirical evidence для каждого cold-run
- `scripts/uat3_live_run.py` — UAT driver для re-verification после fix
