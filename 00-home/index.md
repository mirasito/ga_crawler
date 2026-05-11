---
tags: [home, index]
date: 2026-05-11
---

# GA Crawler — Vault Index

Парсер ассортимента и цен **goldapple.kz** против **viled.kz** для коммерческой команды viled. Раз в неделю — Excel-отчёт в Telegram.

## Ориентируйся отсюда

- **[[Текущие приоритеты — Phase 5 plan ready, execute next]]** — что делать прямо сейчас (Phase 5 discuss + plan завершены 2026-05-11; 16 решений D-501..D-516, 6 plans across 6 waves, plan-checker ✅ PLANS PASS; готов к `/gsd-execute-phase 5`)
- Phase 5 discuss trail: ~~[[Текущие приоритеты — Phase 5 reporter ready для discuss]]~~ — superseded 2026-05-11 (Phase 5 contexted + planned в одном сеансе)
- Phase 4 execute trail: ~~[[Текущие приоритеты — Phase 4 plan ready, execute next]]~~ — superseded 2026-05-11 evening (Phase 4 executed end-to-end, verifier PASS 11/11)
- Phase 3 transition: ~~[[Текущие приоритеты — Phase 3 closed окончательно, дальше Phase 4]]~~ — superseded 2026-05-11 PM (Phase 3 security re-audited, Phase 4 contexted + planned)
- Phase 3 plan-09 UAT trail: ~~[[Текущие приоритеты — Phase 3 plan 09 shipped, ждём operator UAT]]~~ — superseded 2026-05-11T11:18Z (operator UAT прошёл: 4/4 cold-spawn runs reached run_loop)
- Phase 3 plan-gaps trail: ~~[[Текущие приоритеты — Phase 3 Finding 1 → plan-gaps]]~~ — superseded 2026-05-11 PM (plan-gaps выполнен; теперь ждём operator UAT)
- Phase 2 trail: ~~[[Текущие приоритеты — Phase 2 ready для plan]]~~ — superseded 2026-05-11 (Phase 2 closed 2026-05-07; узкое горлышко переместилось на Phase 3 Finding #1)
- Phase 2/4 fork point: ~~[[Текущие приоритеты — Phase 3 done, дальше Phase 2 или Phase 4]]~~ — superseded 2026-05-07 (выбран Phase 2 path)
- Phase 3 execute trail: ~~[[Текущие приоритеты — Phase 3 execute]]~~ — closed 2026-05-06 (8 plans, status passed)
- Phase 3 plan trail: ~~[[Текущие приоритеты — Phase 3 план]]~~ — superseded 2026-05-06 (план готов)
- Phase 1 audit: ~~[[Текущие приоритеты — Phase 1 спайк]]~~ — closed 2026-05-06
- Ядро решений: [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/REQUIREMENTS|REQUIREMENTS.md]]

## Атлас (карта проекта)

- [[Архитектура — модульный монолит на pipe-and-filter]]
- [[Стек — Python 3.12 + curl_cffi + Playwright + SQLite]]
- [[БД — append-only snapshots с run_id]]
- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]]

## Knowledge

