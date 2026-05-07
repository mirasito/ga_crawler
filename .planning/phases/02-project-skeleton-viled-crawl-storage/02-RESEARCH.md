# Phase 2: Project Skeleton + viled Crawl + Storage — Research

**Researched:** 2026-05-07
**Domain:** SQLModel/SQLite storage layer + curl_cffi viled crawler + shared parser/normalizer modules
**Confidence:** HIGH (stack locked in CLAUDE.md + Phase 3 frozen interfaces; LOW only on viled `__NEXT_DATA__` exact paths and catalog/1310 enumeration mechanism — Wave 0 probe required)

## Summary

Phase 2 строит реальную имплементацию четырёх Phase 2 Protocols, замороженных Phase 3 в `src/ga_crawler/interfaces.py` (BrandAlias / Normalizer / SnapshotWriter / RunWriter), и краулер viled.kz Tier 0 через `curl_cffi`. Контракт жёсткий: всё, что Phase 3 уже потребляет через 4 stub'а в `cli.py` (StubBrandAlias / StubNormalizer / StubSnapshotWriter / StubRunWriter), должно сохранить семантическую эквивалентность за теми же Protocol'ами. Stub'ы потом удаляются (D-212), их роль в тестах перехватывается mocks из `tests/conftest.py`.

Ключевые архитектурные оси: (1) immutable snapshot table `(run_id, retailer, sku_id)` UNIQUE с WAL и атомарным `json_patch` на `runs.stats` — Pitfall 6 атомарного merge между viled.* и goldapple.* пространствами имён; (2) `curl_cffi impersonate="chrome"` с tenacity 3-attempt + exponential jitter, sequential `time.sleep(2)` (NO async) для viled — спайк подтвердил 15/15 success at 2s pause; (3) catalog/1310 enumeration через `__NEXT_DATA__` pagination на 2 endpoint'ах — НЕ через sitemap (sitemap=42k luxury без category metadata); (4) shared parser interface через `ParseDispatcherProtocol` совместим с goldapple microdata parser из Phase 3 — viled добавляет `__NEXT_DATA__` ветку; (5) layered volume normalizer (regex tokenize → unit-table → multipack-detect) и flat-dict YAML brand-alias seeded из spike payloads.

**Primary recommendation:** Идти Wave-by-Wave: Wave 0 — pyproject namespace + schema bootstrap + probe-crawl одного `/men/catalog/1310` URL для верификации D-217 stock-state paths и enumeration mechanism (D-224 кандидаты в порядке приоритета). Wave 1 — storage (SQLModel + WAL + json_patch). Wave 2 — normalizers (3 модуля + YAML loader). Wave 3 — viled enumeration + fetcher + parser. Wave 4 — orchestrator `runners/viled_run.py` + интеграция с CLI. Wave 5 — gates (sanity-N + parse-quality) + Norm06Writer + sanity-test corpus. Wave 6 — backup script + integration test E2E против fixture HTML. Stub cutover (D-212) в финальной wave после зелёных тестов.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sanity-gate N for viled (CRAWL-05):**
- **D-201:** Auto-suggest after 4 weeks pattern, seed N=100 static (revised 2026-05-07 после scope-narrowing). Mirror D-310 from Phase 3 для goldapple. Conservative catastrophic-failure detector для beauty-only sub-catalog (~30-40% от ожидаемого SKU-count). Со 5-й недели и далее run эмитит ops-Telegram сообщение `new N-rec for viled: 0.7 × 4-week-median viled_count = X` после каждого успешного run. Operator решает поднимать N через PR в config. NEVER auto-tune.
- **D-202:** Static N storage location: `pyproject.toml [tool.ga_crawler.crawl.viled] sanity_gate_n` — consistent с Phase 3 layout. Operator override через CLI `--sanity-gate-n`.
- **D-203:** Auto-suggest mechanic shared с Phase 3 D-310: вынести `auto_suggest_threshold(history, factor=0.7, min_runs=4)` из `runner/gates.py` (currently goldapple-specific) в retailer-agnostic helper, либо параметризовать. Default: refactor — DRY winning over isolation на v1.

**Brand-alias YAML format (NORM-01):**
- **D-204:** Location `config/brand-aliases.yaml` (top-level, новая директория Wave 0). NOT in-src, NOT data/.
- **D-205:** Schema: flat dict `{brand_norm: [aliases...]}`. Никакой richer-schema (canonical, category) на v1.
- **D-206:** Seed mechanism: planner extracts top-50 viled brands из spike artifacts. Источники в порядке приоритета: (a) `viled-fetch-results.json` (15 fetched products); (b) `viled-home-brands-extract.json` (homepage brand-list); (c) первые ~50 product fetches Wave 0 probe-crawl. Manual RU/EN-варианты для брендов с явным кириллическим вариантом.
- **D-207:** Runtime reload: read-once at run start. Никакого hot-reload / file-watcher.

**NORM-06 review queue format:**
- **D-208:** File-based: `.planning/runs/{run_id}/norm06-review.md` markdown table per run. Schema: `brand_or_slug | source (viled-unmatched | goldapple-new-slug) | run_id | status (pending | aliased | skip | reviewed)`.
- **D-209:** Operator workflow: edit md в Obsidian/editor, добавить alias в YAML / mark `skip` / `reviewed`. Никаких automated workflows.
- **D-210:** NO DB-table backup на v1. Audit trail через git history.
- **D-211:** Phase 3 stub cli.py больше не пишет review-queue в Stubs. Phase 2 owns NEW write-path: после Phase 3 forward-NORM-06 + Phase 3 reverse-NORM-06 emit, оркестратор вызывает `Norm06Writer.persist(run_id, viled_unmatched, goldapple_new_slugs)`. Counter в `runs.stats` остаётся.

**Stub cutover + module structure:**
- **D-212:** Delete Stubs from `cli.py` after Phase 2 ships real impls. Их функция (testability) переходит в `tests/conftest.py` mocks. Никакого `--dev-stubs` flag.
- **D-213:** viled fetcher/parser mirror goldapple structure: `fetchers/viled.py`, `parsers/viled_nextdata.py`, `enumeration/viled_sitemap.py`, `runners/viled_run.py` (см. Phase 2 plan для уточнения, sitemap → catalog enumeration после D-223).
- **D-214:** Storage: single `src/ga_crawler/storage/sqlite.py` module — SQLModel tables (Run, Snapshot) + atomic helpers (`patch_stats` через raw SQL `json_patch`, `BrandAliasYamlLoader`, `Norm06Writer`). 200-300 LOC ожидаемо. Refactor если перешагнём 500 LOC.
- **D-215:** Shared normalizers: `src/ga_crawler/normalizers/{brand,name,volume}.py` — три модуля. Volume parser layered: regex tokenize → unit-table lookup → multipack-detect. Multipack flag persists в snapshot row (PARSE-04 + multipack_flag). Unparseable volume → `volume_norm=NULL`, `multipack_flag=False`, parse_error_flag=True; row не блокирует insert.
- **D-216:** Brand-alias loader: `src/ga_crawler/alias/yaml_loader.py` — single class `YamlBrandAlias(BrandAliasProtocol)`.

**PARSE-06 stock-state mapping (D-217):** виледовский `__NEXT_DATA__` mapping — `attributes.in_stock == true → IN_STOCK`, `false → OUT_OF_STOCK`, HTTP 404 → DELISTED, 301/302 redirect → URL_CHANGED, exception/parse-fail → UNKNOWN, `attributes.availability == "preorder"` → UNAVAILABLE. **MEDIUM confidence — Wave 0 верифицирует против `viled-nextdata-shape.json`.**

**PARSE-05 hard-fail invariant (D-218):** Aggregate post-crawl gate, parallel CRAWL-05 N-gate. >5% null on required fields (name OR current_price OR url) → `runs.status='failed'`, reason='parse_quality_below_threshold'. Either gate failing fails run-to-completion. Snapshot rows still persist (audit trail).

**DATA-06 backup (D-219):** Phase 2 creates `backups/` directory + `bin/backup.sh` (online `sqlite3 .backup`, atomic). Retention 4 (`ls -t backups/*.db | tail -n +5 | xargs rm -f`). Phase 7 ops-playbook добавляет cron entry.

**Schema migrations (D-220):** Skip alembic on day 1. Add при первой миграции (v2).

**CRAWL-01 viled brand list provenance (D-221):** Brand list = derived from `v_current_snapshots WHERE retailer='viled' AND run_id=:current`. SQL view создаётся Wave 0.

**CRAWL-01 viled enumeration (D-223..D-227):**
- D-223: Catalog-page enumeration, NOT sitemap-only. Endpoints: `/men/catalog/1310` + `/women/catalog/1310`.
- D-224: Mechanism TBD Wave 0 probe. Кандидаты в приоритете: (1) `__NEXT_DATA__` pagination на category page; (2) HTML pagination fallback; (3) Internal Next.js API `/_next/data/{buildId}/...`. Все Tier 0.
- D-225: Per-catalog rate-limit + concurrency=1 across both endpoints. 2s pause между fetch'ами. Catalog-1 (men) → catalog-2 (women) sequentially.
- D-226: Expected URL pool ~100-600 SKUs (refined Wave 0 probe).
- D-227: Catalog endpoint URLs в `pyproject.toml [tool.ga_crawler.crawl.viled] catalog_urls = [...]`. Operator-managed.

**Test infrastructure (D-222):** Inherit Phase 3 conftest.py (11 fixtures) без изменений. Добавить: `viled_pdp_html` (load из spike sample-payloads), `brand_alias_yaml_fixture`, `in_memory_sqlite_session`. respx НЕ используется для curl_cffi (incompat per Phase 3 D-302); monkey-patch `_fetch_xml`-style wrapper functions.

### Claude's Discretion

- **Module organization for shared utilities**: split `normalizers/{brand,name,volume}.py` (3 файла) vs single `normalizers.py` — оставлено планеру. Default: split.
- **Specific volume unit-table contents** (full mapping `мл/ml/милилитр → ml`, `oz/унция → oz`, etc.) — оставлено планеру.
- **HTTP retry classes для curl_cffi** — оставлено планеру. Mirror Phase 3 tenacity policy (`stop_after_attempt(3) + wait_exponential_jitter(2, 30)`).
- **viled `__NEXT_DATA__` JSON paths**: точные dot-paths для `name`, `brand`, `current_price`, `was_price`, `volume_raw`, `availability`, `sku_id` — оставлено планеру, extract from `viled-nextdata-shape.json` + Wave 0 probe.
- **Concurrency=1 vs sequential async для viled curl_cffi**: viled rate-limit 2s sequential = single-thread sufficient. Default: sync `for` loop с `time.sleep(2)` (NOT async).
- **JSONB column type**: SQLite не имеет native JSONB; используется TEXT с JSON-validation на app-side. Default: TEXT-encoded JSON в `runs.stats` column, raw SQL `json_patch(stats, ?)` в `RunWriter.patch_stats`.

### Deferred Ideas (OUT OF SCOPE)

