---
tags: [decision, discovery, anti-bot, enumeration]
date: 2026-05-16
---

# Brand-pages discovery через cards-list + product-card API

## Решение
goldapple-discovery переезжает с sitemap-парсинга на **brand-page SPA + cards-list XHR capture + product-card variant top-up**. Pyproject toggle `[tool.ga_crawler.crawl.goldapple] discovery_mode = "brand_pages"` (default since c81974c).

## Контекст
- Старый sitemap-парсер давал 89–207 GA SKU за run (≈0.1% каталога).
- viled держит ~6000 SKU; пересечение даже на лучших брендах теряло 95%+.
- На `goldapple.kz/brands/{slug}` SPA рендерит N кардов с lazy-load через `/front/api/catalog/cards-list`.

## Механика
1. `enumerate_brand_via_api(fetcher, slug)`:
   - GoTo `/brands/{slug}`, ждём 5s
   - Извлекаем `categoryId` из `og:image` meta (паттерн `pcdn.goldapple.ru/p/c/{id}/`)
   - Цикл POST `/front/api/catalog/cards-list` через `page.evaluate('fetch(...)')` с pageSize=20, pageNumber=1..N
2. Для каждой карточки с `attributes.units.count > 1` ИЛИ `attributes.colors.count > 1` — follow-up `/front/api/catalog/product-card/base/v3?itemId=X` → массив `variants[]` со своими itemId/units/colors/price.

## Почему не curl_cffi
Прямой POST на cards-list даёт 403 (anti-bot по TLS/cookies). `page.evaluate(fetch)` внутри Camoufox-страницы наследует cookies+fingerprint warmup-сессии, мимикрирует SPA-овский fetch.

## Slug-mapping
Дефолтное правило: `slug = kebab(brand_norm)`. Overrides в `data/ga_brand_slugs.yaml`. Подтверждены empirically через PDP-breadcrumb probe (`scripts/extract_brand_slugs_from_pdps.py`):
- `kiehls → kiehl-s`
- `armani_beauty → armani` (не giorgio-armani)
- `givenchy-beauty → givenchy`
- `frederic_malle → frederic-malle`
- `saint_laurent → yves-saint-laurent`

## Что NOT работает
- Прямой curl_cffi на cards-list — 403 anti-bot
- Sequential page.evaluate fetch >3-4 calls без пауз → 403, см. [[GA cards-list API rate-limit — 403 после 3-4 sequential fetch]]
- pageSize > 20 игнорируется сервером
