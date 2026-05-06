---
phase: 03-goldapple-crawl
plan: 08
subsystem: enumeration + orchestrator
tags: [gap-closure, brand-intersect, norm06, d-305, structural-invariant, longest-prefix-in-whitelist]
dependency_graph:
  requires:
    - "03-02-SUMMARY (slug_fy_bilingual + intersect_brand_pool + fetch_sitemap_slugs primitives)"
    - "03-05-SUMMARY (compute_norm06_forward wrapper + GoldappleStatsBuilder)"
    - "03-06-SUMMARY (run_goldapple_phase orchestrator wiring sitemap → intersect → run_loop)"
    - "03-07-SUMMARY (Wave 6 live-smoke surfaced Finding #3 root-cause)"
    - "03-VERIFICATION (Truth 1 BLOCKER tracing intersect contract mismatch)"
  provides:
    - "index_by_brand_token(slug_map, known_brand_tokens) — longest-prefix-in-whitelist bucket index (Path A)"
    - "intersect_brand_pool(viled_brands, aliases, brand_bucket) — refactored param shape"
    - "compute_norm06_forward(viled_brands, aliases, brand_bucket) — refactored param shape"
    - "Orchestrator Step 3.5: known_brand_tokens whitelist + brand_bucket built before NORM-06 forward"
  affects:
    - "Phase 4 matcher unblocked: orchestrator now produces non-empty final_records against real sitemap shape"
    - "ROADMAP Success Criterion 4 (1-hour live run) — operator re-verification path opens"
tech-stack:
  added: []
  patterns:
    - "longest-prefix-in-whitelist bucket index — depth-bounded (MAX_DEPTH=3), whitelist-driven, O(n×depth)"
    - "structural D-305 enforcement via inspect.getsource AST/source gates (no shell-grep false-positives)"
key-files:
  created:
    - tests/unit/test_brand_token_index.py
  modified:
    - src/ga_crawler/enumeration/goldapple_sitemap.py
    - src/ga_crawler/enumeration/slug.py
    - src/ga_crawler/runner/stats.py
    - src/ga_crawler/runners/goldapple_run.py
    - tests/unit/test_intersect_brand_pool.py
    - tests/integration/test_run_e2e_with_phase2_mocks.py
decisions:
  - "Path A (longest-prefix-in-whitelist) over Path B (bounded prefix-match with whitelist enforcement) — Path A makes D-305 a structural invariant rather than a guarded interpretive step"
  - "BRAND_TOKEN_MAX_DEPTH = 3 — covers single-word, two-word, three-word brand names; beyond depth 3 false-positive risk grows"
  - "Orphan slugs (no whitelisted prefix) silently dropped — operator-driven scope filter; viled doesn't carry that brand, so we don't crawl it"
  - "Operator opt-in disambiguation between brand families (e.g. tom_ford / tom_ford_beauty) — only when both appear in viled_brands does longest-prefix-match split them; otherwise both fall through to shorter prefix"
metrics:
  duration: ~10 minutes
  completed: 2026-05-06T09:07:04Z
---

# Phase 3 Plan 08: NORM-06 brand-intersect bucket fix (gap_closure) Summary

CRAWL-02 BLOCKER closed via Path A — orchestrator now builds a longest-prefix-in-whitelist brand-token bucket from `known_brand_tokens` (precomputed from viled brand-alias slug-variants) and feeds it to `intersect_brand_pool`/`compute_norm06_forward`; Truth 1 (matched_url_count=0 against real sitemap) is structurally fixed and 192/192 non-live tests pass.

## What Shipped

### Path A: longest-prefix-in-whitelist (Option 4)

**Algorithm:** for each product slug, test depth-3, depth-2, depth-1 prefixes against the precomputed `known_brand_tokens` whitelist (longest first); URL goes to bucket of FIRST matched prefix and ONLY that bucket; if no prefix matches → drop.

