---
phase: 02-project-skeleton-viled-crawl-storage
plan: 04
subsystem: parser+fetcher+enumerator
tags: [viled, curl_cffi, tenacity, nextdata, selectolax, tomllib, parse-dispatcher, sync]
wave: 1
type: execute
autonomous: true
status: complete
completed_date: 2026-05-07
duration_minutes: ~70
dependency_graph:
  requires:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md  # D-201..D-227
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-RESEARCH.md  # Pattern 1, 2, 9
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md  # A1, A2, A4, A10 REVISED
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-01-SUMMARY.md
    - tests/fixtures/viled/viled-pdp-407682.html
    - tests/fixtures/viled/viled-pdp-discounted.html
    - tests/fixtures/viled/viled-catalog-men-1310-page1.html
    - src/ga_crawler/interfaces.py  # FROZEN: ParseDispatcherProtocol
    - src/ga_crawler/parsers/goldapple_microdata.py  # FROZEN: dispatcher imports parse_pdp
  provides:
    - src/ga_crawler/parsers/types.py  # StockState Literal enum
    - src/ga_crawler/parsers/viled_nextdata.py  # __NEXT_DATA__-only parse_pdp + ViledRawProduct
    - src/ga_crawler/parsers/dispatcher.py  # ParseDispatcher concrete impl
    - src/ga_crawler/enumeration/viled_catalog.py  # fetch_catalog_urls
    - src/ga_crawler/fetchers/viled.py  # ViledFetcher + fetch_one_isolated + _fetch_html
    - src/ga_crawler/config.py  # ViledConfig.from_pyproject()
    - "+74 GREEN tests across 7 files; 247 → 321 (+74) passing; 13 → 5 skipped"
  affects:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md  # addendum 2026-05-07 closing A4 with v1-limitation note
    - "Plan 02-05 (Wave 4 orchestrator): imports ParseDispatcher, ViledFetcher, fetch_catalog_urls, ViledConfig"
    - "Phase 7 (ops follow-up): catalog pagination beyond page 1 needs reverse-engineered XHR call"
tech-stack:
  added: []
  patterns:
    - "PARSE-02 inversion: per-retailer extraction front-end (microdata for goldapple, __NEXT_DATA__ for viled) behind unified ParseDispatcher"
    - "Reading A price semantics: viled `attributes[0].price` = current/sale; `realPrice` = was/MSRP; was_price set only when realPrice > price"
    - "Stock-state derivation per WAVE0-PROBE A1 REVISED: `item.count > 0` + `item.purchaseType` ∈ {ONLINE, PREORDER}"
    - "Sync curl_cffi fetcher mirroring async GoldappleFetcher: same retry/isolation/run-loop shape, async stripped per D-225"
    - "Runtime SSR-pagination detection: walk page 1, detect server returning page 1 again on `?page=2`, break early; document as v1 limitation"
    - "Pitfall 1 enforced via `test_no_respx_imported` assertion + injectable `fetch_callable` parameter"
