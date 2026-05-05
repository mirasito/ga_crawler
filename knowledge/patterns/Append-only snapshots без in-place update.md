---
tags: [pattern, storage, schema]
date: 2026-05-05
---

# Append-only snapshots без in-place update

Каждая запись в `snapshots` immutable. Никаких `UPDATE snapshots SET price = ... WHERE sku_id = ...`. Новый запуск = новый `run_id` = новые строки.

## Почему

- **Идемпотентность** — пайплайн рестартуется для конкретного `run_id` без потери прошлых
- **Историчность бесплатно** — все `WoW`, `MoM` дельты — простой SQL
- **Отладка** — видно, что **именно** парсер увидел в момент `T`, без догадок
- **Recovery** — если что-то ломается, всегда есть прошлый working `run_id`

## "Current view"

Не таблица, а SQL-вьюха:

```sql
CREATE VIEW v_current_snapshots AS
SELECT * FROM snapshots
WHERE run_id = (SELECT MAX(run_id) FROM runs WHERE status = 'success');
```

Если последний запуск failed — вьюха показывает **предыдущий успешный**. Никогда не показывает мусор.

## Identity = ключ, не URL

```
identity_hash = sha256(brand_norm + name_norm + volume_norm)
```

Это паттерн **Slowly Changing Dimension Type 2** из data warehousing. URL может изменяться (slug rename) — identity нет.

## Связанные

- [[БД — append-only snapshots с run_id]]
- [[Хранить полную историю снапшотов, не только текущий срез]]
