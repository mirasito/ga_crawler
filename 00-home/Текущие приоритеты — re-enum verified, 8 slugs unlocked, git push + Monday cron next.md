---
tags: [priorities, current]
date: 2026-05-16
---

# Текущие приоритеты

## Где мы (после вечерней сессии 2026-05-16)

- **Run-19 re-enum полностью завершён** через hybrid+variant code path. Headline numbers locked in (см. [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]):
  - Goldapple SKU: 1 319 → **2 396** (+82%)
  - Brand overlap: 20 → **40** (+20)
  - Matches: 2 780 → **3 831** (+38%)
  - Match rate: 68.85% → **78.71%** (+9.86 pp)
- **Production wiring bug пойман и исправлен** — runner вызывал scroll-only `enumerate_brand`, multi-variant код из утра не срабатывал в production. Если бы не пойман, понедельничный cron-run выдал бы старые ~2780 матчей.
- **8 новых brand-slug overrides** добавлены через operator-hint про `/brands` page → discovery API `/front/api/brands` с полным списком 1 389 брендов в single XHR.
- **4 локальных коммита**, **НЕ запушены**: `04060d5`, `6a966f3`, `e73ebe7` (+ предыдущий `07e2254` тоже local) → origin/master отстаёт.

## Дальше (по убыванию impact)

1. **`git push origin master`** — самое срочное, до понедельника. Без него Hetzner-cron не подтянет wiring fix и подведёт production-run.
2. **Smoke-проверить Hetzner deploy после push** — operator подключается, `cd /opt/ga_crawler && git pull && uv sync` (или что у вас за deploy-flow), проверить что код актуален. До понедельника окно есть.
3. **Очистить inbox/ + scripts/probe_\*** — operator-debt накапливается, 30+ untracked files. Triage: какие probe-скрипты сохранить (probe_ga_brands_index_v2.py, probe_pdp_variants.py — core), какие удалить (test_*_single.py).
4. **Удалить или переписать `bin/run_goldapple_for_existing_run.py`** — stale imports `GoldappleConfig`, неправильный runner `goldapple_run` (sitemap path вместо brand-pages). Используется `weekly-run --goldapple-only --run-id N` вместо.
5. **(Optional) попробовать ловить 13 «GA-absent» брендов через `/api/search`** — если viled-бренд *вообще* существует в KZ на других маркетплейсах, может быть worth checking. Но это уже coverage-expansion, не для v1.1.

## Ожидаемое для понедельничного weekly-run

- Brand overlap 40 → 48
- ~+700-800 goldapple SKU (если средний 95 SKU/brand)
- **~4 100-4 400 matches** (vs текущих 3 831)
- Если match.rate > 80% — milestone unlock для рассылки commercial team

## Что НЕ работает / known issues

- **Cards-list 403 на page 4 у крупных брендов** (Lancome пример, ~16% брендов) — workaround cooldown 12 сек частично помогает но иногда `api_403_stuck` остаётся. Это accept-loss на v1.1; видимый эффект уже учтён в 2 396 SKU.
- **13 viled brand_norms не на GA вовсе** — affinessence, amouage, jo_malone_london, etc. Permanent floor; не fix-able через slug-archaeology.
- **`bin/run_goldapple_for_existing_run.py`** — broken, see выше.
- **`scripts/probe_ga_brands_index.py` v1** — superseded; v2 живёт рядом.

## Связано

- [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]
- [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]] — утренняя половина дня
- [[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]]
- [[Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant]]
