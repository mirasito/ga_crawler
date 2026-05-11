# Phase 4: Matcher + Match-Rate KPI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 04-matcher-match-rate-kpi
**Areas discussed:** Matches schema, Match-rate denominator, Sanity-gate P (seed + auto-suggest), Idempotency + failed-crawl + CLI shape

---

## Matches table — какие SKU и поведение при N→1

| Option | Description | Selected |
|--------|-------------|----------|
| Денормализованный + N→1 keep-all (Recommended) | WHERE both: multipack=0, stock_state IN (IN_STOCK,UNAVAILABLE), volume_norm NOT NULL. Денормализуем brand/name/volume_norm + цены обоих в строку. При N→1 пишем все пары — reporter решает. Phase 5 не делает join-ы. | ✓ |
| Минимальный (REQ-only) | Схема ровно как в MATCH-02: (run_id, viled_sku, goldapple_sku, price_delta, price_delta_pct). Phase 5 делает join-ы при рендере Excel. | |
| Денормализованный + dedup по min-price | Денормализуем. При N→1 выбираем goldapple SKU с минимальной ценой — одна строка на viled SKU. Чище в Excel, но теряем сигнал о вариантах. | |

**User's choice:** Денормализованный + N→1 keep-all (Recommended)
**Notes:** Сохраняем commercial-signal про множественные goldapple-варианты; Phase 5 reporter решает как показать дубликаты в Excel.

---

## Match-rate denominator (KPI фиксируется надолго)

| Option | Description | Selected |
|--------|-------------|----------|
| Comparable viled SKU в брендах goldapple (Recommended) | denominator = COUNT(viled) WHERE brand_norm IN goldapple_brands AND multipack=0 AND stock!=DELISTED AND volume_norm NOT NULL. Соответствует фильтрам matches — KPI честный. | ✓ |
| Все viled SKU в brands_in_goldapple | denominator = COUNT(viled) WHERE brand_norm IN goldapple_brands. Знаменатель больше, match-rate ниже. Оправдано если multipack/DELISTED — это "работа вперёд". | |
| Все viled SKU (тотал) | denominator = COUNT(viled total). Ниже KPI, но бренды без goldapple-присутствия входят — это видимость ассортиментных разрывов, но размывает метрику. | |

**User's choice:** Comparable viled SKU в брендах goldapple (Recommended)
**Notes:** Symmetric с numerator-фильтром гарантирует честность — нельзя «улучшить» rate, играя только знаменатель.

---

## Sanity-gate P (seed для week 1 + auto-suggest)

| Option | Description | Selected |
|--------|-------------|----------|
| P=20 seed + 0.7×median после 4 runs (Recommended) | Mirror D-201/D-308. Seed P=20 ~30% от консервативного ожидаемого минимума. С 5-й недели ops-Telegram `new P-rec: 0.7×4-week-median`. Operator-PR, не auto-tune. | ✓ |
| P=10 seed (очень консервативный) | P=10 ловит только «normalizer сломался или crawler пустой». Auto-suggest тот же. | |
| P=0 seed (gate дизаблен в week 1) | Первые 4 недели гейт не срабатывает — даём baseline накопиться. После 4 runs auto-suggest предлагает first non-zero P. Риск: при нулевых matches week-1 отчёт всё равно отправится. | |

**User's choice:** P=20 seed + 0.7×median после 4 runs (Recommended)
**Notes:** Третий retailer-domain экземпляр D-201/D-308 паттерна — pattern закрепляется. Operator-PR обязателен (защита от silent KPI drift).

---

## Idempotency + поведение при failed crawl + CLI shape

| Option | Description | Selected |
|--------|-------------|----------|
| DELETE-and-reinsert; skip если любой retailer failed; standalone subcommand (Recommended) | Внутри транзакции DELETE matches WHERE run_id=:N → INSERT заново. Если любой retailer failed — matcher skip. CLI: `python -m ga_crawler matcher-run --run-id N` standalone + main_run integration. | ✓ |
| INSERT OR REPLACE; всегда запускаем, даже при failed | UPSERT по составному PK. При failed crawl всё равно работает на имеющихся snapshots. match_count попадёт в stats в любом случае. | |
| No-op if rows exist; только из main_run | При re-run no-op + warn если matches уже есть. Нет standalone subcommand. Проще, но хуже для recovery после backfill snapshots. | |

**User's choice:** DELETE-and-reinsert; skip если любой retailer failed; standalone subcommand (Recommended)
**Notes:** Standalone CLI mirror Phase 3 `goldapple-smoke`/`goldapple-run` паттерна. Failed-skip защищает auto-suggest history от corruption нулями.

---

## Claude's Discretion

- Stock-state filter точный enum-set (D-402 опирается на `!= 'DELISTED'`, possible tightening после week 1)
- Precision price_delta_pct (SQL `ROUND(price_delta * 100.0 / viled_price, 2)`)
- Per-brand match-rate aggregation в stats (отложено, on-demand в reporter)
- Sync vs async (sync; matcher = single SQL transaction)
- denominator=0 edge case (write match.rate=0.0 + warning; gate trips natural)
- Cron schedule для standalone matcher-run (не нужен — operator-driven recovery only)

## Deferred Ideas

- N→1 dedup по min-price в БД — v2 reporter территория
- match.rate_by_brand JSON в runs.stats — v2 (REPORT-V2-02)
- alembic migration для matches table — v2 при первой column-migration
- Auto-tune P — навсегда отвергнуто
- Fuzzy/rapidfuzz matching — v2 (MATCH-V2-01)
- Per-SKU manual override — v2 (MATCH-V2-02)
- Mid-week matcher run — out-of-scope
- Bulk-replay loop для historical runs — operator-shell, не код
- Week-over-week price delta — v2 (REPORT-V2-01)
- Match-rate degradation alert — v2 (REPORT-V2-04)
- Multi-currency price_delta — N/A для KZT-only
