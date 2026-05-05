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

_TBD — N/10 successful curl_cffi fetches, JSON-LD presence, timing._

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
