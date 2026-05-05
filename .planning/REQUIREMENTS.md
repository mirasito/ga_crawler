# Requirements: GA Crawler

**Defined:** 2026-05-05
**Core Value:** Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

## v1 Requirements

### Reconnaissance

- [ ] **RECON-01**: Спайк-проверка goldapple.kz определяет необходимый anti-bot-tier (1/2/3/4) и провайдера прокси
- [ ] **RECON-02**: Спайк-проверка viled.kz подтверждает осуществимость парсинга через `curl_cffi` без headless-браузера
- [ ] **RECON-03**: Спайк документирует объём страниц у типичного бренда на goldapple (для бюджета прокси) и наличие/отсутствие JSON-эндпоинтов каталога
- [ ] **RECON-04**: Robots.txt и ToS обоих сайтов прочитаны; зафиксирован минимальный и приемлемый rate-limit для каждого

### Crawl

- [ ] **CRAWL-01**: Краулер обходит весь каталог viled.kz (включая пагинацию) и собирает список URL продуктов
- [ ] **CRAWL-02**: Краулер goldapple.kz получает список SKU, ограниченный брендами, присутствующими на viled.kz в текущем `run_id`
- [ ] **CRAWL-03**: Per-SKU isolation — падение одного продукта не валит весь запуск; ошибки логируются и не блокируют остальные SKU
- [ ] **CRAWL-04**: Retry с экспоненциальной задержкой и jitter для временных сбоев (HTTP 5xx, таймауты)
- [ ] **CRAWL-05**: Sanity-assertion после краула: `viled_count > N`, `goldapple_count > M` (пороги конфигурируются); меньше — `runs.status = 'failed'`
- [ ] **CRAWL-06**: Краулер уважает заданный rate-limit (паузы между запросами); параметры конфигурируются

### Parse

- [ ] **PARSE-01**: Парсер для каждого ритейлера извлекает: название, бренд, объём/вес, текущую цену, цену до скидки (если есть), наличие, URL, валюту
- [ ] **PARSE-02**: JSON-LD `Product.offers.price` имеет приоритет над CSS-селекторами; CSS — запасной вариант
- [ ] **PARSE-03**: Парсер отвергает поля вида `*old*`, `*was*`, `*crossed*`, `*club*`, `*gold*`, `*from*` при выборе `current_price`
- [ ] **PARSE-04**: Sanity-check цены: `100 ≤ price ≤ 1_000_000 ₸`; вне диапазона — поле помечается как ошибка парсинга
- [ ] **PARSE-05**: Hard-fail invariant — если у >5% продуктов нет обязательного поля (название, цена, URL), запуск помечается `failed`
- [ ] **PARSE-06**: Стек состояния — enum (`IN_STOCK`, `OUT_OF_STOCK`, `UNAVAILABLE`, `DELISTED`, `URL_CHANGED`, `UNKNOWN`); хранится в схеме как enum, в отчёте v1 сводится к bool

### Normalize

