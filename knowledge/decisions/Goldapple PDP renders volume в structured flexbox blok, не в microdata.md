---
tags: [decision, goldapple, parser, microdata, volume, v1-1-finding]
date: 2026-05-13
phase: v1.1-planning
status: planned-fix
impacts: [PARSE-FIX-01, PARSE-FIX-04]
---

# Goldapple PDP renders volume в structured flexbox blok, не в microdata

## Утверждение

Goldapple PDP на 2026-05-13 рендерит объём в **отдельном structured-блоке** с числом и подписью, БЕЗ `itemprop="size"` или другой semantic микроразметки:

```
[78]  ОБЪЁМ / МЛ
```

Не в title (там `STEREOTYPE sago`), не в JSON-LD Product schema (которой нет на goldapple — они используют microdata), не в `<meta itemprop="size">`.

## Evidence

- Live PDP screenshot (2026-05-13) от пользователя: бренд STEREOTYPE / SKU sago / нишевая парфюмерия / 75 ОБЪЁМ / МЛ / 47 080 ₸ со скидкой 20%
- DB sample run #13 (`prices.db` snapshots WHERE retailer='goldapple' AND run_id=13): `volume_norm IS NULL` у 88/88 SKU несмотря на `current_price` у всех 88
- Stack research (Context7-verified): selectolax 0.4 Lexbor backend поддерживает `:lexbor-contains("ОБЪЁМ" i)` pseudo-class и `LexborSelector.text_contains()` — exact primitive чтобы найти label-ячейку и пройти к sibling'у с числом

## Implications

- **Парсер v1.0** в `src/ga_crawler/parsers/goldapple_microdata.py:358-359` делает `raw_volume_text = name or None` — passthrough из title. На STEREOTYPE shape: `name="STEREOTYPE sago"` → regex `(\d+)\s*мл` не находит → `volume_norm=NULL`
- **Downstream cascade**: `matcher/strict_key.py:58` D-402 фильтр требует `volume_norm IS NOT NULL` → 0 goldapple rows pass → 0 matches → empty xlsx per_sku_deltas и assortment_gaps sheets
- **v1.0 audit пропустил это** потому что unit-тесты используют `_debug-product-page.html` фикстуру (Givenchy от Phase 1 spike) где volume в title `Pour Homme 50 мл` — на ней парсер работает

## Decision

**Phase 8 PARSE-FIX-01**: добавить `_extract_volume_block(tree)` helper в `goldapple_microdata.py` использующий selectolax 0.4 Lexbor `:lexbor-contains("ОБЪЁМ" i)` для поиска label-cell, затем walk к sibling holding число.

**Phase 8 mandatory sub-spike**: 30-PDP shape-sampling в `.planning/spikes/v1.1-brand-name-shapes/` ДО любого кода — не overfitting на единственный STEREOTYPE screenshot. Различные shapes (multipack, sample, gift-set, out-of-stock, English names, Cyrillic names) могут требовать разных селекторов.

**Phase 8 PARSE-FIX-04**: null-rate sanity gate — run помечается `failed` с reason `parser_drift_null_volume_rate` если `goldapple_volume_norm` null rate >50%. Предотвращает silent regression в будущем.

**Phase 9 TEST-HARNESS-06**: Pydantic validation на `SqliteSnapshotWriter` boundary — `RawProduct` model с `volume_raw: NonEmptyStr | None` raise на write если schema violated. Defense-in-depth.

## Alternative considered

- Move to `lxml` + `parsel` (XPath) — REJECTED: 5MB native dep, нулевой incremental capability над selectolax 0.4
- JSON-LD probing — REJECTED: goldapple не emits JSON-LD Product schema (только microdata)
- Hardcoded regex `re.search(r'(\d+)\s*мл', html)` — REJECTED: ловит volume из любого места страницы (отзывы, related products, header), не привязан к product structure

## Sources

- `tests/fixtures/goldapple/_debug-product-page.html` (in-repo Givenchy fixture)
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` § Bug #1
- Context7 `/websites/selectolax_readthedocs_io_en` — Lexbor `:contains` API
- Live PDP screenshot 2026-05-13 (user-provided)
