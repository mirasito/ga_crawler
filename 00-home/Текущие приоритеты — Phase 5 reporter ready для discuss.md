---
tags: [priority, phase-5, reporter, excel, active]
date: 2026-05-11
status: active
---

# Текущие приоритеты — Phase 5 reporter ready для discuss

Phase 4 закрыт сегодня (2026-05-11): matcher + match-rate KPI shipped через 5 волн, MATCH-01..04 done, 465/465 tests passing, KPI formula frozen двухслойным canary. v1 progress = 31/48.

## Прямо сейчас

`/gsd-discuss-phase 5` — Reporter (Excel + Telegram summary). Spec пуст, CONTEXT не gathered. Открытые gray areas (ожидаемые):

1. **Layout листов Excel** — сколько листов (Per-SKU deltas / Brand-level aggregate / Run-meta?), какие колонки, freeze panes
2. **Дельта-форматирование** — color scale (green = goldapple дешевле = good для нас? или красный, т.к. они дешевле = плохо?), data bars vs conditional fill
3. **N→1 дедупликация на уровне рендера** — Plan 04-03 пишет все pairs (D-403 keep-all); reporter решает: показать все варианты, min-price, или both
4. **Per-SKU vs Per-brand агрегация** — REPORT-04 хочет match-rate; нужно ли brand-level breakdown в основном листе или отдельным
5. **Telegram message body** — что в caption, что вложением (вложение — Excel; caption — топ-5 дельт? match.count? match.rate?)
6. **Reporter — независим от delivery** (research decision) — reporter пишет Excel в `reports/run_{run_id}.xlsx`; Phase 6 wraps в Telegram

## Что готово как вход

- `matches` table (13 колонок): brand_norm, name_norm, volume_norm, обе цены, was_prices, price_delta (signed), price_delta_pct (REAL ROUND 2), matched_at
- `runs.stats.match.*` (10 ключей): match.count / .rate / .numerator / .denominator / .brand_overlap_count / .viled_comparable_count / .goldapple_comparable_count / .skipped_reason / .threshold_p / .gate_passed
- `runs.stats.viled.*` + `goldapple.*` — для контекстного блока run-meta

## Не делать

- Не трогать `matches` schema — D-401 frozen с week 1
- Не менять KPI формулу — D-405 source-locked, regression-canary fails если поменять
- Не add async — reporter pure-sync mirror matcher pattern

## Connections

- [[2026-05-11 — Phase 4 executed — matcher + KPI shipped через 5 waves]] — что shipped и почему mat unblocked reporter
- [[Matches table — денормализованная, N→1 keep-all]] — input schema
- [[Match-rate — KPI с первой недели]] — KPI numerator/denominator semantics
- [[Архитектура — модульный монолит на pipe-and-filter]] — reporter = filter после matcher
