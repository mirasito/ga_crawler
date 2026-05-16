---
tags: [debugging, matcher, bucket-veto, false-positive]
date: 2026-05-16
---

# Bucket veto stem-coverage gap — `палетка` / `тени` отсутствовали

## Симптом

Run-19 v3.1 (commit `937213d`) выдал top-1 delta в xlsx:

> `tom_ford палетка теней eye color quad оттенок electric cherry (100,ml,1): 619.9%`

Operator сразу узнал FP — это **eyeshadow palette** на стороне viled, **парфюм** на стороне GA. У них только marketing-name "Electric Cherry" общий. Должен был отсечь matcher v2.8 bucket veto, но не отсёк.

## Root cause

Matcher v2.8's `product_type_bucket()` отображает ведущее cyrillic-слово в продуктовую категорию через `_PRODUCT_TYPE_STEMS`. Veto fires когда обе стороны имеют known bucket, и они различаются.

Список стемов покрывал основные категории (парфюм, крем, помада, etc.) но **отсутствовали** entry для:

| Стем | Bucket | Зачем |
|---|---|---|
| `палетк` | palette | палетка теней / палетка хайлайтеров |
| `тен` | palette | тени для век (same product family) |
| `спре` (был "спрей") | spray | viled normalizer даёт plural "спреи" |

«Палетка теней Eye Color Quad ...» → leading cyrillic = `["палетка", "тенеи"]`. Loop по стемам: ни один не startswith — return None. Veto skipped.

Дальше Path-2 token-overlap: `electric` + `cherry` overlap → accept. Volume-loose JOIN разрешает NULL × 100ml. Готово, FP в DB.

## Fix

`src/ga_crawler/matcher/name_match.py` add stems:

```python
("карандаш",     "pencil"),
("подводк",      "liner"),
("консил",       "concealer"),
("палетк",       "palette"),    # NEW
("тен",          "palette"),    # NEW (same bucket — same product family)
...
("спре",         "spray"),      # WAS "спрей" — covers plural "спреи"
```

4 regression теста в `tests/unit/test_name_match.py`:
1. палетка × парфюм → VETO ✓
2. палетка × палетка → ACCEPT (same bucket) ✓
3. `product_type_bucket("спреи для тела") == "spray"` ✓
4. `product_type_bucket("тени для век")  == "palette"` ✓

**Effect on run-19:** matches 5 337 → 5 060 (−277 FP отвергнуто), rate 105.6% → 100.12%.

## Как поймать в следующий раз

- **Top-3 deltas review** перед каждой Telegram delivery должна быть в чек-листе operator-а. Если top-1/2/3 выглядит «электрик-черри палетка vs парфюм за 619%», тревожно — open xlsx, проверить pair руками.
- **Per-bucket coverage canary:** test против рандомного sample из `snapshots WHERE retailer='viled'` — для каждого SKU вычислить `product_type_bucket(name_norm)` и убедиться что ≥95% возвращают не-None. Bucket=None для viled-стороны почти всегда означает skipped veto = potential FP risk.
- **Periodic stem audit:** raw `SELECT DISTINCT name_norm FROM snapshots WHERE retailer='viled' ORDER BY brand_norm, name_norm LIMIT 100` глазами раз в N недель чтобы заметить новые product-types (например viled добавит «бьюти-блендер» — спойлер: нет стема для `бьюти`).

## Связано

- [[Matcher v2.8 — volume-tolerant + Russian product-type bucket veto]] — родительская архитектура veto
- [[was_price NULL это feature а не bug — GA cards-list omits price.old без акции]]
