---
tags: [debugging, enumeration, cards-list, multi-variant]
date: 2026-05-16
---

# cards-list возвращает 1 itemId на семью variant-ов

## Симптом
Brand-page enum через `/front/api/catalog/cards-list` для Clinique даёт 220 distinct itemId, но среди них **отсутствуют размерные/оттеночные сиблинги**:
- Dramatically Different Moisturizing Lotion 125ml присутствует (sku 15250700066, 20130 KZT)
- 50ml сиблинг (sku 15250700065 @ 11550 KZT) — отсутствует, хотя `attributes.units.values = ["50", "125"]`
- Almost Lipstick Black Honey присутствует (sku 19000126321), Pink Honey и Nude Honey (другие itemId, та же 1.9g, тот же price) — отсутствуют

## Корень
Cards-list — это PLP-листинг (product list page). Возвращает одну "карточку" на product family. Сиблинги (другие размеры/оттенки) скрыты за size-picker'ом на PDP — каждый со своим itemId.

## Решение
PDP-level API `/front/api/catalog/product-card/base/v3?itemId={master}` возвращает `data.variants[]` — массив всех сиблингов, каждый с:
- `itemId`
- `attributesValue.units` (размер) и `attributesValue.colors` (оттенок)
- `price.actual.amount` / `price.old.amount`
- `url`, `inStock`

Для каждой cards-list карточки с `attributes.units.count > 1` ИЛИ `colors.count > 1` делаем follow-up product-card call. Дедуплицируем по itemId (master itemId уже добавлен от cards-list, новые — это сиблинги).

## Реализация
`fetch_product_variants(page, item_id)` в `enumeration/goldapple_brand.py` (commit `3df6aba`). Pacing 600ms между вызовами достаточно — product-card endpoint толерантнее cards-list к sequential fetch (SPA сам стучит по нему один раз на PDP-загрузку, no rate-limit observed).

## Пруф
Bobbi Brown smoke (run_id=9986):
- cards-list: 60 distinct itemId (хит 403 на странице 4)
- product-card multi-variant top-up: 45 master products → 28 extra variants
- final: 88 raw_products (+47% к cards-list-only)

## Связано
- [[Brand-pages discovery через cards-list + product-card API]]
- [[GA cards-list API rate-limit — 403 после 3-4 sequential fetch]]

## Сорс
matcher-review-2026-05-16. Probe сценарии в `scripts/probe_pdp_variants.py`, `scripts/probe_product_card_api.py`. Captured JSON в `inbox/ga_pdp_card_api/`.
