---
phase: 02
plan: 01
subsystem: project-skeleton
tags: [bootstrap, wave-0, viled, fixtures, test-scaffolding]
wave: 0
type: execute
autonomous: true
status: complete
completed_date: 2026-05-07
duration_minutes: ~25
dependency_graph:
  requires:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md  # D-201..D-227
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-RESEARCH.md  # Pattern 1, Pattern 2, A1-A10, Pitfalls 1, 8
    - .planning/spikes/01-goldapple/sample-payloads/viled-nextdata-shape.json
  provides:
    - tests/fixtures/viled/viled-pdp-407682.html
    - tests/fixtures/viled/viled-pdp-discounted.html
    - tests/fixtures/viled/viled-pdp-multipack.html
    - tests/fixtures/viled/viled-catalog-men-1310-page1.html
    - tests/fixtures/viled/viled-catalog-women-1310-page1.html
    - tests/fixtures/viled/viled-nextdata-shape.json
    - tests/fixtures/viled/brand-aliases-fixture.yaml
    - tests/fixtures/normalize/volume-corpus.yaml
    - tests/fixtures/normalize/brand-corpus.yaml
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md
    - "[tool.ga_crawler.crawl.viled] pyproject namespace"
    - "PyYAML 6.0.3 dependency"
    - "24 RED skip-marked test stubs (Waves 1-5)"
    - "8 conftest.py fixtures for Phase 2 (existing 11 preserved)"
  affects:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-RESEARCH.md  # Pattern 1, Pattern 2, Pattern 4 require REVISED notes per A1, A4, A10
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md  # D-223, D-226 require operator review (catalog scope finding)
tech-stack:
  added:
    - pyyaml@6.0.3
  patterns:
    - "Live curl_cffi probe pattern (mirrors Phase 3 spike 01-07)"
    - "RED skip-marked test stubs that flip GREEN as production code lands"
    - "Per-Wave pytestmark.skip reason mapping to enabling Plan ID"
key-files:
  created:
    - tests/fixtures/viled/viled-pdp-407682.html (145 KB, canonical PDP)
    - tests/fixtures/viled/viled-pdp-discounted.html (133 KB, Frederic Malle, price<realPrice)
    - tests/fixtures/viled/viled-pdp-multipack.html (132 KB)
    - tests/fixtures/viled/viled-catalog-men-1310-page1.html (238 KB, 60 items, total=1947)
    - tests/fixtures/viled/viled-catalog-women-1310-page1.html (255 KB, 60 items, total=5750)
    - tests/fixtures/viled/viled-nextdata-shape.json (411 KB pretty-printed)
    - tests/fixtures/viled/brand-aliases-fixture.yaml (3 canonicals × Cyrillic+Latin aliases)
    - tests/fixtures/normalize/volume-corpus.yaml (18 cases)
    - tests/fixtures/normalize/brand-corpus.yaml (11 cases)
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md
    - tests/unit/test_storage_models.py
    - tests/unit/test_run_writer.py
    - tests/unit/test_snapshot_writer.py
    - tests/unit/test_norm06_writer.py
    - tests/unit/test_volume_normalizer.py
    - tests/unit/test_brand_normalizer.py
    - tests/unit/test_name_normalizer.py
    - tests/unit/test_yaml_brand_alias.py
    - tests/unit/test_viled_nextdata_parser.py
    - tests/unit/test_viled_catalog_paginate.py
    - tests/unit/test_viled_fetcher_isolation.py
    - tests/unit/test_viled_retry_policy.py
    - tests/unit/test_viled_rate_limit.py
    - tests/unit/test_viled_stock_state.py
    - tests/unit/test_parse_dispatcher.py
    - tests/unit/test_sanity_n_gate.py
    - tests/unit/test_parse_quality_gate.py
    - tests/integration/test_storage_wal.py
    - tests/integration/test_v_current_snapshots.py
    - tests/integration/test_run_writer_lifecycle.py
    - tests/integration/test_viled_fetcher_mocked.py
    - tests/integration/test_viled_run_e2e_with_real_storage.py
    - tests/integration/test_main_run_e2e.py
    - tests/integration/test_backup_script.py
  modified:
    - pyproject.toml (add [tool.ga_crawler.crawl.viled] + pyyaml dep)
    - uv.lock (pyyaml resolved)
    - tests/conftest.py (append 8 Phase 2 fixtures; existing 11 preserved verbatim)
