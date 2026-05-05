---
tags: [debugging, matching, alias]
date: 2026-05-05
---

# Match-rate резко упал — проверь brand-alias таблицу

## Симптом

- На прошлой неделе match-rate был, скажем, 65%, на этой 30%
- `viled_count` и `goldapple_count` примерно те же
- Sanity-gate `match_count > P` мог сработать

## Диагностика

```sql
-- Бренды viled, для которых были matches на прошлой неделе, но не на этой
SELECT brand FROM matches WHERE run_id = <prev>
EXCEPT
SELECT brand FROM matches WHERE run_id = <current>;
```

## Возможные причины

1. **Goldapple переименовал бренд в Cyrillic-вариант, которого нет в alias-таблице**
   - Открой [[Brand-alias YAML — это v1 deliverable, не v2]]
   - Добавь алиас, перематчи (matcher идемпотентен, см. `MATCH-04`)
2. **Парсер потерял поле `brand`** — посмотри `null_rate(brand)` в snapshots
3. **Goldapple добавил/убрал бренды на сайте** — check `runs.goldapple_brands_seen`
4. **Volume-формат изменился** — см. [[Объёмы не сопоставляются — проверь multipack detection]]

## Превентивно

Лог "бренды на goldapple, не найденные в alias-таблице" (`NORM-06`) пишется каждый запуск. Это weekly review queue — пройдись глазами, дополняй.

## Связанные

- [[Match-rate — KPI с первой недели]]
- [[Brand-alias YAML — это v1 deliverable, не v2]]
- [[Strict-key матчинг вместо fuzzy в v1]]
