---
tags: [home, index]
date: 2026-05-13
---

# GA Crawler — Vault Index

Парсер ассортимента и цен **goldapple.kz** против **viled.kz** для коммерческой команды viled. Раз в неделю — Excel-отчёт в Telegram.

## Ориентируйся отсюда

- **[[Текущие приоритеты — v1.0 milestone shipped, operator deploy next]]** — что делать прямо сейчас (**v1.0 MILESTONE SHIPPED 2026-05-13** — 7/7 phases / 48/48 requirements / 803 tests / git tag `v1.0` / audit verdict `tech_debt` paperwork-only; security 7/7 + nyquist 11/11 closed; operator track: Hetzner CX22 deploy per `README.md §2` → `/gsd-verify-work 7` resume post-deploy → `/gsd-new-milestone` для v1.1)
- Phase 7 close trail: ~~[[Текущие приоритеты — Phase 7 done, v1 milestone close + operator deploy next]]~~ — superseded 2026-05-13 (milestone audit + archive + tag завершены в той же сессии; ROADMAP реорганизован milestone-grouped form; REQUIREMENTS архивирован; MILESTONES + RETROSPECTIVE созданы)
- Phase 7 plan trail: ~~[[Текущие приоритеты — Phase 7 planned, execute next]]~~ — superseded 2026-05-13 (Phase 7 executed end-to-end + code review fixes shipped; v1 code-ship complete)
- Phase 6 done trail: ~~[[Текущие приоритеты — Phase 6 done, Phase 7 next]]~~ — superseded 2026-05-12 (Phase 7 planned end-to-end в одной сессии; 5 plans готовы к execute)
- Phase 6 contexted trail: ~~[[Текущие приоритеты — Phase 6 contexted, plan next]]~~ — superseded 2026-05-12 (Phase 6 planned + executed end-to-end в одной сессии)
- Phase 5 done trail: ~~[[Текущие приоритеты — Phase 5 done, Phase 6 next]]~~ — superseded 2026-05-12 (Phase 6 contexted; D-601..D-616 locked; Phase 5 cascade D-514/D-515/D-405 honored verbatim)
- Phase 5 execute trail: ~~[[Текущие приоритеты — Phase 5 plan ready, execute next]]~~ — superseded 2026-05-12 (Phase 5 executed end-to-end; verifier 6/6 must-haves; 3 visual items в HUMAN-UAT)
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
- **Решения Phase 5 (живые, 2026-05-11):** **[[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]]** (D-514 — 7-key namespace + caption-without-regen invariant; cascades в Phase 6 — verified runtime 2026-05-12) · **[[REPORT-06 size guard — delivery-time concern, не reporter-time]]** (D-515 — xlsx ВСЕГДА пишется + `size_guard_passed=false` flag для Phase 6 DELIVER-03 gate — verified runtime 2026-05-12)
- **Решения Phase 6 (живые, 2026-05-12, runtime-verified):** **[[Delivery failure decoupled from runs.status — Telegram outage stays success]]** (D-605 — ARCHITECTURE «reporter independent of delivery» расширено: Telegram outage → status=success + delivery_status=undelivered + xlsx на диске; manual recovery via `deliver-run --run-id N`; Phase 7 two-tier Healthchecks) · **[[aiogram 3.27 + asyncio.run() sync wrapper — SDK для Telegram delivery]]** (D-601/D-602 — CLAUDE.md lock + mirror goldapple_run precedent в main_run.py:224) · **[[Asymmetric ENV handling — fail-loud для bot token, degrade для chat_id]]** (D-611 — pattern для secrets vs config endpoint distinction; decision rule «без ENV minimum viable operation возможен?» → нет=fail-loud, да=degrade)
- **Решения Phase 7 (живые, 2026-05-12..05-13, ship-stage):** **[[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]]** (D-701 — OOM/segfault/kill-9 coverage; Python in-process pings blind, bash wrapper after `set +e` always reaches cleanup) · **[[Phase 7 ships zero production Python — ops layer over frozen pipeline]]** (структурный canary `tests/test_phase07_structural_canaries.py` ловит любое изменение в `src/ga_crawler/*.py`; 5-way `runs.stats.*` + pyproject namespace invariants preserved) · **[[bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL]]** (D-709 — 9 invariants; exit code 4 reserved HC_PING_URL missing — explicit `if [[ -z ]]; exit 4` после CR-01 fix, не `${VAR:?}` который exit 1; exit 5 reserved flock-double-run-refused + HC `/fail` ping after WR-09 fix; shebang reconciled `#!/usr/bin/env bash` vs D-709 verbatim `#!/bin/bash`) · **[[README 10 sections RU primary EN code — single file для operator-is-developer team]]** (D-707 — single-file не split; H2 canary enforces order + Cyrillic) · **[[Code review ловит deploy-blocking defects невидимые plan-checker'у — uv PATH, useradd -m collision, sudo без sudoers]]** (boomerang lessons 2026-05-13 — 4 Critical defects найдены кодревьюером, source-lock канарейки + plan-checker структурно не могли поймать cross-environment interaction bugs)
- **Решения Phase 3 (живые, 2026-05-11):** **[[SMOKE_URLS rotation — операторская routine, не Phase 3 code defect]]** (первая ротация 2026-05-11; ops-procedure, не fix-plan материал)
- **Решения (superseded):** ~~[[Tier 2 Patchright — стартовый tier для goldapple]]~~ → заменено Camoufox-экспериментом 2026-05-06 → финал [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]]
- **Решения (superseded):** ~~[[Спайковый fetch-OK = HTML 200 плюс product JSON-LD]]~~ → D-14 revised 2026-05-06: goldapple uses inline microdata (`itemprop="price"`), not JSON-LD Product schema
- **Паттерны:** [[JSON-LD первый, CSS резервный в парсерах]] · [[Per-SKU isolation вместо fail-on-first]] · [[Run-level sanity-gate перед доставкой]] · [[Volume как value-object с multipack-флагом]] · [[Тиры anti-bot эскалации]] · **[[CLI stdout UTF-8 на Windows — sys.stdout.buffer.write вместо print]]** (new 2026-05-12 — Plan 05-05 Rule 1 fix для Cyrillic+emoji caption в CLI) · **[[tenacity wait_chain explicit backoff, не wait_exponential для дискретных N M L секунд]]** (new 2026-05-12 — Phase 6 RESEARCH caveat #2 promoted; rule «`wait_exponential` для true exponential, `wait_chain` для дискретных N/M/L»)
- **Debugging:** [[Goldapple показывает Cloudflare-челлендж — эскалация tier]] · [[Match-rate резко упал — проверь brand-alias таблицу]] · [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]] · [[Anti-bot transient gate-shell на быстрых Camoufox cold-spawns]] · **[[Cold-start `Loading` race на первой навигации после Camoufox boot]]** (resolved-empirically 2026-05-11T11:18Z — 4/4 cold-spawn runs reached run_loop) · **[[Pre-finalize-before-matcher в run_weekly — D-411 skip-on-running ловушка]]** (resolved 2026-05-11 Plan 04-05 — composition требует state-handshake перед matcher) · **[[Skip-path ReporterPhaseResult — size_guard_passed расходится между DB и memory]]** (open-for-Phase-6-consumer 2026-05-12 — WR-01; Phase 6 delivery-gate ОБЯЗАН читать БД через `get_stats`, не in-memory `MainRunResult`)

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
- [[2026-05-12 — Phase 5 executed — reporter shipped через 6 waves]]
- [[2026-05-12 — Phase 6 contexted — Telegram delivery decisions D-601..D-616]]
- [[2026-05-12 — Phase 6 planned + executed end-to-end, Telegram delivery shipped]]
- [[2026-05-12 — Phase 7 planned end-to-end, 5 plans across 4 waves ready для execute]]
- [[2026-05-13 — Phase 7 executed end-to-end + code review fixes, v1 milestone code-ship complete]]

## Inbox

- [[inbox/README|inbox/]] — необработанное сюда