decisions:
  - "RESEARCH §Pattern 1 must be REVISED: viled has no `attributes[0].in_stock` boolean — use `item.count > 0` + `item.purchaseType` for stock-state derivation (cascading to Plan 04 PARSE-06)"
  - "RESEARCH §Pattern 2 must be REVISED: pagination keys are `pageProps.items.{content,total,totalPages,pageSize,pageNumber}`, NOT `pageProps.products[]/totalCount/currentPage` (cascading to Plan 04 CRAWL-01)"
  - "RESEARCH §Pattern 4 must be REVISED: curl_cffi exception classes import from `curl_cffi.requests.exceptions`, NOT `curl_cffi.requests.errors` (the latter only exports CookieConflict/CurlError/RequestsError/SessionClosed; Timeout lives in `.exceptions`). Cascading to Plan 04 retry policy."
  - "CONTEXT D-223 + D-226 'beauty + парфюмерия only' assumption requires operator review: catalog/1310 endpoints expose 7,697 SKUs total (men=1947 + women=5750) — full luxury cross-section, not beauty subtree. D-201 N=100 seed remains valid as catastrophic-failure detector; auto-suggest will dial up after 4 weeks."
  - "OOS fixture deferred (6/6 sampled SKUs all in stock with count 2..760). Plan 04 Wave 1 must synthesize one (clone canonical + patch count=0); first weekly run will surface a real one."
  - "Discount fixture pinned (id=367251, attributes[0].price=356745 < realPrice=419700, enableDiscount=True) — confirms PARSE-03 was_price field semantics."
  - "Multipack fixture pinned (id=398309, name contains kit/набор token) — drives NORM-04 multipack-flag detection tests."
metrics:
  duration_minutes: 25
  completed_date: 2026-05-07
  tasks_completed: 3
  files_created: 33
  files_modified: 2
  tests_added: 24
  tests_added_kind: skip-marked-RED
  tests_passing_after: 192
  tests_skipped_after: 24
  tests_failing_after: 0
---

# Phase 02 Plan 01: Wave 0 Bootstrap Summary

Wave 0 of Phase 2 ships test infrastructure that every subsequent wave depends on: pyproject namespace + PyYAML, 5 captured viled HTML fixtures, 2 normalize corpus YAMLs (18 + 11 cases), the brand-alias test seed, 8 conftest fixtures, and 24 RED skip-marked test stubs covering DATA-01..06 / CRAWL-01,03,04,05,06 / PARSE-01..06 / NORM-01..06. The live probe verified A3 + A2 as ASSUMED, REVISED A1 (no `in_stock` boolean), REVISED A4 (pagination keys live under `pageProps.items.{...}`), and REVISED A10 (`curl_cffi.requests.exceptions`, not `.errors`). All revisions cascade to RESEARCH §Pattern 1, §Pattern 2, §Pattern 4 ahead of Plan 04 production code.

## Probe Outcomes (A1-A4 + A10)

| Probe | Status | Finding |
|-------|--------|---------|
| **A1 — `in_stock` field path** | REVISED | No boolean stock field anywhere in `pageProps`. Stock signal lives on `item.count` (int) + `item.purchaseType` (str enum: 'ONLINE' / likely 'PREORDER'). Cascading: Plan 04 PARSE-06 derives state from these, not from `attributes[0].in_stock`. |
| **A2 — discount semantics** | VERIFIED | `attributes[0].price < attributes[0].realPrice` ⇒ discounted, with `enableDiscount=True` flag. Pinned discounted fixture: id=367251 (Frederic Malle, 356745 < 419700, ratio ~85%). Currency: `₸` (display) / `KZT` (ISO, in `initialState.checkout.cart.currency`). |
| **A3 — catalog accessibility** | VERIFIED | Both `/men/catalog/1310` and `/women/catalog/1310` return HTTP 200 with valid `__NEXT_DATA__` via plain `curl_cffi.impersonate="chrome"`. No login redirect, no Cloudflare/DataDome challenge. Pitfall 8 (sitemap+brand-allowlist fallback) NOT required. |
| **A4 — pagination metadata** | REVISED | Keys live under `props.pageProps.items.{content[], pageNumber, totalPages, total, pageSize}` — NOT `pageProps.products[] / totalCount / currentPage` as RESEARCH §Pattern 2 ASSUMED. Sample values: men `total=1947, totalPages=33, pageSize=60`; women `total=5750, totalPages=96, pageSize=60`. **Open question**: `?page=N` query string did not paginate via SSR (men page 2/3/5/10 returned identical 238 KB HTML); Plan 04 must verify the actual pagination convention (likely Next.js internal `_next/data/{buildId}/...json` route). |
| **A10 — curl_cffi exceptions** | REVISED | `curl_cffi.requests.errors` exports only `CookieConflict, CurlError, RequestsError, SessionClosed`. `Timeout` lives at `curl_cffi.requests.exceptions.Timeout` (with `ConnectTimeout`, `ReadTimeout`, `ConnectionError`, `HTTPError`, `RetryError`, etc.). Cascading: Plan 04 retry policy must import from `.exceptions`, not `.errors`. |

