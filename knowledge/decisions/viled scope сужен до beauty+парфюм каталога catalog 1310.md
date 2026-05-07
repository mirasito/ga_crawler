---
tags: [decision, scope, viled, ga_crawler, phase-2, crawl-01, beauty, parfumery, catalog-narrowing]
date: 2026-05-07
project: ga_crawler
phase: 2-project-skeleton-viled-crawl-storage
source_context: "[[.planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT|02-CONTEXT.md]] D-223..D-227"
---

# viled scope сужен до beauty+парфюм каталога catalog 1310

> Decision date: 2026-05-07 (mid-flight scope clarification от оператора в `/gsd-discuss-phase 2`)
> Cascades to: D-201 (sanity-gate N), D-223..D-227 (enumeration), REQUIREMENTS.md CRAWL-01, PROJECT.md v1 active

## Bottom line

**viled crawl ограничен 2 catalog endpoints — `/men/catalog/1310` и `/women/catalog/1310` — это косметика+парфюмерия. Полный luxury каталог viled (одежда, обувь, сумки, аксессуары) НЕ парсится.** Sitemap-based enumeration (исходный план) НЕ применяется потому что sitemap содержит весь luxury-микс без category metadata для фильтрации.

- **Scope source:** operator clarification в чате 2026-05-07
- **Originating phase:** 2 (Project Skeleton + viled Crawl + Storage)
- **Affected requirement:** CRAWL-01

## Почему это правильное решение

**Commercial relevance.** Goldapple.kz — это beauty/parfumery retailer. Сравнение цен между viled-сумкой Saint Laurent и goldapple бессмысленно — goldapple не продаёт сумки. Phase 4 matcher работает на strict-key `(brand_norm, name_norm, volume_norm)` — у одежды нет volume, у сумок нет parfumery-специфичного объёма. Beauty-only narrowing aligns viled crawl с downstream-консумерами.

**Bandwidth + ops.** Полный sitemap viled — 42,294 product URLs (per plan 01-07). Beauty+парфюм sub-catalog — ожидаемо ~100-600 SKUs. **70x reduction в URL pool** → меньше bandwidth, меньше нагрузки на viled.kz, быстрее weekly run, проще Phase 7 monitoring.

**Phase 4 matcher signal.** Чем меньше irrelevant rows в snapshots (одежда/сумки никогда не сматчатся с goldapple), тем чище match-rate KPI. Sanity threshold P для match-count (MATCH-04) можно поставить более строго.

## Что меняется в архитектуре

### Enumeration (D-223, D-224)

**БЫЛО (исходный план):** sitemap-only — 9 sub-sitemaps → 42,294 product URLs at `/item/<numeric_id>`. Phase 1 plan 01-07 эмпирически подтвердил 15/15 success на random `/item/{id}` URLs.

**СТАЛО:** catalog-page enumeration по 2 endpoints:
1. `https://viled.kz/men/catalog/1310`
2. `https://viled.kz/women/catalog/1310`

**Mechanism (TBD — Wave 0 probe):**
1. **`__NEXT_DATA__` on category page** (most likely) — viled built на Next.js, category page вероятно embed'ит `pageProps.products[]` + `totalCount` + `pageSize`. curl_cffi fetches first page, enumerates `?page=2..N`.
2. **HTML pagination** fallback если `__NEXT_DATA__` не emit'ит products.
3. **Internal Next.js API** `/_next/data/{buildId}/men/catalog/1310.json` как optimization (fragile to deploy buildId rotation).

Все три использовать curl_cffi Tier 0 — Camoufox/Patchright не нужны. viled fully Tier 0 (плану 01-07 baseline).

### Sanity-gate N (D-201 revised)

**БЫЛО:** seed `N=20000` (≈48% от sitemap-42,294) — comfortable margin для full-catalog crawl.

**СТАЛО:** seed **`N=100`** — conservative catastrophic-failure detector для beauty-only sub-catalog. Точное значение скорректируется после first probe-crawl Wave 0 (если actual baseline 200 SKUs — N=100 = 50%; если 500 — N=100 = 20%, тоже разумно).

Auto-suggest mechanism (D-310-style) unchanged — со 5-й недели ops-Telegram эмитит `new N-rec: 0.7 × 4-week-median viled_count = X`.

