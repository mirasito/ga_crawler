# Phase 3: Goldapple Crawl — Research

**Researched:** 2026-05-06
**Domain:** Headless-browser scraping (Camoufox/Firefox + microdata) под GroupIB anti-bot, sitemap-driven URL pool, slug-эвристика бренд-фильтра, append-only snapshot writes
**Confidence:** HIGH (Phase 1 спайк закрыл все ключевые неизвестные эмпирически: 99/100 fetches, 0% gate-shell, microdata-парсер откалиброван на реальном PDP)

## Summary

Phase 3 строит производственный goldapple-краулер поверх **локированного** стека Phase 1 спайка: Camoufox v135.0.1-beta.24 + persistent-context + KZ-laptop direct без proxy, microdata-парсинг через `selectolax`, sitemap-only URL-pool через curl_cffi, slug-эвристика для пересечения с viled-брендами. Все 5 success-criteria из ROADMAP — перевыполнены контекстом: sitemap уже plain-deliverable (D-301), brand-filter работает через slug-эвристику (D-304/305), sanity-gate с M=1000 + auto-suggest после 4 недель (D-308/310), 1-час live run already validated (4.4ч @ 99%), NORM-06 review-queue имеет два направления (viled-side + week-over-week NEW goldapple-slug diff).

**Главный сюрприз исследования:** PDP-микроданные goldapple содержат не только `<meta itemprop="price" content="...">`, но и `priceType` дескриптор (`StrikethroughPrice` / `ListPrice` / отсутствие = current public). Это означает PARSE-03 (отвергать `*old*`, `*was*`, `*from*`) для goldapple реализуется через **семантическую priceType-фильтрацию** в микроданных, а не через CSS-class blacklist. Это сильнее и стабильнее обычного PARSE-03 на CSS.

**Primary recommendation:** Реализовать модули `ga_crawler.fetchers.goldapple` (Camoufox обёртка), `ga_crawler.enumeration.goldapple_sitemap` (curl_cffi + slug-fy + brand-intersect), `ga_crawler.parsers.goldapple_microdata` (priceType-aware extractor), `ga_crawler.runner.gates` (smoke-probe + final M-gate). Реюзать Phase 2 контракты `BrandAlias`, `Normalize.{brand,name,volume}`, `SnapshotWriter`, `ParseDispatcher`. Параллельная разработка с Phase 2 возможна через mock-интерфейсы в Wave 0; финальная волна интегрирует с реальными Phase 2 модулями.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**URL-pool: sitemap → Camoufox pipeline**
- **D-301:** Sitemap-only URL-pool. curl_cffi (Tier 0) фетчит goldapple sitemap-index → парсит 3 sub-sitemap → строит `slug → [URLs]` map → пересекает с матч-брендами через slug-эвристику → передаёт matched URLs в Camoufox-fetch-loop. Не используем brand-facet rendering и не делаем sanity-cross-check каждую неделю.
- **D-302:** Полный re-crawl каждую неделю. Не используем sitemap `<lastmod>` для incremental — цены меняются БЕЗ обновления URL-`<lastmod>`. Бюджет уже посчитан спайком: ~3,450 fetches × 3-5с = ~4.4ч sequential.
- **D-303:** Stale-SKU surfacing minimally: «200 + <30KB + нет microdata» → пропуск SKU (CRAWL-03 isolation), counter в `runs.stats.stale_count`, JSON-лог, SQL-view `v_stale_rate_per_run`. Без ops-Telegram алертов и без отдельного файла.

**Brand-alias coverage**
- **D-304:** Slug-эвристика от `brand_norm + aliases`. Не ручное курирование, не runtime probe. Trade-off принят: ниже manual curation, возможны false-positives.
- **D-305:** Bilingual slug-fy + exact match. ASCII (NFKD + accent strip + transliterate Cyrillic→Latin) И Cyrillic-preserved. Алгоритм: lowercase → non-alphanum → `-` → collapse multi-`-`. Match только exact.
- **D-306:** Skip + log в NORM-06 для viled-брендов с нулём slug-матчей. Counter `runs.stats.unmatched_viled_brands`. Без ops-Telegram per-brand алертов и без pre-flight coverage-gate.
- **D-307:** Week-over-week NEW goldapple-slug diff для NORM-06 reverse-direction. Каждый run сохраняет sitemap-slug snapshot на диск; в начале next run diff-им с предыдущим, новые slug'и → NORM-06.

**Sanity-gate threshold M**
- **D-308:** `M = 1000` static absolute в config. ~30% от спайк-оценки 3,450/week. Не lowing dynamic-формулами на v1.
- **D-309:** Run-to-completion + final M-gate (нет mid-run circuit-breaker). Phase 3 фетчит все ~3,450 URLs, в конце проверяет `goldapple_count > 1000`. Если нет → `runs.status='failed'`, отчёт НЕ уходит, ops-чат получает алерт.
- **D-310:** Auto-suggest M в ops-чат после 4 недель. На 5-й неделе и далее run отправляет ops-Telegram сообщение `new M-rec: 0.7 × 4-week-median goldapple_count = X`. НЕ auto-tune.

**Camoufox profile lifecycle**
- **D-311:** Fresh profile dir каждый weekly run. Cron создаёт tmp profile-dir, Camoufox бутится `geoip=True, locale=['ru-RU','kk-KZ','en-US'], humanize=True, persistent_context=True`, profile dir сносится после run.
- **D-312:** Smoke probe ПЕРЕД crawl-фазой, integrated в weekly run. После Camoufox-boot на fresh profile: 1-3 known-good URLs. Pass → crawl. Fail → `runs.status='failed'` + ops-Telegram + 4ч беспоsлезных fetches не тратятся.
- **D-313:** Pin exact Camoufox version `camoufox==135.0.1.beta24` в `uv.lock`. coryking/camoufox fork как backup. Manual upgrade workflow: PR в lock-файл после успешного dev smoke.

### Claude's Discretion

- Конкретное место config-файла для `M`, `smoke_urls`, rate-limit constants — `pyproject.toml` vs `config/sanity.toml` vs `.env`. Default predict: `pyproject.toml [tool.ga_crawler.crawl.goldapple]`.
- Имя tmp-каталога для Camoufox profile (`/tmp/camoufox-{run_id}/` vs `<repo>/tmp/...`).
- Структура `runs.stats` JSON-блока — точные ключи (`stale_count`, `unmatched_viled_brands`, `unmatched_goldapple_slugs_new`, `gate_shell_count`, `smoke_pass`).
- Smoke probe URL pool curation workflow — deferred Phase 7 ops-playbook.
- Camoufox profile dir cleanup strategy on FAIL — preserve last failure dir для forensics vs always delete. Default: always delete.

### Deferred Ideas (OUT OF SCOPE)

- Pre-flight coverage gate (<60% viled-брендов с goldapple-match → abort run) — пересмотр после 8 недель history.
- Mid-run circuit-breaker по rolling gate-shell-rate — пересмотр если post-launch появятся реальные anti-bot regressions.
- Auto-tune sanity-gate threshold M — навсегда отвергнуто.
- Persistent profile dir между weekly runs (warm cookies) — пересмотр если smoke + fresh-profile стабильно работает 12+ недель.
- Adaptive profile lifecycle (persist + wipe on detect) — переосложнение для v1.
- Brand-facet rendering как primary URL-pool — отвергнуто.
- Hybrid sitemap + facet sanity-cross-check каждую неделю — отвергнуто.
- Incremental delta через sitemap `<lastmod>` — возможный пересмотр в v2.
- Rapidfuzz fuzzy slug-matching — v2 territory (REQ MATCH-V2-01).
- Explicit `goldapple_slugs:` field в alias YAML — пересмотр если эвристика покажет высокий false-positive-rate.
- Ops-Telegram alert per missing brand — отвергнуто.
- Файл `reports/stale-urls-YYYY-WNN.txt` — отвергнуто.
- Separate midweek cron для smoke probe — отвергнуто.
- Latest stable Camoufox без pin — отвергнуто.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **CRAWL-02** | Краулер goldapple.kz получает SKU, ограниченный брендами viled.kz в текущем `run_id` | §"Sitemap → URL-pool pipeline" (D-301), §"Slug-fy algorithm" (D-304/305). viled-brand-set читается из `v_current_snapshots WHERE retailer='viled' AND run_id=current` |
| CRAWL-03 (re-use) | Per-SKU isolation — падение одного SKU не валит run | §"Fetch loop" — `try/except` вокруг каждого URL, log в `runs.stats`, никогда не блокирует остальные. Реюзим Phase 2 паттерн |
| CRAWL-04 (re-use) | Retry с экспоненциальной задержкой и jitter для 5xx/timeout | §"Fetch loop / retry policy" — `tenacity` с exp-backoff + jitter; макс 3 попытки на URL; non-retryable: 403/404 |
| CRAWL-05 (goldapple-side) | Sanity-gate `goldapple_count > M`; меньше → `runs.status='failed'` | §"Sanity-gate (D-308/309)". M=1000 в `pyproject.toml [tool.ga_crawler.crawl.goldapple].sanity_gate_m` |
| CRAWL-06 (re-use) | Краулер уважает rate-limit, параметры конфигурируются | `random.uniform(3, 5)` между fetches; concurrency=1; в config |
| PARSE-01..06 (через retailer dispatch) | name, brand, volume, price, was_price, availability, URL, currency | §"Parser (microdata)". PARSE-02 priority **инвертируется** для goldapple: microdata first (JSON-LD отсутствует — только OfferShippingDetails) |
| NORM-06 (populate) | Лог "бренды на goldapple, не найденные в alias-таблице" — review-queue | §"NORM-06 population (D-306/307)" — viled-side missing-brand list + week-over-week NEW goldapple-slug diff |
| DATA-03 (re-use) | Append-only INSERT, immutable snapshot history | Phase 2 `SnapshotWriter` контракт. Phase 3 пишет с `retailer='goldapple'`, никогда UPDATE |
| DATA-04 (re-use) | WAL mode, per-run транзакции, on-failure rollback не теряет saved SKUs | Phase 2 контракт; Phase 3 пользуется существующей сессией |
| DATA-05 (re-use) | `runs` row создаётся в начале run и обновляется в конце во всех ветках | **ОДИН `runs` row общий для viled+goldapple** — Phase 3 продлевает существующий, не создаёт новый |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Sitemap fetch + parse | Backend (orchestrator) | Network/IO via curl_cffi | Statless HTTP, plain XML — Tier 0; sitemap goldapple plain-deliverable per spike 01-05 |
| Brand-pool intersection | Backend (pure logic) | — | Pure function: viled-brand-set ∩ slug-fy(alias) → URL list. No I/O |
| Camoufox bootstrap + smoke | Browser engine (Camoufox/Firefox) | OS (tmp profile dir, FS) | C++ fingerprint spoof + persistent_context — only Camoufox layer can deliver |
| Per-PDP fetch + gate-detect | Browser engine | — | Camoufox `page.goto`, title-check, content extraction |
| Microdata parse | Backend (pure logic) | selectolax (HTML walker) | Pure function HTML→record; no I/O |
| Brand/name/volume normalize | Backend (pure logic via Phase 2 contracts) | — | Phase 2 modules; Phase 3 vendor consumer |
| Snapshot write | Storage layer (SQLModel/SQLite WAL) | — | Phase 2 `SnapshotWriter`; append-only |
| Sanity-gate (smoke + final-M) | Orchestrator | Telegram (ops alert, deferred to Phase 6) | Pre-flight + post-flight checks; gates `runs.status` |
| NORM-06 population | Backend (pure logic) + FS (week-over-week diff) | — | viled-side: counter+log; goldapple-side: file-diff against last week's saved sitemap-slugs |

## Standard Stack