Detailed per-section narrative + cascading-to-Plan-04 table is in `.planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md`.

## Catalog Scope Reality-Check

D-223 framed `/men/catalog/1310` + `/women/catalog/1310` as **beauty + парфюмерия only**. Probe shows the catalogs together hold **7,697 SKUs across 129 pages** — the full luxury cross-section, not a beauty filter. Plan 04 should clarify with operator whether scope-narrowing means a deeper category filter (operator-picked `groupId` / brand whitelist) or trust the 1310 root and budget for ~8k catalog enumerations. D-201's N=100 seed remains valid as a catastrophic-failure detector; auto-suggest will dial it up post-week-4.

## File Inventory

### Captured fixtures (5 HTML + 1 JSON shape + 2 YAML corpora + 1 alias seed)

| File | Bytes | Purpose |
|------|-------|---------|
| `tests/fixtures/viled/viled-pdp-407682.html` | 145 011 | Canonical PDP, drives PARSE-01..02 happy path |
| `tests/fixtures/viled/viled-pdp-discounted.html` | 132 679 | Frederic Malle perfume, drives PARSE-03 was_price |
| `tests/fixtures/viled/viled-pdp-multipack.html` | 132 188 | Kit/набор fixture, drives NORM-04 multipack-flag |
| `tests/fixtures/viled/viled-catalog-men-1310-page1.html` | 238 212 | Page-1 men catalog, drives CRAWL-01 enumeration |
| `tests/fixtures/viled/viled-catalog-women-1310-page1.html` | 255 108 | Page-1 women catalog |
| `tests/fixtures/viled/viled-nextdata-shape.json` | 410 240 | Pretty-printed `__NEXT_DATA__` for human cross-reference |
| `tests/fixtures/viled/brand-aliases-fixture.yaml` | ~150 | 3 canonicals × Cyrillic+Latin aliases, drives YamlBrandAlias unit tests |
| `tests/fixtures/normalize/volume-corpus.yaml` | ~1.5 KB | 18 cases (canonical singletons, multipacks, kits, edge non-volumes) |
| `tests/fixtures/normalize/brand-corpus.yaml` | ~1.0 KB | 11 cases (Cyrillic↔Latin aliases + pure-Latin slugify) |

### Deferred fixture

| File | Reason |
|------|--------|
| `tests/fixtures/viled/viled-pdp-out-of-stock.html` | 6/6 sampled PDPs all had `count > 0` (range 2..760). Plan 04 Wave 1 task: synthesize by cloning canonical + patching `props.pageProps.item.count = 0`. First weekly production run will surface a real one for re-pin. |

### 24 RED test stubs (one per requirement)

| Wave | Plan | File | Reqs covered |
|------|------|------|--------------|
| 1 | 02-02 | tests/unit/test_storage_models.py | DATA-01, DATA-02 |
| 1 | 02-02 | tests/unit/test_run_writer.py | DATA-05 |
| 1 | 02-02 | tests/unit/test_snapshot_writer.py | DATA-03 |
| 1 | 02-02 | tests/unit/test_norm06_writer.py | NORM-06 |
| 1 | 02-02 | tests/integration/test_storage_wal.py | DATA-04 |
| 1 | 02-02 | tests/integration/test_v_current_snapshots.py | DATA-03 + CRAWL-01 provenance |
| 1 | 02-02 | tests/integration/test_run_writer_lifecycle.py | DATA-05 lifecycle |
| 2 | 02-03 | tests/unit/test_volume_normalizer.py | NORM-03, NORM-04 |
| 2 | 02-03 | tests/unit/test_brand_normalizer.py | NORM-02 |
| 2 | 02-03 | tests/unit/test_name_normalizer.py | NORM-05 |
| 2 | 02-03 | tests/unit/test_yaml_brand_alias.py | NORM-01 |
| 3 | 02-04 | tests/unit/test_viled_nextdata_parser.py | PARSE-01..04 |
| 3 | 02-04 | tests/unit/test_viled_stock_state.py | PARSE-06 |
| 3 | 02-04 | tests/unit/test_viled_catalog_paginate.py | CRAWL-01 |
| 3 | 02-04 | tests/unit/test_viled_fetcher_isolation.py | CRAWL-03 |
| 3 | 02-04 | tests/unit/test_viled_retry_policy.py | CRAWL-04 |
| 3 | 02-04 | tests/unit/test_viled_rate_limit.py | CRAWL-06 |
| 3 | 02-04 | tests/unit/test_parse_dispatcher.py | PARSE-02 dispatch |
| 3 | 02-04 | tests/integration/test_viled_fetcher_mocked.py | CRAWL-01, CRAWL-04 integration |
| 4 | 02-05 | tests/unit/test_sanity_n_gate.py | CRAWL-05 |
| 4 | 02-05 | tests/unit/test_parse_quality_gate.py | PARSE-05 |
| 4 | 02-05 | tests/integration/test_viled_run_e2e_with_real_storage.py | end-to-end viled |
| 5 | 02-06 | tests/integration/test_main_run_e2e.py | end-to-end full |
| 5 | 02-06 | tests/integration/test_backup_script.py | DATA-06 |

