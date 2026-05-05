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

| Tier | Engine | Proxy | Geo (IP) | Result | Notes |
|------|--------|-------|----------|--------|-------|
| 2 | Patchright (warm context, headless=False, 21s gate-wait) | none | KZ (laptop, D-06) | 0/7 success, 7/7 gate-shells (0 auto-cleared) | Plan 01-06 — fingerprint-based 403 на `/web/api/v1/settings`. **Patchright superseded for goldapple.** |
| 2 | **Camoufox** v135.0.1-beta.24 (warm `persistent_context`, geoip+humanize, headless=True) | none | KZ (laptop, D-06) | **99/100 success**, 0/100 gate-shells, 1 block (stale `/7681000002-...` SKU returns 200 + 9.5 KB shell, not anti-bot) | Plan 01-08 — gate cleared 100/100 (1× 1000ms wait, 99 instant). Microdata `<meta itemprop="price">` extracted 99/100. **D-13 PASS, D-15 NOT FRAGILE.** |

**Tier 2 Camoufox KZ-laptop: PASS.** Phase 3 production engine = Camoufox direct, no proxy. Plans 01-09 (multi-geo proxy comparison) и 01-10 (Tier 3 escalation) **SKIPPED** — fingerprint alone solves the gate, multi-geo VOI ≈ 0, Tier 3 не triggered. D-08 (IPRoyal pre-register) **CANCELLED**. Plan 01-11 finalize MEMO с verdict "Tier 2 Camoufox direct, no proxy".

### Open Risks (post 01-08)

- **goldapple is microdata-only, NOT JSON-LD.** D-14 originally specified "HTML 200 + JSON-LD product schema present" but goldapple's only JSON-LD block is `OfferShippingDetails` (shipping policy). Pricing comes from inline microdata `<meta itemprop="price" content="..."><meta itemprop="priceCurrency" content="...">`. Phase 3 parser uses `selectolax` + microdata extraction, NOT JSON-LD. Different from viled.kz which uses `__NEXT_DATA__`. Phase 3 stack has TWO parser strategies, not one.
- **Brand-precision shortfall on Tom Ford / Jo Malone London:** numeric-id sitemap (`/<digits>-<slug>`) does not contain product URLs for these 2 brands at all (only `/brands/<slug>/...` facet routes). Spike substituted 51 random product URLs from the sitemap. Phase 4 brand-alias YAML built separately — does not affect "Camoufox passes the gate at scale" hypothesis.
- **Camoufox upstream maintenance:** daijro/camoufox v135.0.1-beta.24 used. CLAUDE.md flagged daijro as "unmaintained as of mid-2025"; we observed fresher releases. Phase 3 ops playbook: weekly check "does Camoufox still pass goldapple?" + alternate to coryking/camoufox fork если daijro stalls.
- **Hetzner-EU + Camoufox compatibility (D-07 lookahead):** не проверено. GroupIB is a Russian-market vendor likely whitelisting local TLD/IP-geo combos. If Phase 7 hosts on EU and the gate-pass regresses → revive D-08 (IPRoyal trial) for KZ-residential. One Camoufox+EU smoke fetch before locking Phase 7 hosting is recommended.
- **Stale-SKU 200-but-9.5KB pattern:** `/7681000002-givenchy-pour-homme-blue-label` returned status 200 with the GUN-shell-sized payload (9.5 KB) but title cleared away from "checking device". This is NOT gate-shell behavior — it's likely a de-listed SKU rendering an empty product page. Phase 3 parser must distinguish "no microdata" (de-listed SKU) from "gate not cleared" (anti-bot block) — match-rate pipeline should not treat de-listed pages as scrape failures.

## Chosen

**Tier:** _TBD_
**Rationale:** _TBD_
**Exact 100-fetch results:**
- KZ-laptop (D-06): _N/100, X challenges_
- EU/RU residential (D-05): _N/100, X challenges_

## JSON-endpoint hunt verdict (D-09, D-10)

**Verdict:** **No usable Tier 0 endpoint** found in the network-hunt phase. **AND** Tier 2 (Patchright direct on KZ-laptop, no proxy) was empirically confirmed **insufficient** to clear the goldapple gate — escalation beyond originally planned Tier-2 baseline is required for Phase 3.

### Method (substituted)

Plan 01-06 Task 1 originally specified a manual Chrome DevTools session. Substituted with a programmatic Patchright capture (script: `.planning/spikes/01-goldapple/scripts/01-06-network-hunt.py`) per user pre-authorization: 01-04 had already established that every goldapple HTML route is JS-gated, so DevTools would require loading the same gate-blocked browser session. Programmatic `page.on("request")` / `page.on("response")` capture exposes the same endpoints in machine-readable form. **7 URLs** probed (home, brands index, 2 brand listings, 3 product/facet pages from selected brands per CONTEXT.md D-12). 256 events captured. Sleep budget 3-5s per page per 01-04 committed rate-limit. Persistent context per D-04. KZ-laptop direct, no proxy per D-06.

See `sample-payloads/goldapple-network-trace.md` for the full investigation; `sample-payloads/goldapple-network-trace.json` for raw 256-event trace; `sample-payloads/goldapple-product-html-1.html` for one evidence challenge-shell sample.

### What was checked

- **5 page types** investigated via Patchright Network capture (home, brands index, 2 brand listings, 3 product pages from Givenchy/Tom Ford/Creed). **7 URLs total.**
- **20-25s per-page wait** (poll loop until title changes off "Gold Apple — checking device" + 5s `networkidle` settle). Total ~21s wall-clock per page.