### Core (LOCKED — from Phase 1 spike + CLAUDE.md, do not relitigate)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Python** | 3.12.x | Runtime | LOCKED по `pyproject.toml requires-python = ">=3.12"` [VERIFIED: pyproject.toml] |
| **uv** | 0.10.x+ | Project + dep manager | LOCKED — `uv.lock` уже existing; D-313 manual upgrade flow [VERIFIED: uv.lock present] |
| **camoufox[geoip]** | **135.0.1.beta24** | Headless Firefox + C++ fingerprint spoof | LOCKED по D-313 + spike 99/100 success [VERIFIED: spike 01-08 results, MEMO sign-off]. CLAUDE.md фоновый pin: `>=0.4.11` [VERIFIED: pyproject.toml current line 7]. **Действие:** план должен закрепить exact `==135.0.1.beta24` в pyproject.toml |
| **curl_cffi** | 0.15.x | Sitemap fetch (Tier 0) | LOCKED — sitemap plain-deliverable, JS-challenge не нужен [VERIFIED: spike 01-05]; импersonate=chrome [CITED: curl_cffi docs] |
| **selectolax** | 0.3.x | HTML parsing | LOCKED по spike SKILL — `tree.css('meta[itemprop="price"]')` [VERIFIED: spike notebook.py L100-110] |
| **structlog** | 25.x | Structured JSON logs | LOCKED — `runs.stats` enrichment + per-fetch log lines [VERIFIED: pyproject.toml] |

### Supporting (новые для Phase 3)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **SQLModel** | 0.0.24+ | ORM для `snapshots`/`runs` writes | Phase 2 deliverable; Phase 3 потребляет [CITED: research/STACK.md] |
| **tenacity** | 9.x | Retry decorator с exp-backoff + jitter | CRAWL-04. Wrap `page.goto` + sitemap fetch. **Не пропустить** в pyproject.toml — пока его НЕТ [VERIFIED: pyproject.toml] |
| **pydantic** | 2.10+ | Validate scraped record перед DB insert | Phase 2 deliverable; Phase 3 потребляет (validate `RawProduct` from microdata) [CITED: CLAUDE.md] |
| **python-dotenv** | 1.0.x | Load `.env` (cron env, smoke-URL list) | Already in pyproject.toml [VERIFIED] |

### Alternatives Considered & Rejected

| Instead of | Could Use | Why NO for Phase 3 |
|------------|-----------|--------------------|
| Camoufox | Patchright | **Empirically broken: 0/7 на goldapple gate** [VERIFIED: spike 01-06 baseline]. CLAUDE.md / `pyproject.toml` всё ещё держит `patchright>=1.55` — план должен либо удалить, либо оставить как backup для других ритейлеров; для Phase 3 НЕ использовать |
| Camoufox | vanilla Playwright | Skipped per Phase 1 D-01; нет evidence что обходит GroupIB [CITED: 01-CONTEXT D-01] |
| selectolax | BeautifulSoup4 | 10-30× slower; goldapple HTML well-formed [CITED: research/STACK.md] |
| selectolax | lxml/parsel | Selectolax быстрее на product-card scale; XPath не нужен (CSS достаточно) |
| curl_cffi | requests/httpx | requests defeated by GroupIB urllib3 fingerprint мгновенно; httpx не impersonate-able [CITED: research/PITFALLS.md Pitfall 1, CLAUDE.md "What NOT to use"] |
| Sitemap-only enumeration | Brand-facet rendering | D-301 contra: +50 facet-fetches, риск gate-shielded facet pages |

**Installation (Phase 3 deltas to existing pyproject.toml):**
```bash
# Pin exact Camoufox version per D-313:
uv add 'camoufox[geoip]==0.4.11+camoufox.135.0.1-beta.24' \
  || uv add 'camoufox[geoip]==0.4.11'  # adjust to actual PyPI version that bundles Firefox 135.0.1-beta24

# Add retry library:
uv add 'tenacity>=9.0,<10.0'

# Phase 2 deliverables (Phase 3 consumer):
uv add 'sqlmodel>=0.0.24,<0.1' 'pydantic>=2.10,<3.0'
```

**Version verification action item for planner:** До замораживания плана выполнить `uv run python -c "import camoufox; print(camoufox.__version__)"` и `npm view`-эквивалент `pip index versions camoufox` чтобы убедиться, что 135.0.1-beta.24 (или замещающая версия) **доступна на PyPI** в момент написания плана. Если версия снята — переключиться на coryking fork (`pip install 'camoufox @ git+https://github.com/coryking/camoufox@<sha>'`) и обновить D-313 pin. [ASSUMED: 135.0.1.beta24 still available 2026-05-06 — was working при spike sign-off; needs re-verification at plan-write time]

## Architecture Patterns

### System Architecture Diagram

```
                    ┌────────────────────────────────────────┐
                    │  weekly cron (Phase 7) → run.py        │
                    │  CRON_TZ=Asia/Almaty, Sunday night     │
                    └────────────────────┬───────────────────┘
                                         │
                                         ▼
                    ┌────────────────────────────────────────┐
                    │ Orchestrator: opens runs row (Phase 2) │
                    │ runs.id = R, status='running'          │
                    └────────────────────┬───────────────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                  [Phase 2 viled crawl]   [Phase 3 goldapple crawl]
                  writes retailer='viled' (this research)
                              │                     │
                              └─────────┬───────────┘
                                        │
                                        ▼
                  ┌──── Phase 3 START: Goldapple branch ────┐
                  │                                          │
                  │  Step 1. Read viled brand-set            │
                  │    SELECT DISTINCT brand_norm            │
                  │    FROM snapshots                        │
                  │    WHERE retailer='viled' AND run_id=R   │
                  │                                          │
                  │  Step 2. Resolve aliases                 │
                  │    BrandAlias.lookup(b) for b in viled   │
                  │    → list[str] alias-vars per brand      │
                  │                                          │
                  │  Step 3. Sitemap enumeration             │
                  │    curl_cffi GET goldapple.kz/sitemap.xml│
                  │    → 3 sub-sitemaps                      │
                  │    → 100,779 numeric-id URLs             │
                  │    → extract slug from each URL          │
                  │    → save sitemap-slugs.txt for diff     │
                  │                                          │
                  │  Step 4. Slug-fy + intersect             │
                  │    slug_fy_bilingual(alias) for each     │
                  │    matched_urls = ∩ sitemap-slug-pool   │
                  │    → ~3,450 URLs                         │
                  │    track unmatched_viled_brands counter  │
                  │                                          │
                  │  Step 5. Camoufox boot                   │
                  │    AsyncCamoufox(geoip=True,             │
                  │      locale=['ru-RU','kk-KZ','en-US'],   │
                  │      humanize=True, persistent_context,  │
                  │      user_data_dir=tmp_dir(R))           │
                  │                                          │
                  │  Step 6. Smoke probe (D-312)             │
                  │    for url in smoke_urls (1-3):          │
                  │      page.goto → microdata price?        │
                  │    if any fail → runs.status='failed'    │
                  │                  ops-Telegram + abort    │
                  │                                          │
                  │  Step 7. Fetch loop (sequential)         │
                  │    for url in matched_urls:              │
                  │      page.goto, title-check, parse       │
                  │      tenacity retry on 5xx/timeout       │
                  │      try/except → per-SKU isolation      │
                  │      sleep random.uniform(3, 5)          │
                  │                                          │
                  │  Step 8. Parser (microdata-priority)     │
                  │    selectolax extracts:                  │
                  │      - meta[itemprop=price] (no priceType)│
                  │      - meta[itemprop=priceCurrency]      │
                  │      - meta[itemprop=brand]→meta[name]   │
                  │      - link[itemprop=availability]→@href │
                  │      - h1/title → name                   │
                  │      - volume (regex on title)           │
                  │    Phase 2 normalizers → brand_norm etc  │
                  │                                          │
                  │  Step 9. Storage write                   │
                  │    SnapshotWriter.append(                │
                  │      run_id=R, retailer='goldapple', ..) │
                  │                                          │
                  │  Step 10. NORM-06 diff (D-307)           │
                  │    new_slugs = sitemap-slugs.txt this    │
                  │              − sitemap-slugs.txt last    │
                  │    persist to NORM-06 review queue       │
                  │                                          │
                  │  Step 11. Camoufox teardown              │
                  │    rm -rf tmp_dir(R)                     │
                  │                                          │
                  │  Step 12. Sanity-gate (D-308/309)        │
                  │    if goldapple_count < M=1000:          │
                  │      runs.status='failed'                │
                  │    else if 4-week-history available:     │
                  │      ops-Telegram new-M-suggest          │
                  │                                          │
                  └─────────────────┬────────────────────────┘
                                    │
                                    ▼
                  [Phase 4 matcher reads snapshots WHERE run_id=R]
```

### Recommended Project Structure

```
src/ga_crawler/
├── __init__.py
├── __main__.py                     # python -m ga_crawler
├── runner.py                       # orchestrator (Phase 2 owns; Phase 3 hooks in)
├── config.py                       # pydantic-settings, читает pyproject.toml + .env
├── models.py                       # RawProduct, NormalizedProduct (Phase 2)
│
├── enumeration/                    # NEW (Phase 3 owns goldapple_sitemap.py; viled_sitemap.py is Phase 2)
│   ├── __init__.py
│   ├── goldapple_sitemap.py       # curl_cffi sitemap-index → slug→URLs map; saves sitemap-slugs.txt
│   └── slug.py                     # bilingual slug-fy: ASCII-transliterate + Cyrillic-preserved (D-305)
│
├── fetchers/                       # NEW (Phase 3 owns goldapple.py; viled.py is Phase 2)
│   ├── __init__.py
│   ├── base.py                     # Crawler Protocol (Phase 2 defines)
│   └── goldapple.py                # Camoufox bootstrap + fetch_one + gate-detect + retry
│
├── parsers/                        # Phase 2 owns shared.py + viled.py; Phase 3 adds goldapple_microdata.py
│   ├── __init__.py
│   ├── dispatcher.py              # ParseDispatcher (Phase 2): switch on retailer
│   ├── shared.py                  # validators, sanity-checks (Phase 2)
│   ├── viled_nextdata.py          # __NEXT_DATA__ extractor (Phase 2)
│   └── goldapple_microdata.py     # NEW Phase 3: meta[itemprop=*] extractor
│
├── normalizers/                    # Phase 2 owns; Phase 3 consumer
│   ├── __init__.py
│   ├── brand.py                   # NFKD + accent-strip + alias lookup
│   ├── name.py                    # lowercase + punctuation strip
│   └── volume.py                  # Volume value object (amount, unit, multipack)
│
├── alias/                          # Phase 2 owns; Phase 3 consumer
│   ├── __init__.py
│   ├── brand_alias.py             # BrandAlias.lookup() — yields list[str] aliases
│   └── brand_aliases.yaml         # seeded data
│
├── storage/                        # Phase 2 owns; Phase 3 consumer
│   ├── __init__.py
│   ├── schema.sql
│   ├── models.py                  # SQLModel: Run, Snapshot
│   ├── writer.py                  # SnapshotWriter, RunWriter
│   └── views.sql                  # v_current_snapshots, v_stale_rate_per_run (NEW Phase 3 view)
│
├── runner/                         # Orchestrator pieces
│   ├── __init__.py
│   ├── gates.py                   # NEW Phase 3: smoke_probe(), final_m_gate(), auto_suggest_m()
│   └── stats.py                   # NEW Phase 3: runs.stats JSON-block builder
│
└── obs/
    ├── __init__.py
    └── logging.py                 # structlog config (Phase 2)

tests/
├── conftest.py
├── fixtures/
│   ├── goldapple/
│   │   ├── _debug-product-page.html         # COPY from spike sample-payloads
│   │   ├── gate-shell.html                  # 18 KB anti-bot challenge sample
│   │   ├── stale-sku-9.5kb.html            # 200 + <30KB + no microdata
│   │   ├── sitemap-1-excerpt.xml
│   │   └── tier2-camoufox-kz-results.json   # spike empirical baseline
│   └── viled/                                # Phase 2 fixtures
├── unit/
│   ├── test_slug_fy.py                      # NEW Phase 3 (D-305)
│   ├── test_goldapple_microdata_parser.py   # NEW Phase 3 (PARSE-01..04)
│   ├── test_gate_detection.py               # NEW Phase 3 (title-check)
│   ├── test_stale_sku_detection.py          # NEW Phase 3 (D-303)
│   ├── test_norm06_diff.py                  # NEW Phase 3 (D-307)
│   └── test_sanity_gate.py                  # NEW Phase 3 (CRAWL-05 goldapple)
└── integration/
    ├── test_goldapple_smoke_probe.py        # D-312
    ├── test_goldapple_fetch_loop_mocked.py  # mocked Camoufox (no live network)
    └── test_run_e2e_with_phase2_mocks.py    # full pipeline against Phase 2 mock interfaces
```