key-files:
  created:
    - src/ga_crawler/parsers/types.py  # 27 lines, StockState Literal
    - src/ga_crawler/parsers/viled_nextdata.py  # 224 lines, parse_pdp + ViledRawProduct + helpers
    - src/ga_crawler/parsers/dispatcher.py  # 57 lines, ParseDispatcher concrete impl
    - src/ga_crawler/enumeration/viled_catalog.py  # 267 lines, fetch_catalog_urls + retry decorator + helpers
    - src/ga_crawler/fetchers/viled.py  # 215 lines, ViledFetcher + fetch_one_isolated + _fetch_html + tenacity decorator
    - src/ga_crawler/config.py  # 72 lines, ViledConfig.from_pyproject()
  modified:
    - tests/unit/test_viled_nextdata_parser.py  # +23 GREEN tests
    - tests/unit/test_viled_stock_state.py  # +8 GREEN tests
    - tests/unit/test_parse_dispatcher.py  # +7 GREEN tests
    - tests/unit/test_viled_catalog_paginate.py  # +11 GREEN tests
    - tests/unit/test_viled_fetcher_isolation.py  # +5 GREEN tests
    - tests/unit/test_viled_retry_policy.py  # +8 GREEN tests
    - tests/unit/test_viled_rate_limit.py  # +9 GREEN tests
    - tests/integration/test_viled_fetcher_mocked.py  # +4 GREEN tests
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md  # addendum: A4 follow-up live probe + v1 limitation
decisions:
  - "Reading A discount semantics empirically validated: `attributes[0].price` is the customer-facing current price (after discount); `realPrice` is the pre-discount MSRP. Discounted Frederic Malle fixture (price=356745 < realPrice=419700) is the regression-canary. The plan code originally inverted this; corrected and documented as Rule 1 deviation."
  - "Stock-state derivation uses `item.count` + `item.purchaseType` (per WAVE0-PROBE A1 REVISED) — viled has no `attributes[0].in_stock` boolean. Mapping: count > 0 + purchaseType=ONLINE → IN_STOCK; count > 0 + purchaseType=PREORDER → UNAVAILABLE; count == 0 → OUT_OF_STOCK; otherwise UNKNOWN. PREORDER spelling is provisional; first weekly run will confirm."
  - "Catalog pagination is a v1 limitation. Live probe 2026-05-07 confirmed every public URL convention (?page=N, ?pageNumber=N, ?p=N, ?offset=, /page/N, /N, _next/data/{buildId}/...json, /api/*) returns page 1 — server-side rendering ignores the params. Implemented runtime detection + graceful page-1-only fallback. Effective output: 120 SKUs (60 men + 60 women) vs 7,697 catalog total. Sufficient for D-201 sanity_gate_n=100; resolution deferred to Phase 3/7 ops follow-up."
  - "curl_cffi exception types imported from `curl_cffi.requests.exceptions` per WAVE0-PROBE A10 REVISED. Added Timeout, ReadTimeout, ConnectionError, HTTPError, RequestException to the tenacity retry-set alongside the synthetic TransientFetchError. The plan only required the synthetic type; including the natives means a curl_cffi-raised timeout retries directly with full traceback observable to operators."
  - "Currency hardcoded unconditionally to KZT (STATE.md plan 01-07 lock). Any non-₸/KZT raw input is logged for observability via `viled_unexpected_currency` warning but never propagates."
  - "ParseDispatcher dispatch signature accepts an optional `url` kwarg beyond the Protocol-declared (retailer, html_or_data) — backward-compatible with `runtime_checkable` Protocol checks (which only verify the named methods exist) and forwarded to the per-retailer parsers for sku_id derivation."
patterns-established:
  - "Reading A price semantics anchored to the live discounted fixture as a permanent regression-canary"
  - "Runtime pagination self-check: detect SSR-not-paginating servers via pageNumber stability + content[0].id stability, break early"
  - "curl_cffi-native exception types in retry-set for direct tenacity observability (vs wrapping every error in TransientFetchError)"
requirements-completed:
  - CRAWL-01
  - CRAWL-03
  - CRAWL-04
  - CRAWL-06
  - PARSE-01
  - PARSE-02
  - PARSE-03
  - PARSE-04
  - PARSE-06
metrics:
  duration_minutes: 70
  completed_date: 2026-05-07
  tasks_completed: 2
  files_created: 6
  files_modified: 9
  tests_added: 74
  tests_added_kind: GREEN
  tests_passing_after: 321
  tests_skipped_after: 5
  tests_failing_after: 0
---

# Phase 02 Plan 04: viled `__NEXT_DATA__` parser + curl_cffi fetcher + catalog enumerator + ViledConfig (Wave 1)

**`__NEXT_DATA__`-only viled PDP parser with empirically-corrected price semantics, curl_cffi sync fetcher with tenacity 3-retry + per-SKU isolation + 2 s pacing, catalog enumerator with runtime SSR-pagination detection, and tomllib-backed ViledConfig — all behind a unified ParseDispatcher routing per retailer-id.**

## Performance

- **Duration:** ~70 min
- **Completed:** 2026-05-07
- **Tasks:** 2 (per plan frontmatter)
- **Files created:** 6 (src) + 1 doc addendum
- **Files modified:** 8 test files (RED skip → GREEN)
- **Tests added:** +74 GREEN
- **Test suite:** 247 passed → 321 passed; 13 skipped → 5 skipped (Wave 4/5 stubs only)

## Accomplishments

