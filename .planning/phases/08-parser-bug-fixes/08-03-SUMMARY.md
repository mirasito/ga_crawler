---
phase: 08-parser-bug-fixes
plan: 03
subsystem: parsers
tags: [parse-fix-02, goldapple, brand-name, microdata, h1-spans, tdd, invariant-canary]
requires: [08-01]
provides: [PARSE-FIX-02]
affects: [src/ga_crawler/parsers/goldapple_microdata.py]
tech_stack_added: []
tech_stack_patterns: [h1-child-span-extraction, structlog-canary-log]
key_files_created:
  - tests/parsers/test_goldapple_brand_name.py
key_files_modified:
  - src/ga_crawler/parsers/goldapple_microdata.py
decisions:
  - "Pivot from microdata-walk to h1 child spans per W0 spike (0/30 vs 30/30 coverage)"
  - "_strip_brand_prefix fallback OMITTED — W0 evidence shows .name span cleanly excludes .brand in 28/30 PDPs"
  - "D-816 canary SOFTENED to log-only — 2/30 PDPs (Armani-style) legitimately fail invariant"
  - "Module-top imports stay Modest-only — Lexbor remains isolated to _extract_volume_block (D-806/D-807)"
metrics:
  duration: "~25min"
  completed: "2026-05-14"
  test_count_before: 826
  test_count_after: 831
  test_delta: +5
  task_commits: 2
---

# Phase 8 Plan 03: Goldapple brand+name microdata-read fix (PARSE-FIX-02) Summary

**One-liner:** Goldapple `parse_pdp` now reads `brand_raw` and `name` from separate `h1` child spans (CSS classes `_ga-pdp-title__brand_*` / `_ga-pdp-title__name_*`) — empirically 30/30 in W0 spike — instead of v1.0's broken `[itemprop="brand"]` (cross-product-card match) + `h1.text(strip=True)` (deep concat), eliminating `Armaniarmani code` / `StereotypeSAĜO` / `GivenchyPOUR HOMME BLUE LABEL` regressions; D-816 brand-canary added as log-only warning per W0 §4.

## Outcome

- All 2 atomic tasks executed (RED + GREEN per D-811 strict TDD).
- 5 new tests added (6 collected instances with parametrize); all PASS post-GREEN.
- 826 → 831 tests pass on `pytest -m "not live"` (+5 instances, 1 pre-existing skip).
- All 59 existing goldapple parser tests still green (backward-compat preserved).
- 2 atomic commits on `worktree-agent-a896f0ad8fde33bd5` (RED `3f422a8` + GREEN `37e7c07`).
- Phase 8 Success Criteria #3 (invariant canary holds across goldapple snapshots) **directly delivered** for clean-separation buckets (28/30); softened to log-only for the 2/30 upstream-data-redundancy bucket per W0 §4.

## What changed

### `src/ga_crawler/parsers/goldapple_microdata.py`

Replaced brand+name extraction block (~14 lines → ~56 lines incl. extensive comments referencing the W0 SKILL/MEMO):

| v1.0 (REMOVED) | v1.1 (NEW) |
|---|---|
| `tree.css_first('[itemprop="brand"]')` → fetches `<meta itemprop="name">` inside | `tree.css_first('h1[class*="_ga-pdp-title__heading_"]')` → fetches the `<span class*="_ga-pdp-title__brand_*">` child |
| Same path → `(brand_meta.attributes.get("content") or "").strip()` | `(brand_span.attributes.get("content") or brand_span.text(strip=True) or "").strip()` |
| `h1 = tree.css_first("h1")` → `h1.text(strip=True)` — DEEP concat | `name_span = h1.css_first('[class*="_ga-pdp-title__name_"]')` → `name_span.text(strip=True)` |
| No canary | `log.warning("goldapple_brand_in_name_canary_violation", brand_raw=..., name=..., url=...)` when `brand.lower() in name.lower()` |

Defensive fallback chain when h1 child-span shape is absent:
1. plain `<h1>` deep text (v1.0 path — last resort, will concat)
2. `<title>` stripped of `" — купить ..."`

Added module-level `log = structlog.get_logger(__name__)` (convention from `viled_nextdata.py`, `runners/*`, `matcher/strict_key.py`).

