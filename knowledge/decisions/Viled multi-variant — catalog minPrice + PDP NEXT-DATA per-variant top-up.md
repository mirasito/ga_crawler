---
tags: [decision, viled, multi-variant, catalog-api, pdp-fetch]
date: 2026-05-16
---

# Viled multi-variant — catalog `minPrice` + PDP `__NEXT_DATA__` per-variant top-up

## Что

Для viled SKU с ≥2 размерами (~12.5% beauty inventory) делаем дополнительный PDP-fetch чтобы извлечь per-variant цены. Один viled SKU → N snapshot rows с compound `sku_id = "{viled_id}-{itemPriceId}"`.

## Зачем

Viled catalog API `https://viled.kz/api/viled-catalog/v2/items/content?gender=...&catalogId=...&page=N` возвращает один item per SKU независимо от количества размеров. Поля:
- `minPrice` — цена МИНИМАЛЬНОГО варианта (часто 7,5 мл)
- `attributes[]` — список всех Размер-атрибутов вперемешку с не-размерами
- Per-variant pricing **НЕ возвращается**

Старый код брал `attributes[0]` как volume + minPrice как current_price → emit one row labeled "100 мл @ 41 400 ₸" когда реально:
- 100 мл = 328 600 ₸
- 50 мл = 219 100 ₸
- 7,5 мл = 41 400 ₸

Это создавало 586% FP-deltas против goldapple, где volume_norm совпадал по строке но реальный товар был не тот.

## Где per-variant pricing

`https://viled.kz/item/{sku_id}` (PDP HTML) embeds `__NEXT_DATA__` blob:

```json
{
  "props": {
    "pageProps": {
      "item": {
        "id": 335978,
        "itemPriceIds": [802455, 280756, 708150],
        "selectAttributes": [{
          "id": 9066,
          "name": "Размер",     // ← Cyrillic in __NEXT_DATA__
          "values": [
            {"value": "100 мл", "itemPriceId": 708150},
            {"value": "50 мл",  "itemPriceId": 280756},
            {"value": "7,5 мл", "itemPriceId": 802455}
          ]
        }]
      },
      "attributes": [
        {"id": 802455, "price": 41400,  "realPrice": 41400,  ...},
        {"id": 280756, "price": 219100, "realPrice": 219100, ...},
        {"id": 708150, "price": 328600, "realPrice": 328600, ...}
      ]
    }
  }
}
```

Note: `/api/viled-catalog/v2/items/{id}` тоже возвращает `selectAttributes`, но с `"name": "size"` (English) вместо Russian "Размер". Парсер принимает оба варианта.

## Implementation

`bin/viled_fast_crawl.py`:
1. `_all_size_attributes(attributes)` — list all Размер values per catalog item
2. If `len(sizes) > 1`: `_fetch_variant_prices(sku_id)` → GET PDP HTML → regex extract `<script id="__NEXT_DATA__">{...}</script>` → JSON parse → return list of {item_price_id, size, price, real_price}
3. `_catalog_item_to_normalized` returns `list[dict]` — N records for multi-variant, 1 record for single-variant
4. Compound `sku_id = "{viled_id}-{itemPriceId}"` ensures UNIQUE constraint hold across runs

PDP-fetch pacing 600ms per multi-variant SKU. Beauty inventory ~5 600 single + ~720 multi-variant → +7 min wall-clock на полный crawl (≈ 19 min vs 13 min без top-up).

## Trade-offs

**+ Pros:**
- Accurate per-variant prices → matcher строит правильные volume-to-volume сравнения
- `was_price` per variant — discounts on specific sizes captured precisely
- Backwards-compat — single-variant 87.5% SKU оставляем на быстром catalog-only пути

**− Cons:**
- +7 min wall-clock на crawl (acceptable)
- Compound `sku_id` ломает naive joins по `viled.id` — но мы используем `sku_id` everywhere, и UNIQUE constraint держится
- Если PDP fetch падает (HTTP 5xx / parse error) — fallback на single-row с `parse_error_flag=True`. Не теряем SKU.

## Не сработало бы

- Альтернатива: фетчить отдельный `item-price-by-id` API endpoint. Probe не нашёл такого; только PDP содержит нужные данные.
- Альтернатива: pure Camoufox per-PDP. Излишне дорого (~3-5 sec/SKU vs 600ms curl_cffi); нет anti-bot на viled — PDP HTML отдаётся без проблем.

## Связано

- [[Brand-pages discovery через cards-list + product-card API]] — analog для goldapple (multi-variant top-up через `product-card/base/v3`)
- [[Matcher v3 — sub-bucketing для perfume concentration и body-part qualifier]] — что делать с volume даже после правильного capture
- [[GA was_price MSRP fallback через price.regular]] — companion fix для GA-side pricing data
