---
tags: [decision, phase-4, matcher, schema, kpi]
date: 2026-05-11
phase: 04-matcher-match-rate-kpi
decision_id: [D-401, D-402, D-403]
---

# Matches table — денормализованная, N→1 keep-all

`matches` table — это **денормализованный** join-result viled ↔ goldapple snapshots для одного `run_id`. Phase 5 reporter работает с ней одной без join-back в `snapshots`.

## Schema (13 колонок)

```sql
CREATE TABLE matches (
  run_id              INTEGER NOT NULL,        -- PK part, FK runs.run_id
  viled_sku           TEXT NOT NULL,           -- PK part, FK snapshots
  goldapple_sku       TEXT NOT NULL,           -- PK part, FK snapshots
  brand_norm          TEXT NOT NULL,           -- денормализовано из snapshots
  name_norm           TEXT NOT NULL,           -- денормализовано
  volume_norm         TEXT NOT NULL,           -- денормализовано (NULL отфильтрован)
  viled_price         INTEGER NOT NULL,        -- KZT
  goldapple_price     INTEGER NOT NULL,        -- KZT
  viled_was_price     INTEGER,                 -- nullable
  goldapple_was_price INTEGER,                 -- nullable
  price_delta         INTEGER NOT NULL,        -- goldapple_price − viled_price (signed)
  price_delta_pct     REAL NOT NULL,           -- ROUND(delta*100.0/viled_price, 2)
  matched_at          TIMESTAMP NOT NULL,
  PRIMARY KEY (run_id, viled_sku, goldapple_sku)
)
```

## Symmetric filters (D-402)

И в numerator (INSERT into matches), и в denominator (match-rate formula) применяется один и тот же фильтр **к обеим сторонам JOIN**:

```sql
WHERE multipack_flag = 0
  AND volume_norm IS NOT NULL
  AND stock_state != 'DELISTED'
```

Asymmetric filter = silent KPI corruption (можно искусственно «улучшить» rate, манипулируя только знаменателем). Symmetric гарантирует честность исторического baseline.

## N→1 keep-all (D-403)

Несколько goldapple SKU с одинаковым `(brand_norm, name_norm, volume_norm)`, совпадающих с одним viled SKU → пишем **все пары**. Composite PK гарантирует уникальность пары. Phase 5 reporter решает как показать дубликаты viled_sku в Excel (dedupe by min-price на этапе рендера если нужно).

## Почему денормализованная

- Phase 5 reporter не делает дополнительные JOIN — все нужные поля уже в matches
- Production-debugging проще: одна таблица содержит full picture одной пары
- Cost: ~3× места на disk vs минимальный schema; для weekly cadence + SQLite — irrelevant
- Никаких update-aномалий: matches **append-only per run_id**; brand_norm и т.д. immutable в snapshots на момент matching

## Что НЕ делаем

- ❌ Минимальная схема `(run_id, viled_sku, goldapple_sku, price_delta, price_delta_pct)` per REQUIREMENTS MATCH-02 — переписана в Phase 5 prep (REQUIREMENTS amendment в plan 04-06)
- ❌ Dedup N→1 по min-price в БД — теряем сигнал о вариантах, Phase 5 reporter решает на рендере
- ❌ Currency normalization — оба ритейлера в KZT
- ❌ Week-over-week price delta column — v2 territory (REPORT-V2-01)

## Связанные

- [[Match-rate — KPI с первой недели]] — denominator формула использует те же symmetric фильтры
- [[Strict-key матчинг вместо fuzzy в v1]] — основа JOIN-ключа
- [[Volume как value-object с multipack-флагом]] — multipack_flag filter
- [[Stock state — enum в схеме, bool в отчёте]] — DELISTED filter
- [[Append-only snapshots с run_id]] — semantic inheritance
- [[.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT|04-CONTEXT.md]] §D-401..D-403
- [[.planning/phases/04-matcher-match-rate-kpi/04-03-PLAN|04-03-PLAN.md]] §INSERT_MATCHES_SQL