- **Интеграции:** [[goldapple.kz — источник цен конкурента]] · [[viled.kz — собственный каталог и источник пересекающихся брендов]] · [[Telegram Bot API — канал доставки отчёта]] · [[Healthchecks.io — dead-mans-switch для weekly cron]] · [[Residential proxies — нужны только для goldapple]]
- **Решения (живые):** [[Парсим viled целиком, goldapple только по пересекающимся брендам]] · [[Strict-key матчинг вместо fuzzy в v1]] · [[Хранить полную историю снапшотов, не только текущий срез]] · [[Brand-alias YAML — это v1 deliverable, не v2]] · [[Match-rate — KPI с первой недели]] · [[Stock state — enum в схеме, bool в отчёте]] · [[Camoufox а не Patchright — engine для goldapple]] · [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] · [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] · [[Multi-geo измерение в спайке — laptop KZ плюс один proxy]] · [[JSON-endpoint hunt — явный deliverable Phase 1]] · [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] (sign-off Phase 1)
- **Решения Phase 3 (живые):** [[Sitemap-only URL pool для goldapple, без brand-facet rendering]] · [[Slug-эвристика для viled→goldapple, не explicit YAML]] · [[Sanity-gate M=1000 static с auto-suggest, не auto-tune]] · [[Fresh Camoufox profile per run + integrated smoke probe]] · **[[Brand-intersect через longest-prefix-in-whitelist, не exact-match]]** (D-305 refined Wave 7)
- **Решения Phase 2 (живые):** **[[viled scope сужен до beauty+парфюм каталога catalog 1310]]** (D-223 mid-flight 2026-05-07; cascading на enumeration + N-gate)
- **Решения Phase 4 (живые, 2026-05-11):** **[[Matches table — денормализованная, N→1 keep-all]]** (D-401/-403) · **[[Sanity-gate P — третий экземпляр паттерна auto-suggest 0.7×median]]** (D-406/-407 — третий retailer-domain экземпляр D-201/D-308 паттерна) · [[Match-rate — KPI с первой недели]] обновлено: формула frozen via D-405 source-locked canary
- **Решения Phase 5 (живые, 2026-05-11):** **[[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]]** (D-514 — 7-key namespace + caption-without-regen invariant; cascades в Phase 6) · **[[REPORT-06 size guard — delivery-time concern, не reporter-time]]** (D-515 — xlsx ВСЕГДА пишется + `size_guard_passed=false` flag для Phase 6 DELIVER-03 gate)
- **Решения Phase 3 (живые, 2026-05-11):** **[[SMOKE_URLS rotation — операторская routine, не Phase 3 code defect]]** (первая ротация 2026-05-11; ops-procedure, не fix-plan материал)
- **Решения (superseded):** ~~[[Tier 2 Patchright — стартовый tier для goldapple]]~~ → заменено Camoufox-экспериментом 2026-05-06 → финал [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]]
- **Решения (superseded):** ~~[[Спайковый fetch-OK = HTML 200 плюс product JSON-LD]]~~ → D-14 revised 2026-05-06: goldapple uses inline microdata (`itemprop="price"`), not JSON-LD Product schema
- **Паттерны:** [[JSON-LD первый, CSS резервный в парсерах]] · [[Per-SKU isolation вместо fail-on-first]] · [[Run-level sanity-gate перед доставкой]] · [[Volume как value-object с multipack-флагом]] · [[Тиры anti-bot эскалации]]
- **Debugging:** [[Goldapple показывает Cloudflare-челлендж — эскалация tier]] · [[Match-rate резко упал — проверь brand-alias таблицу]] · [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]] · [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] · **[[Cold-start `Loading` race на первой навигации после Camoufox boot]]** (resolved-empirically 2026-05-11T11:18Z — 4/4 cold-spawn runs reached run_loop) · **[[Pre-finalize-before-matcher в run_weekly — D-411 skip-on-running ловушка]]** (resolved 2026-05-11 Plan 04-05 — composition требует state-handshake перед matcher)

## Сессии

- [[2026-05-05 — инициализация проекта]]
- [[2026-05-05 — Phase 1 контекст зафиксирован]]
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]]
- [[2026-05-06 — Phase 1 closure через 01-08 Camoufox + 01-11 MEMO + 01-12 wrap-up]]
- [[2026-05-06 — Phase 3 контекст зафиксирован]]
- [[2026-05-06 — Phase 3 план создан, 7 plans across 7 waves]]
- [[2026-05-06 — Phase 3 closed через Wave 6 live-smoke + Wave 7 gap-closure]]
- [[2026-05-07 — Phase 3 audit-stack закрыт + Phase 2 контекст с scope-narrowing]]
- [[2026-05-11 — Phase 3 UAT Test 6 re-opened, SMOKE_URLS rotation + cold-start race promoted]]
- [[2026-05-11 — Phase 3 plan 03-09 ships, cold-start race закрыт structurally]]
- [[2026-05-11 — Phase 3 UAT Test 6 closed empirically, cold-start race fix validated на live KZ-laptop]]
- [[2026-05-11 — Phase 3 security re-audit + Phase 4 discuss и plan готовы]]
- [[2026-05-11 — Phase 4 executed — matcher + KPI shipped через 5 waves]]
- [[2026-05-11 — Phase 5 discuss + plan ready, 6 plans across 6 waves для execute]]

## Inbox

- [[inbox/README|inbox/]] — необработанное сюда