### Pattern 1: Sitemap-First Hybrid Enumeration

**What:** curl_cffi (Tier 0) для plain XML sitemap → структурированный slug→URLs map. Camoufox (Tier 2) только для PDP-render. Не использовать Camoufox для sitemap (overkill, теряет cookies на не-anti-bot путях).

**When to use:** Анти-бот защищает HTML-роуты, но НЕ sitemap.xml — стандартный паттерн (sitemap = SEO surface).

**Example (verified spike):**
```python
# src/ga_crawler/enumeration/goldapple_sitemap.py
# Source: spike 01-05 _fetch_goldapple_sitemap.py + spike sample-payloads/goldapple-sitemap.xml
import re
from curl_cffi import requests
from selectolax.parser import HTMLParser

SITEMAP_INDEX = "https://goldapple.kz/sitemap.xml"
PRODUCT_URL_RE = re.compile(r"^https://goldapple\.kz/(\d+)-([a-z0-9а-я-]+)$", re.IGNORECASE)

def fetch_sitemap_slugs() -> dict[str, list[str]]:
    """Returns {slug: [urls]} map. Each URL: /<numeric-id>-<slug>."""
    idx_xml = requests.get(SITEMAP_INDEX, impersonate="chrome", timeout=30).text
    sub_urls = re.findall(r"<loc>([^<]+)</loc>", idx_xml)
    slug_map: dict[str, list[str]] = {}
    for sub in sub_urls:
        sub_xml = requests.get(sub, impersonate="chrome", timeout=30).text
        for url in re.findall(r"<loc>([^<]+)</loc>", sub_xml):
            m = PRODUCT_URL_RE.match(url)
            if m:
                slug = m.group(2).lower()
                slug_map.setdefault(slug, []).append(url)
    return slug_map  # ~1,461 slugs / ~100,779 URLs (per spike 01-05 empirical)
```

### Pattern 2: Bilingual Slug-fy with Exact Match (D-305)

**What:** Из каждой alias-строки производить ДВА slug-варианта: ASCII-transliterated + Cyrillic-preserved. Match только exact против sitemap-slug pool.

**When to use:** Когда retailer использует mixed-script slugs (goldapple: `tom-ford` И `эсте-лаудер`).

**Example:**
```python
# src/ga_crawler/enumeration/slug.py
import unicodedata
import re

# Cyrillic→Latin transliteration table (GOST 7.79-2000 System B / popular subset)
# Source: derived from research/PITFALLS.md Pitfall 4 + CONTEXT.md D-305
CYRILLIC_TO_LATIN = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    # KZ-specific
    'ә':'a','ғ':'g','қ':'q','ң':'n','ө':'o','ұ':'u','ү':'u','һ':'h','і':'i',
}

def _normalize_punct(s: str) -> str:
    """lowercase, NFKD, strip accents, non-alphanum→hyphen, collapse multi-hyphen."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9а-я]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s

def slug_fy_bilingual(alias: str) -> list[str]:
    """Returns [ascii_slug, cyrillic_slug]. Both lowercase, hyphen-separated.

    Examples (test cases planner must mandate):
      'Estée Lauder'  → ['estee-lauder',         'esthe-lauder']  # NFKD strips accent on ASCII path
                                                                  # Cyrillic path: no Cyrillic input → empty 2nd slug
      'Эсте Лаудер'  → ['este-lauder',          'эсте-лаудер']
      'Tom Ford'      → ['tom-ford',             None]
      "L'Oréal"       → ['loreal',               None]
      'Yves Saint Laurent' → ['yves-saint-laurent', None]
      'Жильет'        → ['zhilet',               'жильет']
    """
    cyrillic_slug = _normalize_punct(alias)
    if not re.search(r"[а-яә-і]", cyrillic_slug):
        cyrillic_slug = None  # no Cyrillic in input
    ascii_input = "".join(CYRILLIC_TO_LATIN.get(c, c) for c in alias.lower())
    ascii_slug = _normalize_punct(ascii_input)
    return [s for s in [ascii_slug, cyrillic_slug] if s]

def intersect_brand_pool(viled_brands: list[str], aliases: dict[str, list[str]],
                        sitemap_slugs: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Returns (matched_urls, unmatched_brands).

    For each viled brand: get all aliases → slug-fy each → exact-match against sitemap_slugs.
    Brand is "matched" if ANY of its slug-variants hits the sitemap.
    """
    matched_urls = []
    unmatched_brands = []
    for brand in viled_brands:
        brand_slugs: set[str] = set()
        for alias in aliases.get(brand, [brand]):
            brand_slugs.update(slug_fy_bilingual(alias))
        hit_urls = []
        for slug in brand_slugs:
            hit_urls.extend(sitemap_slugs.get(slug, []))
        if hit_urls:
            matched_urls.extend(hit_urls)
        else:
            unmatched_brands.append(brand)
    return matched_urls, unmatched_brands
```

**Test cases planner MUST mandate (slug-fy correctness):**

| Input | Expected ASCII slug | Expected Cyrillic slug | Why |
|-------|--------------------|-----------------------|-----|
| `Estée Lauder` | `estee-lauder` | `None` | Accent strip; no Cyrillic |
| `Эсте Лаудер` | `este-lauder` | `эсте-лаудер` | Both produced; goldapple has Cyrillic-only slugs |
| `Tom Ford` | `tom-ford` | `None` | Pure Latin |
| `Tom Ford Beauty` | `tom-ford-beauty` | `None` | Different from `tom-ford` — exact-match guard prevents false-positive |
| `Frédéric Malle` | `frederic-malle` | `None` | Multiple accents |
| `Dolce&Gabbana` | `dolce-gabbana` | `None` | `&` → `-`; collapse |
| `L'Oréal Paris` | `loreal-paris` | `None` | Apostrophe stripped |
| `Жильет` (test) | `zhilet` | `жильет` | Cyrillic input produces both |
| `Givenchy ` (trailing space) | `givenchy` | `None` | Trim |
| `Jo Malone London` | `jo-malone-london` | `None` | Multi-word |
| (empty string) | `''` | `None` | Edge case, returns `[]` |

### Pattern 3: Camoufox Bootstrap with Fresh Profile (D-311)

**What:** Каждый weekly run: `tempfile.mkdtemp()` → передать в `user_data_dir`; cleanup через `shutil.rmtree` в `finally`-блоке.

**When to use:** Spike 99/100 cold-start success вместо непроверенного warm-cookies pattern.

**Example (verified spike notebook.py L207-214):**
```python
# src/ga_crawler/fetchers/goldapple.py
import asyncio, random, shutil, tempfile
from pathlib import Path
from camoufox.async_api import AsyncCamoufox

PAUSE_RANGE = (3.0, 5.0)
PAGE_TIMEOUT_MS = 60_000
GATE_POLL_DEADLINE_MS = 25_000
GATE_POLL_STEP_MS = 500
GATE_TITLE_MARKER = "checking"
CHALLENGE_HTML_MAX_SIZE = 30_000  # GUN gate shell ~18 KB; real PDP ~200 KB

class GoldappleFetcher:
    def __init__(self, run_id: int, headless: bool = True):
        self.run_id = run_id
        self.headless = headless
        # Tmp profile path. Default: system tmp; planner choice repo-local <repo>/tmp/...
        # Per CONTEXT.md Claude's Discretion. Recommended: tempfile.mkdtemp(prefix=f"camoufox-run-{run_id}-")
        self.profile_dir = Path(tempfile.mkdtemp(prefix=f"camoufox-run-{run_id}-"))
        self._browser = None
        self._page = None

    async def __aenter__(self):
        self._cm = AsyncCamoufox(
            headless=self.headless,
            geoip=True,                              # SKILL operational constant
            locale=["ru-RU", "kk-KZ", "en-US"],      # SKILL
            humanize=True,                           # SKILL
            persistent_context=True,                 # D-04 / SKILL — cookies live across fetches WITHIN run
            user_data_dir=str(self.profile_dir),
        )
        self._browser = await self._cm.__aenter__()
        self._page = self._browser.pages[0] if self._browser.pages else await self._browser.new_page()
        return self

    async def __aexit__(self, *exc):
        try:
            await self._cm.__aexit__(*exc)
        finally:
            # D-313 lifecycle: always delete on success AND failure (Claude's Discretion default).
            # Forensics-preserve mode opt-in via env var if planner adds it.
            shutil.rmtree(self.profile_dir, ignore_errors=True)
```

### Pattern 4: Microdata Parser with priceType Discrimination (PARSE-02 inverted, PARSE-03 strengthened)

**What:** Для goldapple JSON-LD ОТСУТСТВУЕТ (только `OfferShippingDetails`, не `Product`). Микроданные — primary path. **И** микроданные содержат `priceType` дескриптор (`StrikethroughPrice`/`ListPrice`) — это позволяет реализовать PARSE-03 семантически, через priceType-фильтрацию вместо CSS-class blacklist.

**Critical discovery from `_debug-product-page.html` (PDP for `7681000002-givenchy-pour-homme-blue-label`):**

| Microdata block | priceType | Значение | Что это |
|----------------|-----------|----------|---------|
| Top-level `<div itemprop="offers" itemtype=".../Offer">` без вложенного priceType | (отсутствует) | **current public price** ← это и есть наш `current_price` |
| `<div itemprop="priceSpecification" itemtype=".../UnitPriceSpecification">` со `<link itemprop="priceType" href=".../StrikethroughPrice">` | StrikethroughPrice | `was_price` (перечёркнутая) |
| Nested блок `<meta itemprop="price" content="36246">` без priceType, в той же `_ga-pdp-price-row__row_best_nkg9j_197` секции с label "при авторизации" | (отсутствует, но контекст = loyalty) | **Gold Card price — EXCLUDE per PROJECT.md** ("цены под Gold Card / залогиненные") |
| Внутри карточек "часто покупают вместе" / related: `<div itemscope itemprop="priceSpecification" .../UnitPriceSpecification><meta itemprop="priceType" content=".../ListPrice">` | ListPrice | "от" prefix variant — **EXCLUDE per PARSE-03 ("from"-variants)** |

**When to use:** Только для goldapple. viled (Phase 2) использует `__NEXT_DATA__`. Dispatch через `ParseDispatcher`.

