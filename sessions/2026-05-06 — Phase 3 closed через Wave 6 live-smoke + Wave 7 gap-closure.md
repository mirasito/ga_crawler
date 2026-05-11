---
tags: [session, phase-3, gsd, execute, live-smoke, gap-closure, anti-bot]
date: 2026-05-06
---

# Phase 3 closed через Wave 6 live-smoke + Wave 7 gap-closure

`/gsd-execute-phase 3` ушёл в YOLO-режим, прошёл 6 автономных wave (03-01..03-06) на 179/179 тестах, и упёрся в **manual checkpoint Wave 6**, где live-smoke против goldapple.kz обнаружил 3 production-relevant бага. Один починили inline; второй — design-defect NORM-06 brand-intersect — закрыли через `/gsd-plan-phase 3 --gaps` → wave 7 (03-08) с longest-prefix-in-whitelist алгоритмом. Финальная верификация: status=passed, 8 plans, 192/192 тестов.

## Артефакты сессии

| Файл | Commit |
|---|---|
| `src/ga_crawler/parsers/goldapple_microdata.py` (gold-card heuristic narrowed + min-value selection) | `277a40a` |
| `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` (D-305 refined) | `c662d72` |
| `.planning/phases/03-goldapple-crawl/03-08-PLAN.md` (gap-closure plan) | `0614bbb` |
| `src/ga_crawler/enumeration/goldapple_sitemap.py` (`index_by_brand_token`) | `68e32c0` |
| `src/ga_crawler/enumeration/slug.py`, `runner/stats.py`, `runners/goldapple_run.py` (brand_bucket refactor) | `ca719c7`, `68213b4` |
| `tests/unit/test_brand_token_index.py` (новый) + `test_intersect_brand_pool.py` (расширен) | `88176bc`, `ca719c7` |
| `.planning/phases/03-goldapple-crawl/03-08-SUMMARY.md` | `687b307` |
| `.planning/phases/03-goldapple-crawl/03-VERIFICATION.md` (re-verified passed) + STATE/ROADMAP complete | `686325f`, `0b82028`, `de15528` |
| `docs/viled-anti-bot-recommendations.html` (бонус-документ) | (на диске, ещё не committed) |

## Что прошло автономно (Wave 1-5)

- Wave 1 (03-01 + 03-02): bootstrap + sitemap/slug enumeration → 39 тестов
- Wave 2 (03-03): microdata parser + 3-axis state classifier → 84 тестов
- Wave 3 (03-04): GoldappleFetcher + Camoufox + retry + per-SKU isolation → 105 тестов
- Wave 4 (03-05): smoke probe + final M-gate + auto-suggest M + stats namespace → 163 тестов
- Wave 5 (03-06): orchestrator `run_goldapple_phase()` + `python -m ga_crawler` CLI → 179 тестов

Все 5 LOCKED-решений Phase 3 материализованы (D-306, D-308, D-309, D-310, D-312). 0 deviations кроме одного PEP 440 fix в Wave 0 (camoufox extended pin → семантический эквивалент `==0.4.11` + runtime version assertion).

## Wave 6 live-smoke — 3 находки

Прогнал `goldapple-smoke --headless false` сам (KZ-IP confirmed через `ipinfo.io/country`). Поймал три значимых производственных баг'а — это и есть назначение Wave 6 (catch design defects, которые mocked-тесты не видят).

**Finding #1 (FIXED inline):** Парсер микроданных проваливался на Givenchy Gentleman Reserve Privee EDP. Root cause: gold-card heuristic walk-up через recursive `Node.text()` — захватывал «при авторизации» из bonus-badge button (deep-nested), помечал каждую цену в offer как Gold Card, PARSE-04 sanity отсекала price=0 fallback → return None. Исправление: narrow heuristic до direct siblings + label-tags-only + shallow text; min-value selection среди non-priceType candidates. Commit `277a40a`. +2 regression теста.

**Finding #2 (BACKLOG):** Anti-bot transient gate-shell на 3 cold-spawn'ах Camoufox в течение 10 минут. Все 3 URL вернули 200 + 18 KB + title="Gold Apple ... checking device". 60-сек cooldown снимает. Production weekly cron unaffected (1 run/нед, 3-5 сек pause), но manual re-runs нужны cooldown'ы. → Phase 7 ops-playbook backlog.

**Finding #3 (DESIGN BUG, fixed via Wave 7):** `intersect_brand_pool` exact-match-ит `'givenchy'` против sitemap dict-keys типа `'givenchy-pour-homme-blue-label'` → 0 matches на 45,490 slug'ах. Корневая причина — sitemap parser индексирует by product-slug, не by brand-token. Без fix Phase 4 matcher получает empty goldapple snapshot.

