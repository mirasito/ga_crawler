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

- [x] **CRAWL-01**: Краулер обходит beauty+парфюмерия каталог viled.kz (`/men/catalog/1310` + `/women/catalog/1310`, через пагинацию) и собирает список URL продуктов — Plan 02-04 ships `enumeration/viled_catalog.py::fetch_catalog_urls` walking `props.pageProps.items.{content, totalPages, pageNumber}` per WAVE0-PROBE A4 REVISED. Scope clarification (CONTEXT D-223, 2026-05-07): viled = beauty+parfumery only (NOT full luxury catalog) — commercial relevance vs goldapple beauty retailer. v1 limitation: SSR ignores `?page=N` and 9 other URL conventions (live probe 2026-05-07); runtime guard breaks early on stuck pageNumber. Effective output: 120 SKUs (60 men + 60 women, page 1 of each catalog) — above D-201 N=100 floor. Full pagination deferred to Phase 3/7 ops.
- [x] **CRAWL-02**: Краулер goldapple.kz получает список SKU, ограниченный брендами, присутствующими на viled.kz в текущем `run_id`
- [x] **CRAWL-03**: Per-SKU isolation — падение одного продукта не валит весь запуск; ошибки логируются и не блокируют остальные SKU — Plan 02-04 ships `fetchers/viled.py::fetch_one_isolated` (sync wrapper around `ViledFetcher.fetch_one`); exceptions logged via structlog `fetch_failed` event + `stats["fetch_failures"]` counter; run_loop continues to next URL.
- [x] **CRAWL-04**: Retry с экспоненциальной задержкой и jitter для временных сбоев (HTTP 5xx, таймауты) — Plan 02-04 ships tenacity-decorated `_fetch_html` with `stop_after_attempt(3)` + `wait_exponential_jitter(initial=2, max=30)`; retry-set includes synthetic TransientFetchError + curl_cffi-native Timeout/ReadTimeout/ConnectionError/HTTPError/RequestException (imports from `curl_cffi.requests.exceptions` per WAVE0-PROBE A10 REVISED); 4xx (e.g. 404, 410, 403) NOT retried — surfaces immediately for caller's DELISTED/PITFALL-8 handling.
- [x] **CRAWL-05**: Sanity-assertion после краула: `viled_count > N`, `goldapple_count > M` (пороги конфигурируются); меньше — `runs.status = 'failed'` — Plan 02-05 ships D-203 retailer-agnostic `final_threshold_gate(count, threshold)` in `runner/gates.py` + Phase 3 backward-compat shims (`final_m_gate(count, M=1000)`, `final_n_gate(count, N=100)`); `runners/viled_run.py` calls `final_threshold_gate(viled_count, config.sanity_gate_n)` after parse-quality gate; `runners/goldapple_run.py` (Phase 3 frozen) calls `final_m_gate(goldapple_count, M)`. Either retailer falling below threshold → `run_writer.fail(run_id, reason)` with explicit count and threshold in reason. Audit-trail invariant: snapshot rows persist regardless of gate outcome (test_sanity_n_gate_fails verifies len(snapshots)==2 + run.status='failed' simultaneously).
- [x] **CRAWL-06**: Краулер уважает заданный rate-limit (паузы между запросами); параметры конфигурируются — Plan 02-04 ships `ViledFetcher.run_loop` with `sleep_fn(self.pause_seconds)` between fetches (N-1 sleeps for N URLs, no sleep after last); `pause_seconds` configurable via constructor or `ViledConfig.pause_seconds` (default 2.0 per D-225, loaded from `[tool.ga_crawler.crawl.viled]` namespace).

### Parse

