---
phase: 08-parser-bug-fixes
plan: 01
type: execute
wave: 0
status: complete
completed: 2026-05-13
---

# Plan 08-01 Summary — W0 Shape-Sampling Spike

## What shipped

- `.planning/spikes/v1.1-brand-name-shapes/` with:
  - `capture.py` (Camoufox 0.4.11 30-PDP fetcher, reuses `GoldappleFetcher` per Plan-08-01 Task 2)
  - `sample_urls.py`, `curate_urls.py`, `probe_brands.py`, `fetch_contre_jour.py`, `inspect_shapes.py` (scratch helpers)
  - `pdp-NN-<slug>.html` × 30 (~6.8 MB total, retained for downstream Plan 08-02/03/04 RED tests)
  - `viled-contre-jour-408872.html` (Bug #3 source PDP)
  - `MEMO.md` — 1-paragraph TL;DR + per-bucket survey + Decisions + Handoff
  - `shape-table.md` — 30-row per-PDP categorization
  - `brand-probe.txt`, `shape-survey.txt`, `sampled-urls.py.snippet` (intermediate artifacts)
- `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` (Bug #1 evidence, 206 KB)
- `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` (Bug #2 evidence, 204 KB)
- `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` (Bug #3 evidence, 197 KB)
- `tests/conftest.py` — 3 new session-scoped fixture loaders
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — system-discoverable index for downstream agents

## Stats

- **30 PDPs captured** (D-801 satisfied), all HTTP 200, sizes 167–447 KB, total ~6.8 MB
- **Shape histogram:** 16× stereotype-style / 11× mixed-case / 2× armani-style / 1× givenchy-baseline
- **h1 .brand + .name extraction:** 30/30 (100%) — empirically validated across 30 captures
- **`<meta itemprop="name">` at product level:** 0/30 (Plan 08-03 premise INVALIDATED — pivot decision committed to MEMO + SKILL)
- **Volume `ОБЪЁМ` flex-box:** 25/30 (83%) — 5 PDPs are non-volumed products (eye creams etc.), legitimate None
- **PII canary:** CLEAN (Nuxt buildId UUID + `Cookie:true` i18n config flagged as false positives — no session tokens, no auth material)
- **Test suite:** 801 passed / 1 skipped / 2 pre-existing failures (`test_cli_deliver.py` x2 — confirmed pre-existing via git stash test against HEAD baseline)
- **Test count delta:** 0 added (this plan is fixtures + spike, not tests; W1 plans add the RED+GREEN test pairs)

## Critical findings (load-bearing for W1)

### Pivot decision: h1 `.brand` / `.name` CSS-class spans replace `<meta itemprop="name">` walking

Plan 08-03 premise of reading product brand+name via `<meta itemprop="name">` inside `[itemprop="brand"]` is **INVALID** against real goldapple HTML (2026-05-13 capture). The 2 `itemprop="name"` occurrences per page are breadcrumb + review-author + Organization metadata, NOT product. The v1.0 production parser's first-match walk was matching against bottom-of-page recommendation cards — coincidental and explains the cross-product contamination in run #13.

**New selectors:**
- Brand: `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]` — read `[content]` attr OR text
- Name: `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__name_"]` — read text
- CSS hash suffix (`_1yrfv_339`) is build-specific — always substring-match (`class*=`)

### `_strip_brand_prefix` fallback NOT NEEDED

28/30 PDPs have clean `.brand` / `.name` separation. 2 exceptions ("armani code", "GIVENCHY GENTLEMAN RESERVE PRIVEE") are upstream data redundancies — stripping would alter the user-facing product name. Plan 08-03 should NOT implement `_strip_brand_prefix`.

### D-816 invariant canary — soften to log-only

`brand.lower() not in name.lower()` fails on legitimate data 2/30 (7%). Convert to structured log warning so per-SKU regressions still get surfaced without failing the whole run.

### SMOKE_URLs rotation slots finalized (for Plan 08-05 PARSE-FIX-05)

| Slot | URL |
|------|-----|
| 1 (STEREOTYPE-style) | https://goldapple.kz/19000440474-stereotype-sago |
| 2 (Armani-style) | https://goldapple.kz/19000195723-armani-code |
| 3 (Givenchy baseline, RETAINED) | https://goldapple.kz/19000488678-givenchy-irresistible |

## Bucket substitutions from D-801

These D-801 brands are NOT carried in goldapple.kz/KZ sitemap (verified via `probe_brands.py`):
- Tom Ford, Jo Malone, Atelier Cologne, Diptyque, Chanel, YSL, Versace, Profumum, Le Labo, Maison Crivelli, Nasomatto, Amouage, Estée Lauder, Paco Rabanne, Narciso Rodriguez, hugo-boss-compound
- Cyrillic-uppercase RU brand slugs (Натура Сибирика, Чистая Линия, Лошадиная Сила, Невская Косметика) — transliterated to Latin (`natura-siberica`) or carried under different umbrella brands

Substitutes drawn from same shape category — coverage of brand-display variance preserved.

## Deviations from plan

1. **Task 1 (operator-action URL curation):** auto-sampled from sitemap via `curate_urls.py` instead of manual operator browse — approved by user at execute-phase start ("Auto-sample from sitemap.xml (Recommended)").
2. **Task 3 (operator-action shape-table fill):** `inspect_shapes.py` programmatically extracted brand/name/volume signal from all 30 captured HTMLs — operator visual inspection compressed to single-pass review of generated `shape-table.md`.
3. **Bucket substitutions from D-801:** noted above — operator-deferred per "from another bucket before commit" resume-signal.
4. **`<meta itemprop="name">` premise of Plan 08-03 invalidated** — pivot to h1-spans strategy documented in MEMO + SKILL.

## Verification (per Plan 08-01 success_criteria)

- [x] W0 spike output gate per CONTEXT.md D-808: shape-table.md commitable ✓ / 3 fixtures committed ✓ / SKILL.md created ✓
- [x] W1 unblocked: Plans 08-02 / 08-03 / 08-04 can target real DOM shapes via the h1-spans strategy documented in SKILL.md
- [x] No regression: existing test suite passes the same as on HEAD (801 / 1 skipped / 2 pre-existing failures)
- [x] No PII leaks in fixtures (V12 ASVS L1) — only Nuxt public buildId + i18n config flagged, no session/auth material
- [x] Contributes to Phase 8 Success Criteria #1 — does not satisfy it directly; W1 + W2 + W3 do

## Next

- Wave 1 (parallel): Plan 08-02 (PARSE-FIX-01 goldapple volume via Lexbor `:lexbor-contains`) + Plan 08-04 (PARSE-FIX-03 viled volume via `_extract_volume_from_nextdata`)
- Wave 2 (sequenced after 08-02): Plan 08-03 (PARSE-FIX-02 goldapple brand+name via h1-spans pivot) — **must reference SKILL.md for the strategy change**
- Wave 3: Plan 08-05 (PARSE-FIX-04 null-rate gate + PARSE-FIX-05 SMOKE rotation + doc cascade)
