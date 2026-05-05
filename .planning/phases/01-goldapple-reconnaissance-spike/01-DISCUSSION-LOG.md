# Phase 1: Goldapple Reconnaissance Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 1-Goldapple Reconnaissance Spike
**Areas discussed:** Tier escalation & timebox, Spike location / IP geo, JSON-endpoint hunt, Success criteria

---

## Tier escalation & timebox

### Q1 — Стартовый tier

| Option | Description | Selected |
|--------|-------------|----------|
| Tier 1 → Tier 2 → +proxy (incremental) | По roadmap. Чистая наука: видим где ломается. Но если vanilla сразу блокируют — тратим время. | |
| Сразу Tier 2 (Patchright) | Drop-in Playwright. Первая реалистичная ставка. Tier 1 скипаем как банальный фейл. | ✓ |
| Tier 0 (сначала JSON-API) | Проверить JSON-эндпоинты до browser-tier'ов. | |

**User's choice:** Сразу Tier 2 (Patchright)

### Q2 — Timebox

| Option | Description | Selected |
|--------|-------------|----------|
| 1 рабочий день | Очень жёстко. Реалистично только если Patchright проходит с первого раза. | |
| 2-3 дня | Сбалансированно. День Tier 2, день Tier 3, полдня robots/memo. | |
| Неделя | Достаточно для Tier 4 (Camoufox/Scrapling) и бенчей прокси. | ✓ |

**User's choice:** Неделя

### Q3 — Stop-rule

| Option | Description | Selected |
|--------|-------------|----------|
| Быстрый фейл: 5 подряд блоков или captcha | 5 подряд 403/429 или первая Cloudflare interstitial → tier failed, эскалация. | ✓ |
| Медленный фейл: ≥60%/30 fetch'ей | 30 fetch'ей с jitter; >60% фейлят → tier failed. Точнее но дольше. | |
| По ситуации | Решаю в момент по характеру ответов. Гибко но невоспроизводимо. | |

**User's choice:** Быстрый фейл: 5 подряд блоков или captcha

### Q4 — Cookie/session reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent context (warm) | Один browser context, cookies живут, slow rate (3-5с). То же что в проде Phase 3. | ✓ |
| Fresh context (cold) | Новый context на каждый fetch. Worst-case, но риск измерять tier который не пойдёт в прод. | |
| Оба режима в memo | 30 cold + 100 warm. Дороже по времени. | |

**User's choice:** Persistent context (warm)

---

## Spike location / IP geo

### Q1 — Methodology

| Option | Description | Selected |
|--------|-------------|----------|
| Single-geo | Гоним только с одной IP. Быстрее. Риск: tier не воспроизведётся в проде. | |
| Multi-geo (laptop + 1 proxy) | 2 гео для сравнения. Дороже, но снимает неопределённость. | ✓ |

**User's choice:** Multi-geo (laptop + 1 proxy)

### Q2 — Baseline IP

| Option | Description | Selected |
|--------|-------------|----------|
| Laptop (KZ-IP) | Бесплатно, быстрый setup. KZ-IP выгодный для KZ-сайта. Не тот IP что в проде. | ✓ |
| Поднять Hetzner CX22 EU сразу | Спайк в боевых условиях. €4.50/мес + час setup. | |
| Residential proxy сразу (KZ или RU) | Самый «привилегированный» baseline. | |

**User's choice:** Laptop (KZ-IP)

### Q3 — Production IP geo

| Option | Description | Selected |
|--------|-------------|----------|
| Hetzner EU IP (по research/STACK) | €4.50/мес. Риск: goldapple бьёт EU-IP сильнее. | |
| Hetzner EU + KZ/RU residential proxy | Гибрид, рекомендация research/STACK для Tier 3. | |
| Решаем по результату спайка | Memo обязан выдать вердикт. | ✓ |

**User's choice:** Решаем по результату спайка

### Q4 — Proxy trial readiness

| Option | Description | Selected |
|--------|-------------|----------|
| Заранее — IPRoyal или Decodo | Регистрация одного провайдера до Tier 2-теста. Без потерь часов на onboarding. | ✓ |
| Реактивно (только после фейла Tier 2) | Экономим время если Tier 2 пройдёт. Риск: 0.5-1 день на KYC. | |
| Берём managed unblocker (ZenRows/Bright Data) | Прямой скачок на Tier 4. | |

**User's choice:** Заранее — IPRoyal или Decodo

---

## JSON-endpoint hunt

### Q1 — Активный hunt