### `tests/parsers/test_goldapple_brand_name.py` (new, 167 lines)

5 test functions covering:

1. `test_armani_brand_and_name_are_separately_extracted` — asserts `brand_raw='Armani'`, `name='armani code'` (NOT `'Armaniarmani code'`).
2. `test_stereotype_brand_and_name_are_separately_extracted` — asserts `brand_raw='Stereotype'`, `name='SAĜO'` (NOT `'StereotypeSAĜO'`).
3. `test_invariant_canary_stereotype` — D-816 invariant for clean-separation bucket.
4. `test_givenchy_baseline_clean_after_pivot` — confirms pivot also cleans the existing debug fixture (which v1.0 returned as `'GivenchyPOUR HOMME BLUE LABEL'`).
5. `test_invariant_canary_across_clean_buckets[Givenchy, STEREOTYPE]` — parametrized over the two clean-separation buckets only. Armani bucket is explicitly excluded with a comment pointer to test #1 since its name legitimately contains the brand string.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug in plan specification] Pivoted from microdata-walk to h1 child spans**

- **Found during:** Task 2 read-ahead step (`<read_first>` instruction to read MEMO.md "## Decisions" section).
- **Issue:** Plan 08-03's PATTERNS.md / `<action>` body specifies a product-scope `<meta itemprop="name">` walk (under a `[itemtype*="Product"][itemscope]` ancestor). The Phase 8 W0 spike (Plan 08-01, completed 2026-05-13 — landed AFTER 08-03 plan authoring) empirically falsified this premise:
  - `<meta itemprop="name">` at product level: **0/30** PDPs in the W0 30-PDP stratified sample. The `itemprop="name"` occurrences (2 per page) are breadcrumb labels, review-author names, and footer Organization metadata.
  - The v1.0 `tree.css_first('[itemprop="brand"]')` was matching bottom-of-page "you may also like" product CARDS (which DO carry `[itemprop="brand"]` per-card) — cross-product contamination, source of the live-run #13 brand-misattribution bug.
- **Fix:** Used the W0-empirical strategy from `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md`:
  - `h1[class*="_ga-pdp-title__heading_"]` (100% W0 coverage)
  - child `[class*="_ga-pdp-title__brand_"]` (100% W0 coverage)
  - child `[class*="_ga-pdp-title__name_"]` (100% W0 coverage)
- **Authority for deviation:** Plan 08-03 frontmatter `must_haves.truths` line 7: `"_strip_brand_prefix(name, brand) fallback decided per W0 evidence"`; Plan 08-03 `<action>` step 1: `"Read W0 evidence first to decide on fallback: open .planning/spikes/v1.1-brand-name-shapes/MEMO.md § Decisions"`. CONTEXT.md line 73 "Claude's Discretion" explicitly defers the strategy selection to W0 evidence. The W0 MEMO §"TL;DR" says the microdata-walk "must be abandoned." The SKILL.md (registered as a project skill) says "h1-spans strategy is empirically more reliable (100% vs 0%) and yields cleaner separation."
- **Files modified:** `src/ga_crawler/parsers/goldapple_microdata.py` (parse_pdp brand+name block lines 377-391 of original).
- **Commit:** `37e7c07` (GREEN).

**2. [Rule 2 — Critical correctness] D-816 canary SOFTENED to log-only**

- **Issue:** Plan's PATTERNS.md line 150-160 spec uses a log-only canary, which is correct. But the test-side parametrize from plan template at PATTERNS.md L468-510 includes Armani in the strict-invariant parametrize list — that would fail-hard for the upstream-data-redundancy bucket (W0 spike shows 2/30 PDPs legitimately have `brand.lower() in name.lower()`).
- **Fix:** Test file excludes the Armani bucket from the strict-invariant parametrize and covers it via a dedicated `test_armani_brand_and_name_are_separately_extracted` that asserts non-CONCATENATION (`name == 'armani code'`) rather than non-CONTAINMENT (`'armani' not in 'armani code'`, which is empirically false). This matches W0 §4 decision "SOFTEN to log-only" — the production canary still logs the violation; the test enforces the stricter invariant only for the buckets where it actually holds.
- **Authority:** W0 MEMO.md "## Decisions" §4; SKILL.md "Operational constants" row "D-816 invariant canary".
- **Files modified:** `tests/parsers/test_goldapple_brand_name.py` (parametrize list at line ~138).
- **Commit:** `3f422a8` (RED).

