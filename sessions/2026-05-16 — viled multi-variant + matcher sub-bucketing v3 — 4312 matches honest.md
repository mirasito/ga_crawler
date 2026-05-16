---
tags: [session, viled-multi-variant, matcher-sub-bucketing, was-price-fallback, operator-forensic-review]
date: 2026-05-16
---

# Сессия 2026-05-16 (вечер) — viled multi-variant + matcher sub-bucketing v3 → 4 312 матчей honest @ 81.74%

Continuation of [[2026-05-16 — post-deliver 3-bug fix block — viled-0 stat, palette FP, was_price clarified]]. После доставки run-21 xlsx operator провёл два круга forensic top-10 review. **Третий раунд правок** закрыл оставшиеся структурные FP-классы.

Целый каскад инсайтов от operator вылез: один screenshot Kilian 7,5/50/100 мл вскрыл, что viled catalog API даёт ОДИН minPrice на семью variant-ов; следующий screenshot Tom Ford Electric Cherry вскрыл волюм-mismatch чище через bucket veto; следующий round указал на палетка-палетка и хайлайтер-парфюм cross-class; финальный round обнажил «same family different sub-type» — EDT × EDP, face cream × eye cream, primer × eye-primer.

## 8 коммитов в этой continuation-сессии

| Commit | Изменение |
|---|---|
| `e504c37` | **Viled multi-variant top-up** через PDP `__NEXT_DATA__` — `attributes[]` + `selectAttributes` дают per-variant pricing для multi-size SKUs (12.5% inventory). Compound sku_id `{viled_id}-{itemPriceId}`. Plus GA was_price MSRP fallback (`regular > current → was = regular`). |
| `4569a4e` | **Bucket stems №2**: `футляр`→case, `массаж`→device, `мист`→spray. Закрывает FP top-3 после viled multi-variant. |
| `ccbba58` | **`_cyrillic_leading_words` scan-all**: was-stop-at-first-English. Закрывает Lancome Teint Idole × Idole рефил FP — English-leading names with Cyrillic product-type word в середине. |
| `3f2df46` | **Top-10 forensic round-1 fixes**: priority `набор`→set override, palette sub-bucketing v1 (eyeshadow/corrector/highlighter), `хайла`/`хаила`/`очист`/`кисть` stems, multipack detection from name+volume. Закрывает 7 FPs из top-10. |
| `dfa4ab7` | **Top-10 forensic round-2 — sub-bucketing v3**: perfume concentration (EDT/EDP/Parfum/Cologne), body-part qualifier on skincare (cream_face/cream_eye/...), compound `крем-основа`→foundation_base + `база`→foundation_base, default-face heuristic, `_all_cyrillic_words` для body-part scan. Закрывает оставшиеся 5 FPs. |
| `1e5d3a4`... | (включает несколько early commits в начале session — wiring fix etc) |

## Полная архитектура bucket-veto после рефакторинга

```
Phase 1: priority overrides (набор/сет → set)
Phase 2: refill strip (рефил- prefix dropped)
Phase 3: base stem scan (compounds FIRST, then singles)
Phase 4: sub-bucketing:
  - palette → palette_eyeshadow / _corrector / _highlighter / _blush / _bronzer
  - perfume → perfume_parfum / _edp / _edt / _cologne
  - skincare base ∈ {cream, serum, oil, lotion, gel, balm, fluid, mask,
                     essence, elixir, milk, foam, soap, scrub, patch,
                     toner, cleanser, spray, mist, foundation_base}
    → scan ALL Cyrillic words for body part qualifier
    → suffix _face / _eye / _hands / _body / _feet / _lips / _lashes /
              _brows / _neck / _decolletage
    → if no qualifier AND base ∈ DEFAULT_FACE_BASES → _face
```

## Run-21 evolution через 5 раундов фиксов

| Стадия | Matches | Rate | Top-1 FP |
|---|---:|---:|---|
| Initial (multi-variant + first stems) | 5 060 | 100% | Tom Ford палетка теней × парфюм (volume FP) |
| + Palette/eyeshadow stems | 5 060 | 100% | Same volume FP closed earlier |
| Multi-variant + 8-slug overrides | 4 754 | 100% | Kilian 100ml × 100ml real signal |
| **+ Viled per-variant** | 4 731 | 90% | Lancome Teint Idole × Idole рефил (English-lead) |
| **+ Cyrillic scan-all + bucket stems №2** | 4 573 | 87% | Multiple same-family different sub-type |
| **+ Sub-bucketing v3 (final)** | **4 312** | **82%** | All real — Darphin Hydraskin Light 182% (genuine markup) |

**Net session delta**: -748 cross-class FPs vetoed, rate dropped to 82% honest reflection.

## User-confirmed FP fixes

All from operator's forensic review of top-10 deltas:

