# Requirements: GA Crawler

**Defined:** 2026-05-05
**Core Value:** Команда viled.kz один раз в неделю получает детализированный, сопоставленный по позициям отчёт о ценах конкурента (goldapple.kz) и может корректировать собственное ценообразование, видеть ассортиментные разрывы и отслеживать чужие промо-акции.

## v1 Requirements

### Reconnaissance

- [ ] **RECON-01**: Спайк-проверка goldapple.kz определяет необходимый anti-bot-tier (1/2/3/4) и провайдера прокси
- [x] **RECON-02**: Спайк-проверка viled.kz подтверждает осуществимость парсинга через `curl_cffi` без headless-браузера
- [x] **RECON-03**: Спайк документирует объём страниц у типичного бренда на goldapple (для бюджета прокси) и наличие/отсутствие JSON-эндпоинтов каталога
- [x] **RECON-04**: Robots.txt и ToS обоих сайтов прочитаны; зафиксирован минимальный и приемлемый rate-limit для каждого

### Crawl

- [x] **CRAWL-01**: Краулер обходит весь каталог viled.kz (включая пагинацию) и собирает список URL продуктов — Plan 02-04 ships `enumeration/viled_catalog.py::fetch_catalog_urls` walking `props.pageProps.items.{content, totalPages, pageNumber}` per WAVE0-PROBE A4 REVISED. v1 limitation: SSR ignores `?page=N` and 9 other URL conventions (live probe 2026-05-07); runtime guard breaks early on stuck pageNumber. Effective output: 120 SKUs (60 men + 60 women, page 1 of each catalog) — above D-201 N=100 floor. Full pagination deferred to Phase 3/7 ops.
- [x] **CRAWL-02**: Краулер goldapple.kz получает список SKU, ограниченный брендами, присутствующими на viled.kz в текущем `run_id`
- [x] **CRAWL-03**: Per-SKU isolation — падение одного продукта не валит весь запуск; ошибки логируются и не блокируют остальные SKU — Plan 02-04 ships `fetchers/viled.py::fetch_one_isolated` (sync wrapper around `ViledFetcher.fetch_one`); exceptions logged via structlog `fetch_failed` event + `stats["fetch_failures"]` counter; run_loop continues to next URL.
- [x] **CRAWL-04**: Retry с экспоненциальной задержкой и jitter для временных сбоев (HTTP 5xx, таймауты) — Plan 02-04 ships tenacity-decorated `_fetch_html` with `stop_after_attempt(3)` + `wait_exponential_jitter(initial=2, max=30)`; retry-set includes synthetic TransientFetchError + curl_cffi-native Timeout/ReadTimeout/ConnectionError/HTTPError/RequestException (imports from `curl_cffi.requests.exceptions` per WAVE0-PROBE A10 REVISED); 4xx (e.g. 404, 410, 403) NOT retried — surfaces immediately for caller's DELISTED/PITFALL-8 handling.
- [ ] **CRAWL-05**: Sanity-assertion после краула: `viled_count > N`, `goldapple_count > M` (пороги конфигурируются); меньше — `runs.status = 'failed'` (deferred to Plan 02-05 — runner/gates.py D-203 retailer-agnostic refactor)
- [x] **CRAWL-06**: Краулер уважает заданный rate-limit (паузы между запросами); параметры конфигурируются — Plan 02-04 ships `ViledFetcher.run_loop` with `sleep_fn(self.pause_seconds)` between fetches (N-1 sleeps for N URLs, no sleep after last); `pause_seconds` configurable via constructor or `ViledConfig.pause_seconds` (default 2.0 per D-225, loaded from `[tool.ga_crawler.crawl.viled]` namespace).

### Parse

