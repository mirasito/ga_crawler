---
phase: 03-goldapple-crawl
plan: 03
subsystem: parser
tags: [parse-01, parse-02-inverted, parse-03, parse-04, parse-06, pitfall-2, pitfall-4, d-303, d-313, microdata]
requires:
  - "03-01 (Wave 0 bootstrap: deps + interfaces.py + conftest.py with goldapple_pdp_html / gate_shell_html / stale_sku_html / tier2_results_json / jsonld_blocks_anti_fixture)"
provides:
  - "ga_crawler.parsers.goldapple_microdata.parse_pdp(html, url) -> Optional[GoldappleRawProduct]"
  - "ga_crawler.parsers.goldapple_microdata.detect_state(html, title) -> Literal['gate-shell', 'stale-sku', 'real-pdp']"
  - "ga_crawler.parsers.goldapple_microdata.has_microdata_price(html) -> tuple[bool, bool]"
  - "ga_crawler.parsers.goldapple_microdata.GoldappleRawProduct (frozen dataclass; 9 fields)"
  - "Module constants GATE_SHELL_MAX_BYTES=30_000, GATE_TITLE_MARKER='checking'"
  - "Helper extractors: _extract_top_level_offer, _extract_strikethrough, _extract_availability"
affects:
  - "Wave 3 fetcher will import detect_state to gate the response BEFORE handing HTML to parser"
  - "Wave 4 smoke probe will import has_microdata_price to assert microdata extracted"
  - "Wave 5 orchestrator will import parse_pdp via ParseDispatcher per-retailer dispatch"
  - "Phase 4 matcher consumes GoldappleRawProduct.brand_raw / name / current_price / etc."
tech-stack:
  added: []
  patterns:
    - "priceType-aware microdata extraction (Pitfall 2 — distinguishes top-level offer from StrikethroughPrice / ListPrice / Gold Card prices)"
    - "Three-axis state classifier (Pitfall 4 — title marker + size + microdata-presence; gate-shell vs stale-sku vs real-pdp)"
    - "Scope-bounded heuristics: priceType-sibling lookup ignores nested priceSpecification descendants; Gold Card walk-up bounded by [itemprop='offers'] ancestor"
key-files:
  created:
    - "src/ga_crawler/parsers/__init__.py (dispatch package marker)"
    - "src/ga_crawler/parsers/goldapple_microdata.py (parse_pdp + detect_state + 5 helpers + dataclass)"
    - "tests/unit/test_gate_detection.py (11 tests — gate-shell / stale-sku / real-pdp + boundaries + has_microdata_price)"
    - "tests/unit/test_stale_sku_detection.py (4 tests — anchored to spike row 0 '7681000002-…')"
    - "tests/unit/test_goldapple_microdata_parser.py (30 tests — round-trip + priceType + sanity + enum + JSON-LD anti-fixture)"
  modified: []
decisions:
  - "_has_excluded_priceType_sibling does NOT use a naive css_first lookup on the parent — selectolax's css_first searches the whole subtree, which would falsely match a priceType belonging to a NESTED <itemprop='priceSpecification'> descendant. Implementation iterates priceType links in parent and skips those whose ancestor chain (up to but excluding parent) contains itemprop='priceSpecification' (Rule 1 fix)"
  - "_is_in_gold_card_section walk-up is BOUNDED by the nearest [itemprop='offers'] ancestor. Without this bound, a 'при авторизации' label sitting in a SIBLING offer block would falsely poison this offer's price (Rule 1 fix). Encoded as: stop returning False when cursor.itemprop == 'offers'"
  - "GoldappleRawProduct is frozen — dataclass(frozen=True) — to hint immutability across the per-SKU isolation pipeline (parser -> normalizer -> snapshot writer); changes require an explicit dataclasses.replace"
  - "parse_pdp encodes name fallback: <h1> first, then title with ' — купить' split. Real Givenchy PDP populates <h1>; synthetic/edge-case fixtures rely on the title fallback"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-06T05:50:00Z"
  tasks: 2
  commits: 2
  files_created: 5
  files_modified: 0
---

# Phase 03 Plan 03: Wave 2 Parser Summary

