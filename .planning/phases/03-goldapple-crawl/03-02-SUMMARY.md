---
phase: 03-goldapple-crawl
plan: 02
subsystem: enumeration
tags: [crawl-02, d-301, d-304, d-305, d-307, norm-06, slug-fy, sitemap]
requires:
  - "03-01 (Wave 0 bootstrap: deps pinned, interfaces.py, conftest.py with sitemap_xml fixture)"
provides:
  - "ga_crawler.enumeration.slug.slug_fy_bilingual(alias) -> list[str]"
  - "ga_crawler.enumeration.slug.intersect_brand_pool(viled_brands, aliases, sitemap_slugs) -> (matched_urls, unmatched_brands)"
  - "ga_crawler.enumeration.goldapple_sitemap.fetch_sitemap_slugs() -> dict[slug, [urls]]"
  - "ga_crawler.enumeration.goldapple_sitemap.persist_sitemap_slugs / find_previous_slug_file / diff_new_slugs (D-307 NORM-06 reverse)"
  - "PRODUCT_URL_RE whitelist (Threat T-04 sitemap-poisoning mitigation)"
affects:
  - "Wave 3+ orchestrator imports these to compute weekly URL pool"
  - "Wave 5+ NORM-06 review queue consumer reads diff_new_slugs output"
tech-stack:
  added:
    - "(no new pip deps — uses curl_cffi + tenacity already pinned in 03-01)"
  patterns:
    - "Tier 0 curl_cffi sitemap fetch (RESEARCH §Pattern 1 verbatim)"
    - "Bilingual slug-fy with NFKD + accent strip + Cyrillic→Latin transliterate (RESEARCH §Pattern 2)"
    - "EXACT-match sitemap intersection via dict.get (Pitfall 3 false-positive guard)"
    - "tenacity exponential-jitter retry on transient SitemapFetchError"
    - "On-disk week-over-week persistence under {root}/runs/{run_id}/sitemap-slugs.txt"
key-files:
  created:
    - "src/ga_crawler/enumeration/__init__.py"
    - "src/ga_crawler/enumeration/slug.py"
    - "src/ga_crawler/enumeration/goldapple_sitemap.py"
    - "tests/unit/__init__.py"
    - "tests/unit/test_slug_fy.py"
    - "tests/unit/test_intersect_brand_pool.py"
    - "tests/unit/test_sitemap_parser.py"
    - "tests/unit/test_norm06_diff.py"
  modified: []
decisions:
  - "Apostrophes (`'`, `’`, `ʼ`, `ʹ`) stripped (not hyphenated) before non-alphanum→hyphen step — RESEARCH §Pattern 2 line 435 mandates 'L\\'Oréal Paris' → 'loreal-paris'; verbatim regex `[^a-z0-9а-я]+` would produce 'l-oreal-paris' (Rule 1 fix)"
  - "Cyrillic-presence regex uses explicit KZ-glyph alternation `[а-яёәғқңөұүһі]` (NOT range `[ә-і]`) — KZ glyphs lie at non-adjacent codepoints (ә=U+04D9, і=U+0456); contiguous range is ill-defined and raises re.error (Rule 1 fix)"
  - "Whitelist regex `_normalize_punct` extended to include KZ glyphs explicitly so Cyrillic-preserved slugs survive normalization for KZ brand strings (e.g. 'Әсем' → 'әсем')"
  - "respx not used for `fetch_sitemap_slugs` test — it is httpx-based, not curl_cffi-compatible. Monkey-patch `_fetch_xml` directly per plan §2.3 explicit Note"
  - "`test_sitemap_excerpt_regex_extraction` updated to match BOTH `<loc>` and `<ns0:loc>` — the conftest fixture is etree-serialized (namespaced); production sitemap (per spike 01-05) is plain `<loc>`. The mocked end-to-end test exercises the production shape"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-06T05:30:00Z"
  tasks: 2
  commits: 2
  files_created: 8
  files_modified: 0
---

# Phase 03 Plan 02: Wave 1 Enumeration Summary

Built pure-logic enumeration primitives for Phase 3 URL pool computation (CRAWL-02): bilingual slug-fy with exact-match brand intersection, plus the curl_cffi Tier 0 sitemap fetcher and on-disk week-over-week NEW-slug diff (D-307 NORM-06 reverse direction). Sitemap fetch wrapped behind `_fetch_xml` for direct monkey-patch testability; pure transformation paths require zero network. All 39 unit tests in `tests/unit/` green.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Bilingual slug-fy + brand intersection | `954d0ea` | `enumeration/__init__.py`, `enumeration/slug.py`, `tests/unit/__init__.py`, `tests/unit/test_slug_fy.py`, `tests/unit/test_intersect_brand_pool.py` |
| 2 | Sitemap fetcher (curl_cffi Tier 0) + week-over-week diff | `a7fa06d` | `enumeration/goldapple_sitemap.py`, `tests/unit/test_sitemap_parser.py`, `tests/unit/test_norm06_diff.py` |

