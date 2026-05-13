---
phase: 08-parser-bug-fixes
plan: 02
type: execute
wave: 1
status: complete
completed: 2026-05-14
---

# Plan 08-02 Summary — PARSE-FIX-01 goldapple volume block

## What shipped

- `src/ga_crawler/parsers/goldapple_microdata.py:270` — new `_extract_volume_block(html: str) -> Optional[str]` helper using selectolax 0.4 Lexbor backend with LOCAL import (D-806 isolation).
- `src/ga_crawler/parsers/goldapple_microdata.py:418` — `parse_pdp` callsite wired: `raw_volume_text = _extract_volume_block(html) or name or None`.
- `pyproject.toml` — selectolax pin bumped `>=0.3,<0.4` → `>=0.4.7,<0.5` (D-805). Installed 0.4.8.
- `uv.lock` — resynced for new selectolax constraint.
- `tests/parsers/test_goldapple_volume_block.py` — 7 tests (4 in plan + 3 added via parametrized round-trip across Givenchy/STEREOTYPE/Armani fixture buckets).

## Stats

- **selectolax version installed:** 0.4.8 (latest as of 2026-05-14).
- **Helper insertion line:** `src/ga_crawler/parsers/goldapple_microdata.py:270` (after `_extract_strikethrough`, before `_extract_availability`).
- **Final selector string:** `'div:lexbor-contains("объём")'` — **single LOWERCASE form**, NO `i` flag (see Pitfalls below).
- **Test count delta:** 818 → 822 (full suite, `-m "not live"`).
- **Existing tests preserved:** 2 pre-existing `test_cli_deliver.py` failures (documented in 08-01 SUMMARY) — no new regressions.
- **3 atomic commits:** `test(08-02): RED` (9df9c55) → `chore(08-02): bump selectolax` (f8fa492) → `feat(08-02): GREEN` (cf247b3).

## Critical deviations from plan

### Selector form: lowercase NOT uppercase, NO `i` flag

PATTERNS.md / RESEARCH.md prescribed `'div:lexbor-contains("ОБЪЁМ" i)'` (uppercase + case-insensitive flag). **This returns 0 matches against the live HTML.** Empirical probe of `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` showed:

- Live HTML emits the label in **lowercase**: `"объём / мл"`.
- selectolax 0.4.8 Lexbor's `i` case-insensitive flag operates **byte-level** for non-ASCII characters — uppercase `"ОБЪЁМ"` with `i` flag does NOT match lowercase `"объём"` because the byte sequences differ (UTF-8: Ё=`D0 81` lowercase=`D1 91`).

**Fix:** match the lowercase literal `"объём"` directly. shape-table.md grep confirms 0 occurrences of "ОБЪЕМ" (with Е) and 2 of "ОБЪЁМ" (in table headers only); all 25/30 volumed PDPs emit `объём` lowercase per W0 evidence. No Ё+Е dual-selector needed.

### Strategy A (sibling-walk) insufficient for Armani DOM shape — replaced with ancestor-walk + regex extraction

PATTERNS.md prescribed Strategy A (sibling-walk for digit-bearing sibling) + Strategy B (label.text(deep=True) fallback). Empirical DOM probe showed:

- **STEREOTYPE-style** (Plan 08-02 Bug #1 evidence fixture): Strategy A works — `<div>12</div>` is a direct sibling of `<div>объём / мл</div>`.
- **Armani-style** (radio-group variant): Strategy A FAILS — siblings are other label divs, not digits. Digits live as separate radio-button text nodes deeper in the DOM. `label.text(deep=True)` was also insufficient — Strategy B returned `"объём / мл"` with no digit.
- **Givenchy baseline:** same Armani-shape; original Strategy B equally failed.

**Replacement strategy (commit cf247b3):**

1. Find label via `tree.css('div:lexbor-contains("объём")')`.
2. Walk up ancestor chain (max depth 3) until ancestor's `text(deep=True)` contains a digit (regex `\d+(?:[.,]\d+)?`).
3. Extract first numeric token (multi-variant SKUs: picks first variant — matches Plan 08-04 v1.1 `[0]` single-variant policy).
4. Extract unit (`мл/г/гр/oz/унц`) from label text.
5. Return `f"{value} {unit}"` (e.g. `"50 мл"`) — format `parse_volume` accepts.

**Why this matters:** `parse_volume` requires `<digit>{whitespace}мл` adjacent. Composed strings like `"объём / мл50100"` (unit before digits) or `"12объём / мл"` (digits before label-with-unit-at-end) ALL fail `parse_volume`. Probing parse_volume directly confirmed only digit-then-unit-adjacent forms succeed.

## Pitfalls encountered (vs RESEARCH.md inventory)

| Pitfall | RESEARCH.md | Actual outcome |
|---------|-------------|----------------|
| 1 (`:lexbor-contains` leading-space `i` flag) | feared | **avoided** by using lowercase literal — never needed `i` flag. |
| 2 (Ё vs Е variant) | feared | **N/A** — 25/30 PDPs use Ё (and lowercase ё); 0 PDPs use Е. Single-selector form is sufficient. |
| 8 (Modest `Node` vs Lexbor `LexborNode` boundary cross) | warned | **respected** — helper takes raw `html: str` and instantiates its own Lexbor tree; never crosses parser boundaries. |
| 9 (selectolax deprecation warning) | warned | **non-issue** — `pyproject.toml` has no `filterwarnings = error` mode. Modest deprecation visible in test output but non-fatal. |
| NEW: byte-level `i` flag on Cyrillic | **not in RESEARCH.md** | **discovered during GREEN** — see "Selector form" deviation above. Should be added to project hazards. |
| NEW: parse_volume needs digit-then-unit adjacent | **not in RESEARCH.md** | **discovered during GREEN** — see "Strategy" deviation above. |

## Verification (per Plan 08-02 success_criteria)

- [x] Phase 8 Success Criteria #2 (goldapple_volume_norm non-null on non-volumeless PDPs): all 3 fixture buckets yield non-None volume_norm via parse_volume round-trip.
- [x] Phase 8 Success Criteria #4 preserved: 822 tests (target ~808, exceeded due to round-trip parametrization).
- [x] STEREOTYPE-style + Armani-style PDPs produce parsed `volume_raw` ("12 мл" / "50 мл" respectively) — matcher's `volume_norm IS NOT NULL` filter now admits these rows.
- [x] Existing 60+ goldapple parser tests still green (D-807 blast-radius isolation verified).
- [x] 3 atomic commits per D-811 (TDD discipline preserved despite mid-flight session resume).

## Next

- **Plan 08-03** (W2, depends on 08-02): goldapple brand+name pivot to h1-spans strategy (PARSE-FIX-02). Per 08-01 SUMMARY line 41-48, the original microdata-walk premise is INVALIDATED — Plan 08-03 must reference SKILL.md and use `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]` selectors instead.
- **Plan 08-05** (W3, depends on 08-02 + 08-03 + 08-04): null-rate gate (PARSE-FIX-04) + SMOKE rotation (PARSE-FIX-05) + doc cascade.

## Open items deferred

- **Multi-variant `[*]` handling** — currently picks first numeric token (matches Plan 08-04 viled `attributes[0]` policy). If Phase 9 brand-coverage canary surfaces multi-variant misses (e.g. SKU sold only in 100ml size but matcher reads 50ml), flag for v1.2.
- **Selectolax i-flag-on-Cyrillic hazard** — add to project hazards documentation in W3 (Plan 08-05 doc cascade).
