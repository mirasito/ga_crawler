---
tags: [atlas, database, sqlite, schema]
date: 2026-05-05
---

# БД — append-only snapshots с run_id

SQLite в WAL-режиме. Никаких in-place обновлений — каждая неделя пишет полный новый snapshot, помеченный `run_id`. Это [[Append-only snapshots без in-place update]] на практике.

## Таблицы

### `runs`
Метаданные одного запуска. Создаётся в начале, **обязательно** закрывается в конце во всех ветках.

| поле | назначение |
|------|------------|
| `run_id` PK | unique per week |
| `started_at`, `finished_at` | timestamps |
| `status` | `success` / `partial` / `failed` |
| `viled_count`, `goldapple_count`, `match_count`, `match_rate` | sanity + KPI |
| `failure_reason` | для алертов |

### `snapshots`
Immutable history. Уникальный ключ `(run_id, retailer, sku_id)`.

Поля: `current_price`, `was_price`, `currency`, `stock_state` (enum, см. [[Stock state — enum в схеме, bool в отчёте]]), `url`, `name`, `brand`, `volume_raw`, `brand_norm`, `name_norm`, `volume_norm`, `multipack_flag`, `scraped_at`.

### `matches`
Производная. Один JOIN на `run_id`. Поля: `viled_sku`, `goldapple_sku`, `price_delta`, `price_delta_pct`.

### View `v_current_snapshots`
SQL-вьюха с последним `run_id` per retailer. Заменяет "current products" таблицу.

## Backup

Nightly — минимум 4 последних бэкапа. Файл `app.db` + WAL копируются в `backups/YYYY-MM-DD.db`.

## Миграция на Postgres

В v2, если: появится дашборд, multi-writer, или БД > 50 GB. Сейчас — overkill.

См. также: [[Хранить полную историю снапшотов, не только текущий срез]]