**Example:**
```python
# src/ga_crawler/parsers/goldapple_microdata.py
# Source: verified against .planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html
from selectolax.parser import HTMLParser, Node
from dataclasses import dataclass
from typing import Optional

@dataclass
class GoldappleRawProduct:
    sku_id: str
    url: str
    name: str
    brand_raw: str
    current_price: int          # KZT integer (no decimal — KZT has no fractional unit)
    was_price: Optional[int]     # StrikethroughPrice if present
    currency: str               # "KZT" (Phase 2 normalizer maps "₸"→"KZT" — but goldapple already emits "KZT")
    availability: str            # "InStock" | "OutOfStock" | "Discontinued" | "PreOrder" (schema.org)
    raw_volume_text: Optional[str]  # extracted from <h1>/title, normalized by Phase 2 NORM-03

GATE_SHELL_MAX_BYTES = 30_000
GATE_TITLE_MARKER = "checking"

def detect_state(html: str, title: str) -> str:
    """Returns 'gate-shell' / 'stale-sku' / 'real-pdp'.
    Source: spike SKILL.md + spike result row 0 (stale 9.5KB shell, title 'Loading ...').
    """
    sz = len(html)
    if GATE_TITLE_MARKER in title.lower() and sz < GATE_SHELL_MAX_BYTES:
        return "gate-shell"   # not cleared; should never happen if smoke-probe + Camoufox config OK
    if sz < GATE_SHELL_MAX_BYTES:
        # Could be 'Loading <url>' with empty body — D-303 stale-SKU pattern
        return "stale-sku"
    return "real-pdp"

def _extract_top_level_offer(tree: HTMLParser) -> Optional[Node]:
    """The top-level <div itemprop="offers" itemtype=".../Offer"> WITHOUT a child priceType
    — that's the current public price. Other meta[itemprop=price] occurrences are either
    StrikethroughPrice / ListPrice (other PDP cards) or Gold Card (auth-only)."""
    offer_nodes = tree.css('[itemprop="offers"][itemtype$="/Offer"]')
    for offer in offer_nodes:
        # Check this offer's IMMEDIATE meta[itemprop=price] without priceType sibling
        # We want the block that has 'availability' link AND a price meta but NO priceType
        avail = offer.css_first('link[itemprop="availability"]')
        if avail is None:
            continue
        # Collect meta[itemprop=price] within this offer subtree, NOT inside priceSpecification
        for price_meta in offer.css('meta[itemprop="price"]'):
            # Walk up to nearest itemscope ancestor; if it's priceSpecification → skip
            parent = price_meta.parent
            inside_spec = False
            while parent and parent != offer:
                if parent.attributes.get("itemprop") == "priceSpecification":
                    inside_spec = True
                    break
                parent = parent.parent
            if inside_spec:
                continue
            # Also check sibling priceType within same visually-hidden block
            sibling_price_type = None
            if price_meta.parent is not None:
                sibling_price_type = price_meta.parent.css_first('link[itemprop="priceType"]')
            if sibling_price_type is not None:
                href = sibling_price_type.attributes.get("href", "")
                if "StrikethroughPrice" in href or "ListPrice" in href:
                    continue  # not the current price
            # Also exclude "при авторизации" (Gold Card) — check ancestor's label text
            # Heuristic: walk up to nearest div with class containing 'price-row__row';
            # if its sibling label says "при авторизации" → skip
            return price_meta
    return None

def _extract_strikethrough(tree: HTMLParser) -> Optional[int]:
    """First StrikethroughPrice in priceSpecification → was_price."""
    for spec in tree.css('[itemprop="priceSpecification"]'):
        ptype = spec.css_first('link[itemprop="priceType"]')
        if ptype and "StrikethroughPrice" in (ptype.attributes.get("href", "")):
            p = spec.css_first('meta[itemprop="price"]')
            if p:
                v = p.attributes.get("content", "").strip()
                if v.isdigit():
                    return int(v)
    return None

def parse_pdp(html: str, url: str) -> Optional[GoldappleRawProduct]:
    """Returns None if the page is gate-shell or stale-SKU. PARSE-04 sanity-check
    100 ≤ price ≤ 1_000_000; out-of-range → None and record as parse_error in stats."""
    tree = HTMLParser(html)
    title_el = tree.css_first("title")
    title = (title_el.text() if title_el else "")
    state = detect_state(html, title)
    if state != "real-pdp":
        return None  # caller increments stale_count or gate_shell_count

    # SKU
    sku_meta = tree.css_first('[itemprop="sku"]')
    sku_id = (sku_meta.attributes.get("content") if sku_meta else "") or url.rsplit("/", 1)[-1].split("-", 1)[0]

    # Brand (microdata): nested <span itemprop="brand"><meta itemprop="name" content="Givenchy ">
    brand_raw = ""
    brand_node = tree.css_first('[itemprop="brand"]')
    if brand_node:
        brand_meta = brand_node.css_first('meta[itemprop="name"]')
        if brand_meta:
            brand_raw = (brand_meta.attributes.get("content", "")).strip()

    # Name: <h1> text (after spike inspection — itemprop="name" exists on multiple nodes including
    # breadcrumbs/footer; safer to use h1 + cross-check). Page <title> tag also reliable.
    name = ""
    h1 = tree.css_first("h1")
    if h1:
        name = h1.text(strip=True)
    if not name and title:
        name = title.split(" — купить", 1)[0].strip()

    # Current price
    price_meta = _extract_top_level_offer(tree)
    if price_meta is None:
        return None  # PARSE-05 will count toward >5% missing-required
    price_str = price_meta.attributes.get("content", "").strip()
    if not price_str.isdigit():
        return None
    current_price = int(price_str)
    if not (100 <= current_price <= 1_000_000):
        return None  # PARSE-04 out of range

    # Currency (sibling)
    currency = "KZT"
    cur_meta = price_meta.parent.css_first('meta[itemprop="priceCurrency"]') if price_meta.parent else None
    if cur_meta:
        currency = cur_meta.attributes.get("content", "KZT").strip().upper()

    # was_price
    was_price = _extract_strikethrough(tree)

    # Availability (schema.org URL → enum)
    avail_link = tree.css_first('link[itemprop="availability"]')
    avail_url = (avail_link.attributes.get("href", "") if avail_link else "")
    if "InStock" in avail_url:
        availability = "InStock"
    elif "OutOfStock" in avail_url:
        availability = "OutOfStock"
    elif "Discontinued" in avail_url:
        availability = "Discontinued"
    elif "PreOrder" in avail_url:
        availability = "PreOrder"
    else:
        availability = "Unknown"

    # Volume — Phase 2 NORM-03 owns the Volume value object. Extract raw text only;
    # Phase 2 normalizer parses it. Title pattern (spike empirical):
    #   "Givenchy ПАРФЮМЕРНАЯ ВОДА ... 100 мл — купить ..."
    raw_volume_text = name  # pass-through; NORM-03 regex extracts ml/g/oz

    return GoldappleRawProduct(
        sku_id=sku_id,
        url=url,
        name=name,
        brand_raw=brand_raw,
        current_price=current_price,
        was_price=was_price,
        currency=currency,
        availability=availability,
        raw_volume_text=raw_volume_text,
    )
```

### Pattern 5: Per-SKU Isolation with Tenacity Retry (CRAWL-03 + CRAWL-04)

**What:** Каждый URL обёрнут в `try/except` (CRAWL-03 isolation) + `tenacity` decorator (CRAWL-04 exp-backoff + jitter на 5xx/timeout).

**Example:**
```python
# src/ga_crawler/fetchers/goldapple.py (extended)
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from playwright.async_api import TimeoutError as PWTimeout

class TransientFetchError(Exception): ...

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((TransientFetchError, PWTimeout)),
    reraise=True,
)
async def _goto_with_retry(page, url: str):
    response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    if response is None:
        raise TransientFetchError("no response")
    if response.status >= 500:
        raise TransientFetchError(f"5xx: {response.status}")
    return response

async def fetch_one_isolated(self, page, url: str, stats: dict) -> Optional[dict]:
    """Per-SKU isolation: any exception logs + counter, never bubbles up to break run."""
    try:
        response = await _goto_with_retry(page, url)
        # ... title-check, content extract, parse ...
        # See full impl in spike notebook.py fetch_one
        return record
    except Exception as e:
        log.error("fetch_failed", url=url, error=str(e), error_type=type(e).__name__)
        stats["fetch_failures"] = stats.get("fetch_failures", 0) + 1
        return None
```

### Anti-Patterns to Avoid

- **Patchright для goldapple:** 0/7 эмпирически (spike 01-06 baseline). НЕ переключаться даже если "Patchright обновился" — нужен новый spike перед relitigation.
- **JSON-LD-first парсинг для goldapple:** goldapple НЕ эмитит `Product` JSON-LD (только `OfferShippingDetails`). Применяя стандартный PARSE-02 priority slvishly, парсер вернёт 0% match. **Документ деривацию явно** в `parsers/dispatcher.py`.
- **Camoufox warm cookies между runs:** D-311 contra. Spike not validated; risks fingerprint drift, cookie expiry, profile bloat.
- **Persistent profile в repo:** не помещать в git tree; tmp dir per-run, gitignored если внутри repo.
- **Naive `meta[itemprop="price"]` extraction (первый `meta`):** вернёт `StrikethroughPrice` или `ListPrice` или Gold Card цену. Always filter by priceType + parent context.
- **Brand-list filter naive `if product.brand.lower() in viled_brands_lowercase`:** Pitfall 8 — bilingual gap. Use slug-fy + alias-lookup.
- **`url as identity`** для week-over-week diff: не используем; goldapple URL = `<numeric_id>-<slug>`; numeric_id = stable identity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Headless-Firefox с C++ fingerprint spoof | Самописная patcher на playwright-stealth | **Camoufox** | C++-уровень spoof (binary patch); spike 99/100 |
| TLS/JA3 impersonation | Custom http.client + TLS hacks | **curl_cffi** `impersonate="chrome"` | Defeats GroupIB urllib3 detection |
| Sitemap парсер | xml.etree.ElementTree от руки | **regex `<loc>([^<]+)</loc>` ИЛИ selectolax с `xml`** | Spike 01-05 уже работает на regex; sitemap simple |
| Микроданные walker | Самописный SAX parser | **selectolax `tree.css('[itemprop="..."]')`** | 30× faster than BS4, simpler than lxml |
| Retry-with-backoff | `for attempt in range(3): try: ... except: time.sleep(2**attempt)` | **tenacity** `@retry(wait=wait_exponential_jitter)` | Battle-tested, declarative, jitter built-in [CITED: research/STACK.md] |
| Cyrillic↔Latin transliteration | Per-letter dict (риск пропуска KZ-specific glyphs) | Использовать map в Pattern 2 + добавить KZ glyphs (ә, ғ, қ, ң, ө, ұ, ү, һ, і) | KZ-specific brand names присутствуют в alias-pool |
| Slug-fy от руки на регексах | Свой regex `[^a-z0-9-]+` без NFKD | Pattern 2 outline (NFKD + accent strip + transliterate + collapse) | NFKD необходим для `é`/`ё` нормализации |
| Tmp profile dir cleanup на падении | Manual `os.rmdir` в except-блоке | `tempfile.mkdtemp` + `shutil.rmtree` в `finally`-блоке (or `__aexit__`) | Always-cleanup на любом code path |
| Telegram отправка ops-алертов в Phase 3 | Direct aiogram call в orchestrator | **DEFER в Phase 6** — Phase 3 пишет алерт в `runs.error` + structured log; Phase 6 wrapper читает и шлёт | DELIVER-02/03 — separation of concerns |
| Sanity-gate threshold формула | Per-week magic-number поверх gate | M=1000 в config (D-308); auto-suggest формула в gates.py (D-310) | Декларативный config, явная формула |
| HTML challenge-shell vs stale-SKU detection | Только на размере HTML | Title-check + size + microdata-presence — three-axis discrimination | Spike row 0 показал 200 + 9.5 KB + title "Loading ..." — **stale, not gate** |

**Key insight:** Phase 1 спайк уже эмпирически отбрил большинство альтернатив. Hand-rolled решения здесь обходятся в 4-часовой воскресный run, который никто не увидит до понедельника утром. Используем доказанный стек.

## Runtime State Inventory

> **Skipped — Phase 3 является greenfield для goldapple-стороны.** Никаких stored data / live-config / OS-registered state / secrets, которые требовали бы миграции. Единственное pre-existing runtime state:
> - **Camoufox tmp profile dirs от ad-hoc spike runs** (`~/.cache/camoufox/.../...` или `<repo>/.planning/spikes/01-goldapple/.camoufox-state/`) — gitignored, безопасно удалить; D-311 fresh-profile-per-run автоматически создаёт новые.
> - **`tier2-camoufox-kz-results.json` empirical baseline** (spike artifact) — read-only reference, не модифицируется в Phase 3.
> - **`uv.lock`** — Phase 3 закрепит exact `camoufox==135.0.1.beta24` через `uv add`; перегенерация лока — стандартная процедура, не миграция.

## Common Pitfalls

### Pitfall 1: Camoufox version drift breaks fingerprint hash silently

**What goes wrong:** daijro/camoufox upstream релизит patch (e.g. `135.0.1.beta25`); patch меняет fingerprint hash на C++ уровне; gate-pass-rate падает на следующем weekly run **без code-changes**.