### Configuration (D-227)

`pyproject.toml [tool.ga_crawler.crawl.viled]`:
```toml
catalog_urls = [
  "https://viled.kz/men/catalog/1310",
  "https://viled.kz/women/catalog/1310",
]
sanity_gate_n = 100
pause_seconds = 2.0
concurrency = 1
```

Operator может добавлять new catalog endpoints через PR (e.g. seasonal beauty sub-categories) без code change. Mirror pattern Phase 3 `smoke_urls`.

## Спайк RECON-02 — что не покрывает

Phase 1 plan 01-07 валидировал `curl_cffi impersonate="chrome"` на 15 random `/item/{id}` URLs:
- Brand-strings из `__NEXT_DATA__` показывают full luxury-микс — Yuzefi (сумки), Alice+Olivia (юбки), Christian Louboutin (туфли), Saint Laurent (украшения, очки), Lorena Antoniazzi (рубашки).
- НИ ОДИН URL не из catalog/1310.

Spike validated:
- ✅ curl_cffi feasibility (15/15 HTTP 200 at 2s pause)
- ✅ `__NEXT_DATA__` extractability (15/15 parsed)
- ✅ ToS / robots.txt compliance (no Crawl-delay, no anti-scraping)

Spike NOT validated:
- ❌ catalog/1310 endpoint structure (URL pool size, pagination shape)
- ❌ category-specific `__NEXT_DATA__` fields (`pageProps.products[]` vs `pageProps.item`)
- ❌ beauty-specific brand list (homepage extraction shows luxury fashion, not beauty)

**Wave 0 Phase 2 probe-crawl необходим** — extract actual catalog/1310 URL pool, verify enumeration mechanism, populate `config/brand-aliases.yaml` seed с реальных beauty brands (НЕ luxury fashion brands из homepage extract).

## Применимость к будущим фазам

- **Phase 4 matcher**: brand_norm/name_norm/volume_norm strict-key — теперь работает только с beauty SKUs. Match-rate KPI чище.
- **Phase 5 reporter**: Excel "Per-SKU deltas" sheet — теперь ровно про beauty/parfumery, понятно для viled commercial team.
- **Phase 7 ops**: monitoring metrics (`viled_count`) — теперь stable baseline ~100-600, не tens-of-thousands. Easier sanity-gate tuning.

Если в v2 потребуется expand до других category IDs (e.g. дополнительные beauty sub-catalogs или men's grooming) — добавить URL в `pyproject.toml [tool.ga_crawler.crawl.viled].catalog_urls`. Никакого code change. Если v2 потребует full luxury catalog (одежда matching против другого retailer) — это отдельный Phase: scope expand в new retailer-config или fork project.

## Эмпирическая работа (Wave 0 Phase 2 must-do)

1. `curl_cffi.requests.get("https://viled.kz/men/catalog/1310", impersonate="chrome")` → grep `<script id="__NEXT_DATA__">` for product list field path
2. Determine pagination semantic: `pageProps.totalCount` / `pageProps.pageSize` / `pageProps.currentPage` (or HTML `<a class="pagination">` если `__NEXT_DATA__` не emit'ит products)
3. Fetch 5 pages → verify aggregate URL count
4. Extract brand strings из `pageProps.products[].brand` → seed candidates для `config/brand-aliases.yaml`
5. Update `02-CONTEXT.md` D-201 seed N if actual baseline differs from estimate

## Connections

- [[Парсим viled целиком, goldapple только по пересекающимся брендам]] — superseded в части viled-целиком; goldapple part valid (still by brand intersection)
- [[Brand-intersect через longest-prefix-in-whitelist, не exact-match]] — Phase 3 D-305 (mechanism для goldapple side); valid после scope narrowing
- [[Strict-key матчинг вместо fuzzy в v1]] — design align: strict-key only meaningful с beauty SKUs (volume invariant)
- [[2026-05-07 — Phase 3 audit-stack закрыт + Phase 2 контекст с scope-narrowing]] — session где это решилось
- [[.planning/REQUIREMENTS|REQUIREMENTS.md]] CRAWL-01 — должно быть amended at next phase transition
- [[.planning/PROJECT|PROJECT.md]] v1 active list — должно быть amended соответственно