- [x] **PARSE-01**: Парсер для каждого ритейлера извлекает: название, бренд, объём/вес, текущую цену, цену до скидки (если есть), наличие, URL, валюту — Plan 02-04 ships `parsers/viled_nextdata.py::parse_pdp` returning `ViledRawProduct(sku_id, url, name, brand_raw, current_price, was_price, currency, availability, raw_volume_text)` 9-field shape mirroring Phase 3 `GoldappleRawProduct`; same shape exposed via `ParseDispatcher().dispatch(retailer, html, url)`.
- [x] **PARSE-02**: JSON-LD `Product.offers.price` имеет приоритет над CSS-селекторами; CSS — запасной вариант — Plan 02-04 ships `parsers/dispatcher.py::ParseDispatcher` per-retailer routing (`viled` → `__NEXT_DATA__`-only parser per spike 01-07's 0/15 JSON-LD finding; `goldapple` → microdata extractor frozen since Phase 3). PARSE-02 inversion: viled parser MUST NOT contain JSON-LD code paths (enforced by `test_no_jsonld_path` source-inspection).
- [x] **PARSE-03**: Парсер отвергает поля вида `*old*`, `*was*`, `*crossed*`, `*club*`, `*gold*`, `*from*` при выборе `current_price` — Plan 02-04 implements per Reading A (WAVE0-PROBE A2): viled `attributes[0].price` is the current/sale price (customer-facing); `attributes[0].realPrice` is the MSRP/was-price; was_price set only when realPrice > price. Live discounted Frederic Malle fixture (price=356745, realPrice=419700) pinned in `test_discounted_fixture_real_corpus` as a permanent regression-canary.
- [x] **PARSE-04**: Sanity-check цены: `100 ≤ price ≤ 1_000_000 ₸`; вне диапазона — поле помечается как ошибка парсинга — Plan 02-04 ships inclusive boundary check in `viled_nextdata.parse_pdp`; verified by `test_sanity_range_low`, `test_sanity_range_high`, `test_sanity_range_boundaries_inclusive`.
- [ ] **PARSE-05**: Hard-fail invariant — если у >5% продуктов нет обязательного поля (название, цена, URL), запуск помечается `failed` (deferred to Plan 02-05 — runner/gates.py parse_quality_gate D-218)
- [x] **PARSE-06**: Стек состояния — enum (`IN_STOCK`, `OUT_OF_STOCK`, `UNAVAILABLE`, `DELISTED`, `URL_CHANGED`, `UNKNOWN`); хранится в схеме как enum, в отчёте v1 сводится к bool — Plan 02-04 ships `parsers/types.py::StockState` Literal enum + `viled_nextdata._map_stock_state(item)` derives from `item.count` (int) + `item.purchaseType` (str) per WAVE0-PROBE A1 REVISED (no in_stock bool exists in viled __NEXT_DATA__). DELISTED is fetcher-level (404/410); URL_CHANGED is orchestrator-level.

### Normalize

- [x] **NORM-01**: Brand-alias таблица (YAML) сопоставляет Cyrillic ↔ Latin варианты брендов (`Estée Lauder` ↔ `Эсте Лаудер` ↔ `Estee Lauder`); seeded топ-50 брендами viled — Plan 02-03 ships `YamlBrandAlias` loader (read-once D-207, lookup + canonical_for reverse helper); production seed config/brand-aliases.yaml lands in Plan 02-06
- [x] **NORM-02**: Нормализация бренда: NFKD + accent strip + lowercase + alias lookup → `brand_norm` — Plan 02-03 ships `normalizers/brand.py::normalize_brand` (REUSE _normalize_punct from enumeration/slug.py via import — no duplication)
- [x] **NORM-03**: Volume value-object `(amount, unit, multipack)`; парсит `30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, `Set of 3 × 50ml` — Plan 02-03 ships `Volume` frozen dataclass + `parse_volume` (3-layer grammar) + 24-entry UNIT_TABLE; all 18 volume-corpus.yaml cases pass
- [x] **NORM-04**: Multipack/kit детектится явно; для v1 такие SKU **исключаются** из price-per-unit-сравнения и помечаются флагом — Plan 02-03 ships `detect_multipack` INDEPENDENT of parse_volume (Open Q4 multipack flag persists when per-unit volume unparseable like `набор пробников`, `10 шт`)
- [x] **NORM-05**: Нормализация имени: lowercase + удаление пунктуации + collapse whitespace → `name_norm` — Plan 02-03 ships `normalizers/name.py::normalize_name` (NFKD + lowercase + strip-non-word-non-space + collapse-whitespace)
- [x] **NORM-06**: Лог "бренды на goldapple, не найденные в alias-таблице" — еженедельная очередь ручной проверки (Plan 02-02 ships `Norm06Writer.persist()` markdown ledger at `.planning/runs/{run_id}/norm06-review.md` per D-208/D-211)

### Match

- [ ] **MATCH-01**: Strict-key матчинг по `(brand_norm, name_norm, volume_norm)` через SQL JOIN между viled и goldapple snapshots для текущего `run_id`
- [ ] **MATCH-02**: Результат записывается в таблицу `matches(run_id, viled_sku, goldapple_sku, price_delta, price_delta_pct)`
- [ ] **MATCH-03**: Match-rate (`matches / viled_skus_with_brand_in_goldapple_brands * 100%`) вычисляется и логируется на каждом запуске
- [ ] **MATCH-04**: Sanity-gate — `match_count > P` (порог конфигурируется); меньше — `runs.status = 'failed'`, отчёт в business-чат **не отправляется**

### Data

- [x] **DATA-01**: SQLite-схема: `runs` (метаданные запуска), `snapshots` (immutable history, уникальный ключ `(run_id, retailer, sku_id)`), `matches` (производная) — Plan 02-02 ships `runs` + `snapshots` SQLModel tables (matches table deferred to Phase 4 per scope)
- [x] **DATA-02**: Snapshots хранят `current_price`, `was_price`, `currency`, `stock_state` (enum), `url`, `name`, `brand`, `volume_raw`, `brand_norm`, `name_norm`, `volume_norm`, `multipack_flag`, `scraped_at` — Plan 02-02 ships 18-col Snapshot SQLModel with all 13 required fields
- [x] **DATA-03**: Все записи immutable — апдейты только через новый `run_id`; "current view" реализуется через SQL `v_current_snapshots` — Plan 02-02 ships UNIQUE (run_id, retailer, sku_id) + INSERT-only `SqliteSnapshotWriter` + `v_current_snapshots` VIEW (D-221)
- [x] **DATA-04**: WAL mode включён; per-run транзакции; on-failure rollback не теряет уже сохранённые SKU — Plan 02-02 ships `make_engine` PRAGMA event listener (WAL + synchronous=NORMAL + foreign_keys=ON) + per-batch commit (DATA-04 mid-run-failure resilience, default batch_size=100)
- [x] **DATA-05**: `runs` row создаётся в начале запуска и **обязательно** обновляется в конце (success/partial/failed) во всех ветках кода — Plan 02-02 ships `SqliteRunWriter.create/patch_stats(json_patch)/get_stats/fail/finalize` lifecycle (atomic Pitfall-6 merge + idempotent fail/finalize). Try/finally orchestration wired in Plan 05.
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

Per-requirement phase mapping (filled by `gsd-roadmapper` 2026-05-05).

| Requirement | Phase | Status |
|-------------|-------|--------|
| RECON-01 | Phase 1 | Pending |
| RECON-02 | Phase 1 | Done (plan 01-07, 2026-05-05) |
| RECON-03 | Phase 1 | Done — page-volume in plan 01-05 (2026-05-05); JSON-endpoint hunt in plan 01-06 (2026-05-06, finding: NO Tier-0 endpoint, vendor identified as GroupIB/F.A.C.C.T., D-14 verification deferred to 01-08) |
| RECON-04 | Phase 1 | Done (plan 01-04, 2026-05-05) |
| CRAWL-01 | Phase 2 | Closed (Plan 02-04 — page-1-only v1; full pagination Phase 3/7 ops backlog) |
| CRAWL-02 | Phase 3 | Done — Wave 7 gap-closure plan 03-08 (2026-05-06) closed Truth 1 BLOCKER via Path A longest-prefix-in-whitelist brand-token bucket index; matched_url_count > 0 against realistic 45,490-slug sitemap shape proven by full-pipeline regression + E2E test; D-305 / Pitfall 3 enforced structurally (inspect.getsource gates) |
| CRAWL-03 | Phase 2 | Closed (Plan 02-04) |
| CRAWL-04 | Phase 2 | Closed (Plan 02-04) |
| CRAWL-05 | Phase 2 (viled threshold) + Phase 3 (goldapple threshold added to same gate) | Pending |
| CRAWL-06 | Phase 2 | Closed (Plan 02-04) |
| PARSE-01 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 viled side; Phase 3 goldapple side already shipped) |
| PARSE-02 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 — ParseDispatcher routes viled `__NEXT_DATA__` + goldapple microdata) |
| PARSE-03 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 — Reading A semantics anchored to live fixtures) |
| PARSE-04 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04) |
| PARSE-05 | Phase 2 (modules shared with Phase 3) | Pending |
| PARSE-06 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 — StockState enum + viled `_map_stock_state` per WAVE0-PROBE A1 REVISED) |
| NORM-01 | Phase 2 (seeded with viled top-50; goldapple variants added in Phase 3) | Plan 02-03 (loader + canonical_for); seed in Plan 02-06 |
| NORM-02 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-03 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-04 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-05 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-06 | Phase 2 (log defined; populated by real goldapple run in Phase 3) | Done (Plan 02-02 — Norm06Writer ships D-208 markdown ledger) |
| MATCH-01 | Phase 4 | Pending |
| MATCH-02 | Phase 4 | Pending |
| MATCH-03 | Phase 4 | Pending |
| MATCH-04 | Phase 4 | Pending |
| DATA-01 | Phase 2 | Done (Plan 02-02 — Run + Snapshot SQLModel tables) |
| DATA-02 | Phase 2 | Done (Plan 02-02 — 18-col Snapshot table with all 13 required fields) |
| DATA-03 | Phase 2 | Done (Plan 02-02 — UNIQUE constraint + append-only writer + v_current_snapshots VIEW) |
| DATA-04 | Phase 2 | Done (Plan 02-02 — WAL PRAGMA event listener + per-batch commit) |
| DATA-05 | Phase 2 | Done (Plan 02-02 — SqliteRunWriter atomic json_patch lifecycle; try/finally orchestration in Plan 05) |
| DATA-06 | Phase 2 | Pending |
| REPORT-01 | Phase 5 | Pending |
| REPORT-02 | Phase 5 | Pending |
| REPORT-03 | Phase 5 | Pending |
| REPORT-04 | Phase 5 | Pending |
| REPORT-05 | Phase 5 | Pending |
| REPORT-06 | Phase 5 | Pending |
| DELIVER-01 | Phase 6 | Pending |
| DELIVER-02 | Phase 6 | Pending |
| DELIVER-03 | Phase 6 | Pending |
| DELIVER-04 | Phase 6 | Pending |
| DELIVER-05 | Phase 6 | Pending |
| SCHED-01 | Phase 7 | Pending |
| SCHED-02 | Phase 7 | Pending |
| SCHED-03 | Phase 7 | Pending |
| SCHED-04 | Phase 7 | Pending |
| SCHED-05 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 48 total (RECON 4 + CRAWL 6 + PARSE 6 + NORM 6 + MATCH 4 + DATA 6 + REPORT 6 + DELIVER 5 + SCHED 5)
- Mapped to phases: 48
- Unmapped: 0
- Note: previous "47 total" count was an off-by-one in the initial summary; the enumerated IDs above sum to 48.

---
*Requirements defined: 2026-05-05*
*Last updated: 2026-05-05 — traceability filled by gsd-roadmapper*