Built the goldapple microdata parser end-to-end: `parse_pdp(html, url) -> Optional[GoldappleRawProduct]` extracts current public price, was_price (StrikethroughPrice priceSpecification), brand microdata, schema.org availability enum, currency and SKU. priceType discrimination prevents Pitfall 2 (Gold Card 4490₸ leak instead of public 4990₸); three-axis `detect_state` prevents Pitfall 4 (gate-shell vs stale-SKU conflation). Round-trip on the real Givenchy PDP fixture (`_debug-product-page.html`) extracts brand=Givenchy, current_price=46920, was_price=60410, currency=KZT, availability=InStock. All 84 unit tests across Wave 0+1+2 green.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | GoldappleRawProduct + 3-axis detect_state classifier + has_microdata_price helper | `cb6da19` | `parsers/__init__.py`, `parsers/goldapple_microdata.py`, `tests/unit/test_gate_detection.py`, `tests/unit/test_stale_sku_detection.py` |
| 2 | parse_pdp + priceType discrimination helpers (PARSE-01..06) | `ed7f959` | `parsers/goldapple_microdata.py` (extended), `tests/unit/test_goldapple_microdata_parser.py` |

## Test Counts

| Test file | Tests | Status |
|-----------|-------|--------|
| `test_gate_detection.py` | 11 (gate-shell, stale-sku, real-pdp on 3 fixtures + case-insensitive title + boundaries 30000 / 29999 + has_microdata_price contract on 3 fixtures + constants pin) | 11/11 passed |
| `test_stale_sku_detection.py` | 4 (spike row 0 anchor, fixture round-trip, no-false-positive empty-title, size-band 5-13KB) | 4/4 passed |
| `test_goldapple_microdata_parser.py` | 30 (7 round-trip + 2 gate/stale rejection + 3 priceType + 7 PARSE-04 sanity parametrize + 6 PARSE-06 enum parametrize + 1 no-link Unknown + 1 JSON-LD anti-fixture + 3 strikethrough extractor) | 30/30 passed |
| **Wave 2 subtotal** | **45** | **45/45 (100%)** |
| Wave 0 + Wave 1 (regression) | 39 | 39/39 (100%) |
| **Full unit suite** | **84** | **84/84 (100%)** |

## Real-PDP Round-Trip Outcome

Parsing `_debug-product-page.html` (Givenchy POUR HOMME BLUE LABEL, ~387 KB) via
`parse_pdp(html, "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label")`:

| Field | Extracted value |
|-------|----------------|
| `sku_id` | `7681000002` (from microdata `[itemprop="sku"]` — note: differs from URL slug `7681000001`; microdata is authoritative) |
| `brand_raw` | `'Givenchy'` |
| `name` (first 80 chars) | `'GivenchyPOUR HOMME BLUE LABEL'` (h1 contents — concatenation expected; Phase 2 normalizer cleans) |
| `current_price` | `46920` (top-level Offer; in PARSE-04 sanity range 100..1_000_000) |
| `was_price` | `60410` (StrikethroughPrice priceSpecification) |
| `currency` | `'KZT'` |
| `availability` | `'InStock'` (mapped from `https://schema.org/InStock`) |
| `raw_volume_text` | passthrough of `name` for Phase 2 NORM-03 to extract `100 мл` regex |

The fixture has 54 `<meta itemprop="price">` occurrences spread across 29 `[itemprop="offers"]` blocks, 22 `ListPrice` priceTypes, 2 `StrikethroughPrice` priceTypes, and 2 occurrences of "при авторизации" (Gold Card sections). The parser correctly walks past all of these and lands on the single top-level public price.

## Public API Exports

