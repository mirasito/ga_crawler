---
tags: [decision, matcher, fuzzy-match, v2, strict-key, business-gap]
date: 2026-05-15
phase: 10
---

# Strict-key matcher даёт 0 matches на real fashion data — fuzzy v2 нужен

## TL;DR

Run #18 c full viled catalog (6,019 SKU) + brand-filtered goldapple (207 SKU) дал **brand_overlap=18, denominator=1,774 candidate pairs, match_count=0**. Strict-key SQL JOIN `(brand_norm, name_norm, volume_norm)` слишком жёсткий для real fashion/beauty product naming — product name templates у viled и goldapple **никогда не identical** даже после NORM-01..04.

## Реальный пример

| Retailer | brand | name |
|---|---|---|
| viled | `Frederic Malle` | `Парфюмерная вода Contre-Jour` |
| goldapple | `Frederic Malle` | `Contre Jour` или `FREDERIC MALLE Contre Jour` |

После lowercase + strip-punct (NORM-02):
- viled `name_norm`: `парфюмерная вода contre jour`
- goldapple `name_norm`: `contre jour`

Они **разные strings** — SQL JOIN fails. Brand+volume часто совпадают идеально (`frederic malle` + `(100,ml,1)`), но `name` префиксуется product-type metadata у viled (`Парфюмерная вода`, `Туалетная вода`, `Парфюм для волос`) который goldapple drops.

## Почему это не code-bug

Это deliberate v1 trade-off per CLAUDE.md scope:

> Matching strictness: Точное совпадение нормализованного ключа `brand + название + объём` (lowercase, без знаков пунктуации) — **на v1; fuzzy-матчинг откладывается до v2**.

Strict-key trades RECALL (low match-rate) за PRECISION (zero false-positive matches). Important: false-positive match → wrong price comparison → wrong business decision. False-negative match → missed comparison but no wrong action.

## Что v2 fuzzy-match должен делать

После strict-key пройдёт 0..N matches, run residual `(brand_norm match) AND (volume_norm match) AND (name_norm fuzzy ~ threshold)` :

- **Stage 1**: same brand + same volume (cheap filter) → candidate list
- **Stage 2**: fuzzy name match (RapidFuzz token_set_ratio >= 85) → suggested match
- **Stage 3**: manual review queue для borderline cases (75-85 score)

Expected impact: match_count 0 → возможно 200-500+ matches на 1,774 candidates.

## Кандидатные библиотеки

- `rapidfuzz` — fastest, C++ Levenshtein impl, token_set_ratio handles word reordering
- `jellyfish` — algorithms (Jaro-Winkler, Soundex) для name variations
- `thefuzz` — pure-python, slower, legacy fuzzywuzzy fork

Recommendation: `rapidfuzz.fuzz.token_set_ratio` для name comparison + manual threshold tuning по validation set (50-100 manually-confirmed pairs).

## Где это болит сегодня

Run #18 xlsx (24 KB, `message_id 32` в ops-chat):
- `per_sku_deltas`: 0 rows (где live price comparison должны быть)
- `assortment_gaps`: 144 rows (goldapple SKU без viled-пары)
- `goldapple_promos`: 85 rows (только goldapple promos, viled side empty)
- `summary`: 1 row (aggregate stats only)

Коммерческая команда не получает **price delta** — основной KPI продукта.

## v2 backlog приоритет

**Higher than viled-fast-API production integration** — fast-API даёт МНОГО viled данных но без fuzzy-match они всё равно не match с goldapple. Fuzzy-match unblocks main business value (price comparison).

Suggested phase order:
1. v1.2 phase: Fuzzy-match Stage 2 (rapidfuzz integration + threshold)
2. v1.3 phase: Manual review queue для borderline
3. v2.0 phase: viled-fast-API в production weekly-run

## Связано

- [[2026-05-15 — Phase 10 closed + viled pagination unlocked + 4 production bugs fixed]] — session note
- [[Viled API endpoint найден — items_content paginated через page+pageSize params]]
- CLAUDE.md "Matching strictness" line — v1 contract
- `tests/unit/test_matcher_strict_key.py` — current strict-key tests
- `src/ga_crawler/matcher/strict_key.py` — где fuzzy stage 2 будет добавлен
