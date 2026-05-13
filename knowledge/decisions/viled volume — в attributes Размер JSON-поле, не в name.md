---
tags: [decision, viled, parser, next-data, volume, v1-1-finding]
date: 2026-05-13
phase: v1.1-planning
status: planned-fix
impacts: [PARSE-FIX-03]
confidence: medium-needs-spike
---

# viled volume — в attributes Размер JSON-поле, не в name

## Утверждение

viled `__NEXT_DATA__` JSON-структура содержит **dedicated volume field** в `props.pageProps.attributes[]` массиве с `name == "Размер"` и `value` типа `"200мл + 200мл + 250мл"` (multipack) или `"100мл"` (single).

Парсер v1.0 НЕ читает этот field — вместо этого делает `raw_volume_text=name` и полагается на regex по названию.

## Evidence

- In-repo fixture `tests/fixtures/viled/viled-pdp-multipack.html` подтверждает shape: `{name: "Размер", value: "200мл + 200мл + 250мл"}` присутствует в `props.pageProps.attributes`
- DB sample run #13 viled snapshots:

| brand | name | volume_raw | volume_norm |
|---|---|---|---|
| Jo Malone London | Одеколон Myrrh & Tonka Cologne Intense Limited Edition, 100 мл | (весь name) | (Decimal('100'), 'ml', 1) |
| Frederic Malle | Парфюмерная вода Contre-Jour | (весь name) | NULL |
| Creed | Парфюмерная вода Wild Vetiver | (весь name) | NULL |

Jo Malone работает только потому что "100 мл" в названии явно. Frederic Malle Contre-Jour и Creed Wild Vetiver — `volume_norm=NULL`.

- viled fixture multipack shape — clothing PDP. **Beauty PDP path не верифицирован** — нужен 30-min Wave-0 probe в Phase 8.

## Confidence

- **HIGH** на field existence (clothing fixture показал shape)
- **MEDIUM** на exact JSON path для beauty PDP — clothing PDP может иметь чуть другую структуру, нужна 15-min capture одной live beauty PDP перед coding

## Decision

**Phase 8 PARSE-FIX-03**: добавить `_extract_volume_from_nextdata(item, a0)` helper в `viled_nextdata.py` читающий `props.pageProps.attributes[].name == "Размер"`. Fallback на regex по `name` только если поле отсутствует (preserves backward-compat для PDP без attributes).

**Phase 8 sub-spike**: Wave-0 probe против live viled beauty PDP — подтвердить exact JSON path (`props.pageProps.item.attributes` vs `props.pageProps.attributes` vs `props.pageProps.product.attributes`) и сохранить как `.planning/spikes/v1.1-viled-volume-path/MEMO.md`.

## Multipack handling

`"200мл + 200мл + 250мл"` — multipack notation. Существующий volume normalizer (`normalizers/volume.py`) уже умеет multipack через 24-entry UNIT_TABLE + 3-layer grammar (Set of N × M unit → N [optional unit] × M unit → keyword-only). Должно работать out-of-the-box если получим raw `value` строку.

## Alternative considered

- Continue with regex-on-name — REJECTED: ловит только товары с "X мл" в названии явно. Frederic Malle и Creed (premium бренды с минималистическими названиями) systematically missed.
- Move volume extraction в normalizer with `__NEXT_DATA__` knowledge — REJECTED: ломает pipe-and-filter (normalizer должен работать на parsed structs, не на raw JSON)

## Sources

- `tests/fixtures/viled/viled-pdp-multipack.html` (in-repo clothing fixture)
- `.planning/research/STACK.md` Bug #3 finding
- `.planning/research/v1.1-PARSER-BUG-FINDINGS.md` § Bug #3
- DB sample run #13 viled snapshots