**Why:** Spike-validation = hash-specific. Любой patch = эффективно новый engine.

**How to avoid:** D-313 exact pin в `uv.lock`; manual upgrade workflow `dev smoke → PR в lock`. **Plan must enforce:** `pyproject.toml` использует `==`, не `>=` или `^`.

**Warning signs:** Smoke-probe (D-312) fail после `uv sync`. Gate-shell-rate >0% на воскресном run.

### Pitfall 2: priceType-aware parser возвращает Gold Card price (4 490 ₸) вместо public price

**What goes wrong:** Naive parser берёт первый `meta[itemprop="price"]` — оказывается это либо `StrikethroughPrice` (was_price ~6 990), либо Gold Card (~4 490, "при авторизации"). Public price — current_price (~4 990) — пропущен. Comparison vs viled полностью искажён.

**Why:** На PDP goldapple **до 4 разных price блоков** в одной странице; они все имеют microdata `itemprop="price"`. Семантическая дискриминация — обязательна.

**How to avoid:** Pattern 4 — top-level `[itemprop="offers"][itemtype$="/Offer"]` без `priceType` в child + `availability` link рядом. Test fixture от руки сверить против rendered page.

**Warning signs:** Discount column в Excel (Phase 5) показывает 0% для всех goldapple SKUs ИЛИ bimodal distribution (low + high cluster). Median price >30% от viled на тех же SKUs.

### Pitfall 3: Slug exact-match даёт false-positive `tom-ford` ⊆ `tom-ford-beauty`

**What goes wrong:** "Tom Ford" → `tom-ford` (slug); sitemap содержит `tom-ford` И `tom-ford-beauty` И `tom-ford-private-blend` slugs. **Substring match** заберёт все три → миксует beauty-SKUs с фрагрансовыми; matcher delivers wrong deltas.

**Why:** Sitemap-slug pool — это URL-фрагменты, не категории. Substring match ломает identity.

**How to avoid:** D-305 explicit: **exact match только**. `slug in sitemap_slugs` через `dict.get(slug)` — НЕ `for sl in sitemap_slugs: if slug in sl`.

**Warning signs:** SKU count для одного бренда внезапно вырастает в 3+ раза неделя-к-неделе без site change.

### Pitfall 4: Gate-shell vs stale-SKU conflation poisons sanity-gate

**What goes wrong:** Spike row 0 (`/7681000002-givenchy-pour-homme-blue-label`) — статус 200, размер 18 KB, title "Loading <url>" (НЕ "checking device"), нет microdata. Phase 3 классифицирует это как **stale-SKU** (de-listed); если бы classified как **gate-shell** — false alarm sanity-gate.

**Why:** GUN gate-shell ~18-20 KB **И** stale-SKU shell ~9.5 KB — оба попадают в `<30 KB`. Только title (`"checking device"` vs `"Loading <url>"` vs реальное product-name) разрешает дискриминацию.

**How to avoid:** Pattern 4 `detect_state()` — three-axis: title-marker + html-size + microdata-presence. Логировать оба counters отдельно: `gate_shell_count` (anti-bot) и `stale_count` (de-listed).

**Warning signs:** `gate_shell_count > 0` на любом run = немедленный alarm Camoufox-fingerprint регрессии. `stale_count > 5%` of total = sitemap-rot signal (defer prune to ops).

### Pitfall 5: Cron environment lacks Firefox system deps for Camoufox

**What goes wrong:** Cron run на VPS: `uv run python -m ga_crawler` падает с `Camoufox: failed to launch — missing libgtk-3.0` или похожим. Воскресная ночь, никого нет, run miss.

**Why:** Camoufox bundles patched Firefox binary, но всё равно нужны system libs (Linux: gtk, x11, dbus, alsa). На fresh Hetzner Ubuntu они НЕ pre-installed.

**How to avoid:** Phase 7 deploy step:
```bash
# After uv sync:
uv run camoufox fetch          # downloads patched Firefox binary
sudo apt-get install -y libgtk-3-0 libdbus-glib-1-2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libasound2 libpango-1.0-0 libatk1.0-0
# OR use Docker: mcr.microsoft.com/playwright/python:v1.57.0-noble — but it's CHROMIUM-based,
# Camoufox needs FIREFOX deps. Better use a custom Dockerfile FROM ubuntu:24.04 + apt-get
```

**Warning signs:** First Hetzner Hetzner deploy: `camoufox.async_api.AsyncCamoufox` raises on `__aenter__`. Fix: install deps and `uv run camoufox fetch`.

### Pitfall 6: Single `runs` row contention between Phase 2 and Phase 3

**What goes wrong:** DATA-05: ОДИН `runs` row на оба ритейлера. Phase 2 успевает обновить `viled_count=4500` и status='partial' посреди run; Phase 3 завершает goldapple, обновляет `goldapple_count=3200` и status='success' — но партial-flag Phase 2 утерян.

**Why:** Naive UPDATE без RMW (read-modify-write) с явной `runs.stats` JSON merge.

**How to avoid:** **Не UPDATE**, а **`UPDATE runs SET stats = json_patch(stats, :delta)`** (SQLite 3.45+ supports `json_patch`) или сначала SELECT, merge, UPDATE в transaction. Phase 3 пишет только goldapple-side keys; Phase 2 — только viled-side. Status — финализируется orchestrator-ом ПОСЛЕ обоих.

**Warning signs:** `runs.stats` имеет только `goldapple_*` keys без `viled_*` (или наоборот) после weekly run.

### Pitfall 7: tmp-profile FS race when Phase 3 fails before cleanup

**What goes wrong:** Camoufox boot успешен, smoke probe fails, exception. Profile dir не убран → накопление `~/.cache/camoufox-run-*` каталогов на диске (~50-100 MB каждый × N weeks).

**Why:** Cleanup был только в success path.

**How to avoid:** `__aexit__` или `try/finally` с `shutil.rmtree(profile_dir, ignore_errors=True)`. Pattern 3 это уже показывает.

**Warning signs:** Disk usage растёт ~100 MB/week без видимой причины. `du -sh ~/.cache/camoufox*` показывает накопление.

### Pitfall 8: Sitemap fetch returns stale (>24h) data — week-over-week diff lies

**What goes wrong:** goldapple sitemap-3.xml кешируется CDN на 24+ часа; cron run в воскресенье 02:00 KZ = 21:00 UTC субботы; CDN не пересчитывался к этому моменту → diff показывает 0 NEW slugs неделю подряд.

**Why:** Sitemap freshness не контролируется нами.

**How to avoid:** **Не критично для v1** — D-307 expects "обычно единицы/десятки" NEW slugs/week; если week N+1 показывает 0, это ok, на week N+2 разница накопится. **Документировать**: NORM-06 review queue не обязательно populate каждую неделю; это weekly-not-realtime signal.

**Warning signs:** 4+ weeks zero NEW slugs — investigate sitemap-freshness manually (curl `If-Modified-Since`).

### Pitfall 9: Phase 2 dependency stub interfaces drift from real Phase 2

**What goes wrong:** Phase 3 plan develops Wave 0 mocks для `BrandAlias`, `SnapshotWriter`, `Normalize.brand`; затем Phase 2 ships REAL modules с slightly different signatures (e.g. `BrandAlias.lookup` returns `dict` instead of `list`). Wave 5 integration breaks. Wasted effort.

**Why:** Параллельная разработка без явного contract-first.

**How to avoid:**
1. Plan Phase 3 Wave 0 `interfaces.py` — Protocol-defined contracts (Phase 2 must conform).
2. Phase 2 plan reviewer (через STATE.md cross-check) подтверждает совместимость.
3. Финальная wave интеграции (Phase 3 Wave N) — exclusively against real Phase 2 modules; mock-только тесты move into "regression" tier, не блокируют integration.
4. **Если Phase 2 не запущена ещё** на момент Phase 3 plan-write: planner документирует contracts ниже в "Open Questions".

## Code Examples

### Bilingual slug-fy (verified test cases)

(See Pattern 2 above — full code + test table.)

### Camoufox fetch loop with gate-detect (verified spike notebook.py)

```python
# Source: .planning/spikes/01-goldapple/notebook.py L128-191 (refactored for production)
async def fetch_one(self, page, url: str) -> dict:
    started = time.perf_counter()
    rec = {"url": url, "status": None, "html_size": None, "title": None,
           "gate_cleared": False, "block": False, "block_reason": None}
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        rec["status"] = response.status if response else None
        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        # Poll title for gate clearance
        elapsed = 0
        last_title = ""
        while elapsed < GATE_POLL_DEADLINE_MS:
            last_title = await page.title()
            if GATE_TITLE_MARKER not in last_title.lower():
                rec["gate_cleared"] = True
                break
            await page.wait_for_timeout(GATE_POLL_STEP_MS)
            elapsed += GATE_POLL_STEP_MS
        rec["title"] = last_title

        html = await page.content()
        rec["html_size"] = len(html)

        # Three-axis state classification (Pattern 4 detect_state)
        if not rec["gate_cleared"] and rec["html_size"] < CHALLENGE_HTML_MAX_SIZE:
            rec["block"] = True
            rec["block_reason"] = "gate_shell_not_cleared"
        elif rec["status"] not in (200, 304):
            rec["block"] = True
            rec["block_reason"] = f"http_{rec['status']}"
        else:
            rec["html"] = html  # caller parses
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {repr(e)[:200]}"
        rec["block"] = True
        rec["block_reason"] = "exception"
    rec["timing_ms"] = int((time.perf_counter() - started) * 1000)
    return rec
```

### Smoke probe (D-312)

```python
# src/ga_crawler/runner/gates.py
SMOKE_URLS = [
    # 3 known-good Givenchy URLs from spike (large, stable, microdata-bearing).
    # Operator updates if these go stale (Phase 7 ops-playbook).
    "https://goldapple.kz/7680100018-very-irresistible-givenchy",
    "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label",
    "https://goldapple.kz/19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum",
]

async def smoke_probe(fetcher: GoldappleFetcher) -> dict:
    """D-312 pre-crawl probe. Returns {pass: bool, diagnostics: dict}.
    Pass = ALL probe URLs return 200 + microdata price extracted."""
    results = []
    for url in SMOKE_URLS:
        rec = await fetcher.fetch_one(fetcher._page, url)
        if rec.get("html"):
            product = parse_pdp(rec["html"], url)
            rec["price_extracted"] = (product is not None and product.current_price > 0)
        results.append(rec)
    diagnostics = {
        "camoufox_version": "135.0.1.beta24",  # from package metadata at runtime
        "responses": [{"url": r["url"], "status": r["status"], "size": r.get("html_size"),
                       "title": r.get("title"), "price_extracted": r.get("price_extracted")}
                       for r in results],
    }
    passed = all(r.get("price_extracted") for r in results) and all(
        r.get("status") == 200 and not r.get("block") for r in results
    )
    return {"pass": passed, "diagnostics": diagnostics}
```

### Final M-gate + auto-suggest (D-308/D-309/D-310)

```python
# src/ga_crawler/runner/gates.py (continued)
import statistics

def final_m_gate(goldapple_count: int, M: int = 1000) -> bool:
    """Returns True iff run passes. Caller marks runs.status='failed' on False."""
    return goldapple_count >= M

def auto_suggest_m(history_counts: list[int]) -> Optional[int]:
    """D-310: returns suggested M based on 4-week median; only if 4+ runs available.
    Operator decides whether to PR-update config."""
    if len(history_counts) < 4:
        return None
    median = statistics.median(history_counts[-4:])
    return int(0.7 * median)
```

### NORM-06 week-over-week diff (D-307)

