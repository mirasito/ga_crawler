---
tags: [debugging, parsing, pricing]
date: 2026-05-05
---

# Wrong price field — Gold Card vs strikethrough vs from

## Симптом

- На каждом продукте `price_delta_pct` постоянно одного знака (например, всегда -30%)
- Бимодальное распределение цен (две явные кучки)
- "0% дискаунт" на каждом goldapple-продукте — подозрительно
- Sanity-check `100 ≤ price ≤ 1_000_000 ₸` периодически валит

## Возможные причины

1. **Парсер взял Gold Card цену** вместо публичной → видим скидку, которой не должно быть. См. [[Фиксируем только публичную цену, без Gold Card]]
2. **Парсер взял strikethrough (`was_price`) как `current_price`**
3. **Парсер взял "from X tg"** для variant-products (когда у товара есть размеры)

## Диагностика

```python
# проверь сразу несколько подозрительных products вручную
# открыти страницы в браузере и сравни визуальные цены с DB

SELECT url, current_price, was_price, brand, name
FROM snapshots
WHERE run_id = <current> AND retailer = 'goldapple'
ORDER BY price_delta_pct DESC LIMIT 20;
```

## Решение

В парсере (Phase 2):

1. **JSON-LD `Product.offers.price` должен быть приоритетом** — см. [[JSON-LD первый, CSS резервный в парсерах]]
2. Если CSS-fallback — отвергать классы:
   ```python
   deny = re.compile(r"(old|was|crossed|club|gold|member|loyalty|from|striked)", re.I)
   ```
3. **Sanity-check** — `100 ≤ price ≤ 1_000_000 ₸`. Вне диапазона → log + skip product

## Связанные

- [[JSON-LD первый, CSS резервный в парсерах]]
- [[Фиксируем только публичную цену, без Gold Card]]
- [[Hard-fail invariants на обязательных полях]]