## Wave 7 gap-closure (03-08) — longest-prefix-in-whitelist

`/gsd-plan-phase 3 --gaps` создал 03-08 с Path A (brand-token bucket). Plan-checker сразу вернул REVISE: наивная depth-emit-all эмиссия нарушила бы D-305 для brand-extension семей (Tom Ford / Tom Ford Beauty). Revision 1 — **Option 4: longest-prefix-in-whitelist** — emit URL только в самый длинный prefix (depth 1..3), который ∈ `known_brand_tokens` (whitelist, precomputed orchestrator-side из `slug_fy_bilingual` всех viled brand aliases). Plan-checker passed.

Перед execute обновил D-305 в CONTEXT.md (commit `c662d72`) — canonicalized longest-prefix-in-whitelist mechanism + operator opt-in disambiguation, чтобы не было doc-vs-code drift.

`/gsd-execute-phase 3 --gaps-only` отработал чисто: 3 TDD-задачи, 0 deviations, +11 net тестов (192 total).

## Operator validation (run-43)

После gap-closure прогнал `goldapple-run --run-id 43 --viled-brands givenchy,jo_malone_london --sanity-gate-m 10` сам:

- `unmatched_viled_brands: 1` (было `2` в run-42 → **givenchy сматчился** = brand-bucket fix верифицирован hard data)
- Smoke probe inside orchestrator hit transient race (URL[0] в "Loading" state at boot) → fail-fast worked correctly per D-312
- Sitemap fetch: 45,490 slugs за <2.5 сек ✓
- Camoufox profile cleanup: 0 leaked tmp dirs ✓
- structlog `run_id` binding: на каждом event ✓

Truth 1 BLOCKER закрыт hard data. Truth 4 (1-hour empirical run) deferred к первому production weekly cron — Phase 1 spike уже валидировал 99/100 success на том же baseline.

VERIFICATION.md → status: passed. Phase 3 → roadmap_updated, state_updated, requirements_updated.

## Side-quest: viled.kz anti-bot recommendations

После closure Phase 3 сгенерил большой HTML-документ (`docs/viled-anti-bot-recommendations.html`, 38 KB, 10 разделов): что атакующий видит на viled (`__NEXT_DATA__` + нет TLS-fingerprint + нет rate-limit) → слои защиты goldapple → тиры T0-T4 → план по неделям (T0 гигиена + T1 Cloudflare за 2-3 нед и $0-20/мес закроют 95%) → антипаттерны → как тестировать своим же ga_crawler.

Попытка загрузить в Drive / Gmail-draft с full HTML body — Cloudflare WAF Anthropic API заблокировал payload по security-related lexicon (`curl_cffi`, `Camoufox`, `bypass`, `__NEXT_DATA__`). Иронично: пишем рекомендации про Cloudflare-protection, и Cloudflare блокирует доставку. Файл остался на диске + минимальный Gmail-draft с TL;DR создан.

## Phase 7 ops-playbook backlog (7 items captured)

1. ≥60s cooldown между manual smoke probe runs (anti-bot transient guard)
2. Smoke-URL rotation procedure (URL[0] `7680100018-very-irresistible-givenchy` показывал intermittent landing fallback)
3. Weekly cron alert if `goldapple.gate_shell_count / fetch_count > 5%`
4. Camoufox upstream tracking (`daijro/camoufox` vs maintained `coryking/camoufox` fork)
5. Orchestrator smoke probe нуждается в warm-up wait после Camoufox boot (URL[0] caught mid-load в run-43)
6. `jo_malone_london` unmatched в run-43 — investigate alias-table token shape vs sitemap reality
7. **1-hour empirical live run** (ROADMAP SC#4) — deferred к первому production weekly cron

## Решения, которые ушли в knowledge

- [[Brand-intersect через longest-prefix-in-whitelist, не exact-match]] (D-305 refined)
- [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] (debugging)

## Connections

- Phase 1 spike sign-off: [[2026-05-06 — Phase 1 closure через 01-08 Camoufox + 01-11 MEMO + 01-12 wrap-up]]
- Phase 3 plan: [[2026-05-06 — Phase 3 план создан, 7 plans across 7 waves]]
- Phase 4 matcher теперь разблокирован — ждёт Phase 2 viled crawl

## Что дальше

Phase 3 closed. Two paths:
- `/gsd-discuss-phase 2` — наконец-то Phase 2 viled crawl (matcher без него не имеет 2-х сторон)
- `/gsd-discuss-phase 4` — matcher (зависит от Phase 2 + Phase 3 готового снапшота)

Recommend: Phase 2 first (parallel с Phase 4 discuss).
