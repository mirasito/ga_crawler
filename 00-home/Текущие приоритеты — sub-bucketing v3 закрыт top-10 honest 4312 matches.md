---
tags: [priorities, current]
date: 2026-05-16
---

# Текущие приоритеты

## Где мы (после поздней вечерней forensic review session 2026-05-16)

- **Run-21 финал**: viled 6 359 / GA 3 744 / **matches 4 312 @ 81.74% rate**. Match rate stricter но honest — top-10 deltas все real product-vs-product KZ-markup signals.
- **Все user-reported FP-классы из forensic review закрыты**:
  - Volume mismatch (Kilian) — viled multi-variant per-variant capture (commit `e504c37`)
  - was_price NULL — MSRP fallback на `price.regular` (`e504c37`)
  - English-leading names — `_cyrillic_leading_words` сканирует все слова (`ccbba58`)
  - Palette eyeshadow vs corrector — palette sub-bucketing (`3f2df46`)
  - EDT vs EDP vs Дух — fragrance concentration sub-bucketing (`dfa4ab7`)
  - Face cream vs eye cream — body-part qualifier + default-face heuristic (`dfa4ab7`)
  - Travel set vs standalone parfum — priority `набор` override (`3f2df46`)
- **8 коммитов в этой continuation-сессии**, всё запушено в `origin/master` (`04060d5 → dfa4ab7`).
- **583/583 unit tests passing** (started 556).
- **xlsx redelivered** через `deliver-run --run-id 21 --force` (message_id=42).

## Архитектура bucket-veto после рефакторинга

```
Phase 1: priority overrides (набор/сет → set)
Phase 2: refill strip (рефил- prefix dropped)
Phase 3: base stem scan (compounds FIRST then singles, 70+ stems)
Phase 4: sub-bucketing на base:
  - palette → palette_{eyeshadow,corrector,highlighter,blush,bronzer}
  - perfume → perfume_{parfum,edp,edt,cologne}
  - skincare base ∈ {cream, serum, ...} → base_{face,eye,hands,body,...}
    + DEFAULT_FACE_BASES → _face fallback if no qualifier
```

## Дальше (по убыванию impact)

1. **MAC Pro Palette × MAC Pro Conceal Palette подобные FPs** — same brand, same sub-bucket, different marketing line. Требует subword/marketing-name distance metric. Архитектурная работа, defer.
2. **Body-part stems extension** — добавить `волос` (hair) когда расширим scope. Сейчас beauty catalog 1310, hair products редки.
3. **Brand-alias canary** (B из старого backlog) — auto-test что `data/ga_brand_slugs.yaml` overrides имеют canonical в `config/brand-aliases.yaml`. Закроет источник Bug-1 на test-time. ~15 мин.
4. **Per-bucket coverage canary** (C) — sample-based проверка что N% viled SKUs резолвятся в не-None bucket. Закрывает источник stem-coverage gaps. ~20 мин.
5. **Inbox/scripts triage** — 30+ untracked artifacts, operator debt. ~20 мин.
6. **Удалить `bin/run_goldapple_for_existing_run.py`** — broken stale-imports скрипт; используется `weekly-run --goldapple-only --run-id N` вместо.

## Что НЕ работает / known limits

- **Different products with shared marketing tokens within same brand/sub-bucket** (MAC Pro Palette × Pro Conceal Palette) проходят token-overlap test. Требует более тонкий name comparison.
- **viled hair products** — нет `волос` body-part stem; если viled добавит hair line, default-face heuristic дать FP. Add stem when seen.
- **GA was_price требует regular > actual для fallback** — если GA SKU имеет identical regular and actual (no promo), `was_price=NULL` корректно. Operator-confirmed: это feature not bug.

## Связано

- [[2026-05-16 — viled multi-variant + matcher sub-bucketing v3 — 4312 matches honest]] — главный session note
- [[Matcher v3 — sub-bucketing для perfume concentration и body-part qualifier]]
- [[Viled multi-variant — catalog minPrice + PDP NEXT-DATA per-variant top-up]]
- [[Default-face heuristic — bare skincare buckets без body part qualifier face]]
- [[GA was_price MSRP fallback через price.regular]]