- [x] **PARSE-01**: Парсер для каждого ритейлера извлекает: название, бренд, объём/вес, текущую цену, цену до скидки (если есть), наличие, URL, валюту — Plan 02-04 ships `parsers/viled_nextdata.py::parse_pdp` returning `ViledRawProduct(sku_id, url, name, brand_raw, current_price, was_price, currency, availability, raw_volume_text)` 9-field shape mirroring Phase 3 `GoldappleRawProduct`; same shape exposed via `ParseDispatcher().dispatch(retailer, html, url)`.
- [x] **PARSE-02**: JSON-LD `Product.offers.price` имеет приоритет над CSS-селекторами; CSS — запасной вариант — Plan 02-04 ships `parsers/dispatcher.py::ParseDispatcher` per-retailer routing (`viled` → `__NEXT_DATA__`-only parser per spike 01-07's 0/15 JSON-LD finding; `goldapple` → microdata extractor frozen since Phase 3). PARSE-02 inversion: viled parser MUST NOT contain JSON-LD code paths (enforced by `test_no_jsonld_path` source-inspection).
- [x] **PARSE-03**: Парсер отвергает поля вида `*old*`, `*was*`, `*crossed*`, `*club*`, `*gold*`, `*from*` при выборе `current_price` — Plan 02-04 implements per Reading A (WAVE0-PROBE A2): viled `attributes[0].price` is the current/sale price (customer-facing); `attributes[0].realPrice` is the MSRP/was-price; was_price set only when realPrice > price. Live discounted Frederic Malle fixture (price=356745, realPrice=419700) pinned in `test_discounted_fixture_real_corpus` as a permanent regression-canary.
- [x] **PARSE-04**: Sanity-check цены: `100 ≤ price ≤ 1_000_000 ₸`; вне диапазона — поле помечается как ошибка парсинга — Plan 02-04 ships inclusive boundary check in `viled_nextdata.parse_pdp`; verified by `test_sanity_range_low`, `test_sanity_range_high`, `test_sanity_range_boundaries_inclusive`.
- [x] **PARSE-05**: Hard-fail invariant — если у >5% продуктов нет обязательного поля (название, цена, URL), запуск помечается `failed` — Plan 02-05 ships `parse_quality_gate(null_rate, threshold=0.05)` in `runner/gates.py` per D-218; `runners/viled_run.py::_compute_null_rate(records)` counts rows where `name OR current_price IS NULL OR url` is missing/falsy and divides by len. The gate runs FIRST in the orchestrator (BEFORE sanity-N) so a "parsed-garbage" run fails for the right reason rather than masquerading as a low-count run. Threshold inclusive (≤): exactly 5% passes; 5.01% fails. Either gate failing → `run_writer.fail(run_id, reason)`; snapshot rows persist regardless (audit-trail invariant per D-218).
- [x] **PARSE-06**: Стек состояния — enum (`IN_STOCK`, `OUT_OF_STOCK`, `UNAVAILABLE`, `DELISTED`, `URL_CHANGED`, `UNKNOWN`); хранится в схеме как enum, в отчёте v1 сводится к bool — Plan 02-04 ships `parsers/types.py::StockState` Literal enum + `viled_nextdata._map_stock_state(item)` derives from `item.count` (int) + `item.purchaseType` (str) per WAVE0-PROBE A1 REVISED (no in_stock bool exists in viled __NEXT_DATA__). DELISTED is fetcher-level (404/410); URL_CHANGED is orchestrator-level.

### Normalize

- [x] **NORM-01**: Brand-alias таблица (YAML) сопоставляет Cyrillic ↔ Latin варианты брендов (`Estée Lauder` ↔ `Эсте Лаудер` ↔ `Estee Lauder`); seeded топ-50 брендами viled — Plan 02-03 ships `YamlBrandAlias` loader (read-once D-207, lookup + canonical_for reverse helper); Plan 02-06 ships production seed `config/brand-aliases.yaml` with **58 canonical brands** (≥50 floor) including 46 Cyrillic alias entries (Эсте Лаудер, Живанши, Шанель, Диор, Том Форд, Джо Малон Лондон, Крид, Фредерик Маль, Амуаж, Килиан, Армани, etc.) per D-204..D-207 priority order (viled-home-brands-extract + STATE.md plan 01-05 luxury/perfumery brands)
- [x] **NORM-02**: Нормализация бренда: NFKD + accent strip + lowercase + alias lookup → `brand_norm` — Plan 02-03 ships `normalizers/brand.py::normalize_brand` (REUSE _normalize_punct from enumeration/slug.py via import — no duplication)
- [x] **NORM-03**: Volume value-object `(amount, unit, multipack)`; парсит `30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, `Set of 3 × 50ml` — Plan 02-03 ships `Volume` frozen dataclass + `parse_volume` (3-layer grammar) + 24-entry UNIT_TABLE; all 18 volume-corpus.yaml cases pass
- [x] **NORM-04**: Multipack/kit детектится явно; для v1 такие SKU **исключаются** из price-per-unit-сравнения и помечаются флагом — Plan 02-03 ships `detect_multipack` INDEPENDENT of parse_volume (Open Q4 multipack flag persists when per-unit volume unparseable like `набор пробников`, `10 шт`)
- [x] **NORM-05**: Нормализация имени: lowercase + удаление пунктуации + collapse whitespace → `name_norm` — Plan 02-03 ships `normalizers/name.py::normalize_name` (NFKD + lowercase + strip-non-word-non-space + collapse-whitespace)
- [x] **NORM-06**: Лог "бренды на goldapple, не найденные в alias-таблице" — еженедельная очередь ручной проверки (Plan 02-02 ships `Norm06Writer.persist()` markdown ledger at `.planning/runs/{run_id}/norm06-review.md` per D-208/D-211)

### Match

- [x] **MATCH-01**: Strict-key матчинг по `(brand_norm, name_norm, volume_norm)` через SQL JOIN между viled и goldapple snapshots для текущего `run_id` — Plan 04-03 ships `src/ga_crawler/matcher/strict_key.py::INSERT_MATCHES_SQL` with symmetric filter per D-402 (`multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'` applied to BOTH retailers); strict-key JOIN ON `v.brand_norm = g.brand_norm AND v.name_norm = g.name_norm AND v.volume_norm = g.volume_norm`. N→1 keep-all per D-403 — composite PK `(run_id, viled_sku, goldapple_sku)` allows multiple goldapple SKUs sharing the same key to map to one viled SKU.
- [x] **MATCH-02**: Результат записывается в денормализованную таблицу `matches(run_id, viled_sku, goldapple_sku, brand_norm, name_norm, volume_norm, viled_price, goldapple_price, viled_was_price, goldapple_was_price, price_delta, price_delta_pct, matched_at)` per D-401 — Plan 04-01 ships `Match` SQLModel + composite PK; Plan 04-03 ships DELETE+INSERT in single SQLite transaction (D-410 idempotency); `price_delta = goldapple_price − viled_price` (signed per D-401); `price_delta_pct = ROUND((g.current_price − v.current_price) × 100.0 / v.current_price, 2)` (D-405 formula frozen with week-1 baseline).
- [x] **MATCH-03**: Match-rate (`matches / viled_skus_with_brand_in_goldapple_brands × 100%`) вычисляется и логируется на каждом запуске — Plan 04-03 ships `compute_denominator(engine, run_id)` per D-404 (symmetric filter: viled comparable SKUs whose brand_norm appears on goldapple this run); Plan 04-04 orchestrator computes `match.rate = round(count * 100.0 / denominator, 2)` with zero-denominator guard (rate=0.0 + structured-log warning `match_zero_denominator`); D-405 KPI formula frozen with week-1 baseline — `test_match_rate_formula_canary` pins formula structurally (source-locked SQL substring + numerical 6/5/3 → 60.0 regression fixture).
- [x] **MATCH-04**: Sanity-gate — `match_count > P` (порог конфигурируется); меньше — `runs.status = 'failed'`, отчёт в business-чат **не отправляется** — Plan 04-01 ships `[tool.ga_crawler.match] sanity_gate_p = 20` (D-408 seed) + `MatchConfig.from_pyproject`; Plan 04-04 orchestrator calls `final_threshold_gate(match_count, threshold_p)` (D-203 retailer-agnostic helper reused) + `run_writer.fail(run_id, reason='match_count_below_threshold:{count}<{threshold}')` on trip; D-409 audit-trail invariant — matches rows ALREADY inserted persist (mirror D-218 gate-fail-but-snapshot-persists). D-407 auto-suggest emits `match_auto_suggest_p` log line after 4+ runs (NEVER auto-tunes — operator-PR only).

### Data

- [x] **DATA-01**: SQLite-схема: `runs` (метаданные запуска), `snapshots` (immutable history, уникальный ключ `(run_id, retailer, sku_id)`), `matches` (производная) — Plan 02-02 ships `runs` + `snapshots` SQLModel tables (matches table deferred to Phase 4 per scope)
- [x] **DATA-02**: Snapshots хранят `current_price`, `was_price`, `currency`, `stock_state` (enum), `url`, `name`, `brand`, `volume_raw`, `brand_norm`, `name_norm`, `volume_norm`, `multipack_flag`, `scraped_at` — Plan 02-02 ships 18-col Snapshot SQLModel with all 13 required fields
- [x] **DATA-03**: Все записи immutable — апдейты только через новый `run_id`; "current view" реализуется через SQL `v_current_snapshots` — Plan 02-02 ships UNIQUE (run_id, retailer, sku_id) + INSERT-only `SqliteSnapshotWriter` + `v_current_snapshots` VIEW (D-221)
- [x] **DATA-04**: WAL mode включён; per-run транзакции; on-failure rollback не теряет уже сохранённые SKU — Plan 02-02 ships `make_engine` PRAGMA event listener (WAL + synchronous=NORMAL + foreign_keys=ON) + per-batch commit (DATA-04 mid-run-failure resilience, default batch_size=100)
- [x] **DATA-05**: `runs` row создаётся в начале запуска и **обязательно** обновляется в конце (success/partial/failed) во всех ветках кода — Plan 02-02 ships `SqliteRunWriter.create/patch_stats(json_patch)/get_stats/fail/finalize` lifecycle (atomic Pitfall-6 merge + idempotent fail/finalize). Try/finally orchestration wired in Plan 05.
- [x] **DATA-06**: Nightly backup БД в отдельную директорию (минимум 4 последних бэкапа) — Plan 02-06 ships `bin/backup.sh` (online sqlite3 .backup + 4-rotate retention per D-219 + RESEARCH §Pitfall 3 atomic+WAL-safe) + `backups/` directory tracked via .gitkeep with `.gitignore` excluding *.db files. 4 integration tests in `tests/integration/test_backup_script.py` verify atomic backup + 4-file retention + missing-source error + auto-mkdir.

### Report

- [x] **REPORT-01**: Excel-файл с листами: `Summary`, `Per-SKU deltas` (виледд × голдэпл по совпавшим), `Assortment gaps` (**SKU на goldapple, отсутствующие на viled по strict-key (brand_norm, name_norm, volume_norm), в пределах brand-overlap CRAWL-02 scope** — D-502 reinterpretation: brand-level gap = ∅ by CRAWL-02 construction, SKU-level = корректный intent), `Goldapple promos` (где `was_price > current_price`) — Plan 05-02 ships excel_builder.py with 4-sheet workbook via `pd.ExcelWriter(BytesIO, engine='xlsxwriter')` (Pitfall 1 explicit); Plan 05-04 ships orchestrator with D-506 always-4-sheets invariant.
- [x] **REPORT-02**: Conditional formatting в Excel: подсветка дельт (зелёный — viled дешевле, красный — viled дороже), frozen panes, autofilter — Plan 05-02 excel_builder.py ships D-505 3-color-scale on `Дельта, %` + `Скидка, %` columns with `mid_type='num', mid_value=0` anchor (parity), D-508 CF-on-2-sheets-only (Per-SKU deltas + Goldapple promos; NOT Summary / Assortment gaps), `freeze_panes(1, 0)` + `autofilter` on all data sheets per Pattern 3.
- [x] **REPORT-03**: Заголовки колонок и текст саммари — на русском — Plan 05-02 excel_builder.py ships D-503 verbatim PER_SKU_HEADERS_RU + GAPS_HEADERS_RU + PROMOS_HEADERS_RU dicts (Бренд / Название / Объём / Цена viled, ₸ / Старая цена viled, ₸ / URL viled / Цена goldapple, ₸ / Старая цена goldapple, ₸ / URL goldapple / Дельта, ₸ / Дельта, % / Скидка, ₸ / Скидка, %); summary_builder.py ships D-504 multi-line emoji template constants (📊/📦/🎯/🆕/💸/🔝) source-locked; `test_russian_headers_match_d503` source-lock canary + golden-file canary `tests/fixtures/reporter/expected-summary-text.txt`.
- [x] **REPORT-04**: Текстовая сводка: `viled_count`, `goldapple_count`, `match_count`, **`match_rate %`**, размер ассортиментного разрыва, top-3 наибольшие дельты, количество промо у goldapple — Plan 05-02 summary_builder.build_summary ships D-504 canonical template; reads upstream stats `viled.fetch_count` / `goldapple.fetch_count` / `match.count` / `match.rate` flat dot-keyed (Pitfall 6) — D-405 KPI formula citation verbatim, no recompute; top-3 sorted by `ABS(price_delta_pct) DESC` via SQL `read_top_n_deltas` (Pattern 7 — doesn't materialize 50k matches into pandas); zero-match D-504 fallback (Top-3 header omitted entirely when match_count==0).
- [x] **REPORT-05**: Excel-файл записывается на диск в архив (`reports/YYYY-WNN.xlsx`) до отправки — отчёт независим от Telegram — Plan 05-03 archive.py ships D-512 ISO-week filename via `Asia/Almaty` ZoneInfo + `date.isocalendar()` (Pitfall 4 year-boundary verified: 2027-01-01 UTC → 2026-W53, 2025-12-29 → 2026-W01) + D-510 atomic write `*.xlsx.tmp` + `os.replace` (crash-safe per Pitfall 5); Plan 05-04 orchestrator path-traversal containment check `target_path.relative_to(repo_root.resolve())`; Plan 05-05 standalone `python -m ga_crawler report-run --run-id N` subcommand (D-509) for SC#3 historical regeneration; ARCHITECTURE.md "reporter independent of delivery" structurally enforced — no Telegram imports in reporter package.
- [x] **REPORT-06**: Размер xlsx проверяется перед отправкой — если > 45 MB, явная сигнализация (Telegram limit 50 MB) — Plan 05-03 archive.check_size_guard ships D-515 flag-only semantics (returns `(passed: bool, size_bytes: int)`, NEVER raises); orchestrator (Plan 05-04) sets `report.size_guard_passed=false` in stats + structlog warning `report_size_exceeded`; **xlsx ALWAYS persists on disk** (D-515 invariant — manual recovery / Phase 6 split-and-send-later) + Run status remains `success` (ARCHITECTURE.md "reporter independent of delivery" удерживается); **Phase 6 DELIVER-03 cascade**: must read `report.size_guard_passed` and route >45MB runs to ops-chat alert (NOT business-chat) — invariant cascaded to STATE.md Accumulated Key Decisions for Phase 6 planner.

### Deliver

- [x] **DELIVER-01**: Telegram-бот отправляет business-чат: текстовая сводка + xlsx-вложение через `send_document` — Plan 06-02 ships `delivery/message_builder.py::business_caption` (D-514 verbatim consumption of `runs.stats.report.summary_text`); Plan 06-03 ships `delivery/telegram_client.py::send_document_with_policy` with FSInputFile(Path) per RESEARCH §3; Plan 06-04 orchestrator wires `_send_async` business-route branch with caption-split fallback (Claude's Discretion: summary_text > 1024 chars → `send_message` + `send_document(caption="См. сводку выше")`). aiogram 3.27 locked per D-601 + CLAUDE.md §Telegram Delivery. `async with Bot()` lifecycle prevents unclosed-session warnings (Pitfall B, RESEARCH §2). Plan 06-05 Wave 4 wires this into `run_weekly` cron entry via D-615 composition gate + D-616 MainRunResult.delivery_status/delivery_route fields.
- [x] **DELIVER-02**: Отдельный ops-чат получает уведомления о падениях, sanity-gate failures, отсутствующих ENV-переменных — Plan 06-02 ships `delivery/message_builder.py::build_ops_alert` (D-610 single-template with reason-field + REASON_SHORT mapping + html.escape per Pitfall A + Asia/Almaty tz per Pitfall E + 3500-char traceback truncation per D-614); golden-file `tests/fixtures/delivery/ops-alert-templates.txt` source-locks 5 scenarios. Plan 06-04 orchestrator routes ops-only via `_send_async` ops branch. parse_mode=HTML (D-609) — escape only `<>&`, NOT MarkdownV2's 16-char escape surface. D-611 asymmetric ENV routing degrades `business_chat_id` missing → ops_only with `missing_env_TG_BUSINESS_CHAT_ID` reason.
- [x] **DELIVER-03**: Pre-send sanity-gate — если `runs.status != 'success'`, в business-чат **ничего не отправляется**, в ops-чат идёт алерт — Plan 06-03 ships `delivery/gate.py::evaluate_gate` composing 4 checks (D-604, first-fail-wins): runs.status=='success' (REUSE `matcher.strict_key.read_run_status` D-411 helper); `report.xlsx_path` non-empty; `report.size_guard_passed==True` (D-515 cascade from Phase 5); `report.summary_text` non-empty after strip. `GateDecision` frozen dataclass with route + gate_failed_check + gate_failure_reason. Plan 06-04 orchestrator gates routing at Step 2; Plan 06-05 E2E test SC#2 (deliberate-failure → ops_only) pins behavior end-to-end.
- [x] **DELIVER-04**: Retry с учётом Telegram rate-limit (`retry-after` header); если Telegram недоступен — отчёт остаётся на диске и помечается как недоставленный — Plan 06-03 ships tenacity 3-retry on `(TelegramNetworkError, TelegramServerError)` ONLY via `wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))` (RESEARCH caveat #2 — NOT `wait_exponential`). `TelegramRetryAfter` handled OUTSIDE tenacity via `_send_with_retry_after_loop` (RESEARCH §11). Pitfall A: `TelegramBadRequest` / `TelegramForbiddenError` / `TelegramNotFound` / `TelegramUnauthorizedError` excluded from retry-set (fail-fast → undelivered). Plan 06-04 orchestrator on exhaustion → `delivery_status='undelivered_telegram_unreachable'` per D-606; xlsx remains on disk for `deliver-run --run-id N` recovery (D-608); Plan 06-05 E2E test pins D-605 invariant (runs.status='success' even when Telegram fails).
- [x] **DELIVER-05**: Конфигурация двух чатов через ENV (`TG_BOT_TOKEN`, `TG_BUSINESS_CHAT_ID`, `TG_OPS_CHAT_ID`) — Plan 06-01 ships `.env.example` template (D-612) + `.gitignore` audit confirms `.env` excluded; Plan 06-02 ships `delivery/config.py::DeliverEnvConfig.from_env` reading via `os.getenv` ONLY (RESEARCH caveat #4 — `load_dotenv` lives only in `cli.py::_cmd_deliver` startup); Plan 06-04 orchestrator applies D-611 asymmetric handling: `TG_BOT_TOKEN` missing → `delivery_status='skipped_no_credentials'` + CLI exit 3; `TG_BUSINESS_CHAT_ID` missing on business route → degrade to ops alert with reason `missing_env_TG_BUSINESS_CHAT_ID`; `TG_OPS_CHAT_ID` missing on ops route → exit 3.

### Schedule & Ops

- [x] **SCHED-01**: Системный cron на VPS запускает `python -m ga_crawler` раз в неделю в ночь воскресенья (Asia/Almaty); отчёт приходит утром в понедельник — Plan 07-02 ships `deploy/etc-cron-d-ga_crawler` config-as-code template (D-708 verbatim) with row `0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh`; Plan 07-04 README.md §2 + §4 documents the deploy procedure (`sudo cp deploy/etc-cron-d-ga_crawler /etc/cron.d/ga_crawler` + `sudo systemctl reload cron`). Sunday 23:00 Almaty = Sunday 18:00 UTC; expected report arrival Monday 02:00-03:00 Almaty (after 3-4h run + delivery). Runtime verification deferred to operator manual smoke per 07-VALIDATION.md «Manual-Only Verifications» — `bin/weekly-run.sh --viled-only --sanity-gate-n 1` (README §2 step 8).
- [x] **SCHED-02**: Cron-запись использует `CRON_TZ=Asia/Almaty` (нет drift из-за UTC server) — Plan 07-02 ships `deploy/etc-cron-d-ga_crawler` with `CRON_TZ=Asia/Almaty` as the first non-comment line (Vixie cron supports `CRON_TZ` scope-limited to `/etc/cron.d/*` file per crontab(5)). `MAILTO=""` also present (Pitfall #2 mitigation — T-07-01 Information Disclosure prevention). Canary `tests/test_phase07_cron_template_shape.py::test_cron_contains_cron_tz_almaty` source-locks the invariant.
- [x] **SCHED-03**: Healthchecks.io dead-man's-switch получает start/success/fail-пинги; пропуск запуска → алерт в ops — Plan 07-03 ships `bin/weekly-run.sh` (D-709 contract): `curl -fsS -m 10 --retry 3 "${HC_PING_URL}/start"` before exec, then bare `"${HC_PING_URL}"` on EXIT=0 OR `"${HC_PING_URL}/fail"` with `--data-raw "exit=$EXIT"` on EXIT≠0; all 3 pings `|| true` fail-soft (HC outage MUST NOT block production exec). D-703 fail-loud: wrapper exits 4 if `HC_PING_URL` missing (`: "${HC_PING_URL:?...}"`). Plan 07-04 README §5 documents HC.io account + check + grace period 2h + Telegram integration via `@my_hc_bot`. Hard-crash coverage rationale: bash wrapper owns pings instead of Python (OOM-killer / segfault / `kill -9` blind spots if Python in-process pinged per D-701).
- [x] **SCHED-04**: Структурированные JSON-логи (structlog) на диск с ротацией; видно через `tail` / `grep` — Plan 07-03 wrapper redirects `uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1` where `LOG_FILE=/var/log/ga_crawler/weekly-run-$(date +%F).log` (datestamped). Plan 07-02 `deploy/etc-logrotate-d-ga_crawler` ships 7 directives (weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create 0644 ga_crawler ga_crawler) — 3 months retention (~65MB total on Hetzner CX22 40GB SSD). Plan 07-04 README §9 documents grep/jq examples (`tail -f`, `grep '"level":"error"'`, `zgrep '"run_id":42' *.log.gz`); structlog `run_id` binding pre-existing from Phase 4..6 makes JSON events grep-friendly without Phase 7 code changes (D-704 — `_configure_logging()` source unchanged).
- [x] **SCHED-05**: Документация по setup: `README.md` с инструкцией установки на чистый VPS (uv, Playwright deps, cron, ENV) и deliberate-failure тест (показать, что ops-алерт работает) — Plan 07-04 ships `README.md` at repo root with exactly 10 H2 sections in D-707 order (canary `tests/test_phase07_readme_structure.py::test_readme_h2_order_matches_d707` source-locks heading list). RU-primary prose; EN code blocks. Sections cover: §2 from-scratch Hetzner CX22 + Ubuntu 24.04 setup with Pitfall #5/#6 user-first ordering (useradd -r -m -d BEFORE logrotate cp BEFORE Camoufox install); §3 ENV vars + reserved exit codes 3/4/5; §4 cron entry verbatim; §5 Healthchecks.io setup; §6 Telegram bot setup; §7 `bin/test-failure-alert.sh` deliberate-failure procedure (D-706 reuses `--viled-only --sanity-gate-n 999999` + `deliver-run --run-id` — NO new production Python paths); §8 operations runbook (deliver-run / report-run / matcher-run / backup recovery); §9 logs + rotation; §10 dev setup. Plan 07-03 ships `bin/test-failure-alert.sh` orchestrator (D-706 5-step + idempotent — failed run stays in DB as evidence per step 5; canary `tests/test_phase07_test_failure_alert_shape.py` source-locks invariants).

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
- **INFRA-V2-04**: Docker image для reproducible redeploys — Camoufox Firefox 135-pinned не совместим с `mcr.microsoft.com/playwright/python:v1.57.0-noble` (Chromium-based); требуется custom base image (build pipeline + Camoufox install + uv + bind-mount volumes). Native install на Ubuntu 24.04 proven через Phase 7 D-708 / D-710; tracked в Phase 8+ backlog.

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
| CRAWL-05 | Phase 2 (viled threshold) + Phase 3 (goldapple threshold added to same gate) | Closed (Plan 02-05 — D-203 retailer-agnostic `final_threshold_gate` + Phase 3 backward-compat shims; viled_run.py + goldapple_run.py both gate-fail with run_writer.fail; audit-trail invariant: snapshots persist regardless of gate outcome) |
| CRAWL-06 | Phase 2 | Closed (Plan 02-04) |
| PARSE-01 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 viled side; Phase 3 goldapple side already shipped) |
| PARSE-02 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 — ParseDispatcher routes viled `__NEXT_DATA__` + goldapple microdata) |
| PARSE-03 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 — Reading A semantics anchored to live fixtures) |
| PARSE-04 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04) |
| PARSE-05 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-05 — D-218 `parse_quality_gate(null_rate, threshold=0.05)` runs FIRST in viled_run.py before sanity-N; ≤5% null-required-field rate passes; >5% sets run.status='failed' with reason 'parse_quality_below_threshold') |
| PARSE-06 | Phase 2 (modules shared with Phase 3) | Closed (Plan 02-04 — StockState enum + viled `_map_stock_state` per WAVE0-PROBE A1 REVISED) |
| NORM-01 | Phase 2 (seeded with viled top-50; goldapple variants added in Phase 3) | Closed (Plan 02-03 loader + canonical_for; Plan 02-06 production seed `config/brand-aliases.yaml` with 58 canonical brands + 46 Cyrillic aliases) |
| NORM-02 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-03 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-04 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-05 | Phase 2 (modules shared with Phase 3) | Plan 02-03 |
| NORM-06 | Phase 2 (log defined; populated by real goldapple run in Phase 3) | Done (Plan 02-02 — Norm06Writer ships D-208 markdown ledger) |
| MATCH-01 | Phase 4 | Done (Plan 04-03 — strict-key SQL JOIN + D-402 symmetric filter + D-403 N→1 keep-all + D-405 source-locked formula canary) |
| MATCH-02 | Phase 4 | Done (Plan 04-01 denormalized Match SQLModel D-401 + Plan 04-03 DELETE+INSERT single TX D-410; schema amended above) |
| MATCH-03 | Phase 4 | Done (Plan 04-03 compute_denominator D-404 + Plan 04-04 orchestrator match.rate D-405 + zero-denominator guard) |
| MATCH-04 | Phase 4 | Done (Plan 04-01 [tool.ga_crawler.match] D-408 + Plan 04-04 final_threshold_gate D-409 + auto_suggest_threshold D-407 log-only) |
| DATA-01 | Phase 2 | Done (Plan 02-02 — Run + Snapshot SQLModel tables) |
| DATA-02 | Phase 2 | Done (Plan 02-02 — 18-col Snapshot table with all 13 required fields) |
| DATA-03 | Phase 2 | Done (Plan 02-02 — UNIQUE constraint + append-only writer + v_current_snapshots VIEW) |
| DATA-04 | Phase 2 | Done (Plan 02-02 — WAL PRAGMA event listener + per-batch commit) |
| DATA-05 | Phase 2 | Done (Plan 02-02 — SqliteRunWriter atomic json_patch lifecycle; try/finally orchestration in Plan 05) |
| DATA-06 | Phase 2 | Closed (Plan 02-06 — bin/backup.sh online sqlite3 .backup + 4-rotate retention per D-219; 4 integration tests verify atomic backup + retention + error path + auto-mkdir) |
| REPORT-01 | Phase 5 | Done (Plan 05-02 excel_builder.py 4-sheet workbook + D-502 SKU-level gap interpretation amendment; D-506 always-4-sheets) |
| REPORT-02 | Phase 5 | Done (Plan 05-02 — D-505 3-color CF mid_value=0 anchor + D-508 CF-on-2-sheets-only + freeze_panes + autofilter) |
| REPORT-03 | Phase 5 | Done (Plan 05-02 — D-503 Russian headers verbatim + D-504 emoji summary template source-locked; golden file canary) |
| REPORT-04 | Phase 5 | Done (Plan 05-02 summary_builder.py — reads runs.stats.match.* flat keys per Pitfall 6 + D-405 KPI verbatim + top-3 SQL ABS LIMIT + zero-match fallback) |
| REPORT-05 | Phase 5 | Done (Plan 05-03 archive.py — D-512 ISO-week + Pitfall 4 year-boundary + D-510 atomic write *.xlsx.tmp + os.replace; Plan 05-04 path-traversal containment; Plan 05-05 standalone report-run CLI per D-509) |
| REPORT-06 | Phase 5 | Done (Plan 05-03 check_size_guard flag-only D-515 + Plan 05-04 orchestrator sets report.size_guard_passed flag + log warning; xlsx persists on disk; Phase 6 DELIVER-03 cascade invariant) |
| DELIVER-01 | Phase 6 | Done (Plan 06-02 message_builder + Plan 06-03 telegram_client + Plan 06-04 orchestrator — D-601/D-602/D-614 aiogram 3.27 + FSInputFile + async-with Bot lifecycle; caption-split for summary_text>1024; Plan 06-05 wires into run_weekly via D-615/D-616) |
| DELIVER-02 | Phase 6 | Done (Plan 06-02 build_ops_alert single-template + D-610 reason-field + D-609 parse_mode=HTML + Pitfall A html.escape + Pitfall E Asia/Almaty tz + golden-file source-lock) |
| DELIVER-03 | Phase 6 | Done (Plan 06-03 evaluate_gate D-604 4-check first-fail-wins + REUSES matcher.strict_key.read_run_status D-411 helper + D-515 size_guard cascade from Phase 5) |
| DELIVER-04 | Phase 6 | Done (Plan 06-03 tenacity wait_chain(5,15,45) per RESEARCH caveat #2 + Pitfall A fail-fast classes excluded + TelegramRetryAfter outside-tenacity loop + Plan 06-04 D-606 delivery_status='undelivered_telegram_unreachable' + Plan 06-05 D-605 E2E invariant) |
| DELIVER-05 | Phase 6 | Done (Plan 06-01 .env.example D-612 + Plan 06-02 DeliverEnvConfig.from_env + Plan 06-04 D-611 asymmetric handling: token=fail-loud, chat_ids=degradable; load_dotenv ONLY in cli.py::_cmd_deliver per RESEARCH caveat #4) |
| SCHED-01 | Phase 7 | Done (Plan 07-02 deploy/etc-cron-d-ga_crawler D-708 + Plan 07-04 README §2/§4 deploy procedure; Sunday 23:00 Almaty cron row) |
| SCHED-02 | Phase 7 | Done (Plan 07-02 D-708 — CRON_TZ=Asia/Almaty first non-comment line; canary test_cron_contains_cron_tz_almaty source-locks invariant) |
| SCHED-03 | Phase 7 | Done (Plan 07-03 bin/weekly-run.sh D-709 — /start before exec + bare URL on EXIT=0 + /fail with --data-raw on EXIT≠0; D-703 fail-loud exit 4 if HC_PING_URL missing; Plan 07-04 README §5) |
| SCHED-04 | Phase 7 | Done (Plan 07-03 wrapper redirects stdout/stderr to /var/log/ga_crawler/weekly-run-YYYY-MM-DD.log + Plan 07-02 deploy/etc-logrotate-d-ga_crawler D-705 — weekly + rotate 13 + compress; D-704 _configure_logging() source unchanged) |
| SCHED-05 | Phase 7 | Done (Plan 07-04 README.md 10 H2 sections per D-707 RU-primary + Plan 07-03 bin/test-failure-alert.sh D-706 5-step orchestrator; canary test_readme_h2_order_matches_d707) |

**Coverage:**
- v1 requirements: 48 total (RECON 4 + CRAWL 6 + PARSE 6 + NORM 6 + MATCH 4 + DATA 6 + REPORT 6 + DELIVER 5 + SCHED 5)
- Mapped to phases: 48
- Closed: 47/48 (Phase 1-7 complete; only Phase 1 RECON-01 conditional plans pending — operator-deferred per Phase 1 ops backlog)
- Unmapped: 0
- Note: previous "47 total" count was an off-by-one in the initial summary; the enumerated IDs above sum to 48.

---
*Requirements defined: 2026-05-05*
*Last updated: 2026-05-05 — traceability filled by gsd-roadmapper*
*Phase 4 update: 2026-05-11 — MATCH-01..04 closed; MATCH-02 schema amended to denormalized 13-column shape per 04-CONTEXT.md D-401 + Action Items.*
*Phase 5 update: 2026-05-12 — REPORT-01..06 closed; REPORT-01 amended per 05-CONTEXT.md D-502 (Assortment gaps reinterpreted as SKU-level within brand-overlap CRAWL-02 scope since brand-level gap=∅ by construction). Plans 05-01..05-06 shipped Wave 0..5 (foundation → builders → archive → orchestrator → main_run + CLI composition → doc cascade); 6 v1 requirements satisfied bringing total to 37/48. D-514/D-515/D-405 cascade items propagated to STATE.md Accumulated Key Decisions for Phase 6 planner.*
*Phase 6 update: 2026-05-12 — DELIVER-01..05 closed; Plans 06-01..06-06 shipped Wave 0..5 (Wave 0 setup → Wave 1 foundations → Wave 2 gate+client → Wave 3 orchestrator+CLI → Wave 4 composition+E2E → Wave 5 doc cascade). Phase 6 closure unblocks Phase 7 (Scheduler + Observability Hardening) — SCHED-01..05 inheritance points: D-605 delivery_status decoupling, D-606 6-value enum for Healthchecks SCHED-03 routing, D-607 8-key deliver.* namespace, D-608 `deliver-run --run-id N` standalone recovery tool, D-611 asymmetric ENV handling. New dep: aiogram>=3.27,<4.0.*
*Phase 7 update: 2026-05-12 — SCHED-01..05 closed; Plans 07-01..07-05 shipped Wave 1..4 (Wave 1 source-lock canaries → Wave 2 deploy templates + bash wrappers parallel → Wave 3 README operator runbook → Wave 4 doc cascade close-out). Phase 7 closes v1: 47/48 v1 requirements satisfied (only Phase 1 RECON-01 conditional plans remain — operator-deferred per spike MEMO). Phase 7 ships ZERO production Python — operator-facing artifacts only (deploy/etc-cron-d-ga_crawler + deploy/etc-logrotate-d-ga_crawler + .env.example HC_PING_URL line + bin/weekly-run.sh + bin/test-failure-alert.sh + README.md 10 H2 sections). v2 backlog gains INFRA-V2-04 per D-710 (Docker image deferred — Camoufox Firefox 135 incompatible with mcr.microsoft.com/playwright/python:v1.57.0-noble Chromium-based). D-701/D-708/D-709/D-710 cascade persisted to STATE.md Accumulated Key Decisions.*
