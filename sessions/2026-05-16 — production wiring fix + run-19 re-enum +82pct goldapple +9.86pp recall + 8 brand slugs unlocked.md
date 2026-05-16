---
tags: [session, matcher, multi-variant, wiring-fix, brand-slugs, recall-jump]
date: 2026-05-16
---

# Сессия 2026-05-16 (вечер) — production wiring fix → run-19 re-enum → +82% GA SKU, +9.86pp recall, 8 новых brand-slug-ов

Continuation of [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]]. Утренняя сессия закоммитила matcher v2.8 + multi-variant capture в `3df6aba`, но не запустила полный re-enum против ground truth. Вечером три пункта из TODO утра закрыты: re-enum, тесты, slug-resolution для unmapped brands. Один critical bug fix всплыл во время верификации.

## 4 коммита в `master` (запушены ещё нет — origin/master отстаёт)

| Commit | Что |
|---|---|
| `04060d5` | **Critical wiring fix:** production runner `goldapple_brand_run.py` всё ещё вызывал `enumerate_brand` (scroll-only) вместо `enumerate_brand_hybrid` — multi-variant код из утренней сессии в проде НЕ срабатывал. Один файл, +7/-3, но load-bearing |
| `6a966f3` | 20 unit-тестов для `fetch_product_variants` + `variant_to_raw_product` (Clinique-lotion и Almost-Lipstick shapes inlined из probe captures) |
| `e73ebe7` | 8 brand-slug overrides + два probe-script v2 для `/front/api/brands` authoritative index |
| (нет 4-го коммита для viled — viled-19 не трогали, преднамеренно) | — |

## Run-19 re-enum: до / после

Backup БД сделан `prices.db.bak-pre-rerun19-multivariant`. Удалены snapshots+matches только для `run_id=19, retailer='goldapple'`, viled-19 (6019 SKU) сохранён → чистое A/B на goldapple-side.

| Метрика | До (scroll-only + matcher v2.8) | После (hybrid + variants + matcher v2.8) | Δ |
|---|---:|---:|---:|
| Goldapple SKU | 1 319 | **2 396** | **+82%** |
| Goldapple resolved brands | 21 | **43** | +22 |
| `match.brand_overlap_count` | 20 | **40** | +20 |
| `match.goldapple_comparable` | 1 206 | 2 218 | +84% |
| `match.viled_comparable` | 6 013 | 6 013 | 0 (как и задумано) |
| `match.denominator` | 4 038 | 4 867 | +20% |
| **`match.count`** | **2 780** | **3 831** | **+38% (+1 051)** |
| **`match.rate`** | **68.85%** | **78.71%** | **+9.86 pp** |
| Длительность goldapple-phase | (старая) | 55 мин (64 brands × ~52с) | — |

XLSX-отчёт `reports/2026-W20.xlsx` 562 KB, sheets cleanly. Top-3 deltas reasonable: Tom Ford eye palette 619%, Creed soap 597%, Kilian fragrance 586% — всё классические "viled inflated vs GA" plays.

## Production wiring fix — почему был баг

Утренний коммит `3df6aba` добавил `enumerate_brand_via_api` + `enumerate_brand_hybrid` + сам multi-variant top-up *inside* `_via_api`. Но production-runner `src/ga_crawler/runners/goldapple_brand_run.py:235` всё ещё вызывал `enumerate_brand` (scroll-only) — последний touch файла в `2d42d33` (`pyproject toggle`), который предшествовал добавлению hybrid/api функций.

> «Verified end-to-end on Bobbi Brown: +28 variants» в commit message относилось к probe-скрипту (`scripts/test_variant_enum.py`), а не к production-CLI. Без `04060d5` re-enum дал бы дельту 0.

[[Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant]]

## Brand-slug resolution — operator-hint unlocked 8 brands

Operator показал screenshot `/brands` page с client-side search, типа "tom fo..." → "Tom Ford". Это означало что полный список рендерится в memory at-once → backing API call в DevTools. Probe v2 (`scripts/probe_ga_brands_index_v2.py`) с XHR-listener захватил `https://goldapple.kz/front/api/brands?locale=ru` — single call, returns **all 1 389 brands** with canonical slugs.

Cross-reference против 21 unmatched brand_norms из `.planning/runs/19/norm06-review.md`:

**8 разрешено (одинаковый паттерн: GA снимает "-beauty"/"-perfume" суффикс):**
```yaml
carolina-herrera-beauty: carolina-herrera
courreges-perfume:       courreges
gucci-beauty:            gucci
hugo-boss-beauty:        hugo-boss
kenzo-beauty:            kenzo
lanvin-beauty:           lanvin
valentino-beauty:        valentino
dr-vranjes:              dr-vranjes-firenze   # GA uses full marca name
```

**13 действительно НЕ на GA** (zero substring hits в 1 389-brand index): affinessence, aj-arabia, amouage, aveda, clive-christian, ex_nihilo, jo_malone_london, margys, marly, nescens, roja-parfums (closest GA hit `OJAR` — другой бренд), starskin, aura-of-kazakhstan (GA `Aura` — другой бренд). Это permanent floor; viled-only бренды.

[[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]]

## Что осталось / ожидаемое для следующего weekly-run

- Brand overlap 40 → 48 (8 новых)
- Average per-brand matches в run-19: 95 → ожидается **+700-800 goldapple SKU**, **~4 100-4 400 matches**
- Hetzner-cron в понедельник auto-pull через `git pull` (если configured) — но пока 4 коммита локальные, **нужен `git push origin master` перед понедельником**

## Untouched / housekeeping

- `bin/run_goldapple_for_existing_run.py` сломан (stale imports `GoldappleConfig` + неправильный runner `goldapple_run` вместо `goldapple_brand_run`). Использовал `weekly-run --goldapple-only --run-id 19` + `matcher-run --run-id 19` + `report-run --run-id 19` вместо. Скрипт надо либо удалить либо переписать на dispatch-by-discovery_mode.
- Untracked inbox/* + scripts/probe_* — operator-debt накапливается, пора triage

## Решения / pattern-discoveries

- [[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]]
- [[Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant]]
- [[Run-19 re-enum через goldapple-only --run-id N сохраняет viled для fair A/B]]

## Связано

- [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]] — утренняя половина
- [[Brand-pages discovery через cards-list + product-card API]]
- [[Matcher v2.8 — volume-tolerant + Russian product-type bucket veto]]
- [[cards-list возвращает 1 itemId на семью variant-ов]]