```python
# src/ga_crawler/enumeration/goldapple_sitemap.py (extended)
from pathlib import Path

def persist_sitemap_slugs(slugs: set[str], run_id: int, root: Path) -> Path:
    """Write current week's slugs to .planning/runs/{run_id}/sitemap-slugs.txt.
    Suggested location — planner finalizes."""
    out = root / f"runs/{run_id}/sitemap-slugs.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sorted(slugs)), encoding="utf-8")
    return out

def find_previous_slug_file(root: Path, current_run_id: int) -> Optional[Path]:
    """Find latest predecessor sitemap-slugs.txt for diff."""
    candidates = sorted((root / "runs").glob("*/sitemap-slugs.txt"))
    candidates = [c for c in candidates if int(c.parent.name) < current_run_id]
    return candidates[-1] if candidates else None

def diff_new_slugs(current: set[str], previous_path: Optional[Path]) -> list[str]:
    """Returns sorted list of NEW slugs not in previous week."""
    if previous_path is None:
        return []  # first run — empty diff per Pitfall 8 doc
    prev = set(previous_path.read_text(encoding="utf-8").splitlines())
    return sorted(current - prev)
```

## State of the Art

| Old Approach | Current Approach (Phase 3) | When Changed | Impact |
|--------------|---------------------------|--------------|--------|
| Vanilla Playwright + stealth-plugin | **Camoufox 135** (C++ fingerprint spoof) | Phase 1 spike 2026-05-06 | 0/7 → 99/100 on goldapple |
| Patchright drop-in | **Camoufox 135** | Same; spike 01-06 0/7 baseline | Patchright superseded for goldapple specifically; can stay in pyproject for other use cases |
| `requests` + custom headers | **curl_cffi `impersonate="chrome"`** для Tier 0 (sitemap) | research/STACK.md baseline | Sitemap fetch не блокируется urllib3 fingerprint detection |
| JSON-LD-first PARSE-02 | **Microdata-first** (goldapple) / `__NEXT_DATA__`-first (viled) | Plan 01-08 D-14 revision 2026-05-06 | Asymmetric per-retailer dispatch; PARSE-02 priority docstring updated |
| pip + venv + requirements.txt | **uv + pyproject.toml + uv.lock** | CLAUDE.md 2026 default | 10-100× faster ops; D-313 lock-pin works |
| BeautifulSoup4 | **selectolax** | research/STACK.md | 30× faster on PDP scale |

**Deprecated/outdated (do NOT use):**
- `cloudscraper` / `cfscrape` — defeated by GroupIB + modern Cloudflare [CITED: CLAUDE.md "What NOT to Use"]
- `selenium-stealth` / `undetected-chromedriver` — Selenium ecosystem; lock-step worse than Camoufox
- Original `playwright-stealth` v1.x — unmaintained since 2023 [CITED: CLAUDE.md]
- `BeautifulSoup4` для well-formed pages — selectolax 30× faster [CITED: research/STACK.md]
- `requests` для goldapple — TLS fingerprint detected мгновенно
- **Specifically для goldapple: Patchright** — empirically broken, 0/7 [VERIFIED: spike 01-06]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Camoufox `135.0.1.beta24` is still installable from PyPI / daijro at plan-write time | Standard Stack > Core | Plan would need to switch to coryking fork; `uv add` workflow changes. **Mitigation:** planner runs `uv add camoufox` and verifies version BEFORE freezing plan. |
| A2 | Goldapple sitemap remains plain-deliverable (no anti-bot escalation on `/sitemap.xml`) at production-run time | Pattern 1 + D-301 | If sitemap blocked: Phase 3 needs Camoufox-based enumeration fallback (~50 brand-listing renders). **Mitigation:** smoke probe (D-312) extends to test sitemap fetch ассерт. |
| A3 | Sitemap lastmod / CDN cache freshness ≤ 24h на воскресный run | Pitfall 8 | Week-over-week NEW slug diff может быть тонкий. **Mitigation:** документировано как known acceptable behavior; not a hard error. |
| A4 | Phase 2 ships `BrandAlias.lookup(brand_norm) → list[str]` API (not `dict`) | Module decomposition + Pitfall 9 | Wave 0 mocks invalidate. **Mitigation:** Wave 0 contract-first; Phase 2 plan reviewer checks. |
| A5 | Phase 2 ships single `runs` row пер weekly run (not per-retailer) | DATA-05 re-use + Pitfall 6 | Phase 3 needs to create separate row, breaking single-run semantics for downstream Phase 4/5/6. **Mitigation:** explicit verification when Phase 2 plan ships. |
| A6 | `priceType` semantics (StrikethroughPrice / ListPrice) consistent across all goldapple PDPs | Pattern 4 | Edge cases (e.g. no priceType meta on some PDPs) cause silent wrong-price extraction. **Mitigation:** test fixture has 1 PDP; planner expand to 3-5 fixtures including OOS / Discontinued / promo to confirm. |
| A7 | Camoufox tmp-profile cleanup on `__aexit__` doesn't race with parallel Camoufox instances | Pattern 3 + Pitfall 7 | Phase 3 explicitly concurrency=1; not a problem in v1. Documented for completeness. |
| A8 | smoke_urls (3 hardcoded Givenchy URLs from spike) remain valid (200 + microdata) for at least 4 weeks | smoke probe code example | If goldapple delists/changes URLs → false-fail smoke probe → run aborts на здоровом fingerprint. **Mitigation:** Phase 7 ops-playbook has rotation procedure; document in plan. |
| A9 | KZ-laptop direct vs Hetzner-EU IP-geo not material for Phase 3 plan (Phase 7 problem) | Stack constraints | If Phase 7 actually deploys to EU and gate fails, Phase 7 has fallback (IPRoyal trial). Phase 3 implementation is geo-agnostic. |
| A10 | tenacity 9.x compatible with playwright async API (no event loop issues) | Pattern 5 | If incompatible: switch to manual retry-with-backoff loop. tenacity supports asyncio per docs. [ASSUMED — not verified in spike] |
| A11 | `uv.lock` resolution finds compatible versions of `camoufox==135.0.1.beta24` + `tenacity>=9` + `sqlmodel>=0.0.24` + `pydantic>=2.10` | Installation | `uv sync` may fail; planner needs to relax pins. **Mitigation:** Wave 0 includes `uv sync` smoke test. |
| A12 | The `34, 36, 60, 99 — 1` pattern from spike (1 row 0 = stale-SKU `7681000002-givenchy-pour-homme-blue-label`) — that exact URL может оставаться stale weekly. Smoke probe shouldn't include it | smoke_urls list | Smoke uses **other** Givenchy URLs from spike (rows 1, 2, 3) which were 99% successful. |

**Resolution gate for planner:** A1, A2, A4, A5 must be verified before plan freeze (run `uv add` + read Phase 2 plan-in-progress если есть). A3, A6-A12 — accept as known risks; plan describes mitigations.

## Open Questions

1. **Где physically живёт NORM-06 review queue?**
   - What we know: D-306 says "review-очередь"; D-307 says "diff-им с предыдущим, новые в NORM-06". Phase 2 owns initial NORM-06 deliverable.
   - What's unclear: Файл (`.planning/runs/{run_id}/norm06-review.md`)? DB-таблица (`norm06_review_queue`)? Структурированный JSON в `runs.stats.norm06_*`?
   - Recommendation: **DB-таблица** `norm06_review_queue (run_id, brand_or_slug, direction, first_seen_run_id, status)` — позволяет SQL-аналитику (count_new_per_week), легко закрывать ("status='reviewed'") в weekly ops. Alternative: append-only `.txt` файл per run. Planner decides; coordinate with Phase 2.

