---
tags: [debugging, wiring-bug, production, code-review-gap]
date: 2026-05-16
---

# Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant

## Симптом

Коммит `3df6aba feat(enumeration): multi-variant capture via product-card/base/v3 API` добавил три функции в `src/ga_crawler/enumeration/goldapple_brand.py`:

- `fetch_product_variants(page, item_id)`
- `variant_to_raw_product(variant, brand, productType, unit_name)`
- multi-variant top-up loop *внутри* `enumerate_brand_via_api`

Commit message заявлял «Verified end-to-end on Bobbi Brown: +28 variants» — но это было через **probe-script** `scripts/test_variant_enum.py`, а не production CLI. В production-runner `src/ga_crawler/runners/goldapple_brand_run.py:235` всё ещё стоял вызов **старой** функции `enumerate_brand` (scroll-only, без multi-variant). Файл `goldapple_brand_run.py` последний раз менялся в `2d42d33` (pyproject toggle), который предшествовал добавлению `enumerate_brand_via_api` / `enumerate_brand_hybrid`.

Эффект: weekly-run в production использовал scroll-only path; multi-variant top-up **никогда не срабатывал в проде** до сегодняшнего fix-коммита.

## Root cause

«Я добавил функцию, импорт в runner-е не обновил».

Конкретно — две точки разрыва между моментом «новый код merged» и моментом «production его вызывает»:

1. `goldapple_brand.py` — добавлены новые публичные функции `enumerate_brand_via_api`, `enumerate_brand_hybrid`. Старая `enumerate_brand` сохранена ради тестов / fallback.
2. `goldapple_brand_run.py` — `from ga_crawler.enumeration.goldapple_brand import enumerate_brand` остался прежним; вызов `enumerate_brand(fetcher, slug)` остался прежним.

Без cross-file grep при code review разница невидима — оба файла валидны изолированно.

## Fix

Commit `04060d5`:

```diff
- from ga_crawler.enumeration.goldapple_brand import enumerate_brand
+ from ga_crawler.enumeration.goldapple_brand import enumerate_brand_hybrid

- result = await enumerate_brand(fetcher, slug)
+ result = await enumerate_brand_hybrid(fetcher, slug)
```

Plus docstring update в `run_goldapple_brand_phase`.

## Как поймать в следующий раз

- **Before commit-ы вида «feat X via new function Y»:** grep по новому имени функции — должно быть >= 2 reference (definition + at least one caller). Если caller-reference = 0, значит production path не подключён.
- **Smoke verification on production CLI**, не probe-script: после ship'а нового capture-mechanism — запустить minimum one brand через `weekly-run --goldapple-only --run-id <N>` и проверить логи на event-имя из нового кода (`brand_enum_api_complete` / `multivariant_calls > 0`).
- **Code review для phases вида ops/integration:** memory `feedback_code_review_for_ops_phases.md` — обычно про bash/cron/deploy. Этот случай показывает что **Python integration code тоже надо review-ить cross-file** когда добавляется new function meant-to-be-called-by-production.

## Какие данные я потерял

Никаких — поймал до того как Hetzner-cron в понедельник запустил weekly-run. Если бы не поймал: понедельничный run выдал бы те же ~2780 матчей вместо 3831, и был бы проигрыш по recall на 9.86 pp в первом production-run после ship'а multi-variant.

## Связано

- [[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]] — тот же session, другой fix
- Memory: `feedback_code_review_for_ops_phases.md` — расширить scope на Python-integration cross-file refs
