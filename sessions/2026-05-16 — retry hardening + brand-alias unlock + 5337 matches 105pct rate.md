---
tags: [session, matcher, anti-bot-hardening, brand-alias, run-19-trilogy]
date: 2026-05-16
---

# Сессия 2026-05-16 (поздний вечер) — retry hardening + brand-alias unlock → 5 337 матчей при rate=105.6%

Continuation of [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]. Operator поставил локальный режим (Hetzner-cron на паузе до confidence) и попросил прогнать re-enum + закрыть три TODO утра. Закрыли — но re-enum #2 вскрыл два новых бага, фикс которых довёл до **самого большого скачка** проекта.

## Хронология трёх прогонов run-19

| Прогон | Goldapple SKU | brand_overlap | matches | rate | Цель прогона |
|---|---:|---:|---:|---:|---|
| v1.5 (утренний) | 2 396 | 40 | 3 831 | 78.71% | Validate multi-variant code path |
| v2 (без aliases) | 2 426 | 40 | 3 409 | 70.04% | Pick up 8 new slug overrides — но brand_norm mismatch и enum-instability бьют в обратную |
| v2.1 (alias UPDATE) | 2 426 | 48 | 3 532 | 69.89% | Применить aliases через SQL UPDATE — fixes mismatch, но enum-loss not addressed |
| v3 (retry hardening) | 3 471 | 48 | 5 260 | 104.08% | Hardening + aliases в нормализатор — recovery zielinski/mac/clarins частично |
| **v3.1 (targeted recovery)** | **3 675** | **48** | **5 337** | **105.6%** | Wider params + recover 3 budget-exhausted brands — финал |

**+3 977 матчей** vs утренний v1.5 (`+103.8%`).

## 6 коммитов в этой continuation-сессии

| Commit | Что |
|---|---|
| `04060d5` | **Critical wiring fix:** `enumerate_brand` → `enumerate_brand_hybrid` в production runner. Без этого multi-variant в проде НЕ срабатывал |
| `6a966f3` | 20 unit-тестов для `fetch_product_variants` + `variant_to_raw_product` |
| `e73ebe7` | 8 brand-slug overrides + probe-v2 + resolver scripts |
| `5f4116a` | docs(vault): первый «evening session» note |
| `209a4ff` | **Retry hardening + 8 brand-aliases:** per-page exponential backoff (12s→24s→48s), skip-page-on-403-instead-of-break-brand, per-brand 403 budget, post-burst cooldown |
| (текущий) | params bumped 6→12 budget / 10s→20s cooldown + new `bin/recover_brands.py` + vault notes |

## Два бага вскрылись в v2 → fixed в v3

### Баг 1: brand_norm mismatch на 8 новых slug overrides

Viled emits `"Carolina Herrera Beauty"`, GA emits `"Carolina Herrera"`. Slug-override маршрутизировал enumeration на правильный `/brands/{slug}` URL, но matcher SQL JOIN видел два разных нормализованных string. 8 новых брендов enumerate-ились, но 0 матчей с виледом.

Fix: 8 alias entries в `config/brand-aliases.yaml`, canonical = viled-side form (suffix preserved) → GA-side normalizes к этому же canonical через alias map. Plus SQL UPDATE на существующих run-19 GA snapshots чтобы apply сейчас не дожидаясь следующего enum.

[[Brand-alias mismatch — viled добавляет -beauty suffix, GA снимает]]

### Баг 2: enumeration instability через API 403

Cards-list API имеет per-session burst limit — после 3-4 sequential XHR возвращает HTTP 403. Старый код:
  1. Retry 1 раз с 12s cooldown
  2. Если ещё 403 — **бросал весь бренд**

zielinski_rozen (badge=340, 17 страниц) терял 14 unread страниц после первого stuck. v2 result: 100/340 SKU = 29%. v1.5 случайно повезло (337/340).

Fix через 5 рычагов в `enumerate_brand_via_api`:
  1. Base inter-page delay 2.8s → 4.0s
  2. Per-page retry: 1 → 3 attempts с exponential backoff `[12s, 24s, 48s]`
  3. **Skip-page-on-403 instead of break-brand** — pageN не означает page(N+1) тоже сломан
  4. Per-brand 403 budget = 12 (всего 403 across all pages)
  5. Anti-burst cooldown: после `pages_per_burst=3` успешных pages — 20s sleep

Result: zielinski_rozen 100 → 320 (94%), MAC 98 → 212, Clinique 201 → 219 (99.5%), Clarins 195 → 248 (100%).

[[Cards-list per-session burst limit — 3-4 страницы потом 403]]

## Targeted recovery script (`bin/recover_brands.py`)

После v3 три бренда ещё не получили полное coverage (clarins 79%, clinique 91%, zielinski 53%). Делать full re-enum (90 мин) ради 3 брендов — wasteful. Написал `bin/recover_brands.py`:

```bash
uv run python bin/recover_brands.py --run-id 19 \
    --brand-norms zielinski_rozen,clarins,clinique
```

Делает: открывает Camoufox session per-brand, hybrid enum с текущими (wider) defaults, DELETE существующих rows для этого brand_norm, INSERT новых. 3 бренда за ~10 мин wall-clock.

## Финальное состояние run-19

- **goldapple: 3 675 SKU / 51 brand_norms / 48 в overlap с виледом**
- **viled: 6 019 SKU / 64 brand_norms (не трогали)**
- **matches: 5 337 при rate=105.6%** (D-403 N→1: одна viled SKU мэтчится с N вариантами; multi-variant capture даёт >1 GA SKU per viled SKU)
- **xlsx: `reports/2026-W20-run19-final.xlsx`** 801 KB, sheets: 5337 deltas / 3272 gaps / 1425 promos
- **archival DB:** `prices.db.bak-run19-v3-final`

## Что осталось (open)

- **13 viled brand_norms permanently absent on GA** — affinessence, amouage, jo_malone_london, etc. Verified через `scripts/resolve_unmatched_brands_v2.py` против 1 389-brand authoritative index. Не fix-able.
- **Budget=12 ещё может exhaust** на брендах badge>340. Не видели после v3.1 — но Camoufox session rotation per N brands добавит запас прочности при будущей кампании добавления брендов.
- **Hetzner-cron не реактивирован** — operator продолжает локальный режим до confidence в воспроизводимости. См. memory `feedback_local_only_until_confident.md`.

## Связано

- [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]
- [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]]
- [[Brand-alias mismatch — viled добавляет -beauty suffix, GA снимает]]
- [[Cards-list per-session burst limit — 3-4 страницы потом 403]]