| Option | Description | Selected |
|--------|-------------|----------|
| Да, явный deliverable спайка | 30-60 мин в DevTools / mitmproxy. Дешёвая проверка с высоким upside. | ✓ |
| Нет, строго browser-tier | По roadmap. JSON ищем в Phase 3. | |
| Только если Tier 2 фейлится | Сначала Patchright. JSON как fallback до Tier 3. | |

**User's choice:** Да, явный deliverable спайка

### Q2 — Если JSON найдён

| Option | Description | Selected |
|--------|-------------|----------|
| Новый сценарий: Tier 0 + curl_cffi | Memo рекомендует Tier 0 как primary. Patchright — резерв. Phase 3 упрощается. | ✓ |
| Bonus, но основной вердикт по browser-tier | JSON как backup. Прод всё равно на Patchright. | |
| Memo пишет оба пути | Verdict + альтернатива. Решение в начале Phase 3. | |

**User's choice:** Новый сценарий: Tier 0 + curl_cffi

### Q3 — Page-volume estimate (RECON-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Sitemap.xml + pagination meta | Часто открыт без anti-bot. Дёшево и точно. | ✓ |
| Полный обход 1-2 средних брендов | Точно, но ~30 мин + proxy budget. Опыт ближе к Phase 3. | |
| Оценка от 5-10 ручных сэмплов | Быстро, но грубо. | |

**User's choice:** Sitemap.xml + pagination meta

### Q4 — Brand selection

| Option | Description | Selected |
|--------|-------------|----------|
| Пересечение с viled top-10 | 3-5 брендов которые точно на viled. Бонус Phase 3. | ✓ |
| Крупные + мелкие (микс) | 1 «тяжёлый» + 1 «лёгкий» бренд. Разброс структур. | |
| Случайные 100 SKU из sitemap | Чистая статистика, но не видно brand-listing поведения. | |

**User's choice:** Пересечение с viled top-10

---

## Success criteria

### Q1 — Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| 100/100 строго | Самый жёсткий бар. Прод будет жить в этом сценарии. | |
| ≥95/100 с ретраями | Проходят 5xx-ретраи и timeout-ретраи. Реалистичный бар 2026. | ✓ |
| 100/100 с явным retry budget | Max 3 повтора на страницу + ≤1 captcha-recovery. | |

**User's choice:** ≥95/100 с ретраями

### Q2 — Определение «успешный fetch»

| Option | Description | Selected |
|--------|-------------|----------|
| HTML 200 + product JSON-LD найден | Прокси для «прод сможет парсить». | ✓ |
| HTML 200, без captcha-page | Менее строго. Парсинг не проверяется. | |
| current_price извлечён | End-to-end до цифры. Риск выйти за scope throwaway. | |

**User's choice:** HTML 200 + product JSON-LD найден

### Q3 — Cloudflare/DataDome challenge

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-resolved — проход | Если решился без человека и страница отдалась — считаем. Фиксируем в memo. | ✓ |
| Любой challenge — фейл | Tier «low-trust». Прод стремится к 0 challenges. | |
| Логируем но не фейлим | Challenge-rate как метрика. Решение по числу. | |

**User's choice:** Auto-resolved — проход

### Q4 — Где живут артефакты

| Option | Description | Selected |
|--------|-------------|----------|
| .planning/spikes/01-goldapple/ + Obsidian копия в knowledge/decisions/ | Auditable git + поиск в vault. | ✓ |
| Только .planning/spikes/ | Одно место. Меньше синхронизации. | |
| Только Obsidian | GSD-агенты ищут в .planning/. Симлинки. | |

**User's choice:** .planning/spikes/01-goldapple/ + Obsidian копия в knowledge/decisions/

---

## Claude's Discretion

- Формат decision memo: короткий template (problem / options tested / chosen tier+rationale / next-step impact / open risks).
- viled-проба: ≥10 fetch'ей + side-deliverable (timing, JSON-LD, pagination).
- Notebook vs script: `.py` script по умолчанию.
- KZ-legal review (research/SUMMARY рекомендация): self-review robots/ToS в спайке, юрист — TODO в Phase 7.

## Deferred Ideas

- Полный KZ-legal review (30 мин с юристом) → Phase 7 TODO.
- Camoufox / Scrapling Tier 4 тесты — только если Tier 2 + 3 оба фейлят.
- Бенчмарк IPRoyal vs Decodo vs Bright Data — в спайке только один провайдер.
- Захват goldapple HTML-fixtures для unit-тестов парсера → Phase 3.
- Match-rate baseline-симуляция → Phase 4.
