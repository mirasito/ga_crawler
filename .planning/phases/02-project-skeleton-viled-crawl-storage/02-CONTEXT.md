# Phase 2: Project Skeleton + viled Crawl + Storage - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 строит инфраструктурный скелет проекта (storage layer, brand-alias, normalizer, parser-dispatch) и **scope-narrowed** краулер viled.kz через Tier 0 `curl_cffi`. **Scope clarification (2026-05-07):** под "viled-каталог" подразумеваются ТОЛЬКО косметика+парфюмерия — конкретно 2 catalog endpoints `/men/catalog/1310` и `/women/catalog/1310` — НЕ весь luxury fashion каталог (одежда, обувь, сумки, аксессуары). Commercial relevance — goldapple — beauty/parfumery retailer; matching одежды/сумок против goldapple не имеет смысла. Phase 3 (`goldapple-crawl`) уже исполнен first и потребляет shared-модули через 4 stub Phase 2 implementations в `cli.py`; Phase 2 заменяет эти стабы реальными имплементациями за теми же `interfaces.py` Protocols (frozen at Wave 0 of Phase 3). По завершении Phase 2 `python -m ga_crawler` выполняет end-to-end weekly run viled-side с записью immutable snapshots в SQLite (WAL, append-only, atomic `runs.stats` json_patch), seed-нутая brand-alias YAML обслуживает strict-key matching downstream, и sanity-gate блокирует delivery при viled_count < N. Phase 2 НЕ строит matcher (Phase 4), reporter (Phase 5), Telegram-delivery (Phase 6), cron-deploy (Phase 7) — это последующие фазы.

</domain>

<decisions>
## Implementation Decisions

### Sanity-gate N for viled (CRAWL-05)

- **D-201:** **Auto-suggest after 4 weeks pattern, seed N=100 static** (revised 2026-05-07 after scope-narrowing). Mirror D-310 из Phase 3 для goldapple. Стартуем с **N=100** (conservative catastrophic-failure detector для beauty-only sub-catalog — ~30-40% от ожидаемого SKU-count в catalog/1310 endpoints; точное значение скорректируется после first probe-crawl Wave 0). Со 5-й недели и далее run эмитит ops-Telegram сообщение `new N-rec for viled: 0.7 × 4-week-median viled_count = X` после каждого успешного run. Оператор сам решает поднимать N или нет (PR в config). НЕ auto-tune (защита от silent drift вниз при постепенной regression beauty-catalog).
  - **Rationale for revision**: исходный seed N=20000 базировался на full sitemap-42,294 URLs. После scope-narrowing до 2 catalog/1310 endpoints (косметика+парфюм only) ожидаемый URL pool — hundreds, не tens-of-thousands. Точный baseline установится первой Wave 0 probe-crawl; planner может скорректировать seed N в `pyproject.toml`.
- **D-202:** **Static N storage location**: `pyproject.toml [tool.ga_crawler.crawl.viled]` ключ `sanity_gate_n` — consistent с Phase 3 layout `[tool.ga_crawler.crawl.goldapple] sanity_gate_m=1000`. Same namespace pattern, разные ключи. Operator override через CLI `--sanity-gate-n` (mirror Phase 3).
- **D-203:** **Auto-suggest mechanic shared с Phase 3 D-310**: вынести `auto_suggest_threshold(history, factor=0.7, min_runs=4)` из `runner/gates.py` (currently goldapple-specific) в retailer-agnostic helper, либо параметризовать. Plan-time: planner решает refactor vs duplicate. Default: refactor — DRY winning over isolation на v1 для simple median-formula.

### Brand-alias YAML format (NORM-01)

- **D-204:** **Location: `config/brand-aliases.yaml`** — top-level `config/` directory under repo root. Operator-editable через git PR; cron deploy реплицирует через `git pull`. NOT in-src (deploy-cycle на каждый alias-fix), NOT data/ (no other data-mutation files на v1). `config/` создаётся в Phase 2 Wave 0 (новая директория).
- **D-205:** **Schema: flat dict `{brand_norm: [aliases...]}`** — plain mapping. Пример:
  ```yaml
  estee_lauder:
    - "Estée Lauder"
    - "Estee Lauder"
    - "Эсте Лаудер"
  givenchy:
    - "Givenchy"
    - "Живанши"
  ```
  Никакой richer-schema (canonical, category) на v1 — PROJECT.md закрепляет strict brand+name+volume key, нет fuzzy/category-routing на v1. v2 (REQ MATCH-V2-01..02) можно расширить без миграции (YAML-format additive).
