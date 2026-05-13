---
name: spike-findings-v1.1-brand-name-shapes
description: Phase 8 W0 spike findings - goldapple PDP brand+name+volume shape buckets and the h1 .brand/.name CSS-class extraction strategy. Use when planning or implementing PARSE-FIX-01..05 in Phase 8, designing Phase 9 brand-coverage canaries, or any future parser-drift investigation against goldapple.kz.
---

# Phase 8 W0: Brand-Name-Volume Shape Findings (Reference Skill)

**Source memo:** [[../../.planning/spikes/v1.1-brand-name-shapes/MEMO]] (repo-local)
**Spike completed:** 2026-05-13
**Phase 8 status:** W0 complete, W1 unblocked
**Sign-off:** spike-only — operator review at W0 output-gate checkpoint

## What was decided

**Goldapple PDPs do NOT carry product-level `<meta itemprop="name">` microdata.** All 30/30 captured PDPs have brand+name inside h1 child spans (CSS classes `_ga-pdp-title__brand_*` + `_ga-pdp-title__name_*`, both substring-match). This **invalidates Plan 08-03's microdata-walk premise** and **strengthens** the Bug #1+#2 fix because the two spans are physically separate DOM nodes — no concatenation bug can occur when each is extracted independently. The "STEREOTYPEsago" / "Armaniarmani code" bugs were caused by the v1.0 parser doing a naive `h1.text()` deep-concat (or matching against bottom-of-page "you may also like" product CARDS, which DO carry `[itemprop="brand"]`). The h1-spans strategy fixes both.

| Field | Value |
|---|---|
| **Brand selector** | `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]` |
| **Name selector** | `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__name_"]` |
| **Volume block selector** | `selectolax 0.4 Lexbor`: `div:lexbor-contains("ОБЪЁМ" i)` |
| **Microdata fallback** | NONE — `<meta itemprop="name">` does not exist at product level |
| **`_strip_brand_prefix`** | NOT NEEDED (28/30 PDPs already have clean separation) |

## Shape buckets identified

| Bucket | Count | Description | Bug source |
|--------|-------|-------------|------------|
| stereotype-style | 16 (53%) | Brand title-case, name UPPERCASE (e.g. Creed/AVENTUS); or brand UPPERCASE (MAISON MARGIELA) | Bug #1 (pdp-16-stereotype-sago) |
| mixed-case | 11 (37%) | Brand and name both Title-Case / Sentence case | — |
| armani-style | 2 (7%) | Brand string is a substring of name ("Armani" in "armani code") — upstream data redundancy | Bug #2 (pdp-07-armani-code) |
| givenchy-baseline | 1 (3%) | Brand title-case, name lowercase ("Calvin Klein" / "cotton musk") | — |

## Operational constants for Phase 8

- **h1 .brand extraction:** 30/30 (100%) — read `[content]` attribute when present, fall back to text content
- **h1 .name extraction:** 30/30 (100%) — read text content
- **Brand whitespace:** goldapple sometimes appends a trailing space to brand (`"Givenchy "`) — preserve as-is, the normalizer strips
- **Volume block (ОБЪЁМ + МЛ flex-box):** 25/30 (83%) — 5 PDPs are non-volumed (eye creams, gels, patches) where None is legitimate
- **D-816 invariant canary `brand.lower() not in name.lower()`:** SOFTEN to log-only — 2/30 PDPs legitimately fail (armani-code, GIVENCHY GENTLEMAN); fail-hard would block runs on upstream data quality

## Stack constraints (do not deviate without re-spike)

- **selectolax 0.4.7+** required for Lexbor `:lexbor-contains` (case-insensitive volume word match). Modest stays default; Lexbor import is LOCAL to `_extract_volume_block` helper per D-806/D-807.
- **CSS class hash suffix is build-specific** (e.g. `_1yrfv_339` will change on goldapple deploy). Always substring-match (`class*=`), never full-string match.
- **`<title>` tag is concat-noise** — useful as last-resort fallback only ("Armani духи armani code  75 мл — купить в Алматы..." for pdp-07)
- **`[itemprop="brand"]` and `[itemprop="name"]` at product level do NOT exist** on goldapple PDPs as of 2026-05-13. The v1.0 parser's `tree.css_first('[itemprop="brand"]')` was matching against bottom-of-page recommendation cards — coincidental and unreliable.

## Bug evidence fixtures

- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` — Bug #1 evidence (brand=Stereotype, name=SAĜO, vol present)
- `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` — Bug #2 evidence (brand=Armani, name="armani code")
- `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — Bug #3 evidence (viled Frederic Malle, beauty PDP, Размер attr behavior)

## SMOKE_URLs rotation (Plan 08-05 D-818)

| Slot | URL | Shape covered |
|------|-----|---------------|
| 1 | `https://goldapple.kz/19000440474-stereotype-sago` | STEREOTYPE-style canonical |
| 2 | `https://goldapple.kz/19000195723-armani-code` | Armani-style canonical |
| 3 | `https://goldapple.kz/19000488678-givenchy-irresistible` (RETAINED from `runner/gates.py:34-35`) | Givenchy mass-market baseline |

## When to consult this skill

- `/gsd-execute-phase 8` (Plans 08-02, 08-03, 08-04, 08-05) — for h1 selector strategy, soften D-816, SMOKE rotation slots
- `/gsd-plan-phase 9` (TEST-HARNESS-01..06) — brand-coverage canary must use these h1 selectors when designing brand-presence assertions
- Any future "goldapple parser drift" investigation — start here to understand the structural DOM shape
- Phase 11 (DEPLOY-01..08) operator-deploy regression checks — SMOKE_URLs slots 1+2+3 are the smoke baseline

## Critical files (entry points)

- [[../../.planning/spikes/v1.1-brand-name-shapes/MEMO]] — full decision memo
- [[../../.planning/spikes/v1.1-brand-name-shapes/shape-table]] — 30-row per-PDP survey
- [[../../.planning/spikes/v1.1-brand-name-shapes/inspect_shapes]] — reference extraction logic
- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` — Bug #1 fixture
- `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` — Bug #2 fixture
- `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` — Bug #3 fixture
- `tests/conftest.py::goldapple_pdp_html_live_stereotype` — session-scoped loader
- `tests/conftest.py::goldapple_pdp_html_live_armani` — session-scoped loader
- `tests/conftest.py::viled_pdp_html_live_contre_jour` — session-scoped loader

## What was NOT decided here (defer to relevant phase)

- viled `Размер` attribute presence on Contre-Jour: requires Plan 08-04 RED test against the live fixture. The legitimate-None case per D-814 may or may not hold — let RED test confirm.
- selectolax 0.4.7 backend-fallback behavior under Lexbor: Plan 08-02 owns this. The 5 PDPs without ОБЪЁМ block (pdp-02, pdp-06, pdp-21, pdp-23, pdp-25) are correct None-targets.
- Phase 9 syrupy snapshot strategy against the 30 captured PDPs: TEST-HARNESS-01..06 owns this.
