---
tags: [decision, matcher, sub-bucketing, fragrance, body-part]
date: 2026-05-16
---

# Matcher v3 — sub-bucketing для perfume concentration и body-part qualifier

## Что

`product_type_bucket` теперь возвращает **discriminative sub-bucket** вместо плоской категории. Architecture:

```
Phase 1: priority overrides (набор/сет → set)
Phase 2: refill strip
Phase 3: base bucket scan (compounds FIRST, then singles)
Phase 4: sub-bucketing based on base:
  base = "palette"  → _eyeshadow / _corrector / _highlighter / _blush / _bronzer
  base = "perfume"  → _parfum / _edp / _edt / _cologne
  base ∈ SKINCARE_FAMILY → _face / _eye / _hands / _body / _lashes / etc.
    + default-face fallback for { cream, serum, essence, toner, foundation_base }
```

## Зачем

Operator review 2026-05-16 вскрыл cross-class FPs трёх типов:

1. **Same perfume, different concentration**: viled "Туалетная вода Alive" (EDT) vs GA "Духи Hugo Boss Alive" (Parfum). Both bucket=perfume → no veto → FP. Sub-bucket `perfume_edt` vs `perfume_parfum` → veto fires.

2. **Same cream, different body part**: viled "Антивозрастной крем Smart Clinical" (face cream) vs GA "Крем для глаз" (eye cream). Both bucket=cream → no veto. Sub-bucket `cream_face` (default) vs `cream_eye` → veto fires.

3. **Same primer, different qualifier**: viled "База под макияж" vs GA "Крем-основа для области вокруг глаз". Need compound stem + body-part scan + default-face heuristic to land both на consistent sub-bucket.

## Дизайнные решения

**Compounds first**: candidates list = compounds + singles. Без этого порядка single "крем" стем хитает раньше compound "крем-основа", и primer bucket ловит cream.

**`_all_cyrillic_words` для body-part scan**: leading-3-words cap (used for base bucket) недостаточен — body part может быть word #6 ("крем основа для области вокруг ГЛАЗ"). Отдельная функция scans all words.

**Default-face heuristic**: bare `cream` / `serum` / `essence` / `toner` / `foundation_base` без body part qualifier → `_face`. Operator-confirmed: «Антивозрастный крем» без квалификатора подразумевает face. Без default `cream` (bare) vs `cream_eye` совпадают via prefix-compat, что нежелательно. Default-face FORCES strict equality.

**Spray/mask НЕ default-face**: спрей чаще для тела/волос; маска часто для разных body parts. Bare `spray` / `mask` остаются без суффикса; cross-mismatch only when обе стороны имеют explicit body parts.

**Priority `набор`**: travel sets и парфюмерные наборы первым словом ловят «парфюмерный» (perfume) или «крем» (cream). Без priority override эти продукты матчатся как обычные парфюмы. Multipack-detection во viled-fast-crawl был обходным путём, sub-bucketing решает это в matcher.

## Как применять

При добавлении нового продукта или brand-line:
1. **Имя содержит explicit body part** (для лица/глаз/рук) — sub-bucket автоматически.
2. **Имя bare skincare term без body part** — default-face heuristic; если продукт реально не face (e.g. body cream без «тело» в имени), нужно явно указать body part в normalized form.
3. **Палетка** — quality указать в имени (тени, коррекции, хайлайтер) для правильного sub-bucket; иначе fallback на `palette` bare.
4. **Парфюм** — concentration word критичен: «парфюмерная вода» / «туалетная вода» / «духи» / «одеколон» — без него bare `perfume`.

## Текущий список body-part stems

```python
_BODY_PART_STEMS = (
    ("глаз",   "eye"),
    ("век",    "eye"),       # для век (eyelids) — same sub-bucket
    ("ресниц", "lashes"),
    ("брове",  "brows"),
    ("губ",    "lips"),
    ("лиц",    "face"),
    ("ног",    "feet"),
    ("рук",    "hands"),
    ("шеи",    "neck"),
    ("декольте","decolletage"),
    ("тел",    "body"),       # placed last — generic
)
```

## Risks

- **Wrong default**: viled "Крем Olaplex" — без body part, treated as face. Если на самом деле hair cream → mismatch против GA "крем для волос". Acceptable for our domain (beauty/skincare); если расширим на hair products, надо ревизия.
- **Missing body part in stems**: если у viled появится "крем для подмышек" — `подмышек` нет в стемах → bucket=cream_face (default). FP risk против GA "крем для лица". Add stem when seen in data.

## Связано

- [[Matcher v2.8 — volume-tolerant + Russian product-type bucket veto]] — родительский подход
- [[Bucket veto stem-coverage gap — палетка тени отсутствовали]] — раунд раньше расширения стемов
- [[Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant]]
- [[Default-face heuristic — bare skincare buckets без body part qualifier → _face]]
