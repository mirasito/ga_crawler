---
tags: [pattern, normalization, matching]
date: 2026-05-05
---

# Volume как value-object с multipack-флагом

Объём не строка, а структура: `(amount: Decimal, unit: str, multipack: bool)`. Это нужно потому, что `30 мл` ≠ `3 шт x 50 мл`, а string-сравнение это не различает.

## Структура

```python
@dataclass(frozen=True)
class Volume:
    amount: Decimal       # 30, 50, 1.0
    unit: str             # "ml", "g", "oz"
    multipack: bool       # True если "3 шт x 50мл"
    pack_count: int = 1   # 3 для multipack
    
    def normalized_key(self) -> str:
        return f"{self.amount}_{self.unit}_{self.pack_count}"
```

## Что парсер должен ловить

```
"30 мл"        → Volume(30, "ml", False, 1)
"30мл"         → Volume(30, "ml", False, 1)
"30ml"         → Volume(30, "ml", False, 1)
"1.0 fl oz"    → Volume(1.0, "oz", False, 1)
"3 шт x 50мл"  → Volume(50, "ml", True, 3)
"Set of 3 × 50ml" → Volume(50, "ml", True, 3)
```

## Multipack в matchingе v1

В v1 multipack = True **исключается** из price-per-unit-сравнения и помечается флагом. Сравнивать `1×30мл` с `3×50мл` бессмысленно — это разные SKU и часто разная цена за мл.

В Excel-отчёте на отдельном листе `Multipack flagged` (или просто отдельный фильтр).

## Регулярка

Кaскад: пробуем `(\d+(?:\.\d+)?)\s*(мл|ml|г|g|oz)` → если префиксом `\d+\s*(шт|×|x)\s*` — это multipack.

## Связанные

- [[Strict-key матчинг вместо fuzzy в v1]]
- [[Brand-alias YAML — это v1 deliverable, не v2]]
- [[Объёмы не сопоставляются — проверь multipack detection]]
