---
tags: [decision, goldapple, parser, was_price, discount]
date: 2026-05-16
---

# GA `was_price` MSRP fallback через `price.regular`

## Что

GA parser (`card_to_raw_product` + `variant_to_raw_product` в `goldapple_brand.py`) теперь fallback на `price.regular` когда `price.old` отсутствует, при условии `regular > actual`.

```python
was = _coerce_int_price(price_node.get("old"))
if was is None:
    regular = _coerce_int_price(price_node.get("regular"))
    if regular is not None and regular > current:
        was = regular
if was is not None and was == current:
    was = None
```

## Зачем

Operator screenshot 2026-05-16 показал: `goldapple.kz/19000247144-good-girl-gone-bad` — UI отображает зачёркнутую 315 900 ₸ → 284 310 ₸ (current). Наш snapshot имел `was_price=NULL`.

Расследование: `cards-list` API возвращает `price.old` ТОЛЬКО для items в active promo. Для некоторых SKU discount communicated через `price.regular > price.actual` без `price.old`:

```json
{
  "price": {
    "regular": {"amount": 315900},   // MSRP visible как struck-through
    "actual":  {"amount": 284310}    // current
    // "old" поле absent
  }
}
```

Pre-fix parser смотрел только `price.old` → NULL → `was_price=NULL`. Пользователь видит зачёркнутую цену на сайте, но в Excel промо-столбец пустой.

## После fix

Snapshot для 19000247144 Kilian Good Girl Gone Bad 100ml:
```
current_price=284310, was_price=315900
```

Promo count GA на run-21 wytył 1459 → **2583** (+77%) — большой класс «implicit discounts» теперь captured.

## Когда price.regular == price.actual

Нет акции — `was = regular = actual`. Финальная проверка `if was == current: was = None` обнуляет → bare current_price. Correct.

## Когда price.old и price.regular оба присутствуют

`price.old` имеет приоритет (выше в коде). Это explicit GA-emitted strikethrough — авторитетный. `price.regular` fallback срабатывает только если `old` отсутствует.

## Применено в обоих парсерах

- `card_to_raw_product` (cards-list path — основной enumeration)
- `variant_to_raw_product` (product-card/base/v3 path — multi-variant top-up)

3 unit tests pinned:
- `test_regular_used_when_old_missing` (Kilian case)
- `test_regular_ignored_when_equal_to_actual` (no-discount sanity)
- `test_explicit_old_still_preferred_when_present` (old wins if both)

## Связано

- [[Brand-pages discovery через cards-list + product-card API]] — где живёт парсер
- [[was_price NULL это feature а не bug — GA cards-list omits price.old без акции]] — предыдущая декларация что NULL это design; данный коммит уточняет: дизайн справедлив только когда regular == actual; при regular > actual fallback нужен
