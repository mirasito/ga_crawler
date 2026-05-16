---
tags: [debugging, parser, goldapple, pricing-semantics]
date: 2026-05-16
---

# `was_price` NULL — feature, не bug. GA `cards-list` опускает `price.old` без акции

## Симптом

Operator: «Почему в `goldapple.kz/19000402298-electric-cherry-eau-de-parfum` нет старой цены вообще?»

Run-19 статистика:
- GA снапшоты с `was_price IS NOT NULL`: **1 594** (43%)
- GA снапшоты с `was_price IS NULL`: **2 081** (57%)
- viled аналогично: 2 919 (48%) / 3 100 (52%)

## Не bug — design

`/front/api/catalog/cards-list` (и `/front/api/catalog/product-card/base/v3`) выдают JSON следующего вида:

**SKU без активной акции:**
```json
{
  "price": {
    "regular": {"amount": 309555, "currency": "KZT"},
    "actual":  {"amount": 309555, "currency": "KZT"}
    // "old" поле ОТСУТСТВУЕТ — нет зачёркнутой цены на странице
  }
}
```

**SKU на акции:**
```json
{
  "price": {
    "regular":  {"amount": 30500, "currency": "KZT"},
    "actual":   {"amount": 20130, "currency": "KZT"},  // discounted
    "old":      {"amount": 30500, "currency": "KZT"},  // = regular
    "discount": {"amount": 10370, "currency": "KZT"}
  }
}
```

Parser в `card_to_raw_product` и `variant_to_raw_product`:
```python
was = _coerce_int_price(price_node.get("old"))
if was is not None and was == current:
    was = None   # «old==actual» = no real discount
```

Это **отражает то что пользователь видит на сайте**: зачёркнутая цена есть → was_price есть. Зачёркнутой нет → was_price NULL.

## Что если хочется «всегда показывать MSRP»

Можно сделать fallback:
```python
was = _coerce_int_price(price_node.get("old"))
if was is None:
    # Fallback to regular (MSRP) when no active discount
    was = _coerce_int_price(price_node.get("regular"))
if was is not None and was == current:
    was = None
```

**Trade-off:** Excel-колонка `was_price` перестанет различать «акция есть» от «акции нет» — оба покажут MSRP-цену. Промо-аналитика в Excel будет требовать дополнительный signal (например `discount.amount > 0`).

**Сейчас не делаем** — defer до явного product call. Текущий semantic ближе к «what user sees on the page» и proxy-ит discount presence implicitly.

## Если operator всё-таки жалуется

Скажи: «У этого SKU прямо сейчас нет акции на goldapple.kz — поэтому `was` NULL. Если хочешь MSRP-fallback (показывать `regular` как `was` всегда) — это product decision, нужно решить как тогда отличать акционные SKU в Excel.»

## Связано

- [[Bucket veto stem-coverage gap — палетка тени отсутствовали]] — другой fix из той же сессии
- [[Brand-pages discovery через cards-list + product-card API]]
