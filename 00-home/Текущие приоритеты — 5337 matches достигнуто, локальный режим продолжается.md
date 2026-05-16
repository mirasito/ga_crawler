---
tags: [priorities, current]
date: 2026-05-16
---

# Текущие приоритеты

## Где мы (после поздней вечерней сессии 2026-05-16)

- **run-19 финальный**: goldapple 3 675 SKU / 51 brand_norms / 48 в overlap. matches **5 337 при rate=105.6%**. xlsx `reports/2026-W20-run19-final.xlsx` 801 KB.
- **6 коммитов локальных** (НЕ запушены): `04060d5`, `6a966f3`, `e73ebe7`, `5f4116a`, `209a4ff`, ещё текущий. Все на master.
- **Hetzner-cron на паузе** — operator продолжает локальный режим до confidence (см. memory `feedback_local_only_until_confident.md`).
- **Два архитектурных бага закрыты в этой сессии**: brand-alias mismatch + cards-list burst-limit. [[Brand-alias mismatch — viled добавляет -beauty suffix, GA снимает]] + [[Cards-list per-session burst limit — 3-4 страницы потом 403]].

## Прогресс по run-19 (5 итераций за день)

| Прогон | GA SKU | matches | rate |
|---|---:|---:|---:|
| v1 (sitemap старт) | 207 | 0 | 0% |
| v1.5 (matcher v2.8 + multi-variant утром) | 2 396 | 3 831 | 78.71% |
| v2 (8 new slugs, baseline reverted) | 2 426 | 3 409 | 70.04% |
| v2.1 (alias SQL UPDATE) | 2 426 | 3 532 | 69.89% |
| v3 (retry hardening) | 3 471 | 5 260 | 104.08% |
| **v3.1 (targeted recovery)** | **3 675** | **5 337** | **105.6%** |

**Net в этой сессии**: matches `3 831 → 5 337` (+1 506, +39%).

## Дальше (по убыванию impact)

1. **Понять что 105% rate означает для business stakeholders** — пользователи получают `Совпало: 5337 (105.6%)`, где >100% непривычно. Возможно нужна перерасчёт rate как `min(matches/denominator, 100%)` или показывать `matches_per_viled_sku = X` рядом. Или объяснить в Excel summary. **Это product-call, не code-call.**
2. **Второй смоук-прогон с нуля** — чтобы убедиться в воспроизводимости. Создать run-20, прогнать viled+goldapple+matcher end-to-end локально. Если v3-числа выпадают похожие (5 200-5 500 matches, GA ≥3 400) — confidence-bar взят, можно реактивировать Hetzner-cron.
3. **Inbox+scripts triage** — 30+ untracked artifacts. Какие probe-скрипты в `scripts/` сохранить (v2 версии core), какие удалить (one-shot).
4. **`bin/run_goldapple_for_existing_run.py` — broken**, stale imports. Либо удалить либо переписать на dispatch-by-discovery_mode.
5. **`bin/recover_brands.py` — добавить unit-тестов** для `_recover_brands` orchestrator + написать integration smoke на mock GoldappleFetcher.
6. **brand-alias canary**: для каждого entry в `data/ga_brand_slugs.yaml` overrides — проверять что соответствующий canonical brand_norm существует в `config/brand-aliases.yaml`. Mismatch — FAIL test. Это закроет источник Bug-1 на корне.

## Что НЕ работает / known issues

- **13 viled brand_norms permanently absent on GA** — `scripts/resolve_unmatched_brands_v2.py` подтвердил через authoritative 1 389-brand index. Не fix-able через slug-archaeology.
- **rate=105.6%** — D-403 поведение (N→1 match keep-all) теперь дает >100% потому что multi-variant capture даёт N GA вариантов на одну viled SKU. Это feature, не bug, но требует объяснения в delivery-summary.
- **Camoufox brand_overlap нестабилен между прогонами** на старых брендах — pre-v3 hardening (mac 175 в v1.5 vs 98 в v2). Hardening лечит, recovery loop добавляет страховку.

## Связано

- [[2026-05-16 — retry hardening + brand-alias unlock + 5337 matches 105pct rate]]
- [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]
- [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]]
- [[Brand-alias mismatch — viled добавляет -beauty suffix, GA снимает]]
- [[Cards-list per-session burst limit — 3-4 страницы потом 403]]
- [[GA brands index — single XHR на front-api-brands возвращает все 1389 брендов]]
- [[Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant]]