- **D-206:** **Seed mechanism: planner extracts top-50 viled brands из spike artifacts**. Источники в порядке приоритета: (a) `.planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json` (15 fetched products, brand-string field из `__NEXT_DATA__`); (b) `.planning/spikes/01-goldapple/sample-payloads/viled-home-brands-extract.json` (homepage brand-list extraction); (c) первые ~50 product fetches в первом probe-crawl Phase 2 (planner adds Wave для extraction-only run). Top-50 — приоритезация по spike-traffic (luxury fashion + niche perfumery per plan 01-05); rest of viled brands добавляются operator-driven в первые 4 недели через NORM-06 review-queue feedback loop. Manual RU/EN-варианты вручную для брендов с явным кириллическим вариантом (Estée Lauder ↔ Эсте Лаудер); pure-Latin бренды без RU-варианта seed-ятся одной строкой.
- **D-207:** **Runtime reload: read-once at run start**. `BrandAlias.__init__()` парсит YAML в memory dict, lookup методы — pure dict-get. Никакого hot-reload / file-watcher — weekly cron run живёт ~1 час, alias-changes между runs не нужны mid-run. `config/brand-aliases.yaml` под git — operator-edits видны со следующего run.

### NORM-06 review queue format

- **D-208:** **File-based: `.planning/runs/{run_id}/norm06-review.md`** — markdown-таблица per run, single source of truth для оператора. Schema:
  ```markdown
  # NORM-06 Review Queue — Run {run_id} ({YYYY-MM-DD})

  | brand_or_slug | source | run_id | status |
  |---------------|--------|--------|--------|
  | jo_malone_london | viled-unmatched | 44 | pending |
  | tom-ford-private-blend | goldapple-new-slug | 44 | pending |
  ```
  Source enum: `viled-unmatched` (Phase 3 NORM-06 forward — viled brand с zero goldapple match) / `goldapple-new-slug` (Phase 3 D-307 NORM-06 reverse — week-over-week NEW slug). Status default `pending`; operator dimы редактирует to `aliased` / `skip` / `reviewed` после ревью.
- **D-209:** **Operator workflow**: открыть `.md` в Obsidian/editor, для каждой `pending` строки:
  - `aliased` → добавить alias в `config/brand-aliases.yaml`, status пометить `aliased`
  - `skip` → бренд намеренно отсутствует на goldapple ИЛИ slug — false-positive ноун (российский регион-only)
  - `reviewed` → катch-all для сложных случаев (требует ручной investigate)
  Никаких automated-workflows вокруг review (no GitHub Issues, no auto-PR). Pure markdown ledger. Historical artifact в `.planning/runs/` директории под git.
- **D-210:** **NO DB-table backup на v1**. Audit trail через git history `.planning/runs/{id}/norm06-review.md`. Если потребуется trend-аналитика (REPORT-V2 territory) — добавлять в v2.
- **D-211:** **Phase 3 stub cli.py больше не пишет review-queue в Stubs**. Сейчас Phase 3 эмитит counters (`unmatched_viled_brands`, `unmatched_goldapple_slugs_new`) в `runs.stats`; Phase 2 owns NEW write-path: после Phase 3 forward-NORM-06 + Phase 3 reverse-NORM-06 emit, оркестратор вызывает `Norm06Writer.persist(run_id, viled_unmatched, goldapple_new_slugs)` который рендерит markdown-файл. Counter в `runs.stats` остаётся (для observability), markdown — operator-facing format.

### Stub cutover + module structure

- **D-212:** **Delete Stubs from `cli.py` after Phase 2 ships real impls**. Stubs (StubBrandAlias / StubNormalizer / StubSnapshotWriter / StubRunWriter) удаляются from production code; их функция (testability) переходит в `tests/conftest.py` mocks (which already exists per `03-01-SUMMARY.md` — 11 fixtures including `mock_brand_alias`, `mock_normalizer`, `mock_snapshot_writer`, `mock_run_writer`). Никакого `--dev-stubs` flag — runtime divergence между dev и prod = риск bugs, не выигрыш.
- **D-213:** **viled fetcher/parser mirror goldapple structure**:
  ```
  src/ga_crawler/
    fetchers/
      goldapple.py   # existing (Camoufox)
      viled.py       # NEW Phase 2 (curl_cffi Tier 0)
    parsers/
      goldapple_microdata.py   # existing
      viled_nextdata.py        # NEW Phase 2 (__NEXT_DATA__ extraction)
    enumeration/
      goldapple_sitemap.py     # existing
      viled_sitemap.py         # NEW Phase 2 (curl_cffi sitemap-index walker)
    runners/
      goldapple_run.py         # existing
      viled_run.py             # NEW Phase 2 (orchestrator: sitemap → fetch → parse → snapshot → gate)
  ```
  Per-retailer split mirrors Phase 3; ParseDispatcher (interfaces.py Protocol) routes by retailer-id; runners/main_run.py composes both retailers in one weekly run (Phase 4+ may relocate).
