---
tags: [decision, observability, kpi, phase-4]
date: 2026-05-05
updated: 2026-05-11
phase: 04-matcher-match-rate-kpi
decision_id: [D-404, D-405]
---

# Match-rate — KPI с первой недели

Процент пересекающихся SKU из числа возможных. Логируется в `runs.stats.match.rate` на каждом запуске с недели 1.

## Формула (frozen 2026-05-11 как D-405 — НЕ менять)

```
match_rate = matches / viled_skus_with_brand_in_goldapple_brands × 100%
```

Денормализованно в SQL: `ROUND(numerator * 100.0 / denominator, 2)` — REAL с 2 знаками.

Знаменатель — viled-SKUs, у которых бренд **присутствует** на goldapple, **отфильтрованные symmetrically с numerator** (D-404):
```sql
denominator = COUNT(*) FROM snapshots v
  WHERE v.retailer='viled' AND v.run_id=:run_id
    AND v.multipack_flag = 0
    AND v.volume_norm IS NOT NULL
    AND v.stock_state != 'DELISTED'
    AND v.brand_norm IN (
      SELECT DISTINCT g.brand_norm FROM snapshots g
      WHERE g.retailer='goldapple' AND g.run_id=:run_id
    )
```

Symmetric с numerator-фильтром — нельзя «улучшить» rate, манипулируя только знаменателем. Если бренда нет на goldapple — это не "no match", это "out of scope" и SKU не входит в denominator.

## Защита от silent drift формулы (D-405)

Frozen via **two-layer regression canary** в Phase 4:
1. **Plan 04-03 Test 14 `test_match_rate_formula_canary`** — source-locks SQL substring через `inspect.getsource`: должно содержать `ROUND(` и `*100.0/v.current_price`. Plus numerical fixture: 6 matches / 5 denominator → 60.0 (точное значение pinned).
2. **Plan 04-04 Test 10 `test_kpi_formula_end_to_end`** — reproduces через orchestrator full-stack.

Изменение формулы (e.g. switch denominator на total viled) **проваливает оба теста**; deliberate change требует обновления fixture с явной motivation.

## Зачем именно с недели 1

1. **Канарейка тихих сбоев** — если match-rate упал на 30% относительно прошлой недели, что-то сломалось: парсер, нормализация, alias-таблица, или сам сайт
2. **Базовая линия для триггера v2 fuzzy** — без 4-недельной истории невозможно понять "match-rate стабильно низкий"
3. **Backfill невозможен** — KPI считается из снапшотов; забыли в неделю 1 = потеряли первый замер навсегда

## Зачем именно с недели 1

1. **Канарейка тихих сбоев** — если match-rate упал на 30% относительно прошлой недели, что-то сломалось: парсер, нормализация, alias-таблица, или сам сайт
2. **Базовая линия для триггера v2 fuzzy** — без 4-недельной истории невозможно понять "match-rate стабильно низкий"
3. **Backfill невозможен** — KPI считается из снапшотов; забыли в неделю 1 = потеряли первый замер навсегда

## Где видно

- `runs.stats.match.rate` (REAL, persisted via atomic patch_stats) + плюс numerator/denominator для прозрачности расчёта
- В text-summary каждого Telegram-отчёта (Phase 6)
- В заголовке Excel-листа `Summary` (Phase 5)

## Связанные

- [[Matches table — денормализованная, N→1 keep-all]] — symmetric filter применяется к обоим
- [[Sanity-gate P — третий экземпляр паттерна auto-suggest 0.7×median]] — gate на match_count работает поверх match-rate
- [[Strict-key матчинг вместо fuzzy в v1]]
- [[Brand-alias YAML — это v1 deliverable, не v2]]
- [[Run-level sanity-gate перед доставкой]]
- [[Match-rate резко упал — проверь brand-alias таблицу]]