- viled __NEXT_DATA__ parser ships with PARSE-01..04 + PARSE-06 closed; the live discounted fixture (item/367251 — Frederic Malle) is pinned in tests as a price-semantics regression-canary.
- ParseDispatcher unifies Phase 2 (viled `__NEXT_DATA__`) and Phase 3 (goldapple microdata) parsers behind one `dispatch(retailer, html, url)` interface; satisfies the `runtime_checkable` `ParseDispatcherProtocol`.
- ViledFetcher mirrors the GoldappleFetcher class shape (run_id init + fetch_one + run_loop) with the async/Camoufox lifecycle stripped per D-225; 3-retry tenacity policy with exp+jitter; per-SKU isolation; 2 s pacing.
- Catalog enumerator walks page-1 + attempts `?page=2..N`, detects the SSR-not-paginating server response, and breaks early — graceful v1 fallback to 120 SKUs across both catalogs.
- ViledConfig loads `[tool.ga_crawler.crawl.viled]` via 3.12-stdlib tomllib; defaults match the operator-edited TOML so direct construction yields identical values.
- WAVE0-PROBE.md gains an addendum closing A4 with empirical evidence and a documented v1 limitation.

## Task Commits

1. **Task 1 — Shared parser types + viled `__NEXT_DATA__` parser + ParseDispatcher** — `f8132cd` (feat)
   - 3 src files created (types.py, viled_nextdata.py, dispatcher.py)
   - 3 test files flipped RED → GREEN (test_viled_nextdata_parser.py, test_viled_stock_state.py, test_parse_dispatcher.py)
   - +38 tests
2. **Task 2 — viled fetcher + catalog enumerator + ViledConfig** — `e342dde` (feat)
   - 3 src files created (config.py, viled_catalog.py, viled.py)
   - 5 test files flipped RED → GREEN (test_viled_catalog_paginate.py, test_viled_fetcher_isolation.py, test_viled_retry_policy.py, test_viled_rate_limit.py, test_viled_fetcher_mocked.py)
   - +36 tests

**Plan metadata commit:** (this commit) — docs: complete plan summary + WAVE0-PROBE A4 addendum + STATE.md update

## Files Created

| File | LOC | Purpose |
|------|-----|---------|
| `src/ga_crawler/parsers/types.py` | 27 | `StockState` Literal enum (PARSE-06) |
| `src/ga_crawler/parsers/viled_nextdata.py` | 224 | `parse_pdp(html, url) → ViledRawProduct` + `_extract_next_data` + `_map_stock_state` (PARSE-01..04, PARSE-06) |
| `src/ga_crawler/parsers/dispatcher.py` | 57 | `ParseDispatcher` concrete impl with `_registry = {viled, goldapple}` (PARSE-02 dispatch) |
| `src/ga_crawler/enumeration/viled_catalog.py` | 267 | `fetch_catalog_urls(catalog_base)` + module-local tenacity-decorated `_fetch_html` + helpers (CRAWL-01) |
| `src/ga_crawler/fetchers/viled.py` | 215 | `ViledFetcher` + `fetch_one_isolated` + tenacity-decorated `_fetch_html` + `TransientFetchError` (CRAWL-03, CRAWL-04, CRAWL-06) |
| `src/ga_crawler/config.py` | 72 | `ViledConfig.from_pyproject()` reading `[tool.ga_crawler.crawl.viled]` via tomllib |

## Files Modified