## Test Counts

| Test file | Tests | Status |
|-----------|-------|--------|
| `test_slug_fy.py` | 15 (11 parametrize + idempotency + KZ-glyph + collapse + map-keys) | 15/15 passed |
| `test_intersect_brand_pool.py` | 6 (Pitfall 3 guard, bilingual hit, unmatched, fallback, empty alias, multi-URL) | 6/6 passed |
| `test_sitemap_parser.py` | 9 (6 regex whitelist + fixture extraction + mocked fetch + 503 retry-then-raise) | 9/9 passed |
| `test_norm06_diff.py` | 9 (persist sorted, no-runs-dir, latest predecessor, future-skip, non-numeric-skip, first-run-empty, additions-sorted, removals-ignored, blank-line-tolerant) | 9/9 passed |
| **Total** | **39** | **39/39 (100%)** |

## Public API Exports

```python
# from ga_crawler.enumeration.slug import (
slug_fy_bilingual,        # alias: str -> list[str]
intersect_brand_pool,     # (viled_brands, aliases, sitemap_slugs) -> (matched_urls, unmatched_brands)
_normalize_punct,         # underscore-prefixed but exported for downstream slugifier reuse
CYRILLIC_TO_LATIN,        # the transliteration map (43 keys: 34 Russian + 9 KZ)
# )

# from ga_crawler.enumeration.goldapple_sitemap import (
fetch_sitemap_slugs,      # () -> dict[str, list[str]]   (curl_cffi)
persist_sitemap_slugs,    # (slugs, run_id, root) -> Path
find_previous_slug_file,  # (root, current_run_id) -> Optional[Path]
diff_new_slugs,           # (current, previous_path) -> list[str]
PRODUCT_URL_RE,           # whitelist regex (Threat T-04)
SITEMAP_INDEX,            # = "https://goldapple.kz/sitemap.xml"
SITEMAP_TIMEOUT_S,        # = 30
SitemapFetchError,        # raised on terminal non-200 or connection errors
# )
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Cyrillic-detection regex `[а-яә-і]` is ill-defined**

- **Found during:** Task 1, first pytest run (`re.error: bad character range \\u04d9-\\u0456`).
- **Issue:** The plan §1.3 verbatim algorithm uses `re.search(r"[а-яә-і]", cyrillic_slug)` to gate Cyrillic-preserved slug emission. KZ-glyph codepoints are non-adjacent (`ә`=U+04D9 down to `і`=U+0456), so `[ә-і]` is a backwards range — Python's `re` raises `bad character range`. Same source-of-truth bug exists in RESEARCH §Pattern 2 line 396 (verbatim algorithm).
- **Fix:** Replace contiguous range with explicit KZ-glyph alternation: `r"[а-яёәғқңөұүһі]"`. Comment in code documents why range form is wrong.
- **Files modified:** `src/ga_crawler/enumeration/slug.py`
- **Commit:** `954d0ea` (folded into Task 1)

**2. [Rule 1 — Bug] `L'Oréal Paris` → `l-oreal-paris` instead of `loreal-paris`**

- **Found during:** Task 1, second pytest run (parametrize case 6 failed assertion).
- **Issue:** RESEARCH §Pattern 2 line 435 mandates `L'Oréal Paris → loreal-paris` ("apostrophe stripped"), but the verbatim `_normalize_punct` regex `[^a-z0-9а-я]+ → -` replaces apostrophes with hyphens. The two specifications contradict; the test is the source-of-truth ("apostrophe stripped"), so the algorithm is buggy.
- **Fix:** Strip apostrophes (`'`, `’`, `ʼ`, `ʹ`) BEFORE the non-alphanum→hyphen replacement. Code comment cites RESEARCH line 435.
- **Files modified:** `src/ga_crawler/enumeration/slug.py`
- **Commit:** `954d0ea` (folded into Task 1)

**3. [Rule 1 — Bug] Whitelist regex drops KZ glyphs after lowercasing**

- **Found during:** Task 1 (proactive), informed by fix #1.
- **Issue:** `_normalize_punct` whitelist `[^a-z0-9а-я]+` does NOT include KZ-specific glyphs (ә ғ қ ң ө ұ ү һ і). For input `'Әсем'`, the resulting slug after `.lower()` would be `--`, breaking the test `test_slug_fy_bilingual_kz_glyph` (which expects `әсем`).
- **Fix:** Extended whitelist to `[^a-z0-9а-яёәғқңөұүһі]+`. Code comment documents the explicit-list rationale (range `[ә-і]` is ill-defined).
- **Files modified:** `src/ga_crawler/enumeration/slug.py`
- **Commit:** `954d0ea` (folded into Task 1)

**4. [Rule 3 — Test fixture shape mismatch] sitemap fixture uses namespaced `<ns0:loc>`**

