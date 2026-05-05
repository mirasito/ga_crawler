---
tags: [decision, observability, kpi]
date: 2026-05-05
---

# Match-rate — KPI с первой недели

Процент пересекающихся SKU из числа возможных. Логируется в `runs` таблице на каждом запуске с недели 1.

## Формула

```
match_rate = matches / viled_skus_with_brand_in_goldapple_brands * 100%
```

Знаменатель — viled-SKUs, у которых бренд **присутствует** на goldapple. Если бренда нет на goldapple — это не "no match", это "out of scope".

## Зачем именно с недели 1

1. **Канарейка тихих сбоев** — если match-rate упал на 30% относительно прошлой недели, что-то сломалось: парсер, нормализация, alias-таблица, или сам сайт
2. **Базовая линия для триггера v2 fuzzy** — без 4-недельной истории невозможно понять "match-rate стабильно низкий"
3. **Backfill невозможен** — KPI считается из снапшотов; забыли в неделю 1 = потеряли первый замер навсегда

## Где видно

- `runs.match_rate` (numeric, persisted)
- В text-summary каждого Telegram-отчёта
- В заголовке Excel-листа `Summary`

## Связанные

- [[Strict-key матчинг вместо fuzzy в v1]]
- [[Brand-alias YAML — это v1 deliverable, не v2]]
- [[Run-level sanity-gate перед доставкой]]
- [[Match-rate резко упал — проверь brand-alias таблицу]]
