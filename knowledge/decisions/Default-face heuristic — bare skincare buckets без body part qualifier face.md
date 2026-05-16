---
tags: [decision, matcher, bucket, body-part, heuristic]
date: 2026-05-16
---

# Default-face heuristic — bare skincare buckets без body part qualifier → `_face`

## Что

Когда `product_type_bucket` приходит в sub-bucketing stage и base ∈ {`cream`, `serum`, `essence`, `toner`, `foundation_base`}, и в имени **нет explicit body part qualifier** (для лица / глаз / рук / etc.) — возвращаем `<base>_face` вместо bare `<base>`.

## Зачем

Operator review run-21 confirmed semantic: viled "Антивозрастной крем Smart Clinical Repair" (no body part) should NOT match GA "Крем для глаз Clinique Smart Clinical Repair" (eye cream). Both same line, but viled implicit-face, GA explicit-eye. Different products.

Без default-face heuristic:
- viled bucket=`cream` (bare)
- GA bucket=`cream_eye` (explicit)
- Strict equality fails → veto fires → ❌ no match for ANY GA SKU of same line (даже когда есть face cream GA SKU)
- Or: prefix-compat → match ANY → FP

С default-face:
- viled bucket=`cream_face` (implicit assumption)
- GA face cream → `cream_face` → match ✓
- GA eye cream → `cream_eye` → mismatch → veto ✓
- Best of both worlds

## Какие base buckets входят в DEFAULT_FACE

```python
_DEFAULT_FACE_BASES = frozenset({
    "cream",          # генерический «крем» без квалификатора чаще всего face
    "serum",          # сыворотки чаще для лица
    "essence",        # эссенции — face-care класс
    "toner",          # тоники — face
    "foundation_base" # primer — face
})
```

## Что НЕ default-face

`spray` / `mask` / `oil` / `lotion` / `gel` / `balm` / `fluid` / `milk` / `foam` / `soap` / `scrub` / `mist` / `patch` / `cleanser` — оставляем bare если body part не найден. Reasoning: эти категории часто для тела/волос/рук; default-face слишком агрессивен.

- Spray: чаще для тела/волос
- Mask: может для лица/волос/тела
- Oil: face oil, body oil, hair oil — слишком ambiguous
- Lotion: body lotion обычно, face lotion редко

Если в data выявятся FPs где bare spray/mask/etc матчит wrong body-part variant — может расширить `_DEFAULT_FACE_BASES` или сделать default зависимым от brand context.

## Risks

**False reject**: viled "Крем Olaplex Bond Repair" (на самом деле hair cream) → cream_face. GA "Крем для волос Olaplex" → cream (no волос stem) → bare cream. Strict equality cream_face vs cream → mismatch → veto. **False reject** for legitimate same product.

Mitigation: add `волос` body part stem if seen in beauty inventory (currently focus on viled beauty catalog 1310 — hair products rare).

**Confirmed acceptable**: операторские примеры — bare cream / serum / toner всегда face в нашем data. Heuristic safe.

## Связано

- [[Matcher v3 — sub-bucketing для perfume concentration и body-part qualifier]]
- [[Bucket veto stem-coverage gap — палетка тени отсутствовали]]