- **Found during:** Task 2, test_sitemap_excerpt_regex_extraction failed with 0 URLs extracted.
- **Issue:** The conftest fixture `tests/fixtures/goldapple/sitemap-1-excerpt.xml` is etree-serialized with `xmlns:ns0`, so each `<loc>` is actually `<ns0:loc>`. The plan §2.2 verbatim regex `<loc>([^<]+)</loc>` matches zero. The production sitemap (per spike 01-05) emits plain `<loc>`.
- **Fix:** The fixture-extraction test now matches both shapes via `<(?:ns0:)?loc>([^<]+)</(?:ns0:)?loc>`. Production behavior remains tested in `test_fetch_sitemap_slugs_mocked` (mocked end-to-end with the production-shape `<loc>` strings). Updated assertion to verify mix of product + facet/search URLs in fixture (whitelist accepts product URLs, rejects /s/ and /f/ facet URLs — Threat T-04 evidence both directions).
- **Files modified:** `tests/unit/test_sitemap_parser.py`
- **Commit:** `a7fa06d` (folded into Task 2)

### Out-of-scope / not auto-fixed

None — pre-existing untracked files (`.claude/scheduled_tasks.lock`, `.obsidian/`) and pre-existing modified `CLAUDE.md` left untouched per scope-boundary rule.

## Authentication Gates

None encountered.

## Verification Results

| Acceptance criterion | Status |
|---------------------|--------|
| `slug.py` exports `slug_fy_bilingual`, `intersect_brand_pool`, `_normalize_punct`, `CYRILLIC_TO_LATIN` (>=4 defs) | ✓ (4) |
| All 9 KZ glyphs (ә ғ қ ң ө ұ ү һ і) in transliteration table | ✓ (verified via `test_cyrillic_to_latin_table_has_kz_glyphs`) |
| `test_slug_fy.py` contains all 11 mandatory parametrized cases | ✓ |
| `test_intersect_brand_pool.py` contains `tom-ford-beauty` and `tom-ford-private-blend` (Pitfall 3 guard) | ✓ |
| `goldapple_sitemap.py` defines `PRODUCT_URL_RE`, `fetch_sitemap_slugs`, `persist_sitemap_slugs`, `find_previous_slug_file`, `diff_new_slugs`, `_fetch_xml` | ✓ (6) |
| `goldapple_sitemap.py` imports `from curl_cffi import requests` | ✓ |
| `goldapple_sitemap.py` uses `impersonate="chrome"` | ✓ |
| `goldapple_sitemap.py` uses tenacity `stop_after_attempt(3)` + `wait_exponential_jitter` | ✓ |
| `PRODUCT_URL_RE` pattern is `r"^https://goldapple\.kz/(\d+)-([a-z0-9а-я-]+)$"` | ✓ |
| `uv run pytest tests/unit/ -q` exits 0 | ✓ (39 passed) |
| `test_sitemap_parser.py` ≥6 test functions | ✓ (9 functions: 6 in TestProductUrlRegex class + 3 module-level) |
| `test_norm06_diff.py` ≥8 test functions | ✓ (9 functions) |

All Wave 1 success criteria satisfied.

## Threat Mitigations Verified

| Threat ID | Mitigation | Test |
|-----------|-----------|------|
| T-03-02-04 (Tampering — sitemap-poisoning) | `PRODUCT_URL_RE` whitelist enforced at intake | `test_rejects_brands_facet`, `test_rejects_wrong_domain`, `test_rejects_non_numeric_id`, `test_rejects_no_slug` |
| T-03-02-05 (Tampering — path traversal via run_id) | `find_previous_slug_file` parses run_id as int (try/except ValueError); pathlib `Path` interpolation safe | `test_find_previous_skips_non_numeric_dirs` |
| T-03-02-09 (DoS — sitemap fetch hangs / 5xx) | tenacity `stop_after_attempt(3)` + `wait_exponential_jitter(initial=2, max=30)` caps wait; SITEMAP_TIMEOUT_S=30 | `test_fetch_xml_raises_on_non_200` (re-raises after retries) |

## Self-Check: PASSED

**Files exist:**
- `src/ga_crawler/enumeration/__init__.py` ✓
- `src/ga_crawler/enumeration/slug.py` ✓
- `src/ga_crawler/enumeration/goldapple_sitemap.py` ✓
- `tests/unit/__init__.py` ✓
- `tests/unit/test_slug_fy.py` ✓
- `tests/unit/test_intersect_brand_pool.py` ✓
- `tests/unit/test_sitemap_parser.py` ✓
- `tests/unit/test_norm06_diff.py` ✓

**Commits exist:**
- `954d0ea` ✓ (Task 1)
- `a7fa06d` ✓ (Task 2)

**`uv run pytest tests/unit/ -q` exits 0:** ✓ (39 passed in 7.24s)