**Why Path A over Path B:**
- Path B (`slug.startswith(brand + '-')` over sitemap_slugs.values() with whitelist enforcement) would still rely on a runtime guard against the "tom-ford ⊆ tom-ford-beauty" false-positive. The guard is interpretive — it depends on the reviewer trusting the whitelist-check-then-startswith logic.
- Path A makes D-305 a STRUCTURAL invariant. The bucket can only contain whitelisted tokens (because we test prefixes ONLY against the whitelist). Each URL belongs to exactly one bucket (longest-match wins, then `break`). Cross-contamination is impossible by construction — not by guard.
- Time complexity is also strictly better: Path A is O(n × MAX_DEPTH) where n=len(slug_map); Path B is O(n × len(brand_slugs)) per brand.

### New helper

```python
# src/ga_crawler/enumeration/goldapple_sitemap.py
BRAND_TOKEN_MAX_DEPTH = 3

def index_by_brand_token(
    slug_map: dict[str, list[str]],
    known_brand_tokens: set[str],
) -> dict[str, list[str]]:
    """Index URLs by LONGEST whitelisted brand-token prefix; orphan slugs dropped."""
```

### Refactor surface

| File | Change |
|------|--------|
| `src/ga_crawler/enumeration/goldapple_sitemap.py` | + `BRAND_TOKEN_MAX_DEPTH`, + `index_by_brand_token`, `__all__` extended |
| `src/ga_crawler/enumeration/slug.py` | param rename `sitemap_slugs` → `brand_bucket`, docstring updated |
| `src/ga_crawler/runner/stats.py` | param rename `sitemap_slugs` → `brand_bucket`, docstring updated |
| `src/ga_crawler/runners/goldapple_run.py` | new Step 3.5: build `known_brand_tokens` whitelist + `brand_bucket = index_by_brand_token(slug_map, known_brand_tokens)`; pass `brand_bucket` to `compute_norm06_forward`; new `phase3_brand_bucket_built` structlog event |
| `tests/unit/test_brand_token_index.py` | NEW — 7 regression tests for the new helper |
| `tests/unit/test_intersect_brand_pool.py` | mechanical rename `sitemap` → `brand_bucket` in 6 existing tests; +3 new tests (full-pipeline regression / inspect.getsource gate / compute_norm06_forward shape) |
| `tests/integration/test_run_e2e_with_phase2_mocks.py` | +1 E2E test against realistic sitemap shape |

### Test count delta

| Test file | Before | After | Delta |
|-----------|--------|-------|-------|
| `tests/unit/test_brand_token_index.py` | 0 | 7 | +7 |
| `tests/unit/test_intersect_brand_pool.py` | 6 | 9 | +3 |
| `tests/integration/test_run_e2e_with_phase2_mocks.py` | 6 | 7 | +1 |
| **Total non-live suite** | **181** | **192** | **+11** |

All 192 tests pass; 0 failures; baseline 181 maintained (no regressions).

## Truth 1 Closure Evidence

```
$ uv run python -c "<phase-level verification 1>"
PASS — Truth 1 closure + D-305 structural disambiguation proven
```

Combined evidence (also runs in `test_intersect_against_real_sitemap_shape` Sub-tests 7a-7f and `test_e2e_brand_intersect_against_realistic_sitemap_shape`):

- Givenchy: 3/3 product URLs matched against synthetic 12-entry sitemap
- Jo Malone London: 2/2 URLs matched (depth-3 prefix `jo-malone-london` resolved correctly)
- Tom Ford WITHOUT disambiguation: 2/2 (noir-extreme + beauty-lipstick both fall to depth-2 `tom-ford`)
- Tom Ford WITH `tom_ford_beauty` operator-disambiguated: 1/1 each, ZERO cross-contamination
- Estée Lauder bilingual: 2/2 — both ASCII (`estee-lauder-…`) and Cyrillic (`эсте-лаудер-…`) matched
- Unknown brand: 0/0 matched, 1/1 unmatched (correctly surfaces to NORM-06 review queue)
- Top-level: matched_url_count > 0 for at least givenchy + jo_malone_london — exactly the BLOCKER condition Truth 1 demanded

## D-305 Structural-Invariant Evidence

### Source-level guard (cross-platform Python via inspect.getsource)
```
$ uv run python -c "<phase-level verification 2>"
D-305 source-level guards passed for all 3 production functions
```

`intersect_brand_pool`, `index_by_brand_token`, `compute_norm06_forward` all verified to contain ZERO `.startswith(`, `.find(`, `.endswith(`, `.contains` primitives. The lookup path is purely exact-key `dict.get()` on a precomputed bucket whose keys are themselves filtered by the `known_brand_tokens` whitelist at indexing time.