| FP | Root cause | Fix |
|---|---|---|
| Tom Ford палетка теней × парфюм (586%) | bucket veto missing palette/тен stems | `палетк`+`тен`→palette stems |
| Kilian 100ml × 100ml (586%) | viled stored 100ml at 7,5ml price (catalog API minPrice + first-attr volume) | Multi-variant PDP top-up emits one row per size |
| Lancome Teint Idole × Idole рефил | viled English-leading name → bucket=None | `_cyrillic_leading_words` scans all words |
| Bobbi Brown brush cleanser × brush | both bucket=None | `очист`→cleanser + `кисть`→brush_tool |
| Кылиан рефил геля душа × парфюм | `гель` stem doesn't catch genitive «геля» | `гель`→`гел` (shorter stem) |
| Travel set × standalone parfum | first word «парфюмерный» → perfume; «набор» далее | Priority pass: «набор» anywhere → set bucket |
| Хайлайтер × рефил парфюм | viled `й→и` normalizer breaks `хайлайт` stem | `хайла`+`хаила` stems |
| Палетка теней × палетка коррекции | both bucket=palette | palette sub-buckets |
| EDT × EDP (Tom Ford / Chloe / Hugo Boss) | both bucket=perfume | perfume_edt / perfume_edp sub-buckets |
| EDT × Дух (Hugo Boss Alive) | both bucket=perfume | perfume_parfum sub-bucket |
| Face cream × eye cream (Clinique) | both bucket=cream | body-part sub-bucketing + default-face heuristic |
| Face primer × eye primer (Bobbi Brown) | viled bucket=None / GA cream | `база`+`крем-основа` → foundation_base + body-part scan |
| Палетка `парфюмированное мыло` (run-19) | `парфюм` stem catches «парфюмированное» adjective | `парфюм`→`парфюмерн` (narrowed) |
| Соар × парфюм | (handled by above) | (handled) |

## Tests added in session

| Test | Class | Purpose |
|---|---|---|
| `test_rejects_perfumed_soap_vs_perfume` | regression | парфюмированное мыло × парфюмерная вода Creed |
| `test_rejects_shower_gel_refill_vs_perfume` | regression | геля душа × parfum (genitive stem) |
| `test_mascara_vs_face_mask_does_not_alias` | regression | маскара (transliteration) vs face mask |
| `test_plural_mascara_form_maps_to_mascara_bucket` | regression | плюрал туши → mascara |
| `test_candle_does_not_bucket_as_perfume` | regression | ароматическая свеча — drop `аромат` стем |
| `test_atomizer_is_not_perfume` | regression | empty atomizer bottle |
| `test_eyeliner_genitive_form_resolves` | regression | водостойкий лайнер «лаин» stem |
| `test_english_leading_name_resolves_cyrillic_product_type` | scan-all | Teint Idole пудра — middle of name |
| `test_palette_eyeshadow_vs_palette_corrector_does_not_match` | sub-bucket | Pro Palette × Pro Conceal |
| `test_brush_cleanser_vs_brush_tool_does_not_match` | bucket | средство очистки × кисть |
| `test_perfume_set_does_not_match_standalone_perfume` | priority override | Парфюм. набор × Парфюм |
| `test_highlighter_vs_perfume_refill_does_not_match` | transliteration | хаилаитер × рефил |
| `test_eau_de_toilette_does_not_match_parfum` | concentration | EDT × Дух |
| `test_eau_de_toilette_does_not_match_eau_de_parfum` | concentration | EDT × EDP |
| `test_face_base_does_match_face_primer_alias` | compound + body-part | viled primer matches GA face primer |
| `test_face_base_does_not_match_eye_base` | body-part | primer face × primer eye |
| `test_face_cream_does_not_match_eye_cream` | default-face | bare cream × cream_eye |

**Unit suite: 583/583** (started session at 556).

## Production artifacts

- xlsx **`reports/2026-W20.xlsx`** 801+ KB redelivered to Telegram (message_id=42)
- DB snapshot **`prices.db`** active, all backups intact in working dir
- 8 commits pushed `04060d5..dfa4ab7`

## Что осталось open

- **«MAC Pro Palette × MAC Pro Conceal» подобные same-bucket same-brand FPs** требуют subword/marketing-name-comparison — отдельная архитектурная работа.
- **viled price drift между прогонами** — `realMinPrice` от catalog API может отличаться от per-variant `realPrice` от PDP `__NEXT_DATA__`. Сейчас берём PDP-данные, что более точно.
- **GA was_price mid-run** — на следующий GA crawl должны видеть price.regular fallback и заполнять was_price для всех discounted SKUs.

## Решения / pattern-discoveries

- [[Matcher v3 — sub-bucketing для perfume concentration и body-part qualifier]]
- [[Viled multi-variant — catalog API minPrice + PDP __NEXT_DATA__ per-variant top-up]]
- [[Default-face heuristic — bare skincare buckets без body part qualifier → _face]]
- [[GA was_price MSRP fallback через price.regular]]

## Связано

- [[2026-05-16 — post-deliver 3-bug fix block — viled-0 stat, palette FP, was_price clarified]]
- [[2026-05-16 — retry hardening + brand-alias unlock + 5337 matches 105pct rate]]
- [[2026-05-16 — production wiring fix + run-19 re-enum +82pct goldapple +9.86pp recall + 8 brand slugs unlocked]]
- [[2026-05-16 — matcher v2.8 + brand-pages discovery + multi-variant capture]]