- **D-214:** **Storage: single `src/ga_crawler/storage/sqlite.py` module** containing all SQLModel table definitions (Run, Snapshot) + atomic helpers (`patch_stats` via raw SQL `json_patch`, `BrandAliasYamlLoader`, `Norm06Writer`). Ожидаемый размер 200–300 строк — split на 3 файла overkill для v1. Refactor если перешагнём 500 строк.
- **D-215:** **Shared normalizers**: `src/ga_crawler/normalizers/{brand,name,volume}.py` — три модуля по одной NORM-* функции. Volume parser layered: regex tokenize → unit-table lookup (`мл/ml/мilliliter` → `ml`, `oz/унция` → `oz`, `г/g/gram` → `g`, `шт/pcs` → `pcs`) → multipack-detect (regex `(\d+)\s*[xх×]\s*(\d+)` или `Set of (\d+)` или `(\d+)\s*шт`). Multipack flag persists в snapshot row directly (PARSE-04 + multipack_flag). Unparseable volume → `volume_norm=NULL`, `multipack_flag=False`, parse_error_flag=True (PARSE-04 sanity-fail), но row не блокирует insert — Phase 4 matcher просто не матчит rows с NULL volume_norm.
- **D-216:** **Brand-alias loader**: `src/ga_crawler/alias/yaml_loader.py` — single class `YamlBrandAlias(BrandAliasProtocol)`. Reads `config/brand-aliases.yaml` once at init, caches dict. `lookup(brand_norm) -> list[str]` returns aliases (or empty list).

### PARSE-06 stock-state mapping (Claude's Discretion — surfaced for review)

- **D-217:** **viled `__NEXT_DATA__` stock-state extraction**:
  - `attributes.in_stock == true` → `IN_STOCK`
  - `attributes.in_stock == false` → `OUT_OF_STOCK`
  - HTTP 404 (no `__NEXT_DATA__`) → `DELISTED`
  - HTTP 301/302 redirect with Location → `URL_CHANGED` (URL stored для Phase 4 потенциального dedup)
  - Exception / parse failure / unknown shape → `UNKNOWN`
  - `UNAVAILABLE` reserved для intermediate "not orderable but exists" state (e.g. pre-order, season-out) — detect via `attributes.availability == "preorder"` or similar string field. Empirically validate в первый run; revise если viled __NEXT_DATA__ shape отличается.
  - **Confidence:** MEDIUM — viled `__NEXT_DATA__` shape known от plan 01-07 (`viled-nextdata-shape.json`) но specific in_stock/availability field paths не документированы в spike — planner Wave 0 верифицирует против spike sample-payload.

### PARSE-05 hard-fail invariant

- **D-218:** **Aggregate post-crawl gate, parallel CRAWL-05 N-gate**. После viled run-loop:
  ```
  required_field_null_rate = (count of rows where name OR current_price OR url is NULL) / total_count
  if required_field_null_rate > 0.05:
      runs.status = 'failed'
      reason = 'parse_quality_below_threshold'
  elif viled_count < sanity_gate_n:
      runs.status = 'failed'
      reason = 'sanity_gate_n_failed'
  else:
      runs.status = 'success'
  ```
  Two gates checked sequentially; either failing fails run-to-completion (mirror D-309 from Phase 3). Snapshot rows still persist (audit trail), но downstream phases (matcher/reporter/delivery) видят `runs.status='failed'` и skip.

### DATA-06 backup strategy

- **D-219:** **Phase 2 creates `backups/` directory + simple `bin/backup.sh` script**. Script: `sqlite3 prices.db ".backup backups/$(date +%Y-%m-%d).db"` (online backup, atomic). Retention rotation (keep 4 most recent) — plain shell `ls -t backups/*.db | tail -n +5 | xargs rm -f`. **Phase 7 ops-playbook** добавляет cron entry: `0 1 * * * /opt/ga_crawler/bin/backup.sh` (daily 01:00 KZ, после weekly run на Sunday). VACUUM INTO рассмотрен но online `.backup` проще + WAL-safe.

### Schema migrations

- **D-220:** **Skip alembic on day 1**. Per CLAUDE.md "Add when schema changes after first deploy. SQLModel ships SQLAlchemy 2.x, alembic integrates cleanly. Skip on day 1, add at first migration." Phase 2 Wave 0 schema (`runs`, `snapshots`) finalized с `was_price`, `stock_state` enum, `multipack_flag` — нет известных predictable migrations на v1 horizon. Add alembic if/when v2 brings migration (e.g. INFRA-V2-01 Postgres migration, REPORT-V2-* new columns).

### CRAWL-01 viled brand list provenance

- **D-221:** **viled brand list = derived from `v_current_snapshots WHERE retailer='viled' AND run_id=:current`**. Brand_norm уже на каждой snapshot row (NORM-02 нормализует во время crawl). Phase 3 reads this view в начале своего run (after viled phase completes) для CRAWL-02 brand-pool. NO separate brand-list extraction step / table — single source of truth = snapshots.brand_norm column. SQL view `v_current_snapshots` создаётся Phase 2 Wave 0 как:
  ```sql
  CREATE VIEW v_current_snapshots AS
  SELECT * FROM snapshots
  WHERE run_id = (SELECT MAX(run_id) FROM runs WHERE status = 'success');
  ```

