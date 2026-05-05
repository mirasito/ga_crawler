# Spike 01: Goldapple Anti-Bot Decision Memo

**Sign-off:** _PENDING — заполнить дату + подпись после plan 01-11_
**Spike start:** _TBD_
**Spike end:** _TBD_

> Заполняется в plan 01-11 на основе всех findings 01-04..01-10.
> На завершении спайка копия дублируется в Obsidian `knowledge/decisions/` через `/gsd-spike --wrap-up`.

## TL;DR

> Однострочное summary: tier, engine, proxy, prod-IP recommendation.

- **Chosen tier:** _TBD (0 / 2 / 3 / 4)_
- **Browser engine:** _TBD (curl_cffi only / vanilla Playwright / Patchright / Camoufox)_
- **Proxy provider:** _TBD (none / IPRoyal residential / Decodo / managed unblocker)_
- **Production IP recommendation (Phase 7):** _TBD_

## Problem

Goldapple.kz anti-bot tier — defining unknown проекта (см. research/SUMMARY.md, research/PITFALLS.md). Phase 3 stack гейтится этим решением.

## Options tested

| Tier | Engine | Proxy | Result | Notes |
|------|--------|-------|--------|-------|
| _TBD_ | _TBD_ | _TBD_ | _TBD/100 fetches, X challenges_ | _TBD_ |

## Chosen

**Tier:** _TBD_
**Rationale:** _TBD_
**Exact 100-fetch results:**
- KZ-laptop (D-06): _N/100, X challenges_
- EU/RU residential (D-05): _N/100, X challenges_

## JSON-endpoint hunt verdict (D-09, D-10)

_TBD — found / not found. Если found: какие эндпоинты, как используются, влияет на сценарий Tier 0._

## Page-volume estimate (RECON-03)

**Method primary:** sitemap.xml at https://goldapple.kz/sitemap.xml (D-11 sitemap-first)
**Method secondary:** none — sitemap was reachable plain via `curl_cffi impersonate="chrome"` (HTTP 200, no JS-challenge); fallback to pagination-meta not needed.
**Sample size:** 5 брендов из пересечения с viled.kz top featured brands (per D-12)
**Brands measured:** Jo Malone London, Tom Ford, Creed, Frederic Malle, Givenchy

### Brand-selection methodology

viled.kz top-10 brands были получены автоматизированно через probe `_fetch_viled_brands.py`: HTTP GET `https://viled.kz/` через curl_cffi с impersonate=chrome → парсинг `<script id="__NEXT_DATA__">` JSON-blob → извлечение `brandName` из секций homepage (см. `sample-payloads/viled-home-brands-extract.json`, 58 брендов).

**Findings about viled.kz market position:** viled.kz — это **luxury fashion + niche perfumery** retailer (НЕ mass-market beauty). Featured beauty brands (section 12 homepage): Jo Malone London, Amouage, Creed, Frederic Malle, Kilian Paris, Armani Beauty, Tom Ford Beauty, Zielinski & Rozen. Также представлены luxury fashion houses (Saint Laurent, Gucci, Givenchy, Maison Margiela, Tom Ford) которые имеют beauty-линии, потенциально совпадающие с goldapple.

Из этого пула выбраны **5 брендов** для эксперимента — те что **наиболее вероятно есть и в goldapple**:
1. Jo Malone London — niche perfumery
2. Tom Ford — luxury cosmetics + perfumery
3. Creed — niche perfumery
4. Frederic Malle — niche perfumery (Editions de Parfums)
5. Givenchy — luxury cosmetics + perfumery

⚠ Default-list из plan_context (Lancôme, Estée Lauder, Chanel, La Roche-Posay, Vichy) был **отвергнут** как не-репрезентативный: viled.kz luxury-positioned, mass-market бренды dermo-cosmetics (La Roche-Posay, Vichy) на viled likely отсутствуют. Документировано как deviation Rule 3 (blocking-issue resolution).

### Per-brand counts

