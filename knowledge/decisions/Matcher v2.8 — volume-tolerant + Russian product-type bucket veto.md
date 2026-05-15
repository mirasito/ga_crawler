---
tags: [decision, matcher, name-matching, false-positives]
date: 2026-05-16
---

# Matcher v2.8 — volume-tolerant + Russian product-type bucket veto

## Решение
Replace strict `name_norm = name_norm` + `volume_norm = volume_norm` SQL JOIN with a 4-layer pipeline. Final shape (commit `c65da49`):

1. **SQL pre-filter**: `brand_norm` equality + `(v.volume_norm = g.volume_norm OR v.volume_norm IS NULL OR g.volume_norm IS NULL)`. Не падаем на single-side NULL volume (помада/тушь у viled часто без объёма в названии).
2. **Python `name_matches(viled_name_norm, goldapple_url, goldapple_name_norm, brand_norm)`** — 4 пути:
   - **Path 0 (cross-category veto)**: первое русское слово → bucket (perfume/cream/serum/lipstick/...). Buckets разные → reject. Закрывает FP типа «Крем для рук Portrait of a Lady» ↔ «Парфюмерная вода Portrait of a Lady».
   - **Path 2 (strict equality fallback)**: single-char synthetic names (preserve test fixtures).
   - **Path 3 (subset)**: `g_tok ⊆ v_tok` — slug помещается внутрь viled.
   - **Path 4 (residual)**: с VARIANT_MARKERS veto (extreme/refill/intense/...) и опционально "one side empty" relaxation.

## Числа
| Версия | Matches | FP >200% | GT recall (82) |
|---|---:|---:|---:|
| v1 strict | 0 | — | 0% |
| v2 token | 1670 | ~30 | — |
| v2.6 | 1555 | 30 | 58% |
| v2.7 (volume-loose, без bucket veto) | 3842 | 162 | 71% |
| **v2.8** | **2780** | **33** | **67%** |

## Решающие компоненты

- **GA token-set = slug ∪ name_norm** (не slug OR name). Slug несёт canonical short form, name содержит вариант-квалификаторы (refill/extreme) которые иначе теряются.
- **Path 3 одно-направленный** (`g ⊆ v`, не bidirectional) — viled-имена систематически длиннее GA-slug-ов; inverse direction ловила false-positives.
- **VARIANT_MARKERS** = frozenset с `extreme/intense/refill/oud/fraiche/sport/drama/classic/signature/...`. Используется как veto в Path 4: если на одной стороне residual есть variant-marker — reject.
- **Russian bucket stems** (≈50 префиксов → 20 категорий). `парфюм/туалетн → perfume`, `крем/гель-крем → cream`, `сыворот/концентрат → serum`, `помад → lipstick`, `тушь → mascara`, etc. См. `_PRODUCT_TYPE_STEMS`.
- **Refill-prefix skip**: если первое слово `рефил/рефилл`, берём bucket следующего слова. Иначе `Рефилл геля для душа` и `Рефил парфюмерной воды` оба попадают в "refill" и не отделяются.

## Что НЕ stopword (важно)
- body-parts (`eye/face/lip/skin/body/...`) ОСТАЮТСЯ discriminative. Stopwording их вернёт FP «All About Clean (мыло)» ↔ «All About Eyes (крем)».
- variant qualifiers (extreme/refill/...) НЕ stopwords и попадают в VARIANT_MARKERS.

## Известные оставшиеся FP
~30 «same name + wildly different price» пар, в основном Kilian. Корневая причина — viled-data-quality (SKU 41400 KZT помечен как «100мл», а цена соответствует 7.5мл sample). Matcher формально прав. Multi-variant capture даст GA-цены на все размеры одной серии → проблема растворится естественно когда matcher сможет выбрать ближайший по цене variant.

## Сорс
matcher-review-2026-05-15..16 FP audit на run 19 + 316-pair ground truth от пользователя.