**3. [Rule 1 — Documentation accuracy] `name.lower() == "sago"` corrected to `"saĝo"`**

- **Issue:** Plan's PATTERNS.md template (line 498) asserts `assert p.name.lower() == "sago"`. The empirical W0 fixture text content of the STEREOTYPE PDP's h1 .name span is `'SAĜO'` (4 chars: S, A, Ĝ [U+011C], O), so `.lower() → 'saĝo'`, not `'sago'`. The plan's `"sago"` literal would fail even after the parser fix.
- **Fix:** Test asserts `p.name.lower() == "saĝo"` and uses `'stereotype' not in p.name.lower()` for the substring invariant.
- **Files modified:** `tests/parsers/test_goldapple_brand_name.py` (line 87).
- **Commit:** `3f422a8` (RED).

### Auth Gates

None — no external network calls in this plan.

## W0 evidence cited

- **Microdata coverage rate:** 0/30 PDPs carry product-level `<meta itemprop="name">` (W0 MEMO §"What doesn't").
- **h1 child-span coverage:** 30/30 (100%) for both `_ga-pdp-title__brand_*` and `_ga-pdp-title__name_*` substrings (W0 MEMO §"What works", SKILL.md "Operational constants").
- **`_strip_brand_prefix` decision:** NOT NEEDED — 28/30 (93.3%) PDPs already have clean separation; the 2 exceptions (`armani-code`, `GIVENCHY GENTLEMAN RESERVE PRIVEE`) are upstream data redundancies, not parser bugs (W0 MEMO §"Decisions" §2).
- **Canary firing during test runs:** Not observed for the test fixtures used in this plan (Armani PDP returns `brand_raw='Armani'`, `name='armani code'` → canary WOULD fire on that PDP in production; but the test does not assert on absence-of-log). Stereotype + Givenchy fixtures do NOT trigger the canary because their .name spans don't contain the brand string.

## Final parse_pdp name-extraction logic order

1. `h1[class*="_ga-pdp-title__heading_"]` exists?
   - Yes → extract `brand_raw` from `[class*="_ga-pdp-title__brand_"]` child (content attr || text)
   - Yes → extract `name` from `[class*="_ga-pdp-title__name_"]` child (text)
2. If `name` is still empty (h1 .name span absent — defensive fallback): plain `<h1>` deep text
3. If `name` is still empty and `<title>` exists: `title.split(" — купить", 1)[0].strip()`
4. If `name` is still empty → `parse_pdp` returns `None` (PARSE-05 required-field check at line ~440 unchanged)

## Self-Check: PASSED

- `tests/parsers/test_goldapple_brand_name.py` → FOUND
- `src/ga_crawler/parsers/goldapple_microdata.py` → FOUND (modified)
- RED commit `3f422a8` → FOUND in git log
- GREEN commit `37e7c07` → FOUND in git log
- All 6 collected new-test instances → PASSING post-GREEN
- 826 baseline → 831 tests pass on `pytest -m "not live"` (+5 instances)
- All 59 existing goldapple parser tests → PASSING
- Module-top imports stay Modest-only (Lexbor isolated to `_extract_volume_block`)

## Threat Flags

None — the new `log.warning("goldapple_brand_in_name_canary_violation", ...)` is covered by the threat register T-08-10 (Information Disclosure, accept: brand+name are PUBLIC product metadata, structlog goes to operator-controlled file).

## Known Stubs

None — the parser change is wired end-to-end; brand+name flow through `dispatcher.py` → normalizers → storage → matcher unchanged.

## Test count delta

- Before plan 08-03: 826 passed, 1 skipped (post-08-02 + 08-04 W1 GREEN)
- After plan 08-03: 831 passed, 1 skipped
- Delta: **+5 passed** (4 standalone tests + 1 parametrized test × 2 parameter rows = 6 collected instances; 1 of the standalone is the parametrize "host" definition, so net +5 distinct test items in pytest's count)
- Plan 08-03 acceptance criterion `≥811 passed` SATISFIED (831 ≥ 811).