### Disambiguation guard test (Task 1 Test 3)

`test_brand_token_index_tom_ford_does_not_contaminate_tom_ford_beauty` proves that with `known_brand_tokens={'tom-ford', 'tom-ford-beauty'}`:
- `bucket['tom-ford-beauty']` contains ONLY the `tom-ford-beauty-eye-cream` URL
- `bucket['tom-ford']` contains `tom-ford-noir-extreme` AND `tom-ford-private-blend-tobacco` (both fall through to depth-2 because their depth-3 prefixes are not whitelisted)
- No cross-contamination in either direction
- No `bucket['tom']` key (depth-1 `tom` not whitelisted)

### Full-pipeline guard test (Task 2 Test 7)

`test_intersect_against_real_sitemap_shape` Sub-test 7d confirms the same invariant end-to-end through `slug_fy_bilingual` → `index_by_brand_token` → `intersect_brand_pool`: when both `Tom Ford` and `Tom Ford Beauty` are operator-disambiguated, the matched URL sets are disjoint by construction.

## Deviations from Plan

None - plan executed exactly as written. All 3 tasks committed in TDD RED→GREEN order on first verify pass, every acceptance gate green on first run.

## Auth Gates

None - pure Python refactor, no external services touched.

## Self-Check: PASSED

- `tests/unit/test_brand_token_index.py` — created, 7 tests pass
- `tests/unit/test_intersect_brand_pool.py` — modified, 9 tests pass
- `tests/integration/test_run_e2e_with_phase2_mocks.py` — modified, 7 tests pass
- `src/ga_crawler/enumeration/goldapple_sitemap.py` — modified (+ index_by_brand_token + BRAND_TOKEN_MAX_DEPTH + `__all__` extension)
- `src/ga_crawler/enumeration/slug.py` — modified (param rename)
- `src/ga_crawler/runner/stats.py` — modified (param rename)
- `src/ga_crawler/runners/goldapple_run.py` — modified (Step 3.5 wiring)
- Commits verified in `git log`:
  - `88176bc` test(03-08): RED phase failing tests
  - `68e32c0` feat(03-08): GREEN phase index_by_brand_token
  - `ca719c7` refactor(03-08): brand_bucket param + full-pipeline regression
  - `68213b4` feat(03-08): orchestrator Step 3.5 wiring + E2E regression
- Full pytest suite (non-live): 192 passed, 0 failed
- D-305 source-gate Python check: passed for all 3 production functions
- AST orchestrator wiring check: `index_by_brand_token` + `slug_fy_bilingual` called; `compute_norm06_forward` receives `brand_bucket`
- AST param-rename check: `sitemap_slugs` no longer a parameter in `slug.py` or `stats.py`
- CLI smoke: `python -m ga_crawler --help` exits 0, lists both subcommands

## Open Follow-ups

1. **Verifier re-run (gsd-verifier):** Phase 3 should now reach `passed` status. Operator runs `/gsd-execute-phase 03 --gaps-only` to re-trigger verifier; Truth 1 is structurally closed, Truths 2/3/5 already verified, Truth 4 remains UNCERTAIN pending live re-run.
2. **Operator live re-run for ROADMAP Success Criterion 4:** `uv run python -m ga_crawler goldapple-run --run-id 43 --viled-brands givenchy,jo_malone_london --sanity-gate-m 10` to obtain the missing 1-hour-run data point. With the bucket fix, `matched_urls` will be non-empty, smoke probe passes, run_loop executes against ~real-shape pool, sanity-gate stays at M=10 to allow partial completion. This is the empirical Truth 4 closure step (NOT a checkpoint task — verifier itself follows up after operator confirms the live run).
3. **Phase 4 (matcher) unblocked:** orchestrator can now produce non-empty `final_records` against real sitemap (subject to Truth 4 re-verification). Phase 4 planning can begin.

---

*Plan executed: 2026-05-06 in ~10 minutes (start 08:57:42Z, end 09:07:04Z)*
*4 commits (1 RED + 3 GREEN/REFACTOR), 6 files modified, 1 file created*
*0 deviations, 0 auth gates, all acceptance gates green on first run*