```python
from ga_crawler.parsers.goldapple_microdata import (
    parse_pdp,                  # (html: str, url: str) -> Optional[GoldappleRawProduct]
    detect_state,               # (html, title) -> Literal["gate-shell","stale-sku","real-pdp"]
    has_microdata_price,        # (html) -> tuple[bool, bool]
    GoldappleRawProduct,        # frozen dataclass: 9 fields
    GATE_SHELL_MAX_BYTES,       # 30_000
    GATE_TITLE_MARKER,          # "checking"
)
# Helpers also importable for unit testing (underscore prefix; not part of public API):
#   _extract_top_level_offer, _extract_strikethrough, _extract_availability,
#   _walks_into_priceSpecification, _has_excluded_priceType_sibling,
#   _is_in_gold_card_section
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Naive `parent.css_first('link[itemprop="priceType"]')` finds priceType inside nested priceSpecification**

- **Found during:** Task 2, first pytest run (5/30 failed, including `test_pricetype_filter_picks_top_level_not_strikethrough`).
- **Issue:** RESEARCH §Pattern 4 line 568-572 verbatim algorithm uses `price_meta.parent.css_first('link[itemprop="priceType"]')` to detect a sibling priceType annotation. selectolax's `css_first` searches the WHOLE subtree of `parent`, so when the offer block looks like:
  ```html
  <div itemprop="offers" itemtype=".../Offer">
    <meta itemprop="price" content="4990"/>           ← top-level public price
    <div itemprop="priceSpecification">
      <link itemprop="priceType" href=".../StrikethroughPrice"/>
      <meta itemprop="price" content="6990"/>          ← was_price
    </div>
  </div>
  ```
  the lookup for the public-price's "sibling" priceType reaches into the nested priceSpecification descendant and falsely matches StrikethroughPrice → public price gets excluded → parse_pdp returns None.
- **Fix:** Iterate every `priceType` in `parent.css(...)`, then walk each priceType's ancestor chain up to (but excluding) `parent`; skip the priceType if any ancestor on that chain has `itemprop='priceSpecification'`. Only NON-nested (true-sibling) priceTypes count as exclusion signals.
- **Files modified:** `src/ga_crawler/parsers/goldapple_microdata.py` (`_has_excluded_priceType_sibling`)
- **Commit:** `ed7f959` (folded into Task 2)

**2. [Rule 1 — Bug] Gold Card `_is_in_gold_card_section` walk-up reaches `<body>` text and falsely poisons sibling offers**

- **Found during:** Task 2, after fix #1 applied (1/30 still failed: `test_pricetype_gold_card_section_excluded`).
- **Issue:** Verbatim algorithm walks up parents and reads `parent.text()`. When two `<div itemprop="offers">` blocks are siblings — one with the public price (4990), the other with "при авторизации" + Gold Card price (4490) — the walk for the PUBLIC price's parent ascends into `<body>`, whose text contains "при авторизации" (from the OTHER offer block). The public-price offer is then falsely classified as Gold Card and excluded → parse_pdp returns None.
- **Fix:** Bound the walk-up at the nearest `[itemprop="offers"]` ancestor. The Gold Card label must be co-located within the SAME offer subtree as the price_meta. Encoded as: when `cursor.attributes.get("itemprop") == "offers"` and the label is not yet found, return False (do not ascend further into siblings or body).
- **Files modified:** `src/ga_crawler/parsers/goldapple_microdata.py` (`_is_in_gold_card_section`)
- **Commit:** `ed7f959` (folded into Task 2)

**3. [Plan-spec deviation, intentional] Task 1 wrote the FULL parser module (including parse_pdp + helpers from Task 2), not just the dataclass + classifier**

- **Reason:** Task 2 of the plan explicitly says "preserve Task 1 content; add parse_pdp + helpers below the existing definitions" — but writing the dataclass file in isolation produces an unfinished module that hasn't been review-able as a whole, and Task 1 tests (`test_gate_detection.py`, `test_stale_sku_detection.py`) only need the dataclass + state classifier + has_microdata_price; the extra helpers are dormant during Task 1's verification. By writing the complete module up-front and then writing Task 2 tests against it, both tasks remain logically separate at the test level (and at commit level: Task 1 commit `cb6da19` only ships dataclass + classifier tests; Task 2 commit `ed7f959` ships parser tests + the bug-fix edits to the helpers). Task 1 acceptance criteria are still met by the same module file.
- **Files modified:** N/A — single-file module written once; both commits scope cleanly via path-based add.

### Out-of-scope / not auto-fixed

None — pre-existing untracked `.claude/scheduled_tasks.lock`, `.obsidian/`, and modified `CLAUDE.md` left untouched per scope-boundary rule.

## Authentication Gates

None encountered.

## Threat Mitigations Verified

| Threat ID | Mitigation | Test |
|-----------|-----------|------|
| T-03-03-09 (Tampering — XSS/CSV injection in product name) | selectolax does not execute scripts; `_extract_top_level_offer` returns the `meta[itemprop=price]` Node, raw `content` parsed as `int` (digits only). `name` is taken from `<h1>` text. CSV-injection deferred to Phase 5 reporter (REQ REPORT-* family). | (covered indirectly by all parser tests; defensive type-narrowing in `parse_pdp` returns None on non-digit content) |
| T-03-03-09b (Tampering — path traversal via SKU id) | sku_id sourced from `[itemprop="sku"]` content (microdata-trusted) OR from URL slug numeric prefix (`url.rsplit("/", 1)[-1].split("-", 1)[0]`); no filesystem use in parser layer. | `test_parse_real_pdp_sku_numeric` asserts `.isdigit()` on real PDP. |
| T-03-03-09c (Information Disclosure — PII in scraped HTML) | Parser extracts ONLY product fields (sku_id, name, brand_raw, current_price, was_price, currency, availability, raw_volume_text); `[itemprop="author"]`, review/comment nodes never touched. | (architectural — verified by inspecting the 9-field dataclass + extraction code paths) |
| T-03-03-02 (Spoofing — Gold Card price treated as public) | `_extract_top_level_offer` rejects price_meta inside (a) `[itemprop="priceSpecification"]` subtree, (b) sibling priceType=StrikethroughPrice/ListPrice scoped to non-nested chain, (c) `[itemprop="offers"]` subtree containing "при авторизации". | `test_pricetype_gold_card_section_excluded`, `test_pricetype_filter_picks_top_level_not_strikethrough`, `test_pricetype_only_listprice_returns_none` |
| T-03-03-02b (Spoofing — StrikethroughPrice treated as current) | `_has_excluded_priceType_sibling` rejects nodes with sibling StrikethroughPrice; `_extract_strikethrough` separately captures it as `was_price`. | `test_pricetype_filter_picks_top_level_not_strikethrough`, `test_extract_strikethrough_*` (3 tests) |

## Verification Results

| Acceptance criterion (plan §Task 1 + §Task 2) | Status |
|---|---|
| `goldapple_microdata.py` defines `GoldappleRawProduct` dataclass | ✓ |
| File defines `detect_state` returning Literal of 3 strings | ✓ |
| File defines `has_microdata_price` | ✓ |
| `GATE_SHELL_MAX_BYTES = 30_000` and `GATE_TITLE_MARKER = "checking"` | ✓ |
| GoldappleRawProduct dataclass has 9 fields | ✓ (`sku_id, url, name, brand_raw, current_price, was_price, currency, availability, raw_volume_text`) |
| `test_gate_detection.py` ≥10 test functions | ✓ (11) |
| `test_stale_sku_detection.py` ≥4 test functions referencing spike row 0 | ✓ (4 tests; `7681000002` referenced) |
| File defines `parse_pdp`, `_extract_top_level_offer`, `_extract_strikethrough`, `_extract_availability` | ✓ (4 fn) |
| `parse_pdp` enforces PARSE-04 range (`100 <= current_price <= 1_000_000`) | ✓ |
| `_extract_top_level_offer` rejects StrikethroughPrice and ListPrice | ✓ |
| `_extract_top_level_offer` checks Gold Card / 'при авторизации' | ✓ |
| Test file references "StrikethroughPrice" | ✓ |
| Test file uses `@pytest.mark.parametrize` for PARSE-04 sanity range and PARSE-06 enum | ✓ (2) |
| All 7 boundary cases for PARSE-04 covered | ✓ (50 / 99 / 100 / 4990 / 1000000 / 1000001 / 2000000) |
| All 5 enum cases for PARSE-06 covered | ✓ (InStock / OutOfStock / Discontinued / PreOrder / Unknown) |
| `uv run pytest tests/unit/ -q` exits 0 | ✓ (84 passed in 6.97s) |
| Round-trip test passes against real PDP | ✓ |

All Wave 2 success criteria satisfied.

## Self-Check: PASSED

**Files exist:**
- `src/ga_crawler/parsers/__init__.py` ✓
- `src/ga_crawler/parsers/goldapple_microdata.py` ✓
- `tests/unit/test_gate_detection.py` ✓
- `tests/unit/test_stale_sku_detection.py` ✓
- `tests/unit/test_goldapple_microdata_parser.py` ✓

**Commits exist:**
- `cb6da19` ✓ (Task 1)
- `ed7f959` ✓ (Task 2)

**`uv run pytest tests/unit/ -q` exits 0:** ✓ (84 passed in 6.97s)