### CRAWL-01 viled enumeration strategy (revised 2026-05-07)

- **D-223:** **Catalog-page enumeration, NOT sitemap-only**. После scope-narrowing scope до beauty+perfumery only, viled URL pool comes из 2 specific catalog endpoints:
  - `https://viled.kz/men/catalog/1310`
  - `https://viled.kz/women/catalog/1310`

  Sitemap-based enumeration (план в исходной D-context) НЕ применяется — sitemap содержит весь luxury-каталог (одежда, обувь, сумки, аксессуары) без category metadata для фильтрации. Эти 2 catalog endpoints — operator-driven scope filter, mirror подхода Phase 3 D-301 (sitemap → brand_bucket whitelist через viled brands).

- **D-224:** **Enumeration mechanism: TBD — investigated в Wave 0 probe**. Кандидаты в порядке приоритета (планер confirms Wave 0):
  1. **`__NEXT_DATA__` on category page** — наиболее вероятно. viled built на Next.js (per plan 01-07 — homepage и privacy pages оба emit `__NEXT_DATA__`). Category page likely embeds initial product list + total count + pagination metadata (`pageProps.products[]`, `pageProps.totalCount`, `pageProps.currentPage`). curl_cffi fetches first page → enumerate `?page=2..N` через `__NEXT_DATA__` `totalCount` / `pageSize`.
  2. **HTML pagination** — fallback если `__NEXT_DATA__` не emit'ит products. Parse links to product pages из HTML, follow pagination links (`<a class="pagination-next">` или query-param style).
  3. **Internal Next.js API** — `_next/data/{buildId}/men/catalog/1310.json` route emit'ит pageProps directly. Faster + cleaner JSON-only response, но fragile (buildId rotates on deploy). Use as optimization если первичный механизм работает.

  Все три cluster'а опираются на curl_cffi Tier 0 — НЕТ Camoufox/Patchright. viled is full-Tier-0 (15/15 in plan 01-07).

- **D-225:** **Per-catalog rate-limit + concurrency=1 across both endpoints**: 2s pause between page fetches (mirror plan 01-04 ToS rate-limit), один retailer = один последовательный fetch loop. Catalog-1 (men) → catalog-2 (women) sequentially. NO async concurrency для viled.

- **D-226:** **Expected URL pool size (rough estimate, refined Wave 0)**: 2 catalogs × ~50-300 products = ~100-600 SKUs total (luxury parfumery + cosmetics — niche selection, not mass-market). Final number устанавливается first probe-crawl. N-gate seed=100 (D-201 revised) safe for катастрофических failures даже при 200-SKU baseline.

- **D-227:** **Catalog endpoint URLs in config**: `pyproject.toml [tool.ga_crawler.crawl.viled]` keys:
  ```toml
  catalog_urls = [
    "https://viled.kz/men/catalog/1310",
    "https://viled.kz/women/catalog/1310",
  ]
  ```
  Operator может добавлять new catalog endpoints via PR (e.g. seasonal beauty sub-categories) без code change. Mirror pattern для Phase 3 `smoke_urls` operator-managed list.

### Test infrastructure inheritance

- **D-222:** **Inherit Phase 3 test infrastructure без изменений**. `tests/conftest.py` (11 fixtures), `tests/unit/`, `tests/integration/` уже configured. Phase 2 adds fixtures для viled HTML samples (`viled_pdp_html` — load from `.planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json` или дополнительные viled HTML), brand-alias YAML test fixture, in-memory SQLite session factory. respx по-прежнему НЕ используется для curl_cffi (incompat per Phase 3 D-302); monkey-patch `_fetch_xml`-style wrapper functions.

### Claude's Discretion