- `--dev-stubs` flag для production CLI — runtime divergence = risk
- Richer brand-alias YAML schema (canonical, category, taxonomy) — v2 territory
- Auto-tune `sanity_gate_n` — навсегда отвергнуто, auto-suggest only
- DB-table backup для NORM-06 review queue — markdown + git history достаточно
- Persistent `goldapple_count + viled_count` separate table — `runs.stats` json_patch достаточно
- Hot-reload brand-alias YAML during run
- Storage split на 3 файла (`storage/{runs,snapshots,stats}.py`)
- alembic с day 1
- VACUUM INTO для backup
- Cron entry для backup в Phase 2 (Phase 7)
- Async curl_cffi для viled (открыто, default sync)
- viled JSON-LD parser fallback (empirical 0/15)
- CRAWL-01 brand-list extraction отдельный шаг
- Multipack handling beyond flag (price-per-unit splitting, kit decomposition)
- Camoufox для viled fallback
- Real-time viled probe (mid-week health check)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DATA-01** | SQLite-схема: `runs`, `snapshots` (UNIQUE `(run_id, retailer, sku_id)`), `matches` (Phase 4 stub) | §SQLModel Schema; tables Run, Snapshot defined with indices |
| **DATA-02** | Snapshots хранят `current_price`, `was_price`, `currency`, `stock_state` enum, `url`, `name`, `brand`, `volume_raw`, `brand_norm`, `name_norm`, `volume_norm`, `multipack_flag`, `scraped_at` | §SQLModel Schema; full Snapshot model with all 13 fields |
| **DATA-03** | Все записи immutable; "current view" через SQL `v_current_snapshots` | §SQLModel Schema §SQL Views; SnapshotWriter — append-only INSERT, no UPDATE |
| **DATA-04** | WAL mode включён; per-run транзакции; on-failure rollback не теряет уже сохранённые SKU | §PRAGMAs and Transactions; per-batch (NOT per-run) commit pattern |
| **DATA-05** | `runs` row создаётся в начале запуска и **обязательно** обновляется в конце во всех ветках | §RunWriter contract; `create()` at start + `finalize(status, reason)` in `try/finally`-equivalent; mirror Phase 3 PhaseResult pattern |
| **DATA-06** | Nightly backup БД в отдельную директорию (минимум 4 последних) | §Backup; `bin/backup.sh` shell + `backups/` dir + 4-rotate logic |
| **CRAWL-01** | Краулер обходит beauty+парфюмерия каталог viled.kz (`/men/catalog/1310` + `/women/catalog/1310`, через пагинацию) и собирает список URL продуктов | §viled Enumeration Strategy; `__NEXT_DATA__` page-1 → totalCount/pageSize → enumerate `?page=2..N` |
| **CRAWL-03** | Per-SKU isolation — падение одного продукта не валит весь запуск | §Per-SKU Isolation; `fetch_one_isolated` wrapper from Phase 3 — reuse pattern verbatim |
| **CRAWL-04** | Retry с экспоненциальной задержкой и jitter для временных сбоев (HTTP 5xx, таймауты) | §Tenacity Policy; `stop_after_attempt(3) + wait_exponential_jitter(2, 30) + retry_if_exception_type((curl_cffi.requests.errors.*, Timeout))` |
| **CRAWL-05** | Sanity-assertion после краула: `viled_count > N`; меньше — `runs.status = 'failed'` | §Sanity Gate; `final_n_gate(count, N)` retailer-agnostic helper from goldapple `final_m_gate` refactor (D-203) |
| **CRAWL-06** | Краулер уважает заданный rate-limit; параметры конфигурируются | §Rate Limit; `time.sleep(2)` between fetches; pyproject `pause_seconds=2.0` |
| **PARSE-01** | Парсер для каждого ритейлера извлекает: название, бренд, объём/вес, текущую цену, цену до скидки, наличие, URL, валюту | §viled __NEXT_DATA__ Field Paths; full path table per spike viled-nextdata-shape.json |
| **PARSE-02** | JSON-LD `Product.offers.price` имеет приоритет над CSS-селекторами | §Parser Strategy; for viled INVERTED — `__NEXT_DATA__` first (0/15 JSON-LD per spike); ParseDispatcher protocol routes |
| **PARSE-03** | Парсер отвергает поля вида `*old*`, `*was*`, `*crossed*`, `*club*`, `*gold*`, `*from*` при выборе `current_price` | §Parser Strategy; viled current_price = `attributes[0].realPrice` (current after discount), was_price = `attributes[0].price` (full price); `realPrice` is the explicit current per spike "viled was_price requirement v1 schema satisfiable from week 1 via realPrice field" |
| **PARSE-04** | Sanity-check цены: `100 ≤ price ≤ 1_000_000 ₸`; вне диапазона — поле помечается как ошибка парсинга | §Parser Strategy; sanity range applied при extraction (mirror Phase 3 `_extract_top_level_offer`) |
| **PARSE-05** | Hard-fail invariant — если у >5% продуктов нет обязательного поля → `failed` | §Parse Quality Gate; aggregate gate в `viled_run.py` (D-218); reason='parse_quality_below_threshold' |
| **PARSE-06** | Стек состояния — enum (`IN_STOCK`, `OUT_OF_STOCK`, `UNAVAILABLE`, `DELISTED`, `URL_CHANGED`, `UNKNOWN`); хранится в схеме как enum | §Stock-State Mapping (D-217); SQLModel String + Pydantic Literal validator |
| **NORM-01** | Brand-alias таблица (YAML) сопоставляет Cyrillic ↔ Latin варианты; seeded топ-50 брендами viled | §YamlBrandAlias; flat-dict schema + spike-payload seeding |
| **NORM-02** | Нормализация бренда: NFKD + accent strip + lowercase + alias lookup → `brand_norm` | §normalizers/brand.py; reuse `_normalize_punct` from `enumeration/slug.py` (already accent-strip + NFKD) |
| **NORM-03** | Volume value-object `(amount, unit, multipack)`; парсит `30 мл`, `30мл`, `30ml`, `1.0 oz`, `3 шт x 50мл`, `Set of 3 × 50ml` | §normalizers/volume.py; layered regex grammar with full corpus |
| **NORM-04** | Multipack/kit детектится явно; для v1 такие SKU **исключаются** из price-per-unit-сравнения и помечаются флагом | §Multipack Detection; regex `(\d+)\s*[xх×]\s*\d+`, `Set of (\d+)`, `(\d+)\s*шт`, also keyword `набор`, `kit`, `комплект` |
| **NORM-05** | Нормализация имени: lowercase + удаление пунктуации + collapse whitespace → `name_norm` | §normalizers/name.py; reuse `_normalize_punct` minus the apostrophe-strip nuance |
| **NORM-06** | Лог "бренды на goldapple, не найденные в alias-таблице" — еженедельная очередь ручной проверки | §Norm06Writer; markdown table writer per D-208 schema |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| viled HTML fetch + retry | Crawl (curl_cffi Tier 0) | — | Locked: `impersonate="chrome"`, 2s sequential, 15/15 spike success |
| viled `__NEXT_DATA__` parsing | Parse (viled-nextdata) | — | Spike confirms 15/15 `__NEXT_DATA__` present, 0/15 JSON-LD; selectolax + json.loads |
| Catalog/1310 enumeration | Crawl (paginated) | Parse | Page-1 fetch → parse `__NEXT_DATA__.pageProps` → derive page count → fetch remaining |
| Brand normalization (NFKD+accent+alias) | Normalize | Alias loader | Pure-string transform; alias YAML lookup follows |
| Volume parsing (regex + multipack) | Normalize | — | Pure-string transform; outputs `(amount, unit, multipack_flag)` |
| Snapshot persistence | Storage (SQLModel + WAL) | — | Append-only INSERT keyed `(run_id, retailer, sku_id)` UNIQUE |
| Run lifecycle (open/finalize) | Storage (RunWriter) | Orchestrator | `runs` row created Phase 2 viled side; Phase 3 patches stats only |
| Stats merge across phases | Storage (raw SQL `json_patch`) | — | Atomic merge between viled.* and goldapple.* keys (Pitfall 6) |
| Sanity gates (N-count, parse-quality) | Gate (post-crawl hook) | Orchestrator | Two sequential gates; either failing → `runs.status='failed'` |
| NORM-06 review queue | Storage (markdown writer) | Orchestrator | File-based, operator-facing markdown ledger |
| Backup | Ops (shell script) | — | `bin/backup.sh` shipped Phase 2; cron entry Phase 7 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `curl_cffi` | `>=0.15,<0.16` (already pinned) | HTTP client с TLS-fingerprint impersonation | Locked CLAUDE.md; spike 15/15 success at viled `impersonate="chrome"` [VERIFIED: pyproject.toml] |
| `selectolax` | `>=0.3,<0.4` (already pinned) | HTML parsing | Locked CLAUDE.md; Phase 3 already uses; ~30x faster than BS4 [VERIFIED: pyproject.toml] |
| `sqlmodel` | `>=0.0.24,<0.1` (already pinned) | ORM (SQLAlchemy 2 + Pydantic 2) | Locked CLAUDE.md; same models for schema + validation [VERIFIED: pyproject.toml] |
| `pydantic` | `>=2.10,<3.0` (already pinned) | Data validation | Locked CLAUDE.md; SQLModel underlying validator [VERIFIED: pyproject.toml] |
| `tenacity` | `>=9.0,<10.0` (already pinned) | Retry decorator | Locked CLAUDE.md; Phase 3 fetcher uses `stop_after_attempt(3) + wait_exponential_jitter(2, 30)` [VERIFIED: pyproject.toml] |
| `structlog` | `>=25.0,<26.0` (already pinned) | Structured logging | Locked CLAUDE.md; Phase 3 fetcher already uses [VERIFIED: pyproject.toml] |
| `python-dotenv` | `>=1.0,<2.0` (already pinned) | Load .env for tokens/proxies | Locked CLAUDE.md [VERIFIED: pyproject.toml] |
| `PyYAML` | new dependency, `>=6.0,<7.0` | Parse `config/brand-aliases.yaml` | Standard for YAML in Python; trivially small [CITED: pypi.org/project/PyYAML] |

