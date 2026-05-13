---
tags: [decision, phase-8, viled, parser, json-path, research-correction]
date: 2026-05-13
decision-id: RES-08-01
status: active
---

# viled Размер JSON path — nested attributes[0].attributes[], не item.attributes[]

Для PARSE-FIX-03 (viled volume extraction) descriptive-attributes массив лежит на пути `props.pageProps.attributes[0].attributes[]`, а **не** `props.pageProps.item.attributes[]` как тентативно предполагали `.planning/research/STACK.md` и CONTEXT.md D-803. Empirical trace в Phase 8 research session против трёх существующих in-repo fixtures (`viled-pdp-407682.html`, `viled-pdp-multipack.html`, `viled-pdp-discounted.html`) показал что `pp.item.attributes` is `None` на всех трёх, а `pp.attributes[0].attributes` содержит массив `{name, value}` объектов где один из элементов имеет `name == "Размер"`.

Это **load-bearing override** — без коррекции Plan 08-04 строил бы helper против nullable path и тихо возвращал `None` для каждого viled SKU. Researcher этой фазы поймал ошибку через прямой read in-repo fixtures + JSON path navigation, а не через документацию (которой у viled NextData нет).

## Why nested attributes[0]

viled NextData структура — price-variant array. Каждый элемент `pp.attributes[i]` это отдельный price-variant SKU (для multipack или multi-size beauty), и descriptive-attributes (Размер, Цвет, etc.) лежат внутри каждого варианта как `attributes[i].attributes[]`.

Для v1.1 Plan 08-04 читает только `[0]` (single-variant convention из existing v1.0 code per D-217 Pitfall 2 «beauty SKUs typically have ≤1 size variant»). Multi-variant iteration deferred to v1.2 если Phase 9 brand-coverage canary surfaces misses.

## Clothing vs beauty disambiguation

Тот же `Размер` attribute карьерит clothing size (`"S"`, `"L"`) ИЛИ volume (`"50 мл"`). Helper `_extract_volume_from_nextdata` НЕ branches на category — возвращает raw `Размер` value verbatim. Disambiguation делегируется существующему `normalizers/volume.parse_volume` который возвращает `None` для non-volume строк. Phase 4 matcher SQL filter `volume_norm IS NOT NULL` уже исключает clothing SKUs из join — мы не регрессируем.

## Rejected alternatives

- **`pp.item.attributes[]`** — `None` на всех 3 in-repo fixtures, был бы silent-fail
- **Branching helper по category** — лишний state, fragile к новым категориям; делегирование `parse_volume` чище
- **Multi-variant iteration `[*]`** — over-engineering для v1.1 single-variant baseline; flag на Phase 9 canary

## Connected

- [[viled volume — в attributes Размер JSON-поле, не в name]] (parent decision, точный path был unclear)
- `.planning/phases/08-parser-bug-fixes/08-RESEARCH.md` § viled NextData attributes (lines 358-440 — empirical trace evidence)
- `.planning/phases/08-parser-bug-fixes/08-04-PLAN.md` (implements helper)
- `tests/fixtures/viled/viled-pdp-407682.html` (clothing "S" disambiguation evidence)
- `tests/fixtures/viled/viled-pdp-discounted.html` (beauty "50 мл" volume evidence)