| Brand | Slug | Sitemap facet count | Product-numeric URLs containing slug | Source | Notes |
|-------|------|------:|------:|--------|-------|
| Givenchy | givenchy | 40 | 41 | sitemap | Хорошо представлен; макс. среди выборки |
| Tom Ford | tom-ford | 33 | 0 | sitemap | Slug не появляется в product-numeric URLs (продукты живут под категорийными routes); facet count даёт только catalog complexity |
| Frederic Malle | frederic-malle | 19 | 3 | sitemap | Niche perfumery, средний catalog |
| Creed | creed | 8 | 21 | sitemap | Sparse facets, но 21 product-numeric URL |
| Jo Malone London | jo-malone-london | 1 | 0 | sitemap | Минимальное представление в sitemap; investigate slug variants в 01-08 (возможно бренд индексируется под другим slug или отсутствует в KZ-каталоге) |

⚠ **Critical caveat:** "Sitemap facet count" — это число sub-views под `/brands/<slug>/...` (категорийные срезы каталога), а **НЕ количество SKU**. Реальный SKU count per brand требует рендер brand-listing-страницы, которая JS-gated. Defer real per-brand SKU counts to plan 01-08 warm-Patchright session.

### Aggregates

**Selected-brands sample:**
- **Total facet URLs:** 101
- **Average per brand:** 20.2
- **Min / Median / Max:** 1 / 19 / 40

**Catalog-wide (more reliable Phase 3 anchor):**
- **Total URLs in sitemap:** 112,317
- **Numeric-id product URLs (`/<id>-<slug>`):** 100,779 (89.7% of sitemap)
- **`/brands/<slug>*` facet pages:** 5,083 (4.5%)
- **Distinct brand slugs in `/brands/*`:** 1,461
- **Catalog-wide average products per brand:** ~69 (100,779 / 1,461)

### Implications for Phase 3

**Anchor:** the catalog-wide average (~69 products/brand) is a more robust estimator than sample facet counts, because:
1. Sample facet count ≠ SKU count (caveat above).
2. The 1,461 brand slugs include many small/regional brands; viled∩goldapple intersection will skew toward larger brands → real per-brand SKU might be higher.

Если предположить ~50 брендов в финальном пересечении viled∩goldapple (estimate, finalized в Phase 2 после viled-краула), и средний brand ≈ 69 products:
- **Weekly product fetches:** ~50 × 69 = ~3,450 requests/week
- **+ brand listing page warmup**: ~50 × 5 (avg facets to enumerate) = ~250 requests/week
- **+ retries / pagination**: ~10% overhead → **~4,000 fetches/week**
- **Bandwidth estimate** (assume ~150 KB per page through Patchright, conservative — JS-rendered SPA): ~4,000 × 150 KB ≈ **600 MB/week**
- **Proxy budget** (per research/STACK.md Tier 3 IPRoyal $3.50/GB): ~$2.10/week → **~$110/year**
- **Run duration** at goldapple committed rate-limit 3-5s random uniform, concurrency=1: 4,000 × 4s avg = **16,000s ≈ 4.4 hours/week** — fits Phase 7 cron Sunday-night window comfortably.

⚠ Real numbers будут refined в Phase 2 (viled brand-list — точное пересечение) и Phase 3 (actual goldapple crawl — real per-brand SKU counts via brand-page render). Это **PRELIMINARY estimate** на основе sitemap-данных + catalog-wide-average heuristic.

### Sitemap-as-enumeration-strategy validation

**Strong positive signal for Phase 3:** sitemap.xml is plain-deliverable from goldapple.kz. This means Phase 3 can:
1. Use sitemap as **primary product URL source** — no need to scrape category-listing-pages for enumeration (which would be JS-gated).
2. **Skip brand-listing-page rendering** entirely если только sitemap-derived numeric-product-URLs достаточны (что выглядит так — 100k+ URLs).
3. Sitemap ETags / Last-Modified позволят **incremental delta** между weekly runs (новые/удалённые SKU).

This significantly **simplifies** Phase 3 fetch architecture: enumeration via sitemap (Tier 0 / curl_cffi-only), then product-page fetches via Patchright (Tier 2). It also reduces total fetch count: only product pages need full render, not brand/category listings.

### Raw data

См. `sample-payloads/page-volume-raw.json` для per-brand listing.
См. `sample-payloads/page-volume-meta.json` для meta + catalog-wide aggregates.
См. `sample-payloads/goldapple-sitemap.xml` (primary sitemap-index, 510 B) и `sample-payloads/goldapple-sitemap-1-excerpt.xml` (first 50 URL entries из sub-1 как evidence pattern).
См. `sample-payloads/goldapple-all-urls.txt` (112,317 URLs, deterministic input для `_compute_pagevolume.py`).
См. `sample-payloads/viled-home-brands-extract.json` (58 brands от viled __NEXT_DATA__ — evidence для Task 1 brand-selection).