### Supporting (existing dev group)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | `>=8,<9` | Test runner | Already pinned [VERIFIED: pyproject.toml] |
| `pytest-asyncio` | `>=0.24` | async test support | Already pinned; Phase 2 viled side is sync but orchestrator may compose async [VERIFIED: pyproject.toml] |
| `pytest-mock` | `>=3.14` | Mocker fixture | Already pinned; for SnapshotWriter / RunWriter mocks beyond MagicMock [VERIFIED: pyproject.toml] |
| `respx` | `>=0.21` | HTTPX mocking | **Phase 2 NOT used** — D-302 Phase 3 documented respx incompat with curl_cffi. Use monkey-patch on `_fetch_xml`/`_fetch_html` wrapper functions instead [VERIFIED: 03-CONTEXT D-302 + pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| flat-dict YAML | richer-schema YAML (canonical/category) | v2 territory; flat-dict additive-extensible without migration [LOCKED: D-205] |
| sync `for` loop + `time.sleep(2)` | async `curl_cffi.requests.AsyncSession` + `asyncio.sleep` | Symmetry с goldapple async stack vs simpler sync code; default sync [LOCKED: D-225 / Discretion §Concurrency] |
| `json_patch` raw SQL | UPDATE on Python-merged dict | json_patch is atomic at SQL level — no race between Phase 2 viled writer and Phase 3 goldapple writer if they ever run in parallel; UPDATE round-trip is non-atomic [VERIFIED: sqlite.org/json1.html] |
| separate `prices` history table | snapshot row contains current+was inline | Strict v1 schema is single `snapshots` table per DATA-01..03; history = different `run_id` rows [LOCKED: DATA-01..03] |

**Installation (incremental):**
```bash
uv add pyyaml
# All other deps already pinned in pyproject.toml
```

**Version verification (planner Wave 0):**
```bash
# pyyaml: latest 6.0.x
uv pip show pyyaml || uv add pyyaml
# Verify against PyPI:
# https://pypi.org/project/PyYAML/  (latest 6.0.2 as of 2024-12, expect 6.0.x stable through 2026)
```

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    python -m ga_crawler weekly-run                   │
│                                                                      │
│  cli.py (argparse) → runners/main_run.py (composes both retailers)   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Step 1: storage.RunWriter.create(run_id) → INSERT runs row      │ │
│  │   (DATA-05 — fail-loud if can't open run)                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│              ↓                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Step 2: viled_run.run_viled_phase()  (NEW Phase 2 module)       │ │
│  │   2a. enumeration/viled_sitemap.fetch_catalog_urls()             │ │
│  │       (curl_cffi → 2 catalog/1310 endpoints → __NEXT_DATA__      │ │
│  │        pagination → flat list of /item/{id} URLs)                │ │
│  │   2b. for url in urls (sequential, 2s pause, per-SKU isolated):  │ │
│  │       fetcher.fetch_one(url) → raw_html (curl_cffi+tenacity)     │ │
│  │       parser.dispatch('viled', html) → ViledRawProduct           │ │
│  │       normalizer.brand/name/volume(...)                          │ │
│  │       snapshot_writer.append(run_id, 'viled', records[batch])    │ │
│  │   2c. parse_quality gate (D-218): >5% null → failed              │ │
│  │   2d. final_n_gate (D-201): viled_count < N=100 → failed         │ │
│  │   2e. run_writer.patch_stats(run_id, viled.* delta)              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│              ↓                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Step 3: read v_current_snapshots WHERE retailer='viled'         │ │
│  │   → distinct brand_norm list → goldapple_run viled_brands input │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│              ↓                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Step 4: runners/goldapple_run.run_goldapple_phase() (existing) │ │
│  │   passes the SAME run_id, REAL Phase 2 protocols (no stubs)     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│              ↓                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Step 5: Norm06Writer.persist(run_id, viled_unmatched,            │ │
│  │           goldapple_new_slugs)                                  │ │
│  │   → .planning/runs/{run_id}/norm06-review.md                    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│              ↓                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Step 6: storage.RunWriter.finalize(run_id, status='success'/'failed') │
│  │   IDEMPOTENT — call from try/finally so even crash records      │ │
│  │   status='failed' with stack-trace reason                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘

External:
  config/brand-aliases.yaml         (operator-edited; read-once at run start)
  pyproject.toml [tool.ga_crawler.crawl.viled]   (operator-edited)
  prices.db (WAL+shm+wal files)     (single SQLite file under repo root or /var)
  backups/{YYYY-MM-DD}.db           (cron Phase 7)
  .planning/runs/{run_id}/          (norm06-review.md + sitemap-slugs.txt + runs.json[stub])
  /var/log/ga_crawler/*.log         (structlog JSON sink)
```

### Recommended Project Structure

```
src/ga_crawler/
├── __main__.py                    # existing — runs cli.main()
├── cli.py                         # MODIFY: stub Phase 2 impls REPLACED
│                                  # by real imports; new `weekly-run` subcommand
├── interfaces.py                  # FROZEN — do not modify
├── config.py                      # NEW: load pyproject.toml [tool.ga_crawler.crawl.viled]
│                                  # + .env via dotenv; expose ViledConfig dataclass
├── enumeration/
│   ├── __init__.py                # existing
│   ├── slug.py                    # existing — REUSE _normalize_punct in normalizers/
│   ├── goldapple_sitemap.py       # existing — DO NOT MODIFY (frozen Phase 3)
│   └── viled_catalog.py           # NEW: catalog/1310 page enumeration
│                                  # (was "viled_sitemap.py" in D-213; rename for accuracy)
├── fetchers/
│   ├── __init__.py                # existing
│   ├── goldapple.py               # existing — DO NOT MODIFY
│   └── viled.py                   # NEW: ViledFetcher (curl_cffi + tenacity, sync)
├── parsers/
│   ├── __init__.py                # existing
│   ├── goldapple_microdata.py     # existing — DO NOT MODIFY
│   ├── viled_nextdata.py          # NEW: __NEXT_DATA__ extractor + ViledRawProduct
│   ├── dispatcher.py              # NEW: ParseDispatcher concrete impl (Protocol-conforming)
│   └── types.py                   # NEW: shared StockState enum + ParsedProduct dataclass
├── normalizers/
│   ├── __init__.py                # NEW
│   ├── brand.py                   # NEW: NORM-02 (NFKD+accent+lower+alias_lookup)
│   ├── name.py                    # NEW: NORM-05 (lower+strip-punct+collapse-ws)
│   ├── volume.py                  # NEW: NORM-03+04 (Volume VO + multipack-detect)
│   └── facade.py                  # NEW: Normalizer class implementing NormalizerProtocol,
│                                  #      composes brand/name/volume + holds YamlBrandAlias ref
├── alias/
│   ├── __init__.py                # NEW
│   └── yaml_loader.py             # NEW: YamlBrandAlias(BrandAliasProtocol) — D-216
├── storage/
│   ├── __init__.py                # NEW
│   ├── sqlite.py                  # NEW: SQLModel models (Run, Snapshot) + WAL session +
│   │                              #      SnapshotWriter, RunWriter (D-214 — single module)
│   └── norm06_writer.py           # NEW: Norm06Writer.persist() — markdown ledger
├── runner/                        # existing dir — DO NOT RENAME
│   ├── __init__.py                # existing
│   ├── gates.py                   # MODIFY: extract `auto_suggest_threshold(history,
│   │                              #         factor=0.7, min_runs=4)` retailer-agnostic
│   │                              #         (D-203 refactor); add `final_n_gate` if needed
│   │                              #         OR generalize `final_m_gate(count, threshold)`
│   └── stats.py                   # MODIFY: add ViledStatsBuilder mirror of
│                                  #         GoldappleStatsBuilder (parallel namespace
│                                  #         pattern); consider extracting NamespaceStatsBuilder
│                                  #         base class
├── runners/                       # existing dir
│   ├── __init__.py                # existing
│   ├── goldapple_run.py           # existing — DO NOT MODIFY (frozen)
│   ├── viled_run.py               # NEW: run_viled_phase() — mirror of goldapple_run
│   │                              #      structure; sync inside, async-await wrapper for
│   │                              #      orchestrator symmetry
│   └── main_run.py                # NEW: end-to-end weekly run; composes viled→goldapple→
│                                  #      norm06_writer→finalize; owns runs row lifecycle
└── gates/                         # NEW dir (or merge into runner/) — Claude's discretion
    ├── __init__.py
    ├── parse_quality.py           # NEW: parse-quality gate (D-218; >5% null)
    └── sanity_n.py                # NEW: viled-side sanity gate (D-201)
                                   # (or live in runner/gates.py; minor preference)

config/
└── brand-aliases.yaml             # NEW dir + file (D-204) — operator-edited, in git

bin/
└── backup.sh                      # NEW: D-219 SQLite online backup + 4-rotate

backups/                           # NEW dir, gitignored
└── .gitkeep

tests/
├── conftest.py                    # MODIFY: add viled_pdp_html, viled_catalog_html,
│                                  #         brand_alias_yaml_fixture, in_memory_sqlite_session
├── fixtures/
│   ├── goldapple/                 # existing
│   ├── viled/                     # NEW
│   │   ├── viled-pdp-407682.html  # NEW: capture from spike (or first probe)
│   │   ├── viled-catalog-men-1310-page1.html  # NEW: probe Wave 0
│   │   ├── viled-nextdata-shape.json    # COPY from spike
│   │   └── brand-aliases-fixture.yaml   # NEW: small test seed
│   └── normalize/
│       └── volume-corpus.yaml     # NEW: test corpus (criteria #4 success)
├── unit/
│   ├── test_volume_normalizer.py     # NEW
│   ├── test_brand_normalizer.py      # NEW
│   ├── test_name_normalizer.py       # NEW
│   ├── test_yaml_brand_alias.py      # NEW
│   ├── test_viled_nextdata_parser.py # NEW
│   ├── test_viled_catalog_paginate.py # NEW
│   ├── test_parse_dispatcher.py      # NEW
│   ├── test_storage_models.py        # NEW (SQLModel column types, FK)
│   ├── test_run_writer.py            # NEW (json_patch atomic merge)
│   ├── test_snapshot_writer.py       # NEW (append-only invariant)
│   ├── test_norm06_writer.py         # NEW (markdown format)
│   ├── test_parse_quality_gate.py    # NEW
│   └── test_sanity_n_gate.py         # NEW
└── integration/
    ├── test_storage_wal.py           # NEW (PRAGMA WAL + concurrent reads)
    ├── test_v_current_snapshots.py   # NEW (SQL view returns latest run only)
    ├── test_viled_fetcher_mocked.py  # NEW (monkey-patch curl_cffi.requests.get)
    ├── test_viled_run_e2e_with_real_storage.py  # NEW (in-memory SQLite + fixture HTML)
    └── test_main_run_e2e.py          # NEW (viled phase + goldapple phase composed,
                                      #      real Phase 2 storage, mock fetchers)
```

### Pattern 1: viled `__NEXT_DATA__` Field Paths (Pydantic-validated)

**What:** Phase 2 viled parser extracts product fields from inline `<script id="__NEXT_DATA__" type="application/json">` payload (NOT JSON-LD; spike confirmed 0/15 JSON-LD presence).

**When to use:** Every viled `/item/{id}` response (PDP) AND every `/men/catalog/1310?page=N` response (for enumeration + initial product list extraction).

**Authoritative paths (verified against `viled-nextdata-shape.json`):**

| Field | Path | Notes |
|-------|------|-------|
| sku_id | URL `/item/(\d+)` regex group | 6-digit numeric ID per `viled-product-urls.txt` |
| name | `props.pageProps.item.name` | string, e.g. "Кружевное боди" [VERIFIED: viled-nextdata-shape.json] |
| brand_raw | `props.pageProps.item.brandName` | string, e.g. "Alice+Olivia" [VERIFIED] |
| **current_price** | `props.pageProps.attributes[0].realPrice` | int, KZT [VERIFIED + STATE.md "viled was_price requirement v1 schema satisfiable from week 1 via realPrice field"] |
| **was_price** | `props.pageProps.attributes[0].price` | int — original price before discount; equal to realPrice if no discount; emit None if equal [ASSUMED — Wave 0 verifies; the shape file shows price=187700 + realPrice=187700 (no-discount product) so both presence is confirmed; DISCOUNTED products inferred] |
| currency | `props.pageProps.attributes[0].currency` | "₸" → hardcode normalize to "KZT" [VERIFIED + STATE.md "viled currency: ₸ → KZT hardcoded"] |
| volume_raw | `props.pageProps.item.name` (passthrough); volume regex extracted by NORM-03 | beauty SKUs likely have "30 мл" / "100ml" / "1.0 oz" suffix; CLOTHING items (out-of-scope per D-223) have no volume |
| availability | `props.pageProps.attributes[0].in_stock` (boolean) → enum mapping per D-217 | **Path ASSUMED — D-217 caveat:** the shape file shows `attributes[0]` has fields `id, price, realPrice, currency, itemImages, enableDiscount, attributes, article, namePlates`. **`in_stock` field NOT visible in the captured shape** — Wave 0 probe MUST verify exact field name (might be `count`, `purchaseType`, `enableDiscount`, or absent and inferred from `count > 0`) |
| url | request URL passthrough | canonical |

**Multi-attributes handling:** `attributes` is a LIST (len=2 for the captured fixture) — typically one per size variant. **Recommendation:** for Phase 2 v1, use `attributes[0]` as the canonical price source; emit one snapshot row per `(sku_id, retailer)` (NOT per size variant). Document this as a known limitation if size-level price differences materialize in the wild.

**Code skeleton:**

```python
# parsers/viled_nextdata.py
import json
from dataclasses import dataclass
from typing import Optional
from selectolax.parser import HTMLParser

@dataclass(frozen=True)
class ViledRawProduct:
    sku_id: str
    url: str
    name: str
    brand_raw: str
    current_price: int  # realPrice
    was_price: Optional[int]  # price; None if equal to realPrice
    currency: str  # "KZT"
    availability: str  # "IN_STOCK" | "OUT_OF_STOCK" | "UNAVAILABLE" | "UNKNOWN"
    raw_volume_text: Optional[str]  # passthrough name; NORM-03 owns regex

def _extract_next_data(html: str) -> Optional[dict]:
    tree = HTMLParser(html)
    node = tree.css_first('script#__NEXT_DATA__')
    if node is None:
        return None
    try:
        return json.loads(node.text())
    except json.JSONDecodeError:
        return None

def parse_pdp(html: str, url: str) -> Optional[ViledRawProduct]:
    nd = _extract_next_data(html)
    if nd is None:
        return None
    try:
        page_props = nd["props"]["pageProps"]
        item = page_props["item"]
        attrs = page_props["attributes"]
        if not attrs:
            return None
        a0 = attrs[0]
        current_price = int(a0["realPrice"])
        if not (100 <= current_price <= 1_000_000):  # PARSE-04
            return None
        full_price = int(a0.get("price", current_price))
        was_price = full_price if full_price > current_price else None
        currency = "KZT" if a0.get("currency", "").strip() in ("₸", "KZT") else a0.get("currency", "KZT")
        # D-217: Wave 0 probe must verify exact path for in_stock
        in_stock_raw = a0.get("in_stock")  # ASSUMED — verify
        if in_stock_raw is True:
            availability = "IN_STOCK"
        elif in_stock_raw is False:
            availability = "OUT_OF_STOCK"
        else:
            availability = "UNKNOWN"
        # Extract sku_id from URL: /item/407682 -> "407682"
        sku_id = url.rstrip("/").rsplit("/", 1)[-1]
        return ViledRawProduct(
            sku_id=sku_id,
            url=url,
            name=item["name"],
            brand_raw=item["brandName"],
            current_price=current_price,
            was_price=was_price,
            currency=currency,
            availability=availability,
            raw_volume_text=item["name"],  # pass full name; NORM-03 extracts
        )
    except (KeyError, TypeError, ValueError):
        return None
```

### Pattern 2: Catalog/1310 Pagination (D-224 candidates)

**Strategy (planner Wave 0 — probe-then-pick):**

1. **First probe:** Fetch `/men/catalog/1310` page-1 with `curl_cffi impersonate="chrome"`. Inspect `__NEXT_DATA__`:
   - Look for `props.pageProps.products[]` (list of product cards) — likely
   - Look for `props.pageProps.totalCount` or `pageProps.pagination.{total,perPage,currentPage}` — likely
   - Look for build identifier in `buildId` top-level key — present per `viled-nextdata-shape.json`

2. **If `__NEXT_DATA__` has products + total:**
   ```python
   def fetch_catalog_urls(catalog_base: str) -> list[str]:
       page1_html = _fetch_html(catalog_base)
       nd = _extract_next_data(page1_html)
       products = nd["props"]["pageProps"].get("products", [])
       total = nd["props"]["pageProps"].get("totalCount", len(products))
       per_page = nd["props"]["pageProps"].get("pageSize", len(products))
       urls = [p["url"] for p in products]  # or build from p["id"]
       num_pages = (total + per_page - 1) // per_page
       for page in range(2, num_pages + 1):
           time.sleep(2.0)  # rate limit between pages too
           page_html = _fetch_html(f"{catalog_base}?page={page}")
           page_nd = _extract_next_data(page_html)
           urls.extend(p["url"] for p in page_nd["props"]["pageProps"]["products"])
       return urls
   ```

3. **Fallback if `__NEXT_DATA__` empty/no products:** parse HTML for `<a href="/item/...">` links + pagination links via selectolax.

4. **Optimization (defer):** `/_next/data/{buildId}/men/catalog/1310.json` returns pageProps directly. Skip on v1 — buildId rotates on viled deploy and breaks scrapers.

**Concurrency:** `concurrency=1` across both catalog endpoints, sequential men → women (D-225).

### Pattern 3: SQLModel Schema (DATA-01..DATA-05)

```python
# storage/sqlite.py
from datetime import datetime, timezone
from typing import Optional, Literal
from sqlmodel import Field, SQLModel, Index, UniqueConstraint, create_engine, Session, text

# PARSE-06 enum (string-typed for SQLite portability)
StockState = Literal["IN_STOCK", "OUT_OF_STOCK", "UNAVAILABLE", "DELISTED", "URL_CHANGED", "UNKNOWN"]

class Run(SQLModel, table=True):
    __tablename__ = "runs"
    run_id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    status: str = Field(default="running")  # running | success | failed | partial
    fail_reason: Optional[str] = None
    stats: str = Field(default="{}")        # JSON-encoded text; SQLite TEXT (D-Discretion §JSONB)

class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.run_id", index=True)
    retailer: str = Field(index=True)        # "viled" | "goldapple"
    sku_id: str
    url: str
    name: str
    brand: str                               # raw brand string from source
    brand_norm: str = Field(index=True)
    name_norm: str
    volume_raw: Optional[str] = None
    volume_norm: Optional[str] = None        # serialized "(amount, unit, count)" or NULL
    multipack_flag: bool = Field(default=False)
    parse_error_flag: bool = Field(default=False)
    current_price: Optional[int] = None
    was_price: Optional[int] = None
    currency: str = Field(default="KZT")
    stock_state: str = Field(default="UNKNOWN")  # StockState enum value
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("run_id", "retailer", "sku_id", name="uq_snapshot_run_retailer_sku"),
        Index("ix_snapshot_retailer_brand_norm", "retailer", "brand_norm"),
        Index("ix_snapshot_run_retailer", "run_id", "retailer"),
    )
```

**Schema bootstrap (D-220 alembic-deferred):**

```python
def init_db(db_path: str) -> None:
    """Idempotent first-run schema creation. Phase 2 Wave 0 — no migrations."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)
    # Apply PRAGMAs and create v_current_snapshots view
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        conn.exec_driver_sql("""
            CREATE VIEW IF NOT EXISTS v_current_snapshots AS
            SELECT * FROM snapshots
            WHERE run_id = (SELECT MAX(run_id) FROM runs WHERE status = 'success')
        """)
        conn.commit()
```

### Pattern 4: RunWriter with Atomic `json_patch`

```python
# storage/sqlite.py (continued)
import json
from sqlmodel import Session

class SqliteRunWriter:
    """RunWriterProtocol impl. Owns the runs row lifecycle and atomic stats merge."""

    def __init__(self, engine):
        self.engine = engine

    def create(self, run_id: Optional[int] = None) -> int:
        """Open a new runs row. Returns assigned run_id."""
        with Session(self.engine) as session:
            row = Run(run_id=run_id, status="running")
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.run_id

    def patch_stats(self, run_id: int, delta: dict) -> None:
        """Atomic merge into runs.stats using SQLite json_patch (RFC-7396 MergePatch).
        Pitfall 6: Phase 2 (viled.*) and Phase 3 (goldapple.*) keys merge cleanly.
        """
        delta_json = json.dumps(delta, ensure_ascii=False, default=str)
        with Session(self.engine) as session:
            session.exec(
                text("UPDATE runs SET stats = json_patch(stats, :delta) WHERE run_id = :rid"),
                params={"delta": delta_json, "rid": run_id},
            )
            session.commit()

    def get_stats(self, run_id: int) -> dict:
        with Session(self.engine) as session:
            row = session.get(Run, run_id)
            if row is None:
                return {}
            return json.loads(row.stats or "{}")

    def fail(self, run_id: int, reason: str) -> None:
        """Idempotent — safe to call from try/finally."""
        with Session(self.engine) as session:
            session.exec(
                text("UPDATE runs SET status='failed', fail_reason=:r, finished_at=:t WHERE run_id=:rid"),
                params={"r": reason, "rid": run_id, "t": datetime.now(timezone.utc)},
            )
            session.commit()

    def finalize(self, run_id: int, status: str = "success") -> None:
        """Close run with explicit status. Different from fail() because callable on success."""
        with Session(self.engine) as session:
            session.exec(
                text("UPDATE runs SET status=:s, finished_at=:t WHERE run_id=:rid AND status='running'"),
                params={"s": status, "rid": run_id, "t": datetime.now(timezone.utc)},
            )
            session.commit()
```

> **NOTE — RunWriter Protocol gap:** `interfaces.py` defines `patch_stats / get_stats / fail` but NO `create` or `finalize`. Phase 3 mentions in `code_context`: *"Phase 2 owns runs table schema + RunWriter.create() (новый метод not in `interfaces.py` Protocol — добавить или Phase 2 решает create-вне-protocol-pattern)."* **Recommendation:** ADD `create(run_id=None) -> int` and `finalize(run_id, status='success') -> None` as concrete methods on `SqliteRunWriter`, but do NOT add them to `RunWriterProtocol` — they're Phase-2-orchestrator-only operations and Phase 3 must not reach for them. Phase 3 only uses `patch_stats / get_stats / fail` — no Protocol drift.

### Pattern 5: SnapshotWriter (append-only, batched)

```python
# storage/sqlite.py (continued)
class SqliteSnapshotWriter:
    """SnapshotWriterProtocol impl. Append-only INSERT; never UPDATE.
    
    DATA-04: per-batch transaction — on failure mid-batch, the partial batch
    rolls back but PRIOR batches' rows are durable. Smaller blast radius than
    per-run transaction (which would lose entire run on a single bad row).
    """

    def __init__(self, engine, batch_size: int = 100):
        self.engine = engine
        self.batch_size = batch_size

    def append(self, run_id: int, retailer: str, products: list) -> int:
        if not products:
            return 0
        inserted = 0
        with Session(self.engine) as session:
            for product in products:
                row = Snapshot(
                    run_id=run_id,
                    retailer=retailer,
                    **product,  # caller passes dict matching Snapshot fields
                )
                session.add(row)
                inserted += 1
                if inserted % self.batch_size == 0:
                    session.commit()
            session.commit()
        return inserted
```

### Pattern 6: Volume Normalizer (NORM-03+04)

**Layered grammar:**

```python
# normalizers/volume.py
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

UNIT_TABLE: dict[str, str] = {
    # Russian
    "мл": "ml", "милилитр": "ml", "миллилитр": "ml",
    "г": "g", "гр": "g", "грамм": "g",
    "л": "l", "литр": "l",
    "шт": "pcs", "штук": "pcs",
    "унц": "oz", "унция": "oz", "унций": "oz",
    "кг": "kg",
    # English
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "g": "g", "gram": "g", "grams": "g",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "fl": "fl",  # combined "fl oz"
    "kg": "kg",
    "l": "l", "liter": "l", "liters": "l",
    "pcs": "pcs", "pc": "pcs",
}

# Multipack patterns (in order; first hit wins)
MULTIPACK_PATTERNS = [
    re.compile(r"(\d+)\s*[xх×]\s*(\d+(?:[.,]\d+)?)\s*(\w+)", re.IGNORECASE),  # "3 x 50 мл"
    re.compile(r"set\s+of\s+(\d+)", re.IGNORECASE),                            # "Set of 3"
    re.compile(r"(\d+)\s*шт", re.IGNORECASE),                                  # "3 шт"
    re.compile(r"набор", re.IGNORECASE),                                       # keyword
    re.compile(r"\bkit\b", re.IGNORECASE),                                     # keyword
    re.compile(r"комплект", re.IGNORECASE),                                    # keyword
]

# Single-volume pattern: "30 мл", "30мл", "30ml", "1.0 oz", "1,5 л"
SINGLE_VOLUME_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*([a-zа-яё]+)",
    re.IGNORECASE,
)

@dataclass(frozen=True)
class Volume:
    amount: Decimal
    unit: str       # canonical from UNIT_TABLE values
    count: int      # 1 for single; N for multipack

def parse_volume(raw: str) -> Optional[Volume]:
    """Returns Volume or None if unparseable.
    
    Test corpus (see tests/fixtures/normalize/volume-corpus.yaml — REQUIRED):
      "30 мл"            -> Volume(30, "ml", 1)
      "30мл"             -> Volume(30, "ml", 1)
      "30ml"             -> Volume(30, "ml", 1)
      "1.0 oz"           -> Volume(Decimal("1.0"), "oz", 1)
      "1,5 л"            -> Volume(Decimal("1.5"), "l", 1)  # comma-decimal
      "3 шт x 50мл"      -> Volume(50, "ml", 3)             # multipack
      "3 x 50 мл"        -> Volume(50, "ml", 3)
      "Set of 3 × 50ml"  -> Volume(50, "ml", 3)
      "набор пробников"  -> Volume(?, "?", N>1) — multipack True, count UNKNOWN; mark NULL volume
      "Кружевное боди"   -> None  (no volume — clothing; expected for narrowed scope, edge case)
    """
    if not raw:
        return None
    raw_lower = raw.lower()
    
    # Try multipack patterns first
    for pat in MULTIPACK_PATTERNS:
        m = pat.search(raw_lower)
        if m:
            if pat.pattern.startswith("(\\d+)\\s*[xх"):  # "N x AMOUNT UNIT"
                count = int(m.group(1))
                amount = _to_decimal(m.group(2))
                unit_raw = m.group(3)
                unit = UNIT_TABLE.get(unit_raw)
                if unit and amount > 0:
                    return Volume(amount=amount, unit=unit, count=count)
            else:
                # Keyword-only multipack ("набор", "kit", "Set of N", "N шт"):
                # mark multipack but cannot extract per-unit volume
                return None  # caller sets multipack_flag=True, volume_norm=NULL
    
    # Single volume
    m = SINGLE_VOLUME_RE.search(raw_lower)
    if m:
        amount = _to_decimal(m.group(1))
        unit_raw = m.group(2)
        unit = UNIT_TABLE.get(unit_raw)
        if unit and amount > 0:
            return Volume(amount=amount, unit=unit, count=1)
    
    return None

def _to_decimal(s: str) -> Decimal:
    return Decimal(s.replace(",", "."))

def detect_multipack(raw: str) -> bool:
    """True if raw text contains multipack markers (separate from parse_volume
    so multipack_flag survives even when amount/unit can't be extracted)."""
    if not raw:
        return False
    raw_lower = raw.lower()
    return any(pat.search(raw_lower) for pat in MULTIPACK_PATTERNS)
```

**Integration with NormalizerProtocol:**

The protocol's `volume(raw) -> Optional[tuple[Decimal, str, int]]` returns a 3-tuple. Map `Volume(30, "ml", 1)` → `(Decimal("30"), "ml", 1)`. Multipack with unparseable per-unit volume returns `None` — caller (orchestrator) reads the parsed-multipack-flag separately via `detect_multipack(raw)` for the `multipack_flag` column.

### Pattern 7: Brand & Name Normalizers

```python
# normalizers/brand.py
from ga_crawler.enumeration.slug import _normalize_punct  # REUSE

def normalize_brand(raw: str, alias_lookup) -> str:
    """NORM-02: NFKD + accent strip + lowercase + alias lookup → brand_norm.
    
    Step 1: _normalize_punct (already does NFKD + accent strip + lowercase + slugify)
    Step 2: alias_lookup.canonical_for(slug) — reverse-lookup a canonical brand_norm
            from the YAML alias map.
    """
    candidate = _normalize_punct(raw)
    canonical = alias_lookup.canonical_for(candidate)  # see YamlBrandAlias below
    return canonical or candidate
```

```python
# normalizers/name.py
import re
import unicodedata

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")

def normalize_name(raw: str) -> str:
    """NORM-05: lowercase + strip punctuation + collapse whitespace → name_norm."""
    if not raw:
        return ""
    s = unicodedata.normalize("NFKD", raw.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s
```

### Pattern 8: YAML Brand Alias

```python
# alias/yaml_loader.py
from pathlib import Path
import yaml

class YamlBrandAlias:
    """BrandAliasProtocol impl. Read-once at run start; in-memory dict (D-207)."""

    def __init__(self, yaml_path: Path):
        self._raw: dict[str, list[str]] = {}
        self._reverse: dict[str, str] = {}  # alias_normalized → canonical_brand_norm
        if yaml_path.exists():
            self._raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            self._build_reverse()

    def _build_reverse(self) -> None:
        from ga_crawler.enumeration.slug import _normalize_punct
        for canonical, aliases in self._raw.items():
            for a in aliases or []:
                self._reverse[_normalize_punct(a)] = canonical
            self._reverse[canonical] = canonical  # self-loop

    def lookup(self, brand_norm: str) -> list[str]:
        """Per BrandAliasProtocol: returns aliases for a canonical brand_norm."""
        return list(self._raw.get(brand_norm, [brand_norm]))

    def canonical_for(self, normalized_alias: str) -> str | None:
        """Used by normalizers/brand.py to map a fresh raw_brand → canonical brand_norm.
        Returns None if the alias is unknown (caller falls back to normalized_alias)."""
        return self._reverse.get(normalized_alias)
```

### Pattern 9: Tenacity Retry for curl_cffi (CRAWL-04)

```python
# fetchers/viled.py (sync — D-225 default)
import time
from curl_cffi import requests
from curl_cffi.requests.errors import RequestsError, Timeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

class TransientFetchError(Exception):
    """Raised on retryable failures (5xx, network error, timeout)."""

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((TransientFetchError,)),
    reraise=True,
)
def _fetch_html(url: str, timeout_s: int = 30) -> tuple[int, str]:
    try:
        resp = requests.get(url, impersonate="chrome", timeout=timeout_s)
    except (RequestsError, Timeout) as e:
        raise TransientFetchError(f"curl_cffi error: {e}") from e
    if 500 <= resp.status_code < 600:
        raise TransientFetchError(f"http {resp.status_code}")
    return resp.status_code, resp.text  # caller decides on 4xx
```

> **Wave 0 verification:** confirm exact exception class names — `curl_cffi.requests.errors.RequestsError` and `Timeout` are the documented names; actual installed package may expose under a slightly different path. Do `python -c "from curl_cffi.requests.errors import RequestsError, Timeout; print('ok')"` first.

### Anti-Patterns to Avoid

- **DO NOT use `respx` to mock curl_cffi.** It's HTTPX-specific. Phase 3 D-302 documented this — same trap here. Mock by monkey-patching the module-level `_fetch_html` / `_fetch_xml` wrapper instead.
- **DO NOT use UPDATE for stats.** `UPDATE runs SET stats = ?` is non-atomic across phases (read-modify-write race when Phase 2 viled and Phase 3 goldapple write to the same row). Always `UPDATE runs SET stats = json_patch(stats, :delta)`.
- **DO NOT batch all snapshots in one transaction.** Per-batch (e.g. 100 rows) commit means a single bad row only blasts the last batch, not the entire 600-SKU run. DATA-04 says "on-failure rollback не теряет уже сохранённые SKU" — this REQUIRES batched commits.
- **DO NOT eagerly reload `brand-aliases.yaml`.** D-207 locks read-once-at-startup. Operator edits visible next weekly run.
- **DO NOT fetch `attributes` size-variants as separate rows.** v1 emits one snapshot per `(run_id, retailer, sku_id)` (UNIQUE constraint). Document size-variant flattening as known v1 limitation.
- **DO NOT use JSON-LD path for viled.** Empirical 0/15 hit rate — `__NEXT_DATA__` only.
- **DO NOT add `RunWriter.create()` to the Protocol.** Keeping it concrete-only avoids Phase 3 contract drift (Pitfall 9). Same for `finalize()`.
- **DO NOT reuse goldapple `final_m_gate` directly.** Refactor to `final_threshold_gate(count, threshold)` retailer-agnostic — D-203 explicit.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic stats merge | hand-rolled `UPDATE runs SET stats = ?` after Python-side dict merge | `UPDATE runs SET stats = json_patch(stats, :delta)` | SQL-level atomic; RFC-7396 MergePatch semantics; no read-modify-write race [VERIFIED: sqlite.org/json1.html] |
| TLS fingerprint impersonation | custom `requests.Session` with header tricks | `curl_cffi.requests.get(url, impersonate="chrome")` | `requests` exposes urllib3 TLS — Cloudflare reads TLS not headers; locked CLAUDE.md |
| HTML parsing | hand-rolled string split / regex on tags | `selectolax.parser.HTMLParser` | 30x faster than BS4; locked CLAUDE.md |
| Retry with backoff + jitter | hand-rolled `for attempt in range(3)` loop | `tenacity.retry` + `wait_exponential_jitter` | declarative, battle-tested, mirror Phase 3; locked CLAUDE.md |
| Cyrillic↔Latin transliteration | per-letter `dict.get(ch, ch)` from scratch | reuse `enumeration.slug.CYRILLIC_TO_LATIN` + `_normalize_punct` | already shipped + 7 tests passing on it; covers KZ-specific glyphs |
| Pagination of `__NEXT_DATA__` | crawl HTML pages and re-glue | `__NEXT_DATA__.totalCount / pageSize` arithmetic | first-class metadata, no DOM scraping for pagination |
| YAML parse | hand-rolled key-value split | `yaml.safe_load` (PyYAML) | trivial, ubiquitous, safe-load disables arbitrary tag execution |
| SQLite schema bootstrap | hand-rolled `CREATE TABLE` strings | `SQLModel.metadata.create_all(engine)` | already shipped types; one source of truth for column definitions |
| Volume parsing | one mega-regex | layered (multipack-detect → unit-table-lookup → single-volume regex) | mega-regex unmaintainable; layered grammar testable per branch |
| Multi-table BACKUP | naive `.dump`+`.read` round-trip | `sqlite3 prices.db ".backup target.db"` | online backup, atomic, WAL-safe — single shell command |

**Key insight:** Phase 3 already shipped retail-grade impls of fetcher/parser/sitemap/gates. Phase 2's job is reuse + parameterization, not re-invention. The only **new** primitives Phase 2 invents are: Volume value-object grammar, YAML brand-alias loader, json_patch RunWriter, viled `__NEXT_DATA__` parser, catalog/1310 paginator. Everything else is "copy goldapple's pattern, swap retailer".

## Runtime State Inventory

> Phase 2 is greenfield infrastructure (not a rename/refactor). However, since Phase 3 stubs in `cli.py` produced runtime artifacts that Phase 2 must replace, and there are pinned interfaces, this audit is non-empty.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None (Phase 3 stubs write JSON to `.planning/runs/{run_id}/`; not real DB state) | Wave 0 — `init_db()` creates `prices.db` from scratch; no migration needed |
| Live service config | None — no external services to reconfigure | None |
| OS-registered state | None — no cron/launchd/Task Scheduler entries yet (Phase 7 owns cron) | None |
| Secrets/env vars | `.env` referenced by `python-dotenv` (Phase 6/7 deliveries: `TG_BOT_TOKEN` etc.); none new in Phase 2 | None — Phase 2 doesn't touch ENV beyond DB path |
| Build artifacts | `pyproject.toml` already pins all Phase 2 deps except PyYAML | `uv add pyyaml` (one new dep); `uv lock` after pyproject namespace add |
| **Frozen Protocols (interfaces.py)** | `BrandAliasProtocol`, `NormalizerProtocol`, `SnapshotWriterProtocol`, `RunWriterProtocol`, `ParseDispatcherProtocol`, `CrawlerProtocol` | Phase 2 implementations MUST conform — Pitfall 9 contract drift = integration blocker |
| **Phase 3 stub impls in cli.py** | `StubBrandAlias`, `StubNormalizer`, `StubSnapshotWriter`, `StubRunWriter` | DELETE after real Phase 2 impls ship (D-212) — final wave; tests use conftest.py mocks |
| **Phase 3 frozen modules** | `runners/goldapple_run.py`, `parsers/goldapple_microdata.py`, `enumeration/goldapple_sitemap.py`, `fetchers/goldapple.py` | DO NOT MODIFY — Phase 3 closed; only `runner/gates.py` and `runner/stats.py` get refactored (D-203) |

## Common Pitfalls

### Pitfall 1: respx incompatibility with curl_cffi
**What goes wrong:** Tests using `respx.mock` to intercept curl_cffi calls silently pass through real HTTP — tests appear to mock but don't.
**Why it happens:** respx hooks HTTPX transport; curl_cffi is built on libcurl, not HTTPX.
**How to avoid:** Monkey-patch the module-level `_fetch_html` / `_fetch_xml` wrappers (Phase 3 pattern from `enumeration/goldapple_sitemap.py`). Inject a callable via `sitemap_fetcher=` kwarg as `runners/goldapple_run.py` does.
**Warning signs:** Tests pass but logs show real network requests during pytest run.

### Pitfall 2: viled `attributes[0]` size-variant ambiguity
**What goes wrong:** Some viled SKUs emit `attributes` as a list with multiple price entries (one per size). Picking `[0]` may not be the canonical / cheapest / available variant.
**Why it happens:** Single SKU URL with multiple physical variants.
**How to avoid:** Wave 0 probe MUST inspect 5-10 PDPs and document: do all `attributes[i]` share the same price? If yes, `[0]` is safe. If no, `min(a.realPrice for a in attributes if a.in_stock)` is more defensible. **Document the rule chosen.**
**Warning signs:** Same SKU exhibits price variance across runs without an actual price change.

### Pitfall 3: SQLite WAL checkpoint vs backup race
**What goes wrong:** `sqlite3 prices.db ".backup backups/X.db"` during a running write transaction grabs a consistent snapshot, but if the WAL is huge, backup is slow + holds shared lock against checkpointing.
**Why it happens:** WAL accumulates during weekly run; backup at 01:00 might catch a still-WAL-heavy DB.
**How to avoid:** Run backup AFTER weekly cron (D-219 + Phase 7 cron sequence: 02:00 weekly run → 01:00 next-day backup, so DB is fully checkpointed). If urgent before checkpoint: `PRAGMA wal_checkpoint(TRUNCATE);` before `.backup`.
**Warning signs:** Backup file `.db-wal` companion is large; `.backup` takes >30s.

### Pitfall 4: `runs.stats` json_patch overwrites with `null` to delete
**What goes wrong:** Caller passes `delta = {"viled.foo": None}` intending "no value yet" — RFC-7396 MergePatch interprets `null` as DELETE the key.
**Why it happens:** json_patch follows RFC-7396; `null` is the deletion sentinel.
**How to avoid:** Never pass None values in delta. Use sentinels (`-1`, `""`, `[]`) or omit the key. Document in `ViledStatsBuilder.set` (mirror `GoldappleStatsBuilder._BARE_TO_NAMESPACED` enforcement) that None values are rejected.
**Warning signs:** stats keys disappearing after merge.

### Pitfall 5: Brand-alias YAML drift between dev and prod
**What goes wrong:** Operator edits `config/brand-aliases.yaml` in dev, forgets to commit; prod cron runs old version.
**Why it happens:** YAML is operator-edited in git but not enforced by CI.
**How to avoid:** Document in Phase 7 ops-playbook: every alias edit goes through git PR. Optional: CI lint that aliases.yaml has no merge conflict markers + parses cleanly.
**Warning signs:** Same brand normalizes differently across runs.

### Pitfall 6: Volume regex on Russian "л" matches single "л" in random words
**What goes wrong:** Regex `(\d+(?:[.,]\d+)?)\s*(л)` matches `1.5 л` but also matches noise like `5 л.с.` (horsepower) — irrelevant to beauty but as scope expands risk grows.
**Why it happens:** Cyrillic single-letter unit symbols collide with abbreviations.
**How to avoid:** Use word-boundary on unit (`\b(л|мл|г|кг)\b`) and unit-table includes only beauty-relevant units (drop `л` if 1-letter Cyrillic causes too many false positives in expanded scope; keep `мл` always). For v1 (beauty only), risk is low.
**Warning signs:** Volume normalization captures bogus values from name strings.

### Pitfall 7: Schema-drift between Stub and Real impls
**What goes wrong:** StubSnapshotWriter takes any dict in `products`; real `SqliteSnapshotWriter` enforces SQLModel column types — fields stub allowed (e.g. extra `images` key) crash insert.
**Why it happens:** Stubs were intentionally permissive; SQLModel is strict.
**How to avoid:** Wave 0 add `tests/integration/test_storage_round_trip.py` that calls `SqliteSnapshotWriter.append` with the EXACT shape `goldapple_run.py` produces (the dict at line 237-250 of `runners/goldapple_run.py`). Treat that dict shape as the source of truth.
**Warning signs:** Phase 3 e2e test passes with stubs; fails with real storage.

### Pitfall 8: Catalog/1310 endpoint blocks unauth requests
**What goes wrong:** `/men/catalog/1310` works in browser (cookies), curl_cffi returns 403 or redirects to login.
**Why it happens:** viled may region/auth-gate catalog pages while leaving individual `/item/{id}` open.
**How to avoid:** Wave 0 probe MUST verify catalog endpoints return 200 with `__NEXT_DATA__` containing products. If not — fallback to sitemap with manual category filter (e.g. brand-allowlist filter on sitemap output).
**Warning signs:** Spike validated `/item/{id}` 15/15, NOT `/catalog/1310`.

## Code Examples

### Initializing the WAL session (verified pattern)

```python
# storage/sqlite.py
from sqlmodel import create_engine, Session
from sqlalchemy import event

def make_engine(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    return engine
```
[Source: SQLAlchemy events doc + sqlite.org PRAGMA docs]

### auto_suggest_threshold refactor (D-203)

```python
# runner/gates.py — REPLACEMENT for auto_suggest_m
import statistics
from typing import Optional

def auto_suggest_threshold(
    history_counts: list[int],
    factor: float = 0.7,
    min_runs: int = 4,
) -> Optional[int]:
    """Retailer-agnostic auto-suggest. Returns int(factor × median(last_min_runs counts)).
    Less than min_runs of history → None.
    
    Formerly auto_suggest_m (goldapple-specific). D-203: extracted for viled reuse.
    """
    if len(history_counts) < min_runs:
        return None
    last = history_counts[-min_runs:]
    return int(factor * statistics.median(last))

# Backward-compat shim:
def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    return auto_suggest_threshold(history_counts, factor=0.7, min_runs=4)
```

### final_threshold_gate refactor

```python
def final_threshold_gate(count: int, threshold: int) -> bool:
    """Retailer-agnostic. count >= threshold → True."""
    return count >= threshold

# Backward-compat shims:
def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    return final_threshold_gate(goldapple_count, M)

def final_n_gate(viled_count: int, N: int = 100) -> bool:
    return final_threshold_gate(viled_count, N)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests + custom headers` for scraping | `curl_cffi impersonate="chrome"` | 2024+ Cloudflare reads TLS, not headers | locked in CLAUDE.md; spike confirms |
| BS4 for HTML parsing | `selectolax` (Cython lexbor) | 2023+ benchmarks | 10-30x faster; locked CLAUDE.md |
| Pydantic 1 + SQLAlchemy 1 separately | `SQLModel` (SQLAlchemy 2 + Pydantic 2 fused) | 2024+ standard Python | one source of truth for schema + validation |
| `requirements.txt + pip` | `uv` for project + deps + Python toolchain | 2025 default for new Python | already adopted |
| Per-row UPDATE on stats | `json_patch` SQL function | SQLite 3.38+ (2022) | atomic, no R-M-W race |
| Selenium + driver protocols | Playwright (or Patchright/Camoufox) | 2024+ | locked CLAUDE.md (Phase 3 uses Camoufox) |

**Deprecated/outdated:**
- `respx` for curl_cffi mocking — never compatible (HTTPX vs libcurl)
- `playwright-stealth v1.x` — unmaintained since 2023; Phase 1 already rejected
- alembic on day 1 — CLAUDE.md explicit: "Skip on day 1, add at first migration"

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | viled `attributes[0].in_stock` is the boolean field for stock state | Pattern 1 §viled __NEXT_DATA__; D-217 stock-state mapping | MEDIUM — actual field name might be different (`count`, `purchaseType`, or absent). Wave 0 probe must verify. If absent, derive from `attributes[0].count > 0`. |
| A2 | `attributes[0].price` ≠ `attributes[0].realPrice` for discounted SKUs | Pattern 1 §viled __NEXT_DATA__; PARSE-03 was_price source | MEDIUM — captured fixture shows both equal (no-discount product). Wave 0 must capture a known-discount SKU to confirm `price > realPrice` semantics. STATE.md notes "viled was_price requirement v1 schema satisfiable from week 1 via realPrice field" but doesn't explicitly verify the inverse direction. |
| A3 | `/men/catalog/1310` returns 200 + `__NEXT_DATA__.pageProps.products[]` for unauthenticated curl_cffi | Pattern 2 §Catalog/1310 Pagination | HIGH — spike validated `/item/{id}` only, NOT catalog pages. If catalog endpoints require auth or use a different render path, enumeration strategy changes (Pitfall 8). |
| A4 | `pageProps.totalCount` and `pageProps.pageSize` (or equivalent pagination metadata) exist on viled catalog `__NEXT_DATA__` | Pattern 2 | MEDIUM — Next.js convention but viled may use different keys (`pagination.total`, `meta.totalItems`, etc.). Wave 0 probe documents actual key names. |
| A5 | Beauty SKUs in `/catalog/1310` carry parseable volume strings ("30 мл", etc.) in `item.name` | Pattern 6 §Volume Normalizer | LOW — beauty/parfum naming convention is universal; spike's 15 random products were luxury fashion (boots, dresses) so volume is absent there but expected in beauty. |
| A6 | viled doesn't aggressively rate-limit catalog page enumeration at 2s pause | Pattern 9 §Tenacity | LOW — spike confirmed 2s for `/item/{id}` 15/15; catalog pages should be no stricter. |
| A7 | `curl_cffi.requests.errors.RequestsError` and `Timeout` are the exact importable exception class names | Pattern 9 | LOW — Wave 0 verifies in 30 seconds (`python -c "..."`). |
| A8 | SQLite 3.38+ (json_patch availability) is bundled with Python 3.12 stdlib | Pattern 4 §RunWriter | LOW — Python 3.12 ships SQLite 3.40+; verifiable with `python -c "import sqlite3; print(sqlite3.sqlite_version)"`. |
| A9 | `attributes` list is at most 1-3 entries (size variants); flattening to row-0 doesn't lose meaningful price data for v1 beauty scope | Pattern 1 §viled __NEXT_DATA__ multi-attributes | LOW — beauty SKUs typically don't have size variants in the way clothing does. Documented as v1 limitation. |
| A10 | The shape of dicts produced by `goldapple_run.py` (`runners/goldapple_run.py:237-250`) is a stable contract that Phase 2 SnapshotWriter must accept verbatim | Pattern 5 §SnapshotWriter; Pitfall 7 | MEDIUM — `frozen=True` Phase 3 modules don't change, but we should add an integration test that asserts the exact dict-shape compatibility. |

**Recommendation for the planner:** Wave 0 of Phase 2 is a **probe-and-pin wave** — its single goal is downgrading A1, A2, A3, A4, A10 from ASSUMED to VERIFIED before any production code is written. Concretely: fetch `/men/catalog/1310` once, fetch 5-10 known-beauty `/item/{id}` (one with discount, one out-of-stock if findable), save HTML to `tests/fixtures/viled/`, document field paths in `RESEARCH-WAVE0-PROBE.md`, then update Pattern 1 §field-paths table from ASSUMED to VERIFIED.

## Open Questions

1. **Should `RunWriter.create()` and `RunWriter.finalize()` be added to `RunWriterProtocol`?**
   - What we know: Phase 3 doesn't need them; only Phase 2 main_run.py uses them.
   - What's unclear: Whether future test mocks need them (planner discretion).
   - Recommendation: Concrete-only (NOT in Protocol). Phase 3 contract stays minimal. Phase 2 main_run.py imports `SqliteRunWriter` directly for `create/finalize`.

2. **Where does the `prices.db` file live?**
   - What we know: Single SQLite file; gitignored; backup goes to `backups/{YYYY-MM-DD}.db`.
   - What's unclear: Repo-relative (`./prices.db`) vs absolute (`/var/lib/ga_crawler/prices.db`).
   - Recommendation: Repo-relative on dev (default `./prices.db`), env override `GA_CRAWLER_DB_PATH` for prod. Phase 7 wires absolute path on VPS.

3. **Should the `weekly-run` CLI subcommand replace `goldapple-run` or coexist?**
   - What we know: D-212 deletes Stubs from cli.py. cli.py currently has `goldapple-smoke` + `goldapple-run` (Phase 3 dev/test entry).
   - What's unclear: Whether Phase 2 keeps `goldapple-run` as a debug entry or deletes it.
   - Recommendation: Add `weekly-run` (the production entry, runs viled → goldapple → finalize). Keep `goldapple-smoke` (dev/ops-playbook tool). DELETE `goldapple-run` Stub-bound subcommand.

4. **Volume normalizer multipack with unparseable per-unit volume — how to represent in SQL?**
   - What we know: D-215 says "unparseable volume → `volume_norm=NULL`, `multipack_flag=False`, parse_error_flag=True; row не блокирует insert". But "набор пробников" IS multipack with unknown unit.
   - What's unclear: Should `multipack_flag=True` AND `volume_norm=NULL` be allowed? Or is multipack_flag also gated by parseable volume?
   - Recommendation: Allow `multipack_flag=True` independent of `volume_norm`. Add `parse_error_flag` separately for "couldn't parse anything". Phase 4 matcher excludes multipack regardless of volume parsability.

5. **Sanity-N test corpus location.**
   - What we know: Success criteria #4 mentions "documented test suite of real strings".
   - What's unclear: Where does this corpus live?
   - Recommendation: `tests/fixtures/normalize/volume-corpus.yaml` — YAML list of `{input, expected_volume, expected_multipack}` triples. Drives `tests/unit/test_volume_normalizer.py` via parametrize.

6. **Concurrency for catalog-page fetches vs SKU-page fetches.**
   - What we know: D-225 "concurrency=1 across both endpoints, 2s pause".
   - What's unclear: Does the 2s pause apply BETWEEN catalog page fetches (page 1 → page 2) and BETWEEN SKU fetches (item/A → item/B), or just SKU fetches?
   - Recommendation: Apply to BOTH. Catalog has fewer pages (3-10 estimated) so cost is small; consistent rate-limit reduces detection surface.

7. **`runs.stats` schema discoverability.**
   - What we know: Phase 3 froze `GOLDAPPLE_STATS_KEYS` (13 keys). Phase 2 should add `VILED_STATS_KEYS`.
   - What's unclear: Final list of `viled.*` keys.
   - Recommendation: Mirror Phase 3 13-key shape: `viled.{fetch_count, fetch_failures, parse_failures, fetch_duration_seconds, mean_fetch_seconds, sanity_gate_n_pass, parse_quality_pass, null_rate_required_fields, auto_suggest_n}`. Document in `runner/stats.py` ViledStatsBuilder.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | ✓ (uv-managed) | 3.12 | — |
| SQLite | Storage | ✓ (stdlib) | 3.40+ via Python 3.12 stdlib | — |
| curl_cffi (libcurl) | Fetcher | ✓ (already pinned) | 0.15.x | — |
| Playwright/Camoufox | Phase 3 only — NOT Phase 2 | ✓ (already installed for Phase 3) | bundled | — |
| `uv` | Build/install | ✓ (mandated by CLAUDE.md) | 0.10+ | — |
| network access to viled.kz | Wave 0 probe + integration tests | requires connectivity | live | mock with fixture HTML |
| YAML lib (PyYAML) | YamlBrandAlias | ✗ NOT YET INSTALLED | needs `uv add pyyaml` | none — required |

**Missing dependencies with no fallback:**
- PyYAML — must add via `uv add pyyaml` in Wave 0

**Missing dependencies with fallback:**
- (none)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 8.x` + `pytest-asyncio 0.24` + `pytest-mock 3.14` |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (existing — already configured) |
| Quick run command | `pytest -m "not live" -x` (deselect live tests; abort on first fail) |
| Full suite command | `pytest -m "not live"` |
| Live network suite | `pytest -m "live"` (Wave 0 probe + Wave 6 acceptance — manual) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Run/Snapshot tables created with correct columns + UNIQUE constraint | unit | `pytest tests/unit/test_storage_models.py -x` | ❌ Wave 1 |
| DATA-02 | Snapshot row stores all 13 fields with correct types | unit | `pytest tests/unit/test_storage_models.py::test_snapshot_columns -x` | ❌ Wave 1 |
| DATA-03 | Append-only — UPDATE attempts on snapshot raise / are absent | unit | `pytest tests/unit/test_snapshot_writer.py::test_append_only -x` | ❌ Wave 1 |
| DATA-04 | WAL mode active; per-batch transactions; mid-batch failure preserves prior batches | integration | `pytest tests/integration/test_storage_wal.py -x` | ❌ Wave 1 |
| DATA-05 | runs row created at start, finalized in success/failed paths, idempotent fail() | integration | `pytest tests/integration/test_run_writer_lifecycle.py -x` | ❌ Wave 1 |
| DATA-06 | `bin/backup.sh` produces valid backup; rotation keeps 4 latest | integration | `pytest tests/integration/test_backup_script.py -x` | ❌ Wave 6 |
| CRAWL-01 | Catalog enumeration extracts list of `/item/{id}` URLs from both endpoints | integration | `pytest tests/integration/test_viled_catalog_enumeration_mocked.py -x` | ❌ Wave 3 |
| CRAWL-03 | Per-SKU isolation — exception in one fetch doesn't abort run | unit | `pytest tests/unit/test_viled_fetcher_isolation.py -x` | ❌ Wave 3 (mirror existing test_fetcher_isolation.py) |
| CRAWL-04 | Tenacity retry on 5xx + Timeout; max 3 attempts | unit | `pytest tests/unit/test_viled_retry_policy.py -x` | ❌ Wave 3 (mirror existing test_retry_policy.py) |
| CRAWL-05 | viled_count < N → run marked failed | unit | `pytest tests/unit/test_sanity_n_gate.py -x` | ❌ Wave 5 |
| CRAWL-06 | 2s pause between fetches; configurable | unit | `pytest tests/unit/test_viled_rate_limit.py -x` | ❌ Wave 3 |
| PARSE-01 | All 8 fields extracted from `__NEXT_DATA__` fixture | unit | `pytest tests/unit/test_viled_nextdata_parser.py::test_full_extract -x` | ❌ Wave 3 |
| PARSE-02 | viled parser uses `__NEXT_DATA__` (NOT JSON-LD) — anti-fixture proves NO JSON-LD path | unit | `pytest tests/unit/test_viled_nextdata_parser.py::test_no_jsonld_path -x` | ❌ Wave 3 |
| PARSE-03 | `realPrice` (current) chosen over `price` (was) — discount fixture | unit | `pytest tests/unit/test_viled_nextdata_parser.py::test_realprice_priority -x` | ❌ Wave 3 |
| PARSE-04 | Price outside 100..1_000_000 → parse_error_flag, no row | unit | `pytest tests/unit/test_viled_nextdata_parser.py::test_sanity_range -x` | ❌ Wave 3 |
| PARSE-05 | Aggregate: >5% null required-field rate → run failed | integration | `pytest tests/integration/test_parse_quality_gate.py -x` | ❌ Wave 5 |
| PARSE-06 | Stock-state enum mapping verified against fixture | unit | `pytest tests/unit/test_viled_nextdata_parser.py::test_stock_state -x` | ❌ Wave 3 |
| NORM-01 | YAML loader parses flat-dict, returns aliases | unit | `pytest tests/unit/test_yaml_brand_alias.py -x` | ❌ Wave 2 |
| NORM-02 | brand: NFKD+accent+lower+alias → brand_norm | unit | `pytest tests/unit/test_brand_normalizer.py -x` | ❌ Wave 2 |
| NORM-03 | Volume corpus parses correctly (10+ cases including kits) | unit | `pytest tests/unit/test_volume_normalizer.py -x` | ❌ Wave 2 |
| NORM-04 | Multipack flag set correctly on `набор`, `Set of N`, `N x M units` | unit | `pytest tests/unit/test_volume_normalizer.py::test_multipack -x` | ❌ Wave 2 |
| NORM-05 | name: lower+strip-punct+collapse-ws → name_norm | unit | `pytest tests/unit/test_name_normalizer.py -x` | ❌ Wave 2 |
| NORM-06 | Norm06Writer renders markdown table per D-208 schema | unit | `pytest tests/unit/test_norm06_writer.py -x` | ❌ Wave 4 |
| Phase 3 stub cutover | Replacing stubs with real impls — Phase 3 e2e still 192/192 + new Phase 2 tests | integration | `pytest -m "not live"` (full suite green) | partially (existing 192 tests must stay green) |

### Sampling Rate
- **Per task commit:** `pytest -m "not live" -x` (~30s for current 192 + Phase 2 additions)
- **Per wave merge:** `pytest -m "not live"` (full suite, no `-x`)
- **Phase gate:** `pytest -m "not live"` green AND optional manual `pytest -m "live"` against viled (Wave 0 probe + final acceptance)

### Wave 0 Gaps

- [ ] `tests/fixtures/viled/viled-pdp-407682.html` — captured viled PDP for parser tests (re-fetch from spike or first probe)
- [ ] `tests/fixtures/viled/viled-catalog-men-1310-page1.html` — captured catalog page 1 for enumeration tests
- [ ] `tests/fixtures/viled/viled-pdp-discounted.html` — captured discounted viled PDP (price ≠ realPrice) for PARSE-03 verification
- [ ] `tests/fixtures/viled/viled-pdp-out-of-stock.html` — captured OOS viled PDP for PARSE-06 verification
- [ ] `tests/fixtures/viled/viled-pdp-multipack.html` — captured "набор" / kit SKU for NORM-04 verification
- [ ] `tests/fixtures/normalize/volume-corpus.yaml` — test corpus (≥15 cases per criteria #4)
- [ ] `tests/fixtures/viled/brand-aliases-fixture.yaml` — small test seed
- [ ] `tests/conftest.py` — add fixtures: `viled_pdp_html`, `viled_catalog_html`, `brand_alias_yaml_fixture`, `in_memory_sqlite_session`, `volume_corpus_cases`
- [ ] `uv add pyyaml` — install dep
- [ ] Add `pyproject.toml [tool.ga_crawler.crawl.viled]` namespace with `sanity_gate_n=100`, `pause_seconds=2.0`, `concurrency=1`, `retry_attempts=3`, `catalog_urls=["https://viled.kz/men/catalog/1310", "https://viled.kz/women/catalog/1310"]`

## Project Constraints (from CLAUDE.md)

CLAUDE.md locks the following — Phase 2 plans must comply:

| Directive | Source | Compliance |
|-----------|--------|-----------|
| Use `uv` for project + deps + Python toolchain | §Recommended Stack §Development Tools | All `uv add` for new deps; no requirements.txt |
| Python 3.12.x runtime | §Core Technologies | Already pinned in pyproject |
| `curl_cffi` + `impersonate="chrome"` for HTTP | §Core Technologies + §Tier 0 viled.kz | viled fetcher uses this — locked |
| `selectolax` for HTML parsing (not BeautifulSoup) | §Core Technologies | Both viled parser and any HTML inspection uses selectolax |
| `SQLModel` 0.0.24+ for ORM | §Core Technologies | All storage layer |
| SQLite v1, **alembic SKIP on day 1** | §Storage v1 + §Stack Patterns | Schema bootstrap via `SQLModel.metadata.create_all` |
| WAL mode + synchronous=NORMAL PRAGMAs | §Storage v1 | Storage init applies these |
| Composite indices `(retailer, normalized_key)` and `(product_id, captured_at)` | §Storage v1 | Snapshot model has equivalent indices |
| `tenacity` for retry with exponential backoff + jitter | §Supporting Libraries | All network calls wrapped |
| `pydantic` for validation | §Supporting Libraries | SQLModel uses Pydantic 2 |
| `structlog` for logging | §Supporting Libraries | All modules import structlog |
| `python-dotenv` for ENV | §Supporting Libraries | Phase 6/7 will use; Phase 2 doesn't add new ENV |
| Use **system cron** (not APScheduler/Celery) | §Scheduling | Phase 7 territory; Phase 2 ships `bin/backup.sh` only |
| **DO NOT use** Selenium / requests / cloudscraper / BS4 / openpyxl / Polars / playwright-stealth v1.x | §What NOT to Use | None proposed |
| Hetzner CX22 VPS + cron entry | §Deployment | Phase 7 territory; Phase 2 unaffected |
| **Conventions: not yet established** | §Conventions | Phase 2 establishes via real impls; capture in code review |
| **Architecture: not yet mapped** | §Architecture | Phase 2 ships canonical layout — see Pattern §Recommended Project Structure |
| GSD Workflow Enforcement (no direct edits outside GSD) | §GSD Workflow Enforcement | Phase 2 work routes through `/gsd-execute-phase 2 NN` |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md` — D-201..D-227 verbatim user decisions
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-DISCUSSION-LOG.md` — alternatives considered + scope-narrowing rationale
- `.planning/REQUIREMENTS.md` §Crawl/Parse/Norm/Data — DATA-01..06, CRAWL-01/03..06, PARSE-01..06, NORM-01..06
- `.planning/ROADMAP.md` — Phase 2 success criteria 1-5
- `CLAUDE.md` (root) — full Tech Stack section, locked tools, "What NOT to Use" anti-patterns
- `src/ga_crawler/interfaces.py` — frozen Protocols (BrandAliasProtocol, NormalizerProtocol, SnapshotWriterProtocol, RunWriterProtocol, ParseDispatcherProtocol, CrawlerProtocol)
- `src/ga_crawler/cli.py` — current Stub impls (StubBrandAlias / StubNormalizer / StubSnapshotWriter / StubRunWriter) — behavioral contract
- `src/ga_crawler/runners/goldapple_run.py` — orchestrator template + dict-shape Phase 2 SnapshotWriter must accept
- `src/ga_crawler/enumeration/slug.py` — REUSE source for `_normalize_punct` + `CYRILLIC_TO_LATIN` table
- `src/ga_crawler/enumeration/goldapple_sitemap.py` — `_fetch_xml` curl_cffi+tenacity pattern Phase 2 mirrors
- `src/ga_crawler/parsers/goldapple_microdata.py` — parser pattern + state classifier Phase 2 mirrors
- `src/ga_crawler/runner/gates.py` — `auto_suggest_m`, `final_m_gate` source for D-203 refactor
- `src/ga_crawler/runner/stats.py` — `GoldappleStatsBuilder` pattern for ViledStatsBuilder
- `tests/conftest.py` — 11 existing fixtures Phase 2 inherits + extends
- `pyproject.toml` — pinned deps + `[tool.ga_crawler.crawl.goldapple]` namespace pattern
- `.claude/skills/spike-01-goldapple/SKILL.md` — spike findings, viled rate limit 2s, viled `__NEXT_DATA__`-first parser strategy
- `.planning/spikes/01-goldapple/sample-payloads/viled-nextdata-shape.json` — viled `__NEXT_DATA__` field paths (8 canonical paths captured)
- `.planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json` — 15-fetch results (15/15 success at 2s)
- `.planning/spikes/01-goldapple/sample-payloads/viled-home-brands-extract.json` — homepage brand-list extraction (seed for top-50)
- `.planning/spikes/01-goldapple/sample-payloads/viled-product-urls.txt` — 15 sample `/item/{numeric_id}` URLs
- `.planning/spikes/01-goldapple/sample-payloads/viled-sitemap.xml` — full sitemap (42,294 URLs — NOT used per D-223)
- `.planning/spikes/01-goldapple/sample-payloads/viled-kz-robots.txt` — no Crawl-delay, no anti-scraping clauses

### Secondary (MEDIUM confidence)
- [SQLite json_patch docs](https://sqlite.org/json1.html) — RFC-7396 MergePatch semantics, atomic at SQL level
- [SQLite Tutorial — json_patch](https://www.sqlitetutorial.net/sqlite-json-functions/sqlite-json_patch-function/) — syntax + examples
- `pyproject.toml` Phase 3 `[tool.ga_crawler.crawl.goldapple]` namespace — pattern for viled mirror
- `.planning/research/STACK.md` (referenced by CONTEXT canonical_refs) — full stack rationale (not re-read; trusted as canonical)
- `.planning/research/PITFALLS.md` Pitfall 6 (atomic merge into runs.stats), Pitfall 9 (Protocol contract drift) — referenced in CONTEXT

### Tertiary (LOW confidence — flagged for Wave 0 verification)
- `attributes[0].in_stock` field name on viled `__NEXT_DATA__` — Wave 0 probe required (A1)
- `attributes[0].price` vs `realPrice` discount semantics — Wave 0 probe required (A2)
- `/men/catalog/1310` returns `__NEXT_DATA__` with `pageProps.products[]` for unauth curl_cffi — Wave 0 probe required (A3)
- Pagination metadata key names (`totalCount`/`pageSize` vs `pagination.{}`) — Wave 0 probe required (A4)
- curl_cffi exception class import paths — Wave 0 verification (A7)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — locked in CLAUDE.md, pyproject.toml already pins all but PyYAML
- Architecture: HIGH — Phase 3 frozen modules supply 80% of patterns; Phase 2 mirrors them
- Storage layer: HIGH — SQLModel + SQLite + json_patch is well-trodden
- Volume normalizer grammar: MEDIUM — corpus needs Wave 0 probe to expand multipack patterns from real beauty SKU strings
- viled `__NEXT_DATA__` field paths: MEDIUM — 8 of 8 captured in spike but `in_stock` and discount semantics need Wave 0 verification (A1, A2)
- Catalog/1310 enumeration: LOW-MEDIUM — D-224 explicitly defers mechanism choice to Wave 0 probe; spike never tested catalog endpoints

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (30 days — stable libraries; viled HTML structure is the only volatile element, mitigated by snapshot-table immutability so a single bad week is recoverable)