- **Module organization for shared utilities**: разделение `normalizers/{brand,name,volume}.py` vs single `normalizers.py` файл — оставлено планеру. Default: split на 3 файла т.к. NORM-02 (brand) комбинирует accent-strip + alias lookup, NORM-03 (volume) комбинирует regex + unit-table + multipack — каждый non-trivial.
- **Specific volume unit-table contents** (full mapping `мл/ml/милилитр → ml`, `oz/унция → oz`, etc.) — оставлено планеру, planner extracts from spike payloads + Phase 4 matcher hint (что unit-table должна нормализовать к ENUM consumed by strict-key matching).
- **HTTP retry classes для curl_cffi** — оставлено планеру. Mirror Phase 3 tenacity policy (`stop_after_attempt(3) + wait_exponential_jitter(2, 30) + retry_if_exception_type((curl_cffi.requests.errors.*))`); специфичные exception classes verify планер в Wave 0.
- **viled `__NEXT_DATA__` JSON paths**: точные dot-paths для `name`, `brand`, `current_price`, `was_price`, `volume_raw`, `availability`, `sku_id` — оставлено планеру, extract from `viled-nextdata-shape.json` + первый probe-fetch Phase 2 Wave 0.
- **Concurrency=1 vs sequential async для viled curl_cffi**: viled rate-limit 2s sequential = single-thread sufficient. Default: sequential `for` loop, `time.sleep(2)` (NOT async). Phase 3 needs `async with Camoufox` lifecycle; viled simpler. Planner может выбрать async для symmetry. Trade-off: simpler sync code vs uniform async stack with goldapple. Default: sync для viled side, async-await для goldapple side (each retailer best fit; orchestrator коcomposes).
- **JSONB column type**: SQLite не имеет native JSONB; используется TEXT с JSON-validation на app-side (SQLModel + Pydantic) или native SQLite `json_*` functions. Phase 3 D-310 уже использует raw SQL `json_patch`. Default: TEXT-encoded JSON в `runs.stats` column, raw SQL `json_patch(stats, ?)` в `Phase 2 RunWriter.patch_stats`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — core value, scope, constraints, key decisions
- `.planning/REQUIREMENTS.md` §Crawl (CRAWL-01,03,04,05,06), §Parse (PARSE-01..06), §Norm (NORM-01..06), §Data (DATA-01..06)
- `.planning/ROADMAP.md` §"Phase 2: Project Skeleton + viled Crawl + Storage" — phase goal, success criteria 1-5, requirement list

### Spike findings (LOCKED — Phase 2 inherits)
- `.planning/spikes/01-goldapple/notebook-viled.py` — RECON-02 reference implementation; curl_cffi `impersonate="chrome"` at 2s pause, 15/15 success
- `.planning/spikes/01-goldapple/sample-payloads/viled-fetch-results.json` — 15 product fetch records (brand, price, status, JSON-LD presence per URL); seed source для brand-alias YAML
- `.planning/spikes/01-goldapple/sample-payloads/viled-home-brands-extract.json` — homepage brand-list extraction; supplementary seed source
- `.planning/spikes/01-goldapple/sample-payloads/viled-product-urls.txt` — sample of 15 viled product URLs at `/item/<numeric_id>`
- `.planning/spikes/01-goldapple/sample-payloads/viled-sitemap.xml` — viled sitemap-index (9 sub-sitemaps, 42,294 product URLs)
- `.planning/spikes/01-goldapple/sample-payloads/viled-sitemap-1-excerpt.xml` — sub-sitemap-1 sample excerpt
- `.planning/spikes/01-goldapple/sample-payloads/viled-nextdata-shape.json` — `__NEXT_DATA__` JSON shape reference (для D-217 stock-state path verification)
- `.planning/spikes/01-goldapple/sample-payloads/viled-kz-robots.txt` — robots.txt; no Crawl-delay, no anti-scraping clauses
- `.planning/spikes/01-goldapple/tos-audit.md` — committed rate-limits (viled 2s sequential), no UA-strictness