## viled.kz feasibility (RECON-02)

**Status:** **CONFIRMED — curl_cffi viable for Phase 2 (Tier 0).** No headless browser needed.

**Method:** `curl_cffi.requests.get(url, impersonate="chrome", timeout=30)` — single thread, sequential.
**Sample size:** 15 product URLs (autonomous probe из viled.kz/sitemap.xml — sitemap-index → 9 sub-sitemaps → diversified step-stride sample of 15 across `/item/<numeric_id>` route).
**Rate-limit used:** **2s pause** between fetches (per `tos-audit.md` viled.kz committed rate-limit; 1 req per 2s sequential).
**Reproducible script:** `.planning/spikes/01-goldapple/notebook-viled.py`
**Brand selection script:** `.planning/spikes/01-goldapple/_fetch_viled_urls.py` (sitemap-driven, replaces checkpoint:human-action Task 1).

### Per-URL outcomes

- **HTTP 200:** **15 / 15** (100% success)
- **JSON-LD present:** 0 / 15 (viled does NOT use JSON-LD schema.org — see "Critical finding" below)
- **JSON-LD has Product:** 0 / 15
- **JSON-LD has price (D-14 satisfaction proxy):** 0 / 15 — **D-14 не применим к viled**
- **`__NEXT_DATA__` present:** **15 / 15** (Next.js SSR JSON blob — Phase 2 PARSE-02 alternative key surface)
- **Errors:** none — no timeouts, no 403, no 429, no Cloudflare/DataDome challenges.

### Timing

- **Min / Avg / Max:** 300 / 485 / 671 ms per fetch
- **Wall-clock for 15 fetches @ 2s pause:** 35.3s (≈14 fetches/min effective rate)
- **Implications:** at avg 485ms response × ~50,000 viled product URLs (full catalog enumeration via sitemap) = ~7 hours sequential. **For weekly run targeting beauty subset** (`sizeType=BEAUTY`, ~10-20% of catalog ≈ 5,000-10,000 SKUs) → ~70 minutes per weekly run. Phase 2 throughput budget comfortably accommodates.

### Critical finding: viled uses `__NEXT_DATA__`, not JSON-LD

This was unexpected and is **load-bearing for Phase 2 PARSE-02**:

- viled.kz is a **Next.js SSR site** — server-side rendered HTML embeds page data in `<script id="__NEXT_DATA__" type="application/json">{...}</script>` (Next.js framework convention).
- **No `<script type="application/ld+json">` tags in product HTML** — schema.org Product markup is NOT present (likely a deliberate choice or oversight by viled SEO team).
- Phase 2 PARSE-02 for viled MUST extract price/brand/title/volume from `__NEXT_DATA__` JSON blob, NOT from JSON-LD.
- This pattern was already validated for viled in 01-04 (privacy page) and 01-05 (homepage); now confirmed for product pages.

### Phase 2 PARSE-02 hot-start: viled `__NEXT_DATA__` schema

Inspected via `_inspect_viled_nextdata.py` on 4 sample products (apparel + perfumery + cosmetics + watch). Canonical field paths for v1 schema:

| v1 schema field | `__NEXT_DATA__` JSON path | Sample value |
|---|---|---|
| `current_price` | `props.pageProps.attributes[0].price` | `44300` (integer KZT) |
| `was_price` | `props.pageProps.attributes[0].realPrice` | `44300` (== price when no sale) |
| `currency_display` | `props.pageProps.attributes[0].currency` | `"₸"` (unicode tenge) — programmatic mapping → `KZT` |
| `brand` | `props.pageProps.item.brandName` | `"Jo Malone London"` |
| `title` (product name) | `props.pageProps.item.name` | `"Одеколон Wood Sage & Sea Salt Cologne"` |
| `volume` (beauty only) | `props.pageProps.attributes[0].attributes[].name == "Размер"` → `.value` | `"30 мл"` (parse to ml integer in normalizer) |
| `category enum` | `props.pageProps.item.sizeType` | `BEAUTY` / `APPAREL` / `JEWELLERY` / `null` |
| `subcategory` | nested `attributes[].name == "Подгруппа"` | `"Одеколоны"`, `"Праймеры/Базы/Фиксаторы"` |
| `product_id` (URL slug) | `urlparse(url).path.split('/')[-1]` | `407682` (numeric, stable) |

