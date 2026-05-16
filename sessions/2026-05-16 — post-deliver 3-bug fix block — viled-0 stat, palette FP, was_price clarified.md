---
tags: [session, post-deliver, matcher, bucket-veto, fp-fix]
date: 2026-05-16
---

# Сессия 2026-05-16 (после доставки) — 3 бага вскрылись на operator review

После доставки run-19 xlsx в Telegram (`message_id=33`) operator сразу заметил три проблемы в caption + content. Все три закрыты в одной итерации.

## Багов выявлено / закрыто

### #1 `viled: 0 SKU` в caption

Reporter `summary_builder.py:67` читает `stats.get("viled.fetch_count", 0)`. Этот ключ **отсутствует** в `runs.stats` JSON для run-19 во **всех 7 backup-ах** трилогии. Источник: первый утренний прогон не дошёл до записи viled-стата (через `bin/run_goldapple_for_existing_run.py` который сломался на ImportError ДО `patch_stats`). Plus `goldapple.fetch_count=3471` оказался устаревшим — `bin/recover_brands.py` insert-ил 204 SKU в DB но не апдейтил stat.

**Fix:**
- Quick: SQL UPDATE patched `viled.fetch_count=6019` и `goldapple.fetch_count=3675` из authoritative DB row counts.
- Permanent: `bin/recover_brands.py` теперь сам апдейтит обе goldapple-stat-ключа в конце через `run_writer.patch_stats(...)`. Этой регрессии больше не будет.

### #2 Tom Ford Electric Cherry — палетка vs парфюм FP (top-1 delta в xlsx!)

Viled SKU `281236 Палетка теней Eye Color Quad оттенок Electric cherry` (volume_norm=NULL потому что палетка) сматчился с GA SKU `19000402298 Парфюмерная вода Tom Ford Electric Cherry Eau De Parfum`. Они делят marketing-name "electric cherry", и volume-loose SQL JOIN разрешает NULL volume с одной стороны.

Matcher v2.8's product-type bucket veto должен был это отвергнуть, **но `_PRODUCT_TYPE_STEMS` не содержал стемов для `палетк-` и `тен-`**. `product_type_bucket("палетка тенеи ...") = None` → veto skipped.

**Fix:** добавил два стема + один шортинг:
```python
("палетк",  "palette"),    # палетка теней / палетка хайлайтеров
("тен",     "palette"),    # тени для век (same bucket — same product family)
("спре",    "spray"),      # БЫЛО "спрей" — viled normalizer даёт plural "спреи"
```

Все три добавки прошли regression-тесты:
- `test_rejects_palette_vs_perfume_same_marketing_name` — палетка × парфюм VETO
- `test_accepts_palette_vs_palette_same_product` — палетка × палетка ACCEPT
- `test_plural_spray_form_resolves_to_spray_bucket` — спреи → spray
- `test_palette_and_eyeshadow_both_map_to_palette_bucket` — палетка/тени → palette

**Effect:** matches `5337 → 5060` (−277 FP отвергнуто), rate `105.6% → 100.12%`. Top-1 delta теперь честная `Creed мыло Green Irish Tweed` дельта 597% (real KZ markup signal, не contamination).

### #3 `was_price` NULL у 57% GA позиций — НЕ bug

Operator спросил почему у Tom Ford Electric Cherry парфюма нет старой цены. Я проверил: stats показывают 1594 / 3675 (43%) GA SKU имеют was_price, 2081 (57%) — нет.

**Не bug — design GA cards-list:**
```json
"price": {
  "regular": {"amount": 309555},  // MSRP
  "actual":  {"amount": 309555},  // current
  // "old" поле отсутствует — нет активной акции
}
```

`price.old` GA эмитит **только** на активной акции. Tom Ford Electric Cherry прямо сейчас без акции — `old=None` → `was_price=NULL` корректно. Это совпадает с поведением страницы на сайте (нет зачёркнутой цены).

Если в будущем потребуется «всегда показывать MSRP» — это **продуктовое решение**: fallback `was_price ← price.regular`. Тогда «промо» колонка перестанет различать акционные от full-price. Defer до явного product call.

## Артефакты сессии

| File | Change |
|---|---|
| `src/ga_crawler/matcher/name_match.py` | +2 bucket stems (палетк, тен), 1 shorting (спрей→спре) |
| `bin/recover_brands.py` | +run_writer.patch_stats call в конце на refresh goldapple.fetch_count |
| `tests/unit/test_name_match.py` | +4 regression tests (bucket-veto coverage) |
| (vault) | этот session note |

Final run-19 после fix: GA 3675 SKU / 5060 matches / 100.12% rate. xlsx redelivered (message_id=35).

## Знание / decision artefacts

- [[Bucket veto stem-coverage gap — палетка/тени отсутствовали]]
- [[was_price NULL это feature а не bug — GA cards-list omits price.old без акции]]

## Связано

- [[2026-05-16 — retry hardening + brand-alias unlock + 5337 matches 105pct rate]] — родительская late-evening сессия (5337 cleaned up до 5060)
- [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]
