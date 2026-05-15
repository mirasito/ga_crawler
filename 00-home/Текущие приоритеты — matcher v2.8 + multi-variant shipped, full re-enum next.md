---
tags: [priorities, current]
date: 2026-05-16
---

# Текущие приоритеты

## Где мы (после сессии 2026-05-16)
- **Matcher v2.8** в проде: volume-tolerant + Russian product-type bucket veto + variant-marker veto. 2780 матчей на run 19, GT recall 67%, FP rate 1.2%.
- **Brand-pages discovery** в проде через pyproject toggle `discovery_mode = "brand_pages"`. 22/30 viled-брендов резолвятся.
- **Multi-variant capture** через `product-card/base/v3` API — задеплоено в commit `3df6aba`. Bobbi Brown smoke: +47% SKU.
- 7 коммитов запушены в `origin/master` (от `7f396fd` до `3df6aba`).
- Hetzner-cron на следующий понедельник подтянет всё автоматически.

## Дальше (по убыванию impact)

1. **Полный run-19 re-enum с multi-variant** (~30 мин стабильного Camoufox) — даст финальные числа на 316 GT
2. **Тесты на multi-variant** — `fetch_product_variants` / `variant_to_raw_product` (моки cards-list + product-card responses)
3. **Slug-discovery для 8 брендов** (Tom Ford, Kiehl's, Givenchy, Jo Malone, Ex Nihilo, Kenzo, Amouage, Creed, Starskin) через scroll `/brands` letter-pagination или search-redirect
4. **Cards-list rate-limit fix** — Camoufox session rotation per N brands или humanlike mouse events

## Что НЕ работает / known issues
- Cards-list 403 после 3-4 sequential fetch — workaround scroll-based primary
- Kilian-style 500%+ deltas — viled data quality на 100ml SKU, multi-variant capture растворит когда добавятся 7.5ml/50ml цены GA
- 8 брендов unresolved slug

## Связано
- [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]]
- [[Brand-pages discovery через cards-list + product-card API]]
- [[Matcher v2.8 — volume-tolerant + Russian product-type bucket veto]]
- [[cards-list возвращает 1 itemId на семью variant-ов]]
- [[GA cards-list API rate-limit — 403 после 3-4 sequential fetch]]