Each stub uses `pytestmark = pytest.mark.skip(reason="Wave N not implemented yet — Plan 02-NN")` so existing 192 Phase 1+3 tests remain green and the test layout is final from Wave 0 forward.

### Conftest fixtures (8 added; existing 11 preserved)

```python
# Added Wave 0 of Phase 2 (D-222):
viled_pdp_html             # session — canonical PDP HTML
viled_pdp_discounted_html  # session — discounted PDP HTML (bonus)
viled_pdp_multipack_html   # session — multipack PDP HTML (bonus)
viled_catalog_html         # session — page-1 men catalog HTML
brand_alias_yaml_fixture   # tmp_path — materialized YamlBrandAlias seed
in_memory_sqlite_session   # in-memory SQLite + foreign-keys PRAGMA, lazy-creates Wave-1 tables
volume_corpus_cases        # parsed list[dict] from volume-corpus.yaml
brand_corpus_cases         # parsed list[dict] from brand-corpus.yaml

# Phase 3 fixtures preserved verbatim:
goldapple_pdp_html, gate_shell_html, stale_sku_html, sitemap_xml,
tier2_results_json, jsonld_blocks_anti_fixture,
mock_brand_alias, mock_normalizer, mock_snapshot_writer, mock_run_writer,
tmp_camoufox_profile_dir
```

## Cascading Constraints for Plan 04

1. **Use `item.count > 0` (not `attributes[0].in_stock`) for stock-state.** RESEARCH §Pattern 1 must be amended; PARSE-06 derives `IN_STOCK` / `OUT_OF_STOCK` / `UNAVAILABLE` from `item.count` and `item.purchaseType`.
2. **Use `pageProps.items.content/total/totalPages/pageSize/pageNumber` keys** (not `pageProps.products[] / totalCount / currentPage`). RESEARCH §Pattern 2 must be amended; CRAWL-01 enumerator iterates pages via this shape.
3. **Verify pagination URL convention before Plan 04 Wave 1.** `?page=N` did NOT paginate via SSR HTML in the probe; likely the Next.js internal `_next/data/{buildId}/men/catalog/1310.json?page=N` route is the right entry point. `buildId` is in `nd["buildId"]`.
4. **Import retry exceptions from `curl_cffi.requests.exceptions`, not `.errors`.** Plan 04 retry policy: `from curl_cffi.requests.exceptions import RequestException, Timeout, ConnectTimeout, ReadTimeout, ConnectionError as CCConnectionError, HTTPError`. RESEARCH §Pattern 4 + §Pitfall 1 must be amended.
5. **Synthesize OOS fixture in Plan 04 Wave 1.** Clone `viled-pdp-407682.html`, patch `props.pageProps.item.count = 0`, save as `viled-pdp-out-of-stock.html`. First weekly production run will replace with a real one.
6. **Operator review needed for catalog scope (D-223).** `catalog/1310` is the full luxury catalog (7,697 SKUs), not a beauty filter. Plan 04 should clarify the actual scope-narrowing mechanism before crawling all 129 catalog pages.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] curl_cffi exception import path correction**
- **Found during:** Task 1 (Wave 0 probe verification)
- **Issue:** Plan's `<verify>` automated check uses `from curl_cffi.requests.errors import RequestsError, Timeout` which fails — `Timeout` does not exist in `curl_cffi.requests.errors` (only `CookieConflict, CurlError, RequestsError, SessionClosed`). The full exception stack lives in `curl_cffi.requests.exceptions`.
- **Fix:** Documented the corrected import path with `cascading: yes` flag in 02-WAVE0-PROBE.md §A10. Plan 04 retry policy will use `curl_cffi.requests.exceptions`. The plan's acceptance criterion explicitly allows this case ("succeeds (or 02-WAVE0-PROBE.md documents the corrected import path with `cascading: yes` flag)").
- **Files modified:** None (research-only correction, cascades to Plan 04).
- **Commit:** d6f1420