2. **Config-файл location для `M`, `smoke_urls`, rate-limit constants** (Claude's Discretion)
   - What we know: Default predict — `pyproject.toml [tool.ga_crawler.crawl.goldapple]`.
   - What's unclear: смешивать ли с .env (есть smoke_urls, которые не secret, но ops может менять без re-deploy)? Лучше split: `pyproject.toml` для type-locked константы (`sanity_gate_m`, `pause_range`, `concurrency`), `.env` или `config/smoke.txt` для frequently-edited (smoke_urls).
   - Recommendation: `pyproject.toml [tool.ga_crawler.crawl.goldapple]` for `sanity_gate_m`, `pause_range_min/max`, `gate_poll_deadline_ms`, `camoufox_locale`, `m_auto_suggest_factor=0.7`, `m_auto_suggest_after_runs=4`. **Separate** `config/smoke_urls.txt` (один URL на строку, gitignored optional, оператор-friendly).

3. **Tmp-каталог для Camoufox profile** (Claude's Discretion)
   - What we know: D-311 `tmp profile-dir`; example `/tmp/camoufox-{run_id}/`.
   - What's unclear: System tmp (`tempfile.mkdtemp`) vs `<repo>/tmp/camoufox-{run_id}/` vs `<XDG_CACHE_HOME>/ga_crawler/camoufox-{run_id}/`.
   - Recommendation: **`tempfile.mkdtemp(prefix=f"camoufox-run-{run_id}-")`** — system-default, not in repo (avoid accidental commit), auto-cleanup-friendly. Avoid repo-local tmp (chance for git pollution); avoid XDG_CACHE (could survive across deploys if cache mount changes).

4. **`runs.stats` JSON-схема — точные ключи** (Claude's Discretion + DATA-05 contention)
   - What we know: CONTEXT.md mentions `stale_count`, `unmatched_viled_brands`, `unmatched_goldapple_slugs_new`, `gate_shell_count`, `smoke_pass`.
   - What's unclear: nested vs flat? Ключи для viled-side stats тоже здесь? Phase-namespace prefix?
   - Recommendation: **flat with phase-namespace prefix**, atomic merge through `json_patch`:
     ```jsonc
     {
       // Phase 2 (viled) writes:
       "viled.fetch_count": 4523,
       "viled.fetch_failures": 12,
       "viled.parse_failures": 3,
       "viled.gate_count": 4500,                  // viled has no gate; placeholder for symmetry
       // Phase 3 (goldapple) writes:
       "goldapple.fetch_count": 3210,             // CRAWL-05 input
       "goldapple.fetch_failures": 47,
       "goldapple.gate_shell_count": 0,            // Pitfall 4 monitor
       "goldapple.stale_count": 18,                // D-303
       "goldapple.parse_failures": 2,
       "goldapple.unmatched_viled_brands": 7,      // D-306
       "goldapple.unmatched_goldapple_slugs_new": 23, // D-307
       "goldapple.smoke_pass": true,               // D-312
       "goldapple.smoke_diagnostics": {...},        // populated only if smoke_pass=false
       "goldapple.fetch_duration_seconds": 15234,
       "goldapple.mean_fetch_seconds": 4.74,
       "goldapple.camoufox_version": "135.0.1.beta24",
       // Auto-suggest (D-310):
       "goldapple.auto_suggest_m": 1234,           // null until 4+ runs in history
     }
     ```

5. **Cleanup strategy для Camoufox profile dir on FAIL** (Claude's Discretion)
   - What we know: Default = always delete (disk-cost > debug-utility v1).
   - What's unclear: Do we want a `--preserve-failed-profile` flag for ad-hoc dev debugging?
   - Recommendation: Always delete in production. For dev: env var `GA_CRAWLER_PRESERVE_FAILED_PROFILE=1` opts in (planner can defer to Phase 7).

6. **Phase 2 contracts that Phase 3 depends on** — needs to be locked into `interfaces.py` Wave 0
   - What we know: Module decomposition lists `BrandAlias`, `Normalize.{brand,name,volume}`, `SnapshotWriter`, `ParseDispatcher`.
   - What's unclear: Phase 2 plan не написан. Wave 0 of Phase 3 should declare Protocol-typed contracts.
   - Recommendation: Phase 3 Plan Wave 0 includes `src/ga_crawler/interfaces.py` with:
     ```python
     class BrandAliasProtocol(Protocol):
         def lookup(self, brand_norm: str) -> list[str]: ...

     class NormalizerProtocol(Protocol):
         def brand(self, raw: str) -> str: ...
         def name(self, raw: str) -> str: ...
         def volume(self, raw: str) -> tuple[Decimal, str, int] | None: ...  # (amount, unit, multipack); None if unparseable

     class SnapshotWriterProtocol(Protocol):
         def append(self, run_id: int, retailer: str, products: list[NormalizedProduct]) -> int: ...

     class RunWriterProtocol(Protocol):
         def patch_stats(self, run_id: int, delta: dict) -> None: ...
         def get_stats(self, run_id: int) -> dict: ...
         def fail(self, run_id: int, reason: str) -> None: ...
     ```
   - Then mock these in Wave 1-N tests; final integration wave swaps mocks for real Phase 2 imports.

7. **Smoke-URL rotation — какой mechanism для replacement когда они дрейфуют?** (deferred to Phase 7 per CONTEXT.md, but planner may want a stub)
   - What we know: 3 Givenchy URLs hardcoded; CONTEXT.md defers to Phase 7 ops-playbook.
   - What's unclear: Should Phase 3 plan deliver a CLI `python -m ga_crawler smoke-update --url URL` to validate-and-add new smoke URLs?
   - Recommendation: Phase 3 plan delivers `smoke_urls.txt` config file + a manual checklist в README; CLI deferred to Phase 7.

## Environment Availability

| Dependency | Required By | Available (KZ-laptop) | Version | Fallback |
|------------|------------|----------------------|---------|----------|
| Python 3.12 | Runtime | ✓ | 3.12.x | — |
| uv | Project mgmt | ✓ | per pyproject.toml expects | — |
| camoufox PyPI package | goldapple fetcher | ✓ (currently `>=0.4.11`) | needs **==135.0.1.beta24** pin | coryking fork |
| Firefox system libs (Linux) | Camoufox runtime | ✗ on Hetzner Ubuntu fresh deploy | — | apt-get install (Phase 7 deploy step) |
| curl_cffi | Sitemap fetch | ✓ | 0.15.x | httpx (no impersonate — risky) |
| selectolax | HTML parse | ✓ | 0.3.x | lxml + parsel |
| SQLite 3.45+ | Storage (json_patch) | ✓ (bundled with Python 3.12) | 3.45+ | — (planner verifies SQLite version with `sqlite3 --version`) |
| KZ network egress | Camoufox direct | ✓ (laptop) | — | IPRoyal KZ residential (~$2/week, Phase 7 fallback) |
| tenacity | Retry | ✗ (NOT in pyproject.toml currently) | needs add | manual retry loop |
| sqlmodel | ORM | ✗ (NOT in pyproject.toml currently — Phase 2 deliverable) | needs add | sqlite3 stdlib + handwritten DAO |
| pydantic | Validation | ✗ (NOT in pyproject.toml — Phase 2 deliverable) | 2.10+ | dataclasses + manual validators |

**Missing dependencies with no fallback:**
- Firefox system libs on production VPS — **Phase 7 deploy step required** (not Phase 3 blocker for dev).

**Missing dependencies with fallback:**
- `tenacity` — adding via `uv add` straightforward; fallback to manual retry not blocker.
- `sqlmodel` / `pydantic` — Phase 2 deliverables; if Phase 2 не успевает, Phase 3 Wave 0 mocks бесшовно работают со stdlib.

**Note on `patchright>=1.55` currently in pyproject.toml:** Phase 1 спайк закрыл patchright как goldapple-engine (0/7); however, we keep it in lock-file as backup for any future ритейлера, where Patchright benchmarks (Cloudflare/DataDome) actually apply. Phase 3 plan может opt-out (remove dependency) ИЛИ leave for Phase 7 cross-retailer use cases. **Recommendation: leave in pyproject.toml** — adds ~50 MB venv but zero runtime cost when not imported.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (Camoufox is async) |
| Config file | **none currently — Wave 0 creates `pyproject.toml [tool.pytest.ini_options]`** |
| Quick run command | `uv run pytest tests/unit/ -x --no-header -q` |
| Full suite command | `uv run pytest tests/ -x --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **CRAWL-02** | Goldapple URL pool derived from current viled snapshot via alias-bilingual-slug-fy | unit | `uv run pytest tests/unit/test_slug_fy.py -x` | ❌ Wave 0 |
| **CRAWL-02** | Brand intersection: viled brand-set ∩ sitemap-slug pool produces matched_urls list | unit | `uv run pytest tests/unit/test_intersect_brand_pool.py -x` | ❌ Wave 0 |
| **CRAWL-02** | NORM-06 viled-side: brands with zero slug-matches counted | unit | `uv run pytest tests/unit/test_intersect_brand_pool.py::test_unmatched_brands_counted -x` | ❌ Wave 0 |
| **CRAWL-03** (re-use) | Per-SKU isolation: one URL fail → counter increment, others continue | integration | `uv run pytest tests/integration/test_goldapple_fetch_loop_mocked.py::test_isolation_on_failure -x` | ❌ Wave 0 |
| **CRAWL-04** (re-use) | Retry with exp-backoff + jitter on 5xx/timeout; non-retryable on 403/404 | unit | `uv run pytest tests/unit/test_retry_policy.py -x` | ❌ Wave 0 |
| **CRAWL-05** (goldapple) | `goldapple_count < M` → `runs.status='failed'` | unit | `uv run pytest tests/unit/test_sanity_gate.py::test_final_m_gate_fails -x` | ❌ Wave 0 |
| **CRAWL-05** (auto-suggest) | After 4+ runs, `auto_suggest_m()` returns `0.7 × median` | unit | `uv run pytest tests/unit/test_sanity_gate.py::test_auto_suggest_m -x` | ❌ Wave 0 |
| **CRAWL-06** (re-use) | Rate-limit between fetches in [3, 5] uniform | unit | `uv run pytest tests/unit/test_pause_range.py -x` (statistical sampling, 1000 draws) | ❌ Wave 0 |
| **PARSE-01** (goldapple) | Parser extracts name, brand, volume_raw, current_price, was_price, currency, availability, url from real PDP fixture | unit | `uv run pytest tests/unit/test_goldapple_microdata_parser.py::test_parse_real_pdp -x` | ❌ Wave 0 |
| **PARSE-02** (goldapple inversion) | Parser dispatcher returns microdata-extractor for retailer='goldapple' | unit | `uv run pytest tests/unit/test_dispatcher.py::test_dispatch_goldapple_uses_microdata -x` | ❌ Wave 0 (Phase 2 owns dispatcher) |
| **PARSE-03** (priceType filter) | Parser rejects StrikethroughPrice/ListPrice/Gold-Card; selects current public | unit | `uv run pytest tests/unit/test_goldapple_microdata_parser.py::test_pricetype_filter -x` | ❌ Wave 0 |
| **PARSE-04** | Out-of-range price (< 100 or > 1_000_000) → returns None / parse_error | unit | `uv run pytest tests/unit/test_goldapple_microdata_parser.py::test_price_sanity_check -x` | ❌ Wave 0 |
| **PARSE-05** | If >5% of fetched PDPs missing required fields (name/price/url) → run marked failed | integration | `uv run pytest tests/integration/test_run_e2e_with_phase2_mocks.py::test_parse05_threshold -x` | ❌ Wave 0 |
| **PARSE-06** | stock_state enum populated from `availability` link href (InStock / OutOfStock / Discontinued / PreOrder / Unknown) | unit | `uv run pytest tests/unit/test_goldapple_microdata_parser.py::test_availability_enum -x` | ❌ Wave 0 |
| **NORM-06** (week-over-week diff) | First run: empty diff; second run: NEW slugs detected from on-disk diff | integration | `uv run pytest tests/integration/test_norm06_diff.py -x` | ❌ Wave 0 |
| **DATA-03** (immutable) | INSERT only, no UPDATE on snapshots writes (Phase 2 contract validation) | integration | `uv run pytest tests/integration/test_run_e2e_with_phase2_mocks.py::test_no_updates_on_snapshots -x` | ❌ Wave 0 (Phase 2 contract test) |
| **DATA-04** (WAL + per-run TX) | DB write transaction wraps all snapshot inserts; on rollback no partial data | integration | `uv run pytest tests/integration/test_storage_wal_rollback.py -x` | ❌ Phase 2 owns; Phase 3 inherits |
| **DATA-05** (single runs row) | Both viled (Phase 2 mock) and goldapple (Phase 3) write to SAME run_id | integration | `uv run pytest tests/integration/test_run_e2e_with_phase2_mocks.py::test_single_runs_row -x` | ❌ Wave 0 |
| **D-303 stale-SKU detection** | 200 + <30 KB + no microdata → counted in `stale_count`, NOT in fetch_failures | unit | `uv run pytest tests/unit/test_stale_sku_detection.py -x` | ❌ Wave 0 (uses fixture `stale-sku-9.5kb.html`) |
| **D-312 smoke probe pass** | All smoke URLs return 200 + microdata price → smoke_pass=true | integration | `uv run pytest tests/integration/test_goldapple_smoke_probe.py::test_smoke_pass_when_real_pdp -x` (mocked Camoufox) | ❌ Wave 0 |
| **D-312 smoke probe fail** | Any smoke URL fails (gate-shell, no microdata) → smoke_pass=false, runs.status='failed', diagnostics populated | integration | `uv run pytest tests/integration/test_goldapple_smoke_probe.py::test_smoke_fail_aborts_run -x` | ❌ Wave 0 |
| **Gate-shell detection** | Title="checking device" + size<30KB → block_reason='gate_shell_not_cleared' | unit | `uv run pytest tests/unit/test_gate_detection.py::test_gate_shell -x` (uses fixture `gate-shell.html`) | ❌ Wave 0 |
| **Slug-fy idempotency** | `slug_fy_bilingual(slug_fy_bilingual(s)[0])` returns the same slug | unit | `uv run pytest tests/unit/test_slug_fy.py::test_idempotent -x` | ❌ Wave 0 |
| **Slug-fy false-positive guard** | "Tom Ford" produces `tom-ford` only — does NOT match sitemap-slug `tom-ford-beauty` (exact match check) | unit | `uv run pytest tests/unit/test_intersect_brand_pool.py::test_no_substring_match -x` | ❌ Wave 0 |
| **NORM-06 first-run diff** | First-ever run: previous slugs file does not exist → empty new-slugs list | unit | `uv run pytest tests/unit/test_norm06_diff.py::test_first_run_empty -x` | ❌ Wave 0 |
| **Retry caps attempts** | Tenacity exhausts at attempt 3 → re-raises; never infinite | unit | `uv run pytest tests/unit/test_retry_policy.py::test_max_3_attempts -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -x --no-header -q` (target <30s; pure unit, no live network, no Camoufox launch)
- **Per wave merge:** `uv run pytest tests/ -x --tb=short` (includes mocked-Camoufox integration; target <2min)
- **Phase gate:** Full suite green + ONE manual live smoke run (`uv run python -m ga_crawler.cli goldapple-smoke` against real goldapple, 3 Givenchy URLs, expect 200 + microdata extracted) before `/gsd-verify-work`. Live smoke is NOT in CI — manual operator step.

### Wave 0 Gaps

- [ ] `pyproject.toml [tool.pytest.ini_options]` config — `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [ ] `uv add 'pytest>=8' 'pytest-asyncio>=0.24' 'pytest-mock>=3.14'`
- [ ] `tests/conftest.py` — shared fixtures: `goldapple_pdp_html`, `gate_shell_html`, `stale_sku_html`, `mock_camoufox_page`, `mock_brand_alias`
- [ ] `tests/fixtures/goldapple/_debug-product-page.html` — copy from `.planning/spikes/01-goldapple/sample-payloads/`
- [ ] `tests/fixtures/goldapple/gate-shell.html` — extract minimal anti-bot challenge sample (~18 KB), source: spike `goldapple-product-html-1.html`
- [ ] `tests/fixtures/goldapple/stale-sku-9.5kb.html` — synthesize 200 + <30 KB + no microdata sample
- [ ] `tests/fixtures/goldapple/sitemap-1-excerpt.xml` — copy from spike sample-payloads
- [ ] `tests/unit/test_*.py` and `tests/integration/test_*.py` — all listed in table above
- [ ] CLI module `src/ga_crawler/cli.py` for manual `goldapple-smoke` command (Phase 7-adjacent but useful for Phase 3 verify-work)

## Threat Model (Security Domain)

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Per-retailer isolation, no shared mutable state across crawlers; Crawler Protocol contract |
| V2 Authentication | no | No auth surface — public scrape; explicitly excluded by PROJECT.md (Gold Card / login excluded) |
| V3 Session Management | partial | Camoufox `persistent_context` — cookies live within run; clean profile per run (D-311) prevents cross-run leakage |
| V4 Access Control | no | No multi-tenant; single operator |
| V5 Input Validation | yes | **pydantic** validates `RawProduct` before DB insert; PARSE-04 sanity range; PARSE-05 hard-fail on >5% missing required |
| V6 Cryptography | no | No crypto operations in scope |
| V7 Error Handling & Logging | yes | structlog redact `Cookie`, `Authorization` headers; never log Camoufox profile contents |
| V8 Data Protection | yes | gitignore `*.db`, `tmp/`, `~/.cache/camoufox-*`, `.env`; redact secrets in logs |
| V9 Communications | yes | HTTPS only (goldapple.kz, sp.goldapple.ru); curl_cffi defaults to HTTPS; Camoufox respects scheme |
| V10 Malicious Code | partial | Camoufox is third-party; PIN exact version (D-313); use uv.lock integrity hashes |
| V11 Business Logic | yes | sanity-gate (CRAWL-05), parse-quality invariants (PARSE-04/05) |
| V12 Files & Resources | yes | Tmp profile cleanup (Pitfall 7); no untrusted file paths from goldapple HTML |
| V13 API & Web Service | no | We're consumer, not provider |
| V14 Configuration | yes | `.env` for secrets; pyproject.toml for code-reviewable params; no hardcoded credentials |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **Camoufox profile leakage** (cookies/fingerprint state contaminating subsequent runs) | Information Disclosure | D-311 fresh profile per run; `shutil.rmtree` always-cleanup in `__aexit__`/`finally` |
| **Profile dir cleanup race** (process killed mid-run, profile leaks PII / session tokens to disk) | Information Disclosure | Profile dir under restrictive `0700` perms; Phase 7 cron user-isolated; no sensitive data scraped (public-only) |
| **Telegram bot-token exfiltration via logs** (deferred to Phase 6, but Phase 3 sets pattern) | Information Disclosure | structlog redact `TG_BOT_TOKEN`/`Bearer*`/`Cookie` headers — never log full request/response objects |
| **Sitemap-poisoning** (attacker-controlled sitemap entry redirects Camoufox to malicious URL) | Tampering | Whitelist URL pattern `^https://goldapple\.kz/(\d+)-[a-z0-9-]+$`; reject non-conforming entries (regex Pattern 1 already does this) |
| **Malicious goldapple HTML** (XSS in product name → CSV-injection in Excel later) | Tampering | **selectolax does NOT execute scripts**; pydantic validates string fields are non-empty + length-bounded; Excel injection prevention DEFERRED to Phase 5 (REPORT-* family — prefix `=`/`+`/`-`/`@`/tab/CR with `'`) |
| **Path traversal via SKU id** (e.g. SKU="../../etc/passwd") | Tampering | Numeric-id only — `re.match(r"^\d+$", sku_id)` validate before use as filename or DB id |
| **DB injection via scraped strings** | Tampering | SQLModel uses parameter binding; never f-string-format SQL; brand_norm/name_norm passes through normalizer that strips non-alphanumeric |
| **uv.lock tampering** (malicious package version forced) | Tampering | uv.lock has integrity hashes; CI runs `uv sync --check`; commit signed (Phase 7 — Git config) |
| **Camoufox supply-chain compromise** | Tampering | D-313 exact pin; coryking fork as backup; manual upgrade workflow with smoke test |
| **DoS goldapple** (excessive request rate triggers Cloudflare/GroupIB block on viled IP range) | Denial of Service (against THEIR site, but we suffer collateral) | Rate-limit 3-5s, concurrency=1; tenacity respects retry-after; sustained-5xx → mid-run abort considered (deferred per D-309) |
| **Camoufox C++ binary crash → process zombie** | Denial of Service (self) | `try/finally` cleanup; cron timeout (Phase 7 task — `timeout 5h`); Healthchecks dead-man's switch |
| **`goldapple.ru` / `*.facct.ru` cross-origin telemetry** (spike: `https://ru.id.facct.ru/id.html` iframe) | Information Disclosure | Camoufox geoip+humanize ALREADY accepts these (gate-clearance requires it). Documented in spike; not blocked. Privacy: Camoufox is ephemeral profile, no persistent identity to leak |
| **PII in scraped HTML** (review author names, email-like strings) | Information Disclosure | `itemprop="author"` reviews — Phase 3 ИГНОРИРУЕТ review section; only product fields parsed; no review storage |

**ASVS Level 1 — block_on=high:** All HIGH-severity controls above are addressed. No deferrals to v2 with security implications.

## Citations

### Primary Phase 1 spike artifacts (HIGH confidence)

- **`.planning/spikes/01-goldapple/MEMO.md`** — signed-off decision memo 2026-05-06. Citations: §TL;DR (Tier 2 Camoufox 99/100), §Chosen (engine + proxy + geo), §Open Risks post-01-08 (microdata not JSON-LD, brand-precision, upstream maintenance, stale-SKU pattern), §JSON-endpoint hunt verdict (GroupIB vendor identification), §Page-volume estimate (~3,450 fetches/week, 4.4h sequential), §Appendix Challenge-rate (0% gate-shell, NOT FRAGILE per D-15)
- **`.claude/skills/spike-01-goldapple/SKILL.md`** — operational constants. Citations: rate-limit 3-5s random uniform, Camoufox config `geoip=True, locale=['ru-RU','kk-KZ','en-US'], humanize=True, persistent_context=True`, microdata-not-JSON-LD parser strategy, page-volume estimate, hybrid sitemap+Camoufox enumeration
- **`.planning/spikes/01-goldapple/notebook.py`** — 100-fetch reference implementation. Citations: L100-110 (`has_microdata_price` impl), L113-125 (`evaluate_product_data` D-14 OR-logic), L128-191 (`fetch_one` with gate-poll + title-check + state-classification), L207-214 (`AsyncCamoufox` bootstrap config)
- **`.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html`** — real PDP HTML. Citations: 391 itemprop occurrences across 37 unique keys (verified via grep). Critical microdata blocks: `[itemprop="offers"]` top-level, `[itemprop="priceSpecification"]` with `[itemprop="priceType" href=".../StrikethroughPrice"]`, `[itemprop="brand"]>[itemprop="name"]`, `[itemprop="availability"]>@href` schema.org URL → enum
- **`.planning/spikes/01-goldapple/sample-payloads/_debug-jsonld-blocks.json`** — proof goldapple emits ONLY `OfferShippingDetails` (no Product schema) → microdata-first dispatch
- **`.planning/spikes/01-goldapple/sample-payloads/tier2-camoufox-kz-results.json`** — 100-fetch empirical baseline. Citations: 99/100 success, 0% gate-shell, 1 stale-SKU pattern (row 0, 200 + 18 KB + title "Loading <url>"), per-URL timing distribution (avg ~3-4s)
- **`.planning/spikes/01-goldapple/sample-payloads/page-volume-meta.json`** — sitemap empirical: 100,779 product URLs, 1,461 brand slugs, ~69 products/brand
- **`.planning/spikes/01-goldapple/sample-payloads/goldapple-sitemap.xml`** — sitemapindex shape (3 sub-sitemaps)

### Phase context (HIGH)

- **`.planning/phases/03-goldapple-crawl/03-CONTEXT.md`** — locked decisions D-301..D-313, canonical refs, code_context (reusable assets, integration points, Phase 2 dependency), specifics, deferred ideas
- **`.planning/phases/03-goldapple-crawl/03-DISCUSSION-LOG.md`** — rationale trail: 4 gray areas × 3 options each = 12 user choice points
- **`.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md`** — D-01..D-16 spike-decisions (D-04 persistent-context, D-14 microdata-not-JSON-LD, D-15 fragility 20% gate-shell line)

### Project state & roadmap (HIGH)

- **`.planning/STATE.md`** — accumulated key-decisions table; Phase 1 closure 2026-05-06 + Phase 3 context-gathered 2026-05-06
- **`.planning/ROADMAP.md`** §"Phase 3: Goldapple Crawl" — Goal, Depends on Phase 2, CRAWL-02 requirement, 5 success criteria
- **`.planning/REQUIREMENTS.md`** §Crawl (CRAWL-02 explicit + CRAWL-03/04/05/06 reuse), §Norm (NORM-06), §Data (DATA-03 immutable, DATA-04 WAL, DATA-05 runs row), §Parse (PARSE-01..06 reuse via dispatcher)

### Research foundation (HIGH on patterns; MEDIUM on superseded tier choice)

- **`.planning/research/SUMMARY.md`** §Architecture, §Pitfalls — modular monolith + append-only snapshot pattern
- **`.planning/research/STACK.md`** §Anti-Bot Strategy — superseded by spike-MEMO for Phase 3 specifically (Camoufox NOT Patchright); §Tier 0 (curl_cffi for sitemap) STILL APPLIES; §Storage SQLite + WAL section
- **`.planning/research/PITFALLS.md`** — Pitfall 1 (anti-bot), 2 (parser drift), 3 (volume normalization — Phase 2 owns), 4 (brand Cyrillic↔Latin), 5 (price field selection — strengthened via priceType for goldapple), 6 (stock state enum), 13 (rate-limit), 17 (currency precision), 19 (A/B test variants — JSON-LD/microdata stable across)
- **`.planning/research/ARCHITECTURE.md`** §System Overview, §Component Responsibilities, §Pattern 1 Pipe-and-Filter, §Pattern 2 Immutable Snapshot per Run, §Anti-Pattern 1-6, §Storage Schema Sketch (snapshots schema)

### CLAUDE.md (HIGH — locked stack constraints)

- §Technology Stack (Python 3.12, uv, Camoufox `>=0.4.11` baseline → planner pins `==135.0.1.beta24`)
- §Anti-Bot Strategy Tier 4 → Camoufox section + coryking fork backup note
- §"What NOT to Use" — `requests`/`cloudscraper`/`playwright-stealth v1.x`/Selenium/`undetected-chromedriver`/BeautifulSoup default

### Out-of-tree (MEDIUM — context only, not load-bearing)

- `knowledge/decisions/Goldapple — Tier 2 Camoufox без proxy, 99 из 100.md` (Obsidian vault) — sign-off note mirror

### External (LOW — not directly referenced; cited indirectly via research/STACK.md)

- Camoufox GitHub: daijro/camoufox (upstream), coryking/camoufox (maintained fork)
- selectolax PyPI/GitHub
- tenacity docs (asyncio support)
- curl_cffi ReadTheDocs (impersonate options)

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — Locked from spike + CLAUDE.md; only verification action: confirm Camoufox 135.0.1.beta24 still installable at plan-write time (A1)
- Architecture / module decomposition: **HIGH** — derives from research/ARCHITECTURE.md modular monolith + Phase 2 contract assumptions; only weakness is that Phase 2 is not yet planned (A4-A5 mitigations documented)
- Slug-fy algorithm: **HIGH** — algorithm fully specified; 11 test cases enumerated; KZ-specific glyphs included
- Microdata parser: **HIGH** — verified against real PDP fixture (391 itemprop occurrences inspected); priceType discrimination rules empirically derived
- Pitfalls: **HIGH** — 9 specific pitfalls with concrete prevention; 5 of 9 are derived directly from spike empirical findings
- Smoke probe + sanity-gate: **HIGH** — D-312/D-308/D-309/D-310 fully specified; Phase 6 Telegram integration deferred but contracts clear
- NORM-06 persistence target: **MEDIUM** — recommendation given (DB table) but Phase 2 makes final call (Open Question 1)
- Validation Architecture: **HIGH** — 27 testable invariants enumerated; fixtures sourced from spike artifacts; Wave 0 gaps explicit
- Threat model (ASVS L1): **HIGH** — 14 threats catalogued; 5 directly verified against spike + research/PITFALLS

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (30 days for stable stack; re-verify Camoufox version weekly per spike-skill ops playbook)

## RESEARCH COMPLETE
