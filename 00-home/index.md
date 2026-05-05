---
tags: [home, index]
date: 2026-05-05
---

# GA Crawler — Vault Index

Парсер ассортимента и цен **goldapple.kz** против **viled.kz** для коммерческой команды viled. Раз в неделю — Excel-отчёт в Telegram.

## Ориентируйся отсюда

- **[[Текущие приоритеты — Phase 1 спайк]]** — что делать прямо сейчас
- Ядро решений: [[.planning/PROJECT|PROJECT.md]] · [[.planning/ROADMAP|ROADMAP.md]] · [[.planning/REQUIREMENTS|REQUIREMENTS.md]]

## Атлас (карта проекта)

- [[Архитектура — модульный монолит на pipe-and-filter]]
- [[Стек — Python 3.12 + curl_cffi + Playwright + SQLite]]
- [[БД — append-only snapshots с run_id]]
- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]]

## Knowledge

- **Интеграции:** [[goldapple.kz — источник цен конкурента]] · [[viled.kz — собственный каталог и источник пересекающихся брендов]] · [[Telegram Bot API — канал доставки отчёта]] · [[Healthchecks.io — dead-mans-switch для weekly cron]] · [[Residential proxies — нужны только для goldapple]]
- **Решения:** [[Парсим viled целиком, goldapple только по пересекающимся брендам]] · [[Strict-key матчинг вместо fuzzy в v1]] · [[Хранить полную историю снапшотов, не только текущий срез]] · [[Brand-alias YAML — это v1 deliverable, не v2]] · [[Match-rate — KPI с первой недели]] · [[Stock state — enum в схеме, bool в отчёте]]
- **Паттерны:** [[JSON-LD первый, CSS резервный в парсерах]] · [[Per-SKU isolation вместо fail-on-first]] · [[Run-level sanity-gate перед доставкой]] · [[Volume как value-object с multipack-флагом]] · [[Тиры anti-bot эскалации]]
- **Debugging:** [[Goldapple показывает Cloudflare-челлендж — эскалация tier]] · [[Match-rate резко упал — проверь brand-alias таблицу]] · [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]

## Сессии

- [[2026-05-05 — инициализация проекта]]

## Inbox

- [[inbox/README|inbox/]] — необработанное сюда
