---
tags: [home, index]
date: 2026-05-06
---

# GA Crawler — Vault Index

Парсер ассортимента и цен **goldapple.kz** против **viled.kz** для коммерческой команды viled. Раз в неделю — Excel-отчёт в Telegram.

## Ориентируйся отсюда

- **[[Текущие приоритеты — Phase 3 execute]]** — что делать прямо сейчас (Phase 3 plan done, execute next)
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
- **Решения Phase 3 (живые):** [[Sitemap-only URL pool для goldapple, без brand-facet rendering]] · [[Slug-эвристика для viled→goldapple, не explicit YAML]] · [[Sanity-gate M=1000 static с auto-suggest, не auto-tune]] · [[Fresh Camoufox profile per run + integrated smoke probe]]
- **Решения (superseded):** ~~[[Tier 2 Patchright — стартовый tier для goldapple]]~~ → заменено Camoufox-экспериментом 2026-05-06 → финал [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]]
- **Решения (superseded):** ~~[[Спайковый fetch-OK = HTML 200 плюс product JSON-LD]]~~ → D-14 revised 2026-05-06: goldapple uses inline microdata (`itemprop="price"`), not JSON-LD Product schema
- **Паттерны:** [[JSON-LD первый, CSS резервный в парсерах]] · [[Per-SKU isolation вместо fail-on-first]] · [[Run-level sanity-gate перед доставкой]] · [[Volume как value-object с multipack-флагом]] · [[Тиры anti-bot эскалации]]
- **Debugging:** [[Goldapple показывает Cloudflare-челлендж — эскалация tier]] · [[Match-rate резко упал — проверь brand-alias таблицу]] · [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]

## Сессии

- [[2026-05-05 — инициализация проекта]]
- [[2026-05-05 — Phase 1 контекст зафиксирован]]
- [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]]
- [[2026-05-06 — Phase 1 closure через 01-08 Camoufox + 01-11 MEMO + 01-12 wrap-up]]
- [[2026-05-06 — Phase 3 контекст зафиксирован]]
- [[2026-05-06 — Phase 3 план создан, 7 plans across 7 waves]]

## Inbox

- [[inbox/README|inbox/]] — необработанное сюда
