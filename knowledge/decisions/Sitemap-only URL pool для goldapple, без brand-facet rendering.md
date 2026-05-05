---
tags: [decision, phase-3, sitemap, url-pool, asymmetric-pipeline]
date: 2026-05-06
phase: 3
decisions: [D-301, D-302]
---

# Sitemap-only URL pool для goldapple, без brand-facet rendering

Phase 3 строит goldapple URL-пул **только из sitemap.xml**: curl_cffi (Tier 0) фетчит sitemap-index → парсит 3 sub-sitemap → строит `slug → [URLs]` map → пересекает с матч-брендами через slug-эвристику → передаёт matched URLs в Camoufox-fetch loop. **Никакого brand-facet rendering** (`/brand/{slug}` страницы) и **никакого hybrid sanity-cross-check** на v1. Полный re-crawl каждую неделю.

## Asymmetric pipeline

```
Tier 0 (curl_cffi)  : sitemap-index → 3 sub-sitemaps → slug→URLs map
Tier 2 (Camoufox)   : matched URLs → microdata extraction
```

Sitemap **plain-deliverable** через curl_cffi (валидировано спайк 01-05): 1,461 brand slugs / 100,779 product URLs / no anti-bot на sitemap layer. Только product PDPs идут через Camoufox.

## Почему **не** brand-facet rendering

Альтернатива — Camoufox рендерит `/brand/{slug}` listing pages, парсит карточки, следует на PDP. Отвергнуто:

- **+50 facet-fetches через Camoufox** (по одному на матч-бренд) = +5 минут к runs
- **Риск gate-shielded facet pages** — спайк не проверял facet routes; могут быть жёстче чем product PDPs
- **Утилита** = ловить within-week SKUs до обновления sitemap (≤7 дней лаг). Для weekly weekly batch с целью pricing intelligence — низкая.

## Почему **не** hybrid sanity-cross-check

Альтернатива — sitemap = primary, на 1-й facet-странице каждого бренда cross-check через Camoufox/curl_cffi-probe, флаг расхождений в ops. Отвергнуто:

- +50 facet-probes (одна страница на бренд), ~2-3 мин к runs
- **На v1 утилита ниже стоимости** — sitemap rotation для goldapple не валидирован как «слома-паттерн»
- Возможный пересмотр в v2 если появятся реальные кейсы потери покрытия

## Почему **не** incremental через `<lastmod>`

Sitemap `<lastmod>` отслеживает URL-события (URL добавлен / удалён), **не** content-change. Цены меняются БЕЗ обновления `<lastmod>` → incremental режим оставит **stale prices** в weekly snapshot. Pricing intelligence не терпит этого. Полный re-crawl каждую неделю — invariant v1.

## Spike-validation

Спайк 01-05: sitemap-index 200 OK, 1.2 KB, no JS-challenge. 112,317 total URLs (100,779 product-numeric + brand slugs + категории). Sitemap-only стратегия даёт ~3,450 fetches/week → ~$0/week proxy → ~4.4ч sequential.

## Связанные

- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — но sitemap живой
- [[Тиры anti-bot эскалации]] — pattern parent (asymmetric tiers)
- [[Slug-эвристика для viled→goldapple, не explicit YAML]] — что фильтрует sitemap-pool
- [[Хранить полную историю снапшотов, не только текущий срез]] — почему full re-crawl приемлем
- [[Goldapple — Tier 2 Camoufox без proxy, 99 из 100]] — Camoufox stack для product render
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` §URL-pool — D-301, D-302
- `.planning/spikes/01-goldapple/sample-payloads/` — empirical sitemap evidence