- [ ] **NORM-01**: Brand-alias таблица (YAML) сопоставляет Cyrillic ↔ Latin варианты брендов (`Estée Lauder` ↔ `Эсте Лаудер` ↔ `Estee Lauder`); seeded топ-50 брендами viled
- [ ] **NORM-02**: Нормализация бренда: NFKD + accent strip + lowercase + alias lookup → `brand_norm`
- [ ] **NORM-03**: Volume value-object `(amount, unit, multipack)`; парсит `30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, `Set of 3 × 50ml`
- [ ] **NORM-04**: Multipack/kit детектится явно; для v1 такие SKU **исключаются** из price-per-unit-сравнения и помечаются флагом
- [ ] **NORM-05**: Нормализация имени: lowercase + удаление пунктуации + collapse whitespace → `name_norm`
- [ ] **NORM-06**: Лог "бренды на goldapple, не найденные в alias-таблице" — еженедельная очередь ручной проверки

### Match

- [ ] **MATCH-01**: Strict-key матчинг по `(brand_norm, name_norm, volume_norm)` через SQL JOIN между viled и goldapple snapshots для текущего `run_id`
- [ ] **MATCH-02**: Результат записывается в таблицу `matches(run_id, viled_sku, goldapple_sku, price_delta, price_delta_pct)`
- [ ] **MATCH-03**: Match-rate (`matches / viled_skus_with_brand_in_goldapple_brands * 100%`) вычисляется и логируется на каждом запуске
- [ ] **MATCH-04**: Sanity-gate — `match_count > P` (порог конфигурируется); меньше — `runs.status = 'failed'`, отчёт в business-чат **не отправляется**

### Data

- [ ] **DATA-01**: SQLite-схема: `runs` (метаданные запуска), `snapshots` (immutable history, уникальный ключ `(run_id, retailer, sku_id)`), `matches` (производная)
- [ ] **DATA-02**: Snapshots хранят `current_price`, `was_price`, `currency`, `stock_state` (enum), `url`, `name`, `brand`, `volume_raw`, `brand_norm`, `name_norm`, `volume_norm`, `multipack_flag`, `scraped_at`
- [ ] **DATA-03**: Все записи immutable — апдейты только через новый `run_id`; "current view" реализуется через SQL `v_current_snapshots`
- [ ] **DATA-04**: WAL mode включён; per-run транзакции; on-failure rollback не теряет уже сохранённые SKU
- [ ] **DATA-05**: `runs` row создаётся в начале запуска и **обязательно** обновляется в конце (success/partial/failed) во всех ветках кода
- [ ] **DATA-06**: Nightly backup БД в отдельную директорию (минимум 4 последних бэкапа)

### Report

- [ ] **REPORT-01**: Excel-файл с листами: `Summary`, `Per-SKU deltas` (виледд × голдэпл по совпавшим), `Assortment gaps` (бренды на goldapple, отсутствующие на viled), `Goldapple promos` (где `was_price > current_price`)
- [ ] **REPORT-02**: Conditional formatting в Excel: подсветка дельт (зелёный — viled дешевле, красный — viled дороже), frozen panes, autofilter
- [ ] **REPORT-03**: Заголовки колонок и текст саммари — на русском
- [ ] **REPORT-04**: Текстовая сводка: `viled_count`, `goldapple_count`, `match_count`, **`match_rate %`**, размер ассортиментного разрыва, top-3 наибольшие дельты, количество промо у goldapple
- [ ] **REPORT-05**: Excel-файл записывается на диск в архив (`reports/YYYY-WNN.xlsx`) до отправки — отчёт независим от Telegram
- [ ] **REPORT-06**: Размер xlsx проверяется перед отправкой — если > 45 MB, ругается явной ошибкой (Telegram limit 50 MB)

### Deliver

- [ ] **DELIVER-01**: Telegram-бот отправляет business-чат: текстовая сводка + xlsx-вложение через `send_document`
- [ ] **DELIVER-02**: Отдельный ops-чат получает уведомления о падениях, sanity-gate failures, отсутствующих ENV-переменных
- [ ] **DELIVER-03**: Pre-send sanity-gate — если `runs.status != 'success'`, в business-чат **ничего не отправляется**, в ops-чат идёт алерт
- [ ] **DELIVER-04**: Retry с учётом Telegram rate-limit (`retry-after` header); если Telegram недоступен — отчёт остаётся на диске и помечается как недоставленный
- [ ] **DELIVER-05**: Конфигурация двух чатов через ENV (`TG_BOT_TOKEN`, `TG_BUSINESS_CHAT_ID`, `TG_OPS_CHAT_ID`)

### Schedule & Ops

- [ ] **SCHED-01**: Системный cron на VPS запускает `python -m ga_crawler` раз в неделю в ночь воскресенья (Asia/Almaty); отчёт приходит утром в понедельник
- [ ] **SCHED-02**: Cron-запись использует `CRON_TZ=Asia/Almaty` (нет drift из-за UTC server)
- [ ] **SCHED-03**: Healthchecks.io dead-man's-switch получает start/success/fail-пинги; пропуск запуска → алерт в ops
- [ ] **SCHED-04**: Структурированные JSON-логи (structlog) на диск с ротацией; видно через `tail` / `grep`
- [ ] **SCHED-05**: Документация по setup: `README.md` с инструкцией установки на чистый VPS (uv, Playwright deps, cron, ENV) и deliberate-failure тест (показать, что ops-алерт работает)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Matching

- **MATCH-V2-01**: Детерминированный fuzzy-матчинг (Levenshtein/token-set) с порогом и очередью ручной проверки — триггер: если v1 match-rate стабильно ниже приемлемого после 4 недель
- **MATCH-V2-02**: Per-SKU manual override таблица (для редких случаев, когда нормализация не справляется)

### Reporting

- **REPORT-V2-01**: Week-over-week price delta колонка (сравнение с прошлым запуском)
- **REPORT-V2-02**: Brand-level aggregate sheet (средняя дельта по бренду)
- **REPORT-V2-03**: New / disappeared SKU sheet (что появилось/исчезло за неделю)
- **REPORT-V2-04**: Match-rate degradation alert (если match-rate упал > 10% от 4-недельного среднего)
- **REPORT-V2-05**: Promo-frequency view (как часто ритейлер ставит скидку на бренд)

### Infrastructure

- **INFRA-V2-01**: Migration to Postgres (если SQLite станет узким местом или появится дашборд)
- **INFRA-V2-02**: Docker-обёртка для деплоя (если нужно унификация окружения между разработкой и VPS)
- **INFRA-V2-03**: Веб-дашборд для исторических трендов (Streamlit / read-only Metabase)

### Channels

- **DELIVER-V2-01**: Email-канал доставки (PDF-сводка + xlsx)
- **DELIVER-V2-02**: Поддержка дополнительных конкурентов (расширяемая через адаптер `Crawler`)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Цены под Gold Card / залогиненные цены | Риск блокировки аккаунта; для сравнения с viled нужна публичная цена |
| Полный парсинг goldapple.kz (всех брендов) | Не имеет смысла — фокус только на пересекающихся брендах; экономия трафика и риска |
| Real-time / ежедневный мониторинг | Еженедельная частота закрывает бизнес-цикл pricing-команды |
| Алерты на скидки в реальном времени | Всё в недельном отчёте — оперативность не критична |
| Веб-дашборд / UI | На v1 не требуется; xlsx + Telegram достаточно |
| Парсинг прочих маркетплейсов | Фокус строго на goldapple.kz vs viled.kz |
| Картинки и описания товаров | Не нужны для ценового сравнения; экономия места и трафика |
| Машинное обучение для матчинга | Strict-key + brand alias достаточно; ML — overkill для этой задачи |
| Динамическое перепрайсинг (auto-repricer) | Это reporting-инструмент, не automation; решения принимает человек |
| Multi-tenant / SaaS-функционал | Внутренний инструмент одной команды |
| Captcha-solving сервисы | Если потребуется — это сигнал, что мы перешли на enemy territory; решается выбором tier'а в спайке, не obfuscation'ом |
| Поддержка Selenium / requests / cloudscraper / playwright-stealth v1.x | Устарели или неэффективны против Cloudflare/DataDome 2026 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| RECON-01 — RECON-04 | TBD | Pending |
| CRAWL-01 — CRAWL-06 | TBD | Pending |
| PARSE-01 — PARSE-06 | TBD | Pending |
| NORM-01 — NORM-06 | TBD | Pending |
| MATCH-01 — MATCH-04 | TBD | Pending |
| DATA-01 — DATA-06 | TBD | Pending |
| REPORT-01 — REPORT-06 | TBD | Pending |
| DELIVER-01 — DELIVER-05 | TBD | Pending |
| SCHED-01 — SCHED-05 | TBD | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 0 (filled during roadmap creation)
- Unmapped: 47 ⚠️ (will be resolved by gsd-roadmapper)

---
*Requirements defined: 2026-05-05*
*Last updated: 2026-05-05 after initial definition*