### Voluntary Additions

**1. Two bonus session fixtures in conftest.py**
- Added `viled_pdp_discounted_html` and `viled_pdp_multipack_html` alongside the 6 fixtures the plan required. Reason: the discounted and multipack PDPs were captured during Task 1 anyway, and Plan 04 PARSE-03 / NORM-04 tests need easy access. No cost to add now; saves a fixture-add commit later.

**2. One extra RED stub: `tests/unit/test_viled_stock_state.py`**
- The plan's table enumerates 23 stubs but the prose + acceptance criterion requires `≥24`. Split `test_viled_nextdata_parser.py` (PARSE-01..04 + PARSE-06) into two files: parser happy-path (PARSE-01..04) and stock-state derivation (PARSE-06). Cleaner test boundary for Plan 04, satisfies the `≥24` criterion exactly. Both stubs reference the same Wave 3 / Plan 02-04 implementation work.

### Catalog Scope Discovery (no fix — surfaces a planning question)

- The probe revealed `/men/catalog/1310` and `/women/catalog/1310` together hold 7,697 SKUs (men=1947 + women=5750). D-226 estimated 100-600 — off by an order of magnitude. The catalog endpoint id 1310 appears to be the viled root catalog, not a beauty filter. **Action item for Plan 04**: clarify scope-narrowing mechanism with operator (deeper category filter vs trust the 1310 root). Documented in 02-WAVE0-PROBE.md §"Scope-narrowing reality-check".

## Authentication Gates

None encountered. Probe ran fully autonomous via `curl_cffi.impersonate="chrome"` — no login, no anti-bot challenge, no proxy needed (all 8 fetches HTTP 200 first try).

## Verification Status

| Check | Result |
|-------|--------|
| `grep -q "tool.ga_crawler.crawl.viled" pyproject.toml` | PASS |
| `uv run python -c "import yaml"` | PASS (pyyaml 6.0.3) |
| 5 viled fixtures present (canonical/discounted/multipack/men-cat/women-cat) | PASS |
| nextdata-shape.json present + has `props.pageProps.attributes` | PASS |
| 02-WAVE0-PROBE.md present + sections A1, A2, A3, A4, A10 | PASS |
| volume-corpus.yaml has ≥15 cases | PASS (18) |
| brand-corpus.yaml has ≥10 cases | PASS (11) |
| 24 skip-marked test stubs created | PASS (24) |
| `uv run pytest -m "not live" -q` | PASS (192 passed + 24 skipped + 0 failed in 47.69 s) |
| `[tool.ga_crawler.crawl.viled].sanity_gate_n == 100` | PASS |
| `[tool.ga_crawler.crawl.viled]` has 7 keys (sanity_gate_n, pause_seconds, concurrency, retry_attempts, n_auto_suggest_factor, n_auto_suggest_after_runs, catalog_urls) | PASS |
| Existing goldapple namespace untouched | PASS |
| Existing 11 conftest fixtures preserved | PASS |

## Commits

- `d6f1420` — feat(02-01): wave-0 viled probe + 5 fixtures + WAVE0-PROBE memo
- `34e2be0` — chore(02-01): add [tool.ga_crawler.crawl.viled] namespace + pyyaml dep
- `00e9887` — test(02-01): add 24 RED stubs + 2 corpus YAMLs + 6 conftest fixtures

## Self-Check: PASSED

Verified post-write:
- `tests/fixtures/viled/viled-pdp-407682.html` FOUND
- `tests/fixtures/viled/viled-pdp-discounted.html` FOUND
- `tests/fixtures/viled/viled-pdp-multipack.html` FOUND
- `tests/fixtures/viled/viled-catalog-men-1310-page1.html` FOUND
- `tests/fixtures/viled/viled-catalog-women-1310-page1.html` FOUND
- `tests/fixtures/viled/viled-nextdata-shape.json` FOUND
- `tests/fixtures/viled/brand-aliases-fixture.yaml` FOUND
- `tests/fixtures/normalize/volume-corpus.yaml` FOUND (18 cases)
- `tests/fixtures/normalize/brand-corpus.yaml` FOUND (11 cases)
- `.planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md` FOUND
- All 24 test stubs FOUND under tests/unit and tests/integration
- Commit `d6f1420` FOUND in `git log --oneline`
- Commit `34e2be0` FOUND in `git log --oneline`
- Commit `00e9887` FOUND in `git log --oneline`