See `sample-payloads/viled-nextdata-shape.json` for the full extracted structure.

### Side-deliverables (Phase 2 hot-start)

| Aspect | Finding |
|--------|---------|
| **JSON-LD schema** | **NOT present** on viled product pages. D-14-style success proxy не применим к viled. Use `__NEXT_DATA__` JSON blob instead (see schema table above). |
| **Pagination shape** | **No HTML pagination needed** — viled.kz/sitemap.xml is plain-deliverable (HTTP 200, application/xml) and contains the full catalog: 42,294 product URLs across 9 sub-sitemaps split by gender (`sitemap-items-women.xml` 22,378 URLs / `sitemap-items-men.xml` 11,845 / `sitemap-items-kids.xml` 8,071) + collection/lookbook/news. Phase 2 uses sitemap as primary enumeration source (no `?page=N` traversal, no infinite-scroll, no AJAX paging discovery needed). |
| **URL pattern** | All product URLs follow `https://viled.kz/item/<numeric_id>`. ID range observed: 148026 (oldest in sample) → 409206 (newest); IDs are monotonic sequential (Phase 2 can use `Last-Modified` from sitemap entries for incremental delta). |
| **UA strictness** | curl_cffi default impersonate=chrome works on the first request. No cookies required (no session-warmup). No CAPTCHA, no Cloudflare interstitial, no DataDome challenge. **viled has NO anti-bot layer** — confirmed by 15/15 plain success at 2s pause. |
| **Cookies / session** | No session-token required; statelessly fetchable. Phase 2 can use `curl_cffi` without persistent context. |
| **Pricing format** | Integer (`187700` = 187,700 KZT). No decimal. No formatted strings (`"5 990,00"`). Cleanest possible price extraction — no normalization regex needed. |
| **Currency format** | Display: `"₸"` (single unicode tenge sign). No programmatic `KZT` field in `__NEXT_DATA__`; Phase 2 NORMALIZE-01 hardcodes `"₸" → "KZT"`. All viled prices are denominated in KZT (no multi-currency). |
| **Robots/UA strictness** | viled.kz/robots.txt has no `Crawl-delay`, no User-Agent restrictions for our purpose (per 01-04 audit). 2s pause is courtesy-only (Pitfall 13). curl_cffi default chrome UA was not challenged. |
| **Was-price availability** | `realPrice` and `price` are SEPARATE fields in `__NEXT_DATA__`. In our sample they were equal (no active discount), but the dual-field structure means Phase 2 v1 schema's `was_price` requirement is **directly satisfiable** without retroactive backfill (per STATE.md "was_price captured in v1 schema" decision). When `realPrice > price`, that's a sale; report `was_price = realPrice`. |
| **HTTP fetch size** | ~190-200 KB per product page (gzipped HTTPS). For ~5,000 weekly viled fetches → ~1 GB/week bandwidth (no proxy needed since direct curl_cffi works). |

### Verdict

**Phase 2 stack confirmed: `curl_cffi` (Tier 0) + `selectolax` for HTML walking + Python `json` parsing of `__NEXT_DATA__`.** No headless browser, no proxy, no anti-bot escalation needed for viled.kz. Phase 2 PARSE-02 is **immediately viable** with the `__NEXT_DATA__` field paths above.

**RECON-02 — CLOSED.** All side-deliverables captured. Phase 2 starts with hot data, not cold reconnaissance.

See `sample-payloads/viled-fetch-results.json` for raw per-URL metrics (15 records).
See `sample-payloads/viled-nextdata-shape.json` for `__NEXT_DATA__` shape extract.
See `sample-payloads/viled-product-urls.txt` for the 15 sampled URLs (reproducible via `_fetch_viled_urls.py`).

## robots/ToS audit summary (RECON-04)

_См. tos-audit.md. Committed rate-limits:_
- viled.kz: _TBD_
- goldapple.kz: _TBD_

## Next-step impact

- **Phase 3 stack:** _TBD_
- **Phase 7 hosting / prod-IP:** _TBD_

## Open risks

- _TBD_

## Appendix: Challenge-rate (D-15)

_TBD — если challenge-rate >20%, tier помечается "fragile" даже на технически-passing._
