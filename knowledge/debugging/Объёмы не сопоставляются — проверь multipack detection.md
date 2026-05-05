---
tags: [debugging, matching, volume]
date: 2026-05-05
---

# Объёмы не сопоставляются — проверь multipack detection

## Симптом

- Match-rate ниже expected
- В логах "unmatched volume" растёт
- В отдельных случаях matched, но `price_delta_pct` ~= 200% (3x larger)

## Возможные причины

1. **Multipack не детектится**
   - viled пишет `1 шт x 30 мл`, goldapple `30 мл` → должно матчиться, но не как multipack у viled
   - Или наоборот — `3 × 50 мл` распарсилось как `3 мл` 😱
2. **Юнит-расхождение** — `30 г` vs `30 мл` — это разные продукты (твёрдое vs жидкое)
3. **Capitalization / spacing** — `30 МЛ` vs `30мл`

## Диагностика

```python
# тест-кейсы, которые должны проходить
assert parse_volume("30 мл") == Volume(Decimal("30"), "ml", False, 1)
assert parse_volume("3 шт x 50мл") == Volume(Decimal("50"), "ml", True, 3)
assert parse_volume("Set of 3 × 50ml") == Volume(Decimal("50"), "ml", True, 3)
```

Прогони suite — что не проходит, то и сломалось.

## Решение

Расширить regexp в `Volume.parse()`. Добавить failing samples в test-suite. См. [[Volume как value-object с multipack-флагом]].

## Превентивно

Multipack-detection regexp пишется первым в Phase 2 с **полным test-suite реальных строк** с обоих сайтов. Любой новый паттерн — кейс в тестах.

## Связанные

- [[Volume как value-object с multipack-флагом]]
- [[Match-rate резко упал — проверь brand-alias таблицу]]