### What was found (or NOT found)

- **`__NEXT_DATA__`:** **NOT present in any of the 7 fetched HTMLs.** Reason: every page returned the GUN challenge shell, not the real Next.js app. **Tier-0 viability via __NEXT_DATA__ is unverifiable** without first passing the gate.
- **JSON-LD:** **NOT present in any of the 7 fetched HTMLs.** Same root cause as above. **D-14 ALERT:** D-14 success-criterion verification (`HTML 200 + JSON-LD product schema present`) is **deferred to plan 01-08 post-gate-clearance**. We cannot revise D-14 yet without evidence of the post-gate page structure.
- **GraphQL endpoint:** **NOT detected** — neither in challenge HTML scripts nor in observed XHR.
- **Magento `/rest/V1/...`:** **NOT observed** in any frontend code path. Consistent with 01-04's `Disallow: /rest/` finding — the frontend genuinely doesn't call it.
- **Catalog API (Tier-0 candidate):** **NOT detected.**

### What WAS observed (XHR contract behind the gate)

| Endpoint | Method | Status | Role |
|---|---|---|---|
| `/web/api/v1/settings` | GET | **403 (24/24 attempts)** | The gate-clearance API. Frontend retries every 10s; 200 → `location.reload()`. |
| `/front/api/event?u=<uuid>&cfidsw-goldapple=<base64>` | GET | 200 | GUN telemetry beacon (per-event fingerprint blob). |
| `/front/api/event/idw-goldapple` | GET | 200 | Initial telemetry handshake. |
| `https://ru.id.facct.ru/id.html` | GET | 200 | F.A.C.C.T. iframe origin (cross-origin device fingerprint harvest). |
| `https://sp.goldapple.ru/front/api/apm/events` | POST | 202 | Elastic APM telemetry sink (logs denied visitors). |

These are anti-bot infrastructure endpoints, NOT a usable catalog API.

### Critical new intel: anti-bot vendor is GroupIB / F.A.C.C.T. (NOT Cloudflare/DataDome)

The challenge HTML reveals the vendor that 01-04 could only describe as "DataDome-style":

- `window.gib.init({cid: 'w-goldapple', gafUrl: '//ru.id.facct.ru/id.html'})` — `gib` = **GroupIB** (https://www.group-ib.com — Singapore-based fraud-prevention vendor; **rebranded to F.A.C.C.T. for Russian market** in 2023).
- `cid: 'w-goldapple'` confirms goldapple is a paid GroupIB customer.
- Internal frontend log: `error.name = 'GUN_INIT_PAGE'; '403 ошибка нет кук'` — they call the challenge state "GUN init", logged via Elastic APM at `sp.goldapple.ru/front/api/apm/events`.

**Implication for tier escalation:** the 2026 Patchright pass-rate benchmarks cited in CLAUDE.md and research/STACK.md target Cloudflare / DataDome / Akamai. **GroupIB / F.A.C.C.T. is not in those benchmarks.** The "Patchright + residential proxy" path may not be the right escalation tree; **Camoufox** (different fingerprint surface — Firefox-based vs Chromium) becomes a more likely candidate than originally placed at Tier-4 last resort.

### JSON-LD presence in product HTML

**Unverifiable in this phase.** Sample file `sample-payloads/goldapple-jsonld-sample.json` is `[]` (empty). See **D-14 ALERT** above; verification deferred to 01-08.

### Implications for Phase 3

- **Tier 2 stack confirmed INSUFFICIENT on the originally planned baseline (Patchright + KZ-laptop direct, no proxy).** 0/7 successful HTML loads = 0% gate-clearance rate. STATE.md "if ≥98/100 + challenge<10% — proxy not needed" gate is decisively failed at this exploratory step.
- **Required escalation** (to be empirically tested in 01-08): one or more of:
  1. Patchright + IPRoyal residential proxy (revive deferred plan 01-03 — sign up before 01-08 starts to avoid losing a day to KYC).
  2. Camoufox (different fingerprint surface; Firefox-based likely orthogonal to GroupIB Chromium signatures).
  3. Long warmup session (5-15 minutes idle browsing, then start product fetches).
  4. Combinations of the above.
- **Bandwidth estimate** (per `## Page-volume estimate (RECON-03)` section): unchanged at ~600 MB/week through Patchright per the 01-05 anchor.
- **Proxy budget if Tier-3 IPRoyal residential is required:** ~$2.10/week (per 01-05 estimate, IPRoyal Tier-3 KZ residential).
- **Phase 7 prod IP-geo (D-07):** the EU Hetzner baseline likely WORSE than KZ-laptop — GroupIB is a Russian-market vendor likely whitelisting local TLD/IP-geo combinations. Hetzner-EU Phase 7 may need IPRoyal-KZ proxy as a hard requirement, not optional.

**Patchright remains the engine candidate for Phase 3** (vs vanilla Playwright per D-01); we are escalating up the Patchright config space (proxy / Camoufox / warmup), not abandoning Patchright.

### Risks / open questions

- We did NOT observe a real product page; **Phase 3 parser implementation is blocked on 01-08** finding a path past the gate before we can confirm the data-extraction contract (`__NEXT_DATA__` shape, JSON-LD presence, schema.org markup).
- The GroupIB vendor finding may push the project into **Tier 4 / managed unblocker (ZenRows / Bright Data Web Unlocker)** territory if 01-08 also fails — D-02 timebox protection then triggers project re-scoping per CONTEXT.md.

See `sample-payloads/goldapple-network-trace.md` for the full investigation, all 5 implications-for-01-08, and re-run instructions.

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