### Phase 1 + Phase 3 context (decisions cascade)
- `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md` — D-04 persistent-context pattern (irrelevant for viled Tier 0 but useful for unified retry taxonomy)
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` — D-301..D-313 frozen Phase 3 decisions; D-308/D-309/D-310 sanity-gate-and-auto-suggest pattern (Phase 2 mirrors as D-201..D-203); D-311 fresh-profile-per-run (irrelevant for viled, NOT inherited); D-312 smoke-probe (irrelevant for viled — no Camoufox to smoke-test)
- `.planning/phases/03-goldapple-crawl/03-VERIFICATION.md` — Phase 3 verification template; Phase 2 will produce equivalent
- `.planning/phases/03-goldapple-crawl/03-VALIDATION.md` — test-coverage template; Phase 2 inherits + extends

### Frozen interfaces and existing infrastructure
- `src/ga_crawler/interfaces.py` — **FROZEN Wave 0 of Phase 3** Protocol contracts: `BrandAliasProtocol`, `NormalizerProtocol`, `SnapshotWriterProtocol`, `RunWriterProtocol`, `ParseDispatcherProtocol`, `CrawlerProtocol`. Phase 2 implementations MUST conform; if drift surfaces — Pitfall 9 — это integration-time blocker, не chore.
- `src/ga_crawler/cli.py` — current Stub Phase 2 implementations (StubBrandAlias / StubNormalizer / StubSnapshotWriter / StubRunWriter) — reference for replacement; behavioral parity expected (StubSnapshotWriter writes JSONL append-only — Phase 2 SnapshotWriter writes SQLite append-only with same semantic invariants)
- `tests/conftest.py` — 11 fixtures including `mock_brand_alias`, `mock_normalizer`, `mock_snapshot_writer`, `mock_run_writer`; Phase 2 inherits + may add `viled_pdp_html`, `brand_alias_yaml_fixture`, `in_memory_sqlite_session`
- `pyproject.toml` — dependencies pinned (sqlmodel 0.0.38, pydantic 2.13.3, curl_cffi (existing), tenacity 9.1.4, pytest 8.4.2, pytest-asyncio 1.3.0); `[tool.ga_crawler.crawl.goldapple]` namespace — Phase 2 adds `[tool.ga_crawler.crawl.viled]` mirror

### Research foundation
- `.planning/research/SUMMARY.md` — общая стратегия (modular monolith, snapshot-table integration backbone)
- `.planning/research/STACK.md` §Storage SQLite vs Postgres, §Scheduling — Phase 2 storage decisions inherited verbatim
- `.planning/research/ARCHITECTURE.md` §"Major components", §"snapshots-table integration" — модульный монолит, append-only
- `.planning/research/PITFALLS.md` — Pitfall 6 (atomic merge into runs.stats), Pitfall 9 (Protocol contract drift)

### Project conventions
- `CLAUDE.md` (project root) §Technology Stack, §Storage SQLite vs Postgres, §Conventions, §Architecture — recommended versions, alembic-skip-on-day-1 rule

### Project state & accumulated decisions
- `.planning/STATE.md` — Key Decisions table (90+ rows); Phase 2 cascades many. Particularly relevant:
  - "viled fully Tier 0 confirmed: 15/15 HTTP 200 via curl_cffi impersonate=chrome at 2s pause" (plan 01-07)
  - "Phase 2 PARSE-02 для viled = __NEXT_DATA__-first extraction (NOT JSON-LD-first)" (plan 01-07)
  - "Phase 2 viled enumeration = sitemap-only (42,294 product URLs)" (plan 01-07)
  - "viled was_price requirement v1 schema satisfiable from week 1 via realPrice field" (plan 01-07)
  - "viled currency: ₸ → KZT hardcoded" (plan 01-07)

### Out-of-tree (Obsidian vault)
- `knowledge/decisions/Goldapple — Tier 2 Camoufox без proxy, 99 из 100.md` — Phase 1 sign-off mirror; Phase 2 не блокируется этим, но Camoufox-related decisions cascade в Phase 7 hosting

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`spike-01-goldapple/notebook-viled.py`** — curl_cffi fetch loop pattern, JSON-LD presence detection, per-URL timing instrumentation. Phase 2 production: rewrite into `ga_crawler.fetchers.viled.ViledFetcher` (sync `for` loop, `time.sleep(2)` rate-limit, tenacity retry). Throwaway by D-16 — file НЕ переносится, паттерн переносится.
- **`spike-01-goldapple/_fetch_viled_brands.py` + `_fetch_viled_urls.py` + `_inspect_viled_nextdata.py`** — sitemap parsing + brand extraction + `__NEXT_DATA__` introspection scripts. Phase 2 production: `ga_crawler.enumeration.viled_sitemap.fetch_sitemap_urls()` + `ga_crawler.parsers.viled_nextdata.parse_pdp(html)`. Phase 3's `enumeration/goldapple_sitemap.py` is the structural template (curl_cffi + tenacity + persistence + diff helpers — though viled doesn't need NORM-06-reverse week-over-week diff because viled ↔ alias is forward-only).
- **`src/ga_crawler/runner/gates.py` `final_m_gate(count, M=1000)`** — Phase 3 sanity-gate primitive. Phase 2 reuses as `final_n_gate(count, N=20000)` или параметризует. `auto_suggest_m(history)` similarly reusable as `auto_suggest_threshold(history, factor=0.7, min_runs=4)`.
- **`src/ga_crawler/runner/stats.py` GoldappleStatsBuilder + StatsNamespaceError** — Phase 3 namespace-enforced stats builder. Phase 2 builds parallel `ViledStatsBuilder` (`viled.*` namespace) using same pattern. Recommended refactor: extract `NamespaceStatsBuilder(prefix)` base class.

### Established Patterns
- **Per-retailer parser dispatch** (`ParseDispatcherProtocol`): Phase 3 registers goldapple-microdata; Phase 2 registers viled-nextdata. Switch on retailer-id at runtime. Existing concrete `ParseDispatcher` impl missing — Phase 2 builds it (interfaces.py only defines Protocol; no concrete dispatcher exists yet).
- **Append-only snapshot writes** (DATA-03): keyed `(run_id, retailer, sku_id)` UNIQUE. Phase 2 writes with `retailer='viled'`, Phase 3 with `retailer='goldapple'`. Never UPDATE — only INSERT.
- **`runs` row lifecycle** (DATA-05): single row per weekly run; viled crawl creates row, goldapple crawl extends it (атрибуты `viled_count`, `goldapple_count` оба патчатся в `runs.stats` через json_patch). Phase 2 owns `runs` table schema + `RunWriter.create()` (новый метод not in `interfaces.py` Protocol — добавить или Phase 2 решает create-вне-protocol-pattern).
- **Spike rate-limit pattern**: viled `time.sleep(2)` between fetches; goldapple `random.uniform(3, 5)`. concurrency=1 для обоих. Constants в `pyproject.toml [tool.ga_crawler.crawl.{retailer}]`.
- **No Camoufox для viled**: Phase 1 D-04 (persistent context, stealth UA) НЕ применяется к viled. curl_cffi `impersonate="chrome"` достаточно. No proxy.
- **Phase 3 stub impls в cli.py** (StubBrandAlias / StubNormalizer / StubSnapshotWriter / StubRunWriter) показывают behavioral contract, который Phase 2 должна satisfy. Stubs пишут JSON/JSONL на диск; Phase 2 пишет SQLite + YAML с тем же external behaviour для interfaces.py Protocol calls.

### Integration Points
- **Output → snapshots table** (Phase 2 owns schema): SnapshotWriter.append() с retailer='viled' и all required fields per PARSE-01 (name, brand, volume_raw, current_price, was_price, currency, stock_state enum, url, brand_norm, name_norm, volume_norm, multipack_flag, scraped_at).
- **Output → runs table** (Phase 2 owns schema): RunWriter.create() at start, RunWriter.patch_stats() for `viled.*` keys, RunWriter.fail() on parse-quality / sanity-gate failure. Phase 3 reuses RunWriter.patch_stats() для `goldapple.*` keys без collision (Pitfall 6 atomic merge).
- **Output → config/brand-aliases.yaml** (Phase 2 owns format): seed contents in Wave; operator edits via PR.
- **Output → `.planning/runs/{run_id}/norm06-review.md`** (Phase 2 owns format): markdown ledger; operator-facing.
- **Output → backups/{YYYY-MM-DD}.db** (Phase 2 owns dir + script): cron entry комит из Phase 7.
- **Input → `pyproject.toml [tool.ga_crawler.crawl.viled]` config**: `sanity_gate_n=20000`, `pause_seconds=2.0`, `concurrency=1`, `retry_attempts=3`, etc. Mirror Phase 3 `[tool.ga_crawler.crawl.goldapple]` namespace.
- **Output → Phase 3 unblocked from stubs**: Phase 3 `cli.py` imports real impls instead of Stubs after Phase 2 ships. Test invariant: `pytest -m "not live"` остаётся 192/192 + добавляются Phase 2 tests (estimate 30-50 new tests).
- **Output → Phase 4 matcher**: viled+goldapple snapshots ∩ через strict-key `(brand_norm, name_norm, volume_norm)`; Phase 2 owns brand_norm/name_norm/volume_norm fields population.

### Open dependencies
None — Phase 2 fully unblocked. Phase 1 closed (operator_approved 2026-05-06), Phase 3 closed (operator_approved 2026-05-06), Phase 2 contracts frozen в interfaces.py.

</code_context>

<specifics>
## Specific Ideas

- **«Не дамп всех 1,400+ unmatched goldapple-slugs»** (унаследовано из 03-CONTEXT D-307) — формат NORM-06 review queue должен показывать ТОЛЬКО pending items для operator-review, не все historical. Markdown table per run = только current-week items.
- **«Auto-suggest никогда не auto-tune»** (D-203 mirrors D-310) — оператор всегда подтверждает PR-ом перед изменением `sanity_gate_n`. Защита от silent drift вниз.
- **«Stub cutover без --dev-stubs flag»** (D-212) — runtime divergence между dev и prod = риск bugs. Тесты используют conftest.py mocks (already shipped Wave 0 of Phase 3); production использует real impls. Один code path.
- **«viled rate-limit 2s sequential, NOT async-concurrency»** (D-225) — спайк подтвердил 15/15 на single-thread; async overhead не нужен; goldapple остаётся async (Camoufox lifecycle), viled — sync. Orchestrator composes.
- **«viled brand list = derived from snapshots»** (D-221) — single source of truth. Phase 3 reads `v_current_snapshots WHERE retailer='viled'` для CRAWL-02 brand-pool.
- **«viled scope = ТОЛЬКО beauty+парфюм (2 catalog/1310 endpoints)»** (D-223 — operator clarification 2026-05-07) — НЕ полный luxury каталог viled (одежда, обувь, сумки). Commercial relevance: goldapple — beauty retailer, matching одежды/сумок против goldapple бессмысленно. Spike РECON-02 использовал 15 random `/item/{id}` URLs не из catalog/1310 — Wave 0 probe-crawl установит actual category-1310 URL pool size + enumeration mechanism (likely `__NEXT_DATA__` pagination).
- **«viled enumeration: NOT sitemap-only»** (D-224) — sitemap содержит весь luxury каталог без category metadata для фильтрации. Использовать `__NEXT_DATA__`-based pagination на 2 catalog endpoints.
- **«alembic skip on day 1»** (D-220) — CLAUDE.md explicit; добавить только если первая schema migration реально нужна (v2 territory).

</specifics>

<deferred>
## Deferred Ideas

- **`--dev-stubs` flag для production CLI** — отвергнуто (D-212): runtime divergence = risk. Тесты через conftest.py mocks.
- **Richer brand-alias YAML schema (canonical, category, taxonomy)** — отвергнуто на v1 (D-205): PROJECT.md закрепляет strict-key, нет fuzzy/category-routing на v1. v2 territory (REQ MATCH-V2-01..02).
- **Auto-tune `sanity_gate_n`** — навсегда отвергнуто (D-203 contra). Auto-suggest only.
- **DB-table backup для NORM-06 review queue** — отвергнуто на v1 (D-210): markdown + git history достаточно. v2 territory (REPORT-V2 trend analytics).
- **Persistent `goldapple_count + viled_count` separate table** — отвергнуто: `runs.stats` json_patch namespace pattern справляется (Pitfall 6).
- **Hot-reload brand-alias YAML during run** — отвергнуто (D-207): weekly cron run ~1ч, alias-changes между runs не нужны mid-run.
- **Storage split на 3 файла (`storage/{runs,snapshots,stats}.py`)** — отвергнуто (D-214): overkill для v1, объёмы 200-300 строк expected. Refactor если перешагнём 500 строк.
- **alembic с day 1** — отвергнуто (D-220): CLAUDE.md explicit; добавить при первой migration.
- **VACUUM INTO для backup** — рассмотрено (D-219), отвергнуто в пользу online `.backup` (атомарность + WAL-safe).
- **Cron entry для backup в Phase 2** — отвергнуто: Phase 2 ships dir+script, cron entry → Phase 7 ops-playbook.
- **Async curl_cffi для viled (symmetry с goldapple Camoufox async)** — открыто; default sync; planner Wave 0 решает финально.
- **viled JSON-LD parser fallback** — отвергнуто (plan 01-07 empirical 0/15 JSON-LD); только `__NEXT_DATA__`.
- **CRAWL-01 brand-list extraction step (отдельный)** — отвергнуто (D-221): brand_norm derives from snapshots, single source of truth.
- **Multipack handling beyond flag (price-per-unit splitting, kit decomposition)** — отвергнуто на v1 (PROJECT.md NORM-04): kits flagged, excluded from price comparison. v2 если коммерческое использование требует.
- **Camoufox для viled fallback (если Tier 0 ломается)** — отвергнуто на v1: 15/15 success at 2s pause is solid; viled-anti-bot regression is highly unlikely в horizon. Если случится — escalate to Phase 7 ops-playbook decision.
- **Real-time viled probe (mid-week health check)** — отвергнуто (out-of-scope per PROJECT.md): weekly cadence is the contract.

### Reviewed Todos (not folded)
gsd-tools `todo match-phase 2` not invoked в этой sessions — todos infrastructure не задействована для phase-2 specifically. Если позже surface — ingest через standard NORM-06 flow.

</deferred>

---

*Phase: 2-Project Skeleton + viled Crawl + Storage*
*Context gathered: 2026-05-07*
*Scope-narrowing operator-clarification 2026-05-07: viled crawl restricted to `/men/catalog/1310` + `/women/catalog/1310` (beauty+parfumery only, NOT full luxury catalog). Cascading revisions: D-201 (N-gate seed 20000→100), D-223..D-227 (catalog-page enumeration replaces sitemap-only).*
*Decisions: D-201..D-227 (27 decisions: 22 from initial discuss + 5 net new from scope-narrowing).*

## Action Items for Other Documents

The following changes propagate to other artifacts at next opportunity:

- **`.planning/REQUIREMENTS.md` CRAWL-01**: amend description from "Краулер обходит весь каталог viled.kz (включая пагинацию) и собирает список URL продуктов" → "Краулер обходит beauty+парфюмерия каталог viled.kz (`/men/catalog/1310` + `/women/catalog/1310`, через пагинацию) и собирает список URL продуктов" — surface at /gsd-spec-phase 2 OR planner Wave 0 verifies + amends.
- **`.planning/PROJECT.md` v1 active list**: amend "Полный парсинг каталога viled.kz" → "Полный парсинг beauty+парфюмерия каталога viled.kz (men/catalog/1310 + women/catalog/1310)" — surface at next phase transition.
- **`.planning/STATE.md`**: add to "Accumulated Key Decisions" — "Phase 2 scope narrowed (2026-05-07): viled = beauty+parfumery only, 2 catalog/1310 endpoints, NOT full luxury catalog. Mismatch с Phase 1 spike RECON-02 (15 random /item/{id} URLs) intentional — spike validated curl_cffi feasibility, not category structure."
