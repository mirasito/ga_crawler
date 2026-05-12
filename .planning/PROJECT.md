# GA Crawler — Competitive Pricing Intelligence

## What This Is

Еженедельный краулер ассортимента и цен goldapple.kz vs viled.kz для коммерческой команды viled.kz. Парсит каталог обоих ритейлеров, сопоставляет товары по бренду + названию + объёму, считает дельту цен и присылает в Telegram сводку с приложенным Excel-отчётом раз в неделю.

## Core Value

Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- [x] Полный парсинг beauty+парфюмерия каталога viled.kz (men/catalog/1310 + women/catalog/1310) — Validated in Phase 2 (PARSE-01..06, CRAWL-01,03,04,06)
- [x] Парсинг goldapple.kz, ограниченный брендами, которые есть на viled.kz — Validated in Phase 3 (CRAWL-02 brand-intersect bucket)
- [x] Нормализация и сопоставление товаров по ключу `brand + название + объём` — Validated in Phase 2 (NORM-01..06) + Phase 4 (MATCH-01..04, D-401 denormalized matches schema)
- [x] База данных с историей всех еженедельных срезов (для трендов и дельт) — Validated in Phase 2 (DATA-01..06, SQLite + v_current_snapshots view)
- [x] Сводный отчёт: размер ассортимента у обоих, пересечения, дельты цен по совпавшим SKU — Validated in Phase 5 (REPORT-01..06, xlsxwriter + match-rate KPI)
- [x] Доставка отчёта в Telegram (текстовая сводка + Excel/CSV вложением) — Validated in Phase 6 (DELIVER-01..05, aiogram 3.27 + business/ops chat split)
- [x] Еженедельный автозапуск по расписанию (cron, ночь воскресенья → отчёт в понедельник) — Validated in Phase 7 (SCHED-01..05, cron + bin/weekly-run.sh + Healthchecks.io dead-man's-switch)
- [x] Устойчивость к anti-bot-защите (proxy/headless-стратегия для goldapple.kz) — Validated in Phase 1 (Camoufox direct, no proxy needed per spike MEMO)
- [x] Логи запуска и ошибок (видно, когда парсер упал, что не спарсилось) — Validated across Phases 2-7 (structlog JSON + Phase 7 datestamped log files + logrotate)

### Active

<!-- Current scope. Building toward these. -->

(None — v1 milestone code-ship complete 2026-05-13; operator deploy on Hetzner CX22 next)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Цены под Gold Card / залогиненные цены — рискованно (риск блокировки аккаунта), сложнее, для сопоставления с viled.kz нужна публичная цена
- Полный парсинг goldapple.kz (всех брендов) — нет смысла, нас интересуют только пересекающиеся бренды; экономит трафик и время
- Real-time / ежедневный мониторинг — еженедельной частоты достаточно для коммерческих решений
- Алерты на скидки/изменения цен в реальном времени — всё в недельном отчёте
- Веб-дашборд / UI — не требуется на v1, отчёт в Telegram + Excel закрывает потребность
- Парсинг прочих маркетплейсов / других конкурентов — фокус на goldapple.kz vs viled.kz
- Картинки и описания товаров — не нужны для ценового сравнения
- Машинное обучение для матчинга / fuzzy-сопоставление — на v1 строгий ключ brand+name+volume; fuzzy откладываем до v2, если покрытие окажется низким

## Context

- **Домен:** beauty/cosmetics retail в Казахстане. goldapple.kz — крупный российский ритейлер косметики, заходящий в KZ; viled.kz — местный ритейлер
- **Размер сайтов:** goldapple.kz ожидаемо десятки тысяч SKU; viled.kz существенно меньше. Парсим viled.kz целиком, потом на goldapple ищем только нужные бренды
- **Anti-bot:** goldapple.kz почти наверняка под Cloudflare/DataDome. Нужны headless-браузер (Playwright), прокси, паузы, имитация реального юзера. viled.kz — скорее всего проще
- **Аудитория отчёта:** коммерческая команда viled.kz — закупщики и pricing-менеджеры. Им важна возможность фильтровать в Excel, видеть дельты, понимать акции
- **Цели использования отчёта:**
  1. Корректировка цен viled.kz относительно goldapple.kz
  2. Поиск ассортиментных разрывов (что есть у goldapple и нет у viled)
  3. Мониторинг промо-акций конкурента
- **Запуск:** еженедельный, в ночь воскресенья → отчёт утром в понедельник

## Constraints

- **Tech stack**: Python — стандарт для веб-скрейпинга, богатая экосистема (Playwright, Scrapy, httpx, pandas), легко хостить
- **Frequency**: Раз в неделю — достаточно для бизнес-решений, минимум нагрузки на целевые сайты, минимум риска блокировки
- **Pricing source**: Только публичная цена без логина — справедливое сравнение с viled.kz и нет риска блокировки аккаунта
- **Matching strictness**: Точное совпадение нормализованного ключа `brand + название + объём` (lowercase, без знаков пунктуации) — на v1; fuzzy-матчинг откладывается до v2
- **Data persistence**: Полная история всех срезов в БД (SQLite на v1, миграция на Postgres если понадобится) — для трендов и дельт
- **Delivery channel**: Telegram (бот) + Excel-вложение — выбор пользователя
- **Anti-bot tolerance**: Готовы платить за прокси и headless-браузер, если без этого goldapple не парсится. Решение — после research-фазы
- **Hosting**: Решение принимается в research-фазе на основе требований к прокси и времени запуска (ожидаемо VPS + cron)

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Парсим viled.kz целиком, на goldapple — только пересекающиеся бренды | Goldapple слишком большой, нас интересуют только сопоставимые позиции; экономия трафика и снижение риска блокировки | — Pending |
| Стратегия матчинга: brand + name + volume (нормализованный) | Проще, без ML; покрытие достаточно для коммерческого использования; fuzzy — отдельная задача в v2 если нужно | — Pending |
| История всех срезов в БД, не только последний | Команде нужны тренды цен и динамика промо-акций | — Pending |
| Telegram + Excel как канал доставки | Команда живёт в Telegram, Excel — стандарт для коммерческой работы | — Pending |
| Только публичная цена (без логина / Gold Card) | Справедливое сравнение, отсутствие риска блокировки аккаунта, проще реализовать | — Pending |
| Еженедельная частота (одного запуска в неделю достаточно) | Бизнес-цикл pricing-команды; меньше нагрузки на целевые сайты | — Pending |
| Стек Python | Стандарт для скрейпинга, лучшая экосистема (Playwright/Scrapy/pandas) | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current State

**v1 milestone code-ship COMPLETE 2026-05-13** — Phase 7 (Scheduler + Observability Hardening) closed all 5 SCHED requirements. 47/48 v1 requirements satisfied (only Phase 1 RECON-01 conditional plans remain operator-deferred per Camoufox-direct lock). Code review surfaced 4 Critical + 4 Warning issues — all auto-fixed (commits ed07007..c1e732b). 803/803 tests pass, zero regressions. Next: operator-led VPS deploy on Hetzner CX22 EU per README §2, then `/gsd-complete-milestone v1` for milestone audit and archival.

---
*Last updated: 2026-05-13 after Phase 7 completion*