- `tests/unit/test_viled_nextdata_parser.py` — RED skip → 23 GREEN tests covering PARSE-01..04 + currency hardcode + sku_id derivation + negative-path guards
- `tests/unit/test_viled_stock_state.py` — RED skip → 8 GREEN tests focused on `_map_stock_state` helper
- `tests/unit/test_parse_dispatcher.py` — RED skip → 7 GREEN tests for `dispatch()` routing + Protocol satisfaction
- `tests/unit/test_viled_catalog_paginate.py` — RED skip → 11 GREEN tests using A4 REVISED shape (`pageProps.items.{content, totalPages, pageNumber}`); covers single-page, multi-page, SSR-not-paginating guard, dedup, non-200, real fixture
- `tests/unit/test_viled_fetcher_isolation.py` — RED skip → 5 GREEN tests for CRAWL-03 isolation
- `tests/unit/test_viled_retry_policy.py` — RED skip → 8 GREEN tests including curl_cffi.requests.exceptions Timeout/ConnectionError direct retry + A10 import-path negative-assertion
- `tests/unit/test_viled_rate_limit.py` — RED skip → 9 GREEN tests for run_loop pacing + ViledConfig.from_pyproject()
- `tests/integration/test_viled_fetcher_mocked.py` — RED skip → 4 GREEN tests for end-to-end fetcher with monkey-patched `_fetch_html`; includes `test_no_respx_imported` Pitfall 1 assertion
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md` — addendum 2026-05-07 closing A4 (live probe of 10 URL conventions; all return page 1; v1-limitation documented)

## WAVE0-PROBE Path Consumption

| WAVE0-PROBE assertion | Honored as written? |
|-----------------------|---------------------|
| **A1 REVISED** — viled has no `attributes[0].in_stock`; stock derives from `item.count` + `item.purchaseType` | YES — `_map_stock_state(item)` reads exactly these fields |
| **A2 VERIFIED** — `price` = current, `realPrice` = was, discount when `price < realPrice` | YES — Reading A implemented; pinned discounted fixture asserts current=356745 was=419700 |
| **A3 VERIFIED** — catalog endpoints return HTTP 200 via plain curl_cffi impersonate=chrome | YES — Tier 0 only, no Patchright/Camoufox |
| **A4 REVISED** — pagination keys at `pageProps.items.{content, totalPages, total, pageSize, pageNumber}` | YES — `_items_block(nd)` reads exactly these keys; **plus addendum**: `?page=N` does not paginate (any URL convention returns page 1); runtime guard breaks early on this case |
| **A10 REVISED** — exceptions at `curl_cffi.requests.exceptions`, NOT `.errors` | YES — fetcher imports from `.exceptions`; `test_a10_import_path_correct` negatively-asserts `.errors` lacks `Timeout` |

## Decisions Made

1. **Reading A price semantics anchored to live fixtures.** The plan source code originally treated `realPrice` as current and `price` as was, but the canonical fixture (price=187700, realPrice=187700) and the discounted fixture (price=356745 < realPrice=419700) — combined with WAVE0-PROBE A2 prose explicitly stating "price = customer-facing current price" — invert that reading. Implemented and tested with the empirically-correct semantics; the live discounted fixture pins `current=356745, was=419700`.
2. **Stock-state mapping uses `item.count` + `item.purchaseType`.** `IN_STOCK` requires count>0 AND purchaseType ∉ {PREORDER}; `OUT_OF_STOCK` is count==0; `UNAVAILABLE` is count>0 AND purchaseType=='PREORDER'; `UNKNOWN` covers missing/non-int count.
3. **Currency unconditional KZT.** Per STATE.md plan 01-07 lock; non-₸/KZT raw values logged via `viled_unexpected_currency` warning but never propagated.
4. **Runtime SSR-pagination guard.** Live probe found every public URL convention returns page 1; rather than fail loudly, the enumerator detects `pageNumber` stability or `content[0].id` stability and breaks early with a `catalog_pagination_not_supported` log line. v1 effective output: 120 SKUs.
5. **curl_cffi natives in retry-set.** Plan only required the synthetic `TransientFetchError`; we additionally include `Timeout`, `ReadTimeout`, `ConnectionError`, `HTTPError`, `RequestException` from `curl_cffi.requests.exceptions` so curl_cffi's own raised exceptions retry directly with full traceback.
6. **ParseDispatcher accepts `url` kwarg.** The `ParseDispatcherProtocol` signature is `dispatch(retailer, html_or_data) -> Optional[dict]`. The concrete impl additionally accepts `url=""` (forwarded to per-retailer parsers for sku_id derivation). `runtime_checkable` Protocol checks verify only the named methods exist; the extra arg is backward-compatible.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan source code had price/realPrice semantics inverted relative to live fixtures.**
- **Found during:** Task 1 (parser implementation, while writing the discounted-fixture regression test)
- **Issue:** Plan source listing (lines 330-345 of 02-04-PLAN.md) set `current_price = a0.get("realPrice")` and `was_price = price if price > realPrice else None`. Empirical evidence: canonical fixture has price==realPrice==187700 (no signal either way); discounted Frederic Malle fixture has price=356745 < realPrice=419700. With the plan code, current=419700 (the higher) and was=None (since 356745 < 419700 fails the inequality) — meaning the customer is shown a price 17 % above the actual sale price AND no discount is recorded. WAVE0-PROBE.md §A2 explicitly says "`attributes[0].price = current selling price (after discount)`"; STATE.md plan 01-07 says "viled was_price requirement directly satisfiable from week 1 via realPrice field." These are the source-of-truth.
- **Fix:** Implemented Reading A: `current_price = a0["price"]`, `was_price = realPrice if realPrice > price else None`. Test `test_realprice_priority_discounted` rewritten to match (and a new test `test_discounted_fixture_real_corpus` pins the live discounted fixture with current=356745, was=419700 as a regression-canary). The plan code's `test_realprice_priority` was also rewritten — its assertion was wrong against the live data.
- **Files modified:** src/ga_crawler/parsers/viled_nextdata.py, tests/unit/test_viled_nextdata_parser.py
- **Verification:** All 23 parser tests + the live-fixture canary pass; `uv run pytest tests/unit/test_viled_nextdata_parser.py -x -q` exits 0.
- **Committed in:** f8132cd (Task 1)

**2. [Rule 3 — Blocking] Catalog pagination URL convention is unknown; SSR ignores `?page=N`.**
- **Found during:** Task 2 (catalog enumerator implementation, reading WAVE0-PROBE A4 OPEN ITEM)
- **Issue:** WAVE0-PROBE A4 left the actual page-2+ URL convention unverified; the plan source defaulted to `?page=N`. A live probe of 10 URL variants (`?page=N`, `?pageNumber=N`, `?p=N`, `?offset=N`, `?from=N`, `/page/N`, `/N`, `_next/data/{buildId}/...json` with each query param) confirmed every variant returns the same page 1 content (HTTP 200 with `pageNumber=1` and `content[0].id=408872` invariant). `/page/N` and `/N` return 404; `/api/*` candidates 404. The catalog presumably uses client-side XHR pagination requiring CSRF or other request-signing not exposed via simple GET.
- **Fix:** Implemented runtime detection — after each `?page=N` fetch, the enumerator checks `pageNumber` stability and `content[0].id` stability. On a stuck-at-page-1 response, it logs `catalog_pagination_not_supported` and breaks out of the pagination loop. v1 effective output is the union of page 1 across both catalogs (120 SKUs); D-201 `sanity_gate_n=100` is satisfied. Long-form resolution deferred to Phase 3/7 ops follow-up (likely: capture a real browser session and reverse-engineer the XHR endpoint, OR escalate to a per-`groupId` filter crawl).
- **Files modified:** src/ga_crawler/enumeration/viled_catalog.py (runtime guard + early break + warning log); .planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md (addendum closing A4)
- **Verification:** `test_breaks_when_server_returns_same_page1_for_page2` passes; live-fixture test `test_real_catalog_fixture_extracts_60_urls` confirms 60 URLs from page 1 alone.
- **Committed in:** e342dde (Task 2)

### Voluntary Additions

**1. curl_cffi-native exception types in tenacity retry-set.**
- **Why:** Plan only required `TransientFetchError` (the synthetic wrapper) in the retry-set. Adding `Timeout`, `ReadTimeout`, `ConnectionError`, `HTTPError`, and `RequestException` from `curl_cffi.requests.exceptions` means a curl_cffi-raised timeout is retried directly with its original type and traceback (rather than getting wrapped in `TransientFetchError`). Better operator observability without changing the success criteria.
- **Verified by:** `test_curl_cffi_timeout_is_retried`, `test_curl_cffi_connection_error_is_retried`.

**2. New test `test_a10_import_path_correct` negatively-asserts `.errors` does not export Timeout.**
- **Why:** Cascading defense for WAVE0-PROBE A10. If a future curl_cffi version moves `Timeout` back into `.errors`, the test catches it and reminds the developer to update the fetcher imports + WAVE0-PROBE.md.

**3. New test `test_discounted_fixture_real_corpus` pins the live discounted fixture.**
- **Why:** Synthetic `_base_nextdata()` tests assert the algorithm; this test asserts the algorithm against the actual real-world data. Without it, a future regression in field-name selection would only surface in production.

**4. Two extra negative-path parser tests (`test_returns_none_when_name_missing`, `test_returns_none_when_brand_missing`, `test_returns_none_on_malformed_json`, `test_returns_none_when_price_non_numeric`).**
- **Why:** Plan listed only 12 tests for the parser; we ship 23 covering the full negative space at near-zero cost. Mirrors Phase 3 `test_goldapple_microdata.py`'s defensive density.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 3 blocking) + 4 voluntary additions
**Impact on plan:** Both auto-fixes were necessary for correctness (price-semantics) and graceful handling (catalog pagination). Catalog scope shrinks from "ALL pages × 2 catalogs" (theoretically 7,697 SKUs) to "page 1 × 2 catalogs" (120 SKUs) — sufficient for D-201 and tracked for Phase 3/7 follow-up.

## Issues Encountered

- **curl_cffi.curl.CurlError on /api/* probes** — DNS/timeout connecting to `api.viled.kz` subdomain (which doesn't exist). Confirmed by 404 from main-domain `/api/...` paths. Did not block; treated as further evidence the public surface has no JSON endpoint.

## Phase 3 Frozen-Module Status

`git diff` is empty against:
- `src/ga_crawler/interfaces.py`
- `src/ga_crawler/parsers/goldapple_microdata.py`
- `src/ga_crawler/enumeration/goldapple_sitemap.py`
- `src/ga_crawler/fetchers/goldapple.py`
- `src/ga_crawler/runners/goldapple_run.py`

All Phase 3 contracts honored. ParseDispatcher imports `parse_pdp` from `goldapple_microdata` without modification.

## Cascading Constraints for Plan 02-05

The Wave 4 orchestrator (`runners/viled_run.py`) imports the following symbols:

```python
from ga_crawler.config import ViledConfig
from ga_crawler.parsers.dispatcher import ParseDispatcher
from ga_crawler.parsers.viled_nextdata import ViledRawProduct  # for type hints
from ga_crawler.parsers.types import StockState  # for normalizer mapping
from ga_crawler.fetchers.viled import ViledFetcher, fetch_one_isolated, TransientFetchError
from ga_crawler.enumeration.viled_catalog import fetch_catalog_urls
```

Concrete behavior contracts the orchestrator can rely on:
- `ParseDispatcher().dispatch("viled", html, url)` returns a 9-key dict (sku_id, url, name, brand_raw, current_price, was_price, currency, availability, raw_volume_text) or None.
- `ViledFetcher(run_id=N, pause_seconds=2.0).run_loop(urls, stats, sleep_fn=time.sleep)` is sync, returns `list[dict]` with N-1 sleeps for N URLs.
- `fetch_catalog_urls(base, pause_seconds=2.0)` returns the deduplicated page-1 product URLs (v1 limitation documented).
- `ViledConfig.from_pyproject("pyproject.toml")` returns a frozen dataclass with operator-tunable runtime constants.

PARSE-05 (aggregate parse-quality gate ≥95 %) and CRAWL-05 (sanity-N catastrophic-failure gate) remain deferred to Plan 02-05 per plan frontmatter.

## Next Phase Readiness

- Wave 4 orchestrator (Plan 02-05) can build directly on these primitives.
- Storage (Wave 1, Plan 02-02) and normalizers (Wave 2, Plan 02-03) are already shipped from prior plans; the orchestrator wires them with the parsers/fetcher delivered here.
- v1 catalog scope is 120 SKUs (60 men + 60 women, page 1 of each). This is **above** D-201's `sanity_gate_n=100` floor; the auto-suggest mechanism (D-203) will ramp up from week-5 onward based on observed crawl health.
- Phase 3/7 ops follow-up: reverse-engineer the XHR pagination call OR pivot to a `groupId` filter walk to reach the full 7,697-SKU corpus.

## Self-Check: PASSED

Verified post-write:
- `src/ga_crawler/parsers/types.py` FOUND
- `src/ga_crawler/parsers/viled_nextdata.py` FOUND
- `src/ga_crawler/parsers/dispatcher.py` FOUND
- `src/ga_crawler/enumeration/viled_catalog.py` FOUND
- `src/ga_crawler/fetchers/viled.py` FOUND
- `src/ga_crawler/config.py` FOUND
- All 8 modified test files updated (each with `git diff` showing skip-marker removal + GREEN tests)
- WAVE0-PROBE.md addendum FOUND
- Commit `f8132cd` FOUND in `git log --oneline`
- Commit `e342dde` FOUND in `git log --oneline`
- `uv run pytest -m "not live" -q` → 321 passed, 5 skipped, 0 failed
- `git diff` empty against the 5 frozen Phase 3 module paths

---
*Phase: 02-project-skeleton-viled-crawl-storage*
*Plan: 04*
*Completed: 2026-05-07*
