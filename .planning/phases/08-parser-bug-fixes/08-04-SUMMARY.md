---
phase: 08-parser-bug-fixes
plan: 04
type: execute
wave: 1
status: complete
completed: 2026-05-14
---

# Plan 08-04 Summary — PARSE-FIX-03 viled volume from __NEXT_DATA__

## What shipped

- `src/ga_crawler/parsers/viled_nextdata.py:114` — new `_extract_volume_from_nextdata(a0: dict) -> Optional[str]` helper reading the empirically-verified JSON path `props.pageProps.attributes[0].attributes[]`.
- `src/ga_crawler/parsers/viled_nextdata.py:251` — `parse_pdp` callsite wired: `raw_volume_text=_extract_volume_from_nextdata(a0) or name`.
- `src/ga_crawler/parsers/viled_nextdata.py:259` — `_extract_volume_from_nextdata` added to `__all__`.
- `tests/parsers/test_viled_volume_from_nextdata.py` — 11 tests (6 helper-unit + 5 round-trip across 4 fixtures including new Contre-Jour from W0).
- `tests/unit/test_viled_nextdata_parser.py:321` — existing anchor test `test_raw_volume_text_passthrough_is_name` renamed to `test_raw_volume_text_extraction_or_fallback`, assertion flipped per D-812.

## Stats

- **Helper insertion line:** `src/ga_crawler/parsers/viled_nextdata.py:114` (after `_map_stock_state`, before `_coerce_int`).
- **Test count delta:** 803 baseline → 822 total suite (`-m "not live"`) when combined with Plan 08-02 GREEN. Viled side alone added 11 tests + 1 modified.
- **Tests passing:** 38/38 in scoped viled run (`tests/parsers/test_viled_volume_from_nextdata.py` + `tests/unit/test_viled_nextdata_parser.py`).
- **Contre-Jour fixture handling:** confirmed legitimate-None per D-814 — fallback to `name` runs, `volume_norm` stays NULL, SKU excluded from matcher.
- **Exact assertion line modified:** `tests/unit/test_viled_nextdata_parser.py:321-339` (rename + flexibility assertion replacing rigid `== p.name` anchor).
- **2 atomic commits:** `test(08-04): RED` (214e8ee) → `feat(08-04): GREEN` (cc40621).

## Behavior matrix (verified across 4 fixtures)

| Fixture | Размер attr present | Helper returns | parse_pdp.raw_volume_text |
|---------|---------------------|----------------|--------------------------|
| `viled-pdp-discounted.html` (Frederic Malle, beauty, 50 мл) | yes (`"50 мл"`) | `"50 мл"` | `"50 мл"` |
| `viled-pdp-multipack.html` (beauty bundle) | yes (`"200мл + 200мл + 250мл"`) | `"200мл + 200мл + 250мл"` | multi-volume |
| `viled-pdp-407682.html` (clothing) | yes (`"S"`) | `"S"` | `"S"` → NORM-03 `parse_volume("S")` returns None → `volume_norm = NULL` (D-814 path, intended) |
| `_live-2026-05-13-contre-jour.html` (Frederic Malle Contre-Jour, no size) | no | None | falls back to `name` (full product title) → parse_volume returns None → `volume_norm = NULL` (D-814 legitimate-None) |

## Deviations from plan

- None. Helper template + callsite wiring + anchor-test flip implemented verbatim per PATTERNS.md lines 192-220 + 222-229 + 606. All 4 fixture acceptance rows of `08-VALIDATION.md` pass.

## Multi-variant deferral

Per RESEARCH.md "Open Question 2": v1.1 reads only `attributes[0]` mirroring existing parser behavior. Multi-variant `attributes[*]` iteration deferred to v1.2 — will be reconsidered if Phase 9 brand-coverage canary surfaces multi-variant misses on viled side.

## Verification (per Plan 08-04 success_criteria)

- [x] Phase 8 Success Criteria #1 CONTRIBUTED: viled side now produces clean `volume_norm` for beauty SKUs with Размер attr. Combined with Plan 08-02 goldapple volume + Plan 08-03 brand+name (W2), the matcher's strict-key SQL JOIN can produce matches.
- [x] Phase 8 Success Criteria #4 preserved: 822 tests after Plans 08-02 + 08-04 GREEN (above plan target ~818).
- [x] Frederic Malle Contre-Jour case (legitimate-None per D-814) handled — fallback to `name` runs, downstream filter excludes SKU from matcher.
- [x] STRIDE T-08-13 (malformed JSON) mitigated via isinstance guards.
- [x] STRIDE T-08-16 (clothing "S" disambiguation) mitigated via existing `normalizers/volume.parse_volume("S") -> None`.

## Next

- **Plan 08-03** (W2): goldapple brand+name h1-spans (PARSE-FIX-02). Independent of this plan; together with 08-02 + 08-04 completes the matcher-relevant parser surface.
- **Plan 08-05** (W3): null-rate gate (PARSE-FIX-04) + SMOKE rotation + doc cascade.
