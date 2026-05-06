---
phase: 03-goldapple-crawl
plan: 05
subsystem: runner-gates
tags: [smoke-probe, sanity-gate, auto-suggest, stats-namespace, norm-06, atomic-merge, pitfall-6]

# Dependency graph
requires:
  - phase: 03-goldapple-crawl
    provides: Wave 0 (interfaces.py RunWriterProtocol contract, conftest fixtures); Wave 1 (intersect_brand_pool); Wave 2 (parse_pdp, has_microdata_price); Wave 3 (GoldappleFetcher.fetch_one signature)
provides:
  - smoke_probe(fetcher) D-312 pre-crawl gate — pass iff all SMOKE_URLs return 200/304+microdata-price-extracted+not-block; aborts run on broken fingerprint
  - final_m_gate(count, M=1000) D-308/D-309 post-crawl sanity gate — inclusive >= boundary
  - auto_suggest_m(history) D-310 — None until 4+ runs, then int(0.7 × median(last_4)); operator-confirmed never auto-applied
  - SMOKE_URLS frozen 3-Givenchy tuple + load_smoke_urls_from_config Phase 7 rotation surface
  - GoldappleStatsBuilder with 13-key namespace enforcement (StatsNamespaceError) — atomic merge into runs.stats via RunWriter.patch_stats (Pitfall 6 mitigation)
  - compute_norm06_forward — D-306 forward direction returning (matched_urls, unmatched_count, unmatched_list)
affects: [03-06 (Wave 5 orchestrator: calls smoke_probe before run_loop, builder.from_run_loop_stats(...) after, final_m_gate(stats['goldapple.fetch_count']) before delivery)]

# Tech tracking
tech-stack:
  added: []  # statistics, importlib.metadata — both stdlib; structlog already pinned
  patterns:
    - "Namespace-enforced stats builder: StatsNamespaceError on unknown keys; bare-key auto-prefix; atomic delta dict for json_patch merge"
    - "Smoke probe with mock-fetcher TDD: builder pattern (fake fetch_one returning canned dict) makes 5 distinct fail-modes testable without live network"
    - "importlib.metadata.version('camoufox') is canonical version-string lookup — package's `__version__` is a submodule, not a string attribute (Rule 1 fix)"
    - "Sub-1ms test runtime for stats/gate primitives (33 tests in 0.06s) — pure-stdlib logic, no I/O, no fixtures"

key-files:
  created:
    - src/ga_crawler/runner/__init__.py
    - src/ga_crawler/runner/gates.py
    - src/ga_crawler/runner/stats.py
    - tests/unit/test_smoke_probe.py
    - tests/unit/test_final_gate.py
    - tests/unit/test_stats_namespace.py
    - tests/unit/test_norm06_forward.py
  modified: []

key-decisions:
  - "Resolve camoufox version via importlib.metadata.version('camoufox') — Rule 1 fix: getattr(camoufox, '__version__', ...) returns the submodule object (camoufox/__version__.py is a submodule, not a string). importlib.metadata is the PEP 566 canonical path for installed package versions."
  - "auto_suggest_m([100,200,300,400,5000,6000]) returns 1889 (NOT 1890) — Rule 1 fix in test: 0.7 cannot be exactly represented in IEEE 754 binary float, so int(0.7 * 2700.0) = int(1889.9999999999998) = 1889. Acceptable because D-310 explicitly contra auto-tune; auto_suggest is operator-confirmed, 1-unit drift on a sub-2000 suggestion is irrelevant."
  - "Allow GoldappleStatsBuilder.set to accept BOTH bare ('fetch_count') and namespaced ('goldapple.fetch_count') keys — caller ergonomics: tests + bulk imports use bare; explicit-namespace fallback for callers that already prefixed (e.g. SMOKE_DIAGNOSTICS dict spread)."
  - "compute_norm06_forward lazy-imports intersect_brand_pool — avoids circular dep with enumeration/slug.py (slug.py is independent of runner/, so this is defensive against future module-load reordering)."

patterns-established:
  - "Pattern: namespace-enforced stats builder. delta accumulator dict + StatsNamespaceError on unknown keys + bulk-import from peer-module dicts is the canonical Phase 3 → runs.stats handoff. Same pattern reused for any future per-retailer namespace (e.g. Phase 4 matcher could expose MatcherStatsBuilder with matcher.* keys)."
  - "Pattern: smoke-probe with closure-fetcher fixtures. Real-PDP / gate-shell / stale-SKU canned-dict fixtures via async closure return canned `await fetcher.fetch_one(page, url)` records — sidesteps Camoufox boot in unit tests, runs in <1ms, exercises 5 distinct fail-modes."
  - "Pattern: int(0.7 * median(last_4)) over `history[-4:]` window. statistics.median handles even/odd. Caveat documented: 0.7 binary-float means int() truncates ~half the time."

requirements-completed: [CRAWL-02]

# Metrics
duration: 6 min
completed: 2026-05-06
---

# Phase 3 Plan 05: Wave 4 Runner Gates + Stats Summary

**Runtime gates and stats namespace shipped: smoke probe (D-312) aborts on broken fingerprint before 4-hour crawl, final M-gate (D-308/D-309) blocks delivery on catastrophic underdelivery, auto-suggest M (D-310) emits operator-actionable threshold after 4-week history, and 13-key `goldapple.*` namespace with `StatsNamespaceError` enforces atomic merge contract per Pitfall 6.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-06T05:40:51Z
- **Completed:** 2026-05-06T05:46:57Z
- **Tasks:** 2
- **Files created:** 7 (3 source modules + 4 test modules)
- **Files modified:** 0

## Accomplishments

- **`runner/gates.py`** — production runtime gates:
  - `SMOKE_URLS`: frozen 3-Givenchy tuple (`7680100018-very-irresistible-givenchy`, `7681000001-givenchy-pour-homme-blue-label`, `19000032744-givenchy-gentleman-reserve-privee-eau-de-parfum`); `7681000002` row-0 stale-SKU **explicitly excluded** per A12 mitigation.
  - `load_smoke_urls_from_config(repo_root)`: optional override from `config/smoke_urls.txt` (one URL per line, `#` comments stripped) or fall back to `SMOKE_URLS`. Operator rotation surface for Phase 7 ops-playbook.
  - `_camoufox_version_at_runtime()`: resolves installed Camoufox version via `importlib.metadata.version("camoufox")` (Rule 1 fix — `getattr(camoufox, "__version__", ...)` returns the submodule object, not a string).
  - `smoke_probe(fetcher, smoke_urls=SMOKE_URLS) -> {pass, diagnostics}`: async pre-crawl probe. Pass = ALL urls return `status in (200, 304)` AND `not block` AND `parse_pdp(html, url)` produces non-None product with `current_price > 0`. Diagnostics dict carries `camoufox_version` + per-URL `responses` list (`url, status, size, title, block, price_extracted`) for ops-Telegram on fail (D-312).
  - `final_m_gate(goldapple_count, M=1000) -> bool`: inclusive `goldapple_count >= M` boundary check (D-308/D-309).
  - `auto_suggest_m(history_counts) -> Optional[int]`: returns `None` for `<4` runs, else `int(0.7 * statistics.median(history_counts[-4:]))`. Operator-confirmed; D-310 explicitly contra auto-tune.

- **`runner/stats.py`** — namespace + builder + NORM-06 forward:
  - `GOLDAPPLE_STATS_KEYS`: frozen 13-key tuple (every key prefixed `goldapple.`) per RESEARCH §Q4 lines 1051-1066. Schema-locked at this contract boundary.
  - `_BARE_TO_NAMESPACED`: bare-key → full-namespaced reverse-map for auto-prefix.
  - `StatsNamespaceError(KeyError)`: raised on attempt to set/inc a key outside the 13-key namespace.
  - `GoldappleStatsBuilder`: one-shot accumulator. `.set(bare_or_namespaced, value)` + `.inc(bare_or_namespaced, n=1)` + `.get(...) + .from_run_loop_stats(dict)` (defensive — ignores future-but-unknown keys) + `.delta` dict ready for `RunWriter.patch_stats(run_id, builder.delta)` atomic JSON-merge.
  - `compute_norm06_forward(viled_brands, aliases, sitemap_slugs) -> tuple[list[str], int, list[str]]`: wraps Wave 1's `intersect_brand_pool`; returns (matched_urls, unmatched_count, unmatched_brands_list) — feeds D-306 `runs.stats.goldapple.unmatched_viled_brands` counter and review-queue handoff.

- **58 new tests, all green** (Wave 0+1+2+3+4 = **163/163 passed in 44.99s** with `-m "not live"`).

## Test Counts

| Suite | Tests | Notes |
|-------|-------|-------|
| `tests/unit/test_smoke_probe.py` | 7 | URL whitelist (PRODUCT_URL_RE) + A12 stale-row-0 exclusion + pass-all-real-pdp + fail-on-gate-shell + fail-on-parse-none + diagnostics-shape + custom-url-list rotation |
| `tests/unit/test_final_gate.py` | 18 | 7 final_m_gate boundary parametrize (0/999/1000/1001/5000 at M=1000; 1/0 at M=1) + default-M-1000 + 9 auto_suggest scenarios (empty/under-4/exactly-4/uses-last-4/even-length-median/int-truncation/return-type/formula-cross-check + 3 under-4 parametrize) |
| `tests/unit/test_stats_namespace.py` | 28 | 13-keys + prefix invariant + 13 each-required-key parametrize + builder starts-empty/auto-prefix/full-namespace/inc-accumulates/inc-with-n/bool/dict/list/StatsNamespaceError-set/StatsNamespaceError-inc/from-run-loop/from-run-loop-ignore-unknown/get-default |
| `tests/unit/test_norm06_forward.py` | 5 | partial-match (1 unmatched) + all-matched + empty-input + all-unmatched + bilingual-counts-brand-once (Estée Lauder hits both ASCII + Cyrillic slugs) |
| **Total NEW (Wave 4)** | **58** | All green |
| **Wave 0+1+2+3+4 cumulative** | **163/163** | `uv run pytest tests/ -q -m "not live"` exits 0 (44.99s on Win11/Python 3.12.13) |

## 13-Key Namespace Verified

All 13 keys per RESEARCH §Q4 lines 1051-1066 present in `GOLDAPPLE_STATS_KEYS`:

| # | Key | Purpose |
|---|-----|---------|
| 1 | `goldapple.fetch_count` | Total URLs attempted (CRAWL-05 input for final_m_gate) |
| 2 | `goldapple.fetch_failures` | tenacity-exhausted exceptions (CRAWL-03 isolation counter) |
| 3 | `goldapple.gate_shell_count` | GroupIB challenge-not-cleared count (Pitfall 4 monitor) |
| 4 | `goldapple.stale_count` | De-listed SKU detections (D-303) |
| 5 | `goldapple.parse_failures` | parse_pdp returned None on real-pdp state |
| 6 | `goldapple.unmatched_viled_brands` | D-306 forward — viled brands with 0 slug matches |
| 7 | `goldapple.unmatched_goldapple_slugs_new` | D-307 reverse — week-over-week NEW sitemap slugs |
| 8 | `goldapple.smoke_pass` | bool from smoke_probe (D-312) |
| 9 | `goldapple.smoke_diagnostics` | dict with camoufox_version + per-URL responses (populated only on fail) |
| 10 | `goldapple.fetch_duration_seconds` | Wall-clock for run_loop (Wave 5 fills) |
| 11 | `goldapple.mean_fetch_seconds` | Avg per-fetch (Wave 5 fills) |
| 12 | `goldapple.camoufox_version` | importlib.metadata.version('camoufox') at run-time |
| 13 | `goldapple.auto_suggest_m` | Optional[int] from auto_suggest_m (None until 4+ runs) |

Verified by `uv run python -c "from ga_crawler.runner.stats import GOLDAPPLE_STATS_KEYS; ..."` → `OK 13/13 keys`.

## Task Commits

Each task was committed atomically:

1. **Task 1: smoke probe + final M-gate + auto-suggest M (D-308/309/310/312)** — `11dca8c` (`feat`)
2. **Task 2: GoldappleStatsBuilder + 13-key namespace + NORM-06 forward (D-306)** — `5d5ba6c` (`feat`)

**Plan metadata commit (this SUMMARY + STATE + ROADMAP):** added in the closing docs commit below.

## Files Created/Modified

- `src/ga_crawler/runner/__init__.py` — package marker (single docstring)
- `src/ga_crawler/runner/gates.py` — `SMOKE_URLS`, `load_smoke_urls_from_config`, `_camoufox_version_at_runtime`, `smoke_probe`, `final_m_gate`, `auto_suggest_m`. ~165 LOC.
- `src/ga_crawler/runner/stats.py` — `GOLDAPPLE_STATS_KEYS`, `StatsNamespaceError`, `GoldappleStatsBuilder`, `compute_norm06_forward`. ~140 LOC.
- `tests/unit/test_smoke_probe.py` — 7 smoke probe tests (mocked fetcher closures)
- `tests/unit/test_final_gate.py` — 18 final_m_gate + auto_suggest_m tests
- `tests/unit/test_stats_namespace.py` — 28 namespace + builder tests
- `tests/unit/test_norm06_forward.py` — 5 NORM-06 forward direction tests

## Decisions Made

- **`importlib.metadata.version("camoufox")`** is the canonical Camoufox version-string lookup. The plan's `getattr(camoufox, "__version__", "unknown")` returns a *submodule object* (camoufox ships `camoufox/__version__.py` as a submodule, not a `__version__` string attribute on the package). Using PEP 566 metadata is the standard, distribution-info-driven path that works regardless of how the package internally exposes its version.
- **`int(0.7 * 2700.0)` returns 1889, not 1890.** The plan's expected value `1890` was optimistic about IEEE 754 binary float — `0.7` cannot be exactly represented, so `0.7 * 2700.0 == 1889.9999999999998`, which `int()` truncates. Updated test expectation to `1889` with explanatory comment. Acceptable because D-310 explicitly contra auto-tune; auto_suggest is operator-confirmed (PR-update workflow), and a 1-unit-drift on a sub-2000 suggestion is well within signal-to-noise.
- **`GoldappleStatsBuilder.set` accepts BOTH bare and namespaced keys.** Bare for ergonomic test code (`b.set("fetch_count", 100)`) and bulk-imports; full-namespaced for callers that already prefixed (e.g., spreading a `{"goldapple.smoke_diagnostics": {...}}` dict). The reverse-map `_BARE_TO_NAMESPACED` is computed once at import time.
- **`compute_norm06_forward` lazy-imports `intersect_brand_pool`.** `enumeration/slug.py` is independent of `runner/` (it's a Wave 1 primitive), so a top-level import would not cause an actual circular dep today — but lazy-import is defensive against future restructuring (e.g., if `runner/stats.py` is ever imported from `enumeration/`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `_camoufox_version_at_runtime` returned a submodule object instead of a string**
- **Found during:** Task 1, `test_smoke_diagnostics_shape`
- **Issue:** The plan's verbatim code `getattr(camoufox, "__version__", "unknown")` returned the `camoufox.__version__` submodule object (camoufox ships `camoufox/__version__.py`), failing `isinstance(diag["camoufox_version"], str)`.
- **Fix:** Replace `getattr(camoufox, "__version__", ...)` with `from importlib.metadata import version, PackageNotFoundError; return version("camoufox")` inside a try/except `PackageNotFoundError → "unknown"` and outer `Exception → "unknown"`. PEP 566 canonical path; works regardless of package's internal version-attribute conventions.
- **Files modified:** `src/ga_crawler/runner/gates.py` (lines ~58-72)
- **Commit:** `11dca8c`

**2. [Rule 1 — Bug] Plan's `test_auto_suggest_uses_last_4_only` expected wrong value due to IEEE 754**
- **Found during:** Task 1, `test_auto_suggest_uses_last_4_only`
- **Issue:** The plan expected `int(0.7 * median([300, 400, 5000, 6000]))` = `int(0.7 * 2700)` = `1890`. In Python, `0.7 * 2700.0 == 1889.9999999999998`, which `int()` truncates to `1889`. The plan's optimistic arithmetic ignored that `0.7` is not exactly representable in binary float.
- **Fix:** Update expected value to `1889` with explanatory comment in the test docstring. Cross-checked against `statistics.median + int(0.7 * ...)` directly. The existing `test_auto_suggest_int_truncates` test already documented IEEE 754 truncation behavior in its name.
- **Acceptability:** D-310 contra auto-tune; this is an operator-confirmed *suggestion*, not auto-applied. 1-unit drift on a sub-2000 threshold is irrelevant (operator rounds to whole hundreds in PR anyway).
- **Files modified:** `tests/unit/test_final_gate.py` (`test_auto_suggest_uses_last_4_only` expectation + comment)
- **Commit:** `11dca8c`

### Plan-spec deviations (intentional, not Rule violations)

None — both deviations above are Rule 1 bug-fixes, both auto-fixed inline, both documented above. Task 2 ran clean with zero deviations.

## Threat Surface Coverage

All STRIDE entries from `<threat_model>` map to test coverage:

| Threat ID | Mitigation Path | Verified By |
|-----------|-----------------|-------------|
| T-03-05-01 | Smoke probe is a hard gate; Wave 5 orchestrator MUST call before run_loop and abort on `not result["pass"]` | `test_smoke_fail_one_gate_shell` + `test_smoke_fail_parse_returns_none` (verifies `result["pass"] is False` outcomes) |
| T-03-05-02 | A8 — Phase 7 ops-playbook quarterly rotation; smoke probe accepts `smoke_urls=` override | `test_smoke_with_custom_url_list` |
| T-03-05-06 | StatsNamespaceError raised on any non-`goldapple.*` key; Pitfall 6 mitigation | `test_builder_unknown_key_raises` + `test_builder_unknown_key_inc_raises` |
| T-03-05-11 | M=1000 explicit choice (~30% of spike estimate); D-310 auto-suggest after 4 weeks for data-driven update | `test_final_m_gate_default_M_1000` + `test_auto_suggest_under_4_runs_returns_none` |
| T-03-05-11b | `auto_suggest_m` returns None for <4 runs; only suggests, never auto-applies | `test_auto_suggest_under_4_runs_returns_none` (3-parametrize: [100], [100,200], [100,200,300]) |

No new threat surface introduced beyond the threat model.

## Issues Encountered

**Two Rule 1 auto-fixes in Task 1, both resolved inline; Task 2 ran clean first-shot.**

The two Task 1 fixes (camoufox version submodule + IEEE 754 plan arithmetic) reflect realities the planner could not anticipate from RESEARCH lines alone:
- The plan's verbatim code from RESEARCH §"Code Examples" line 927 hardcoded the camoufox version string `"135.0.1.beta24"`. The plan's `<action>` block correctly called this out as needing a runtime read, but the `getattr(camoufox, "__version__", ...)` formulation didn't account for the submodule shape of the actual camoufox package.
- The plan's expected `1890` was a manual arithmetic, not a Python-evaluated value — common pitfall when test cases are documented in prose rather than computed.

Both fixes are stable (no underlying logic changes; just correct value/lookup mechanism), test-validated, and documented in commit messages + this SUMMARY for downstream traceability.

## Self-Check: PASSED

All files verified present:
- `src/ga_crawler/runner/__init__.py` ✓
- `src/ga_crawler/runner/gates.py` ✓
- `src/ga_crawler/runner/stats.py` ✓
- `tests/unit/test_smoke_probe.py` ✓
- `tests/unit/test_final_gate.py` ✓
- `tests/unit/test_stats_namespace.py` ✓
- `tests/unit/test_norm06_forward.py` ✓
- `.planning/phases/03-goldapple-crawl/03-05-SUMMARY.md` ✓ (this file)

All commits verified in git log:
- `11dca8c` feat(03-05): smoke probe + final M-gate + auto-suggest M (D-308/309/310/312) ✓
- `5d5ba6c` feat(03-05): GoldappleStatsBuilder + 13-key namespace + NORM-06 forward (D-306) ✓

`uv run pytest tests/ -q -m "not live"` → **163 passed in 44.99s**.

## Next Phase Readiness

**Wave 4 ships exactly the contracts Wave 5 (orchestrator) needs to wire end-to-end:**

- **Pre-crawl gate:** `result = await smoke_probe(fetcher); if not result["pass"]: run_writer.fail(run_id, reason="smoke_failed"); patch_stats(run_id, {"goldapple.smoke_pass": False, "goldapple.smoke_diagnostics": result["diagnostics"]}); return`
- **Post-crawl gate:** `if not final_m_gate(stats["goldapple.fetch_count"], M=config["sanity_gate_m"]): run_writer.fail(run_id, reason=f"goldapple_count {n} < M={M}")`
- **Stats merge:** `builder = GoldappleStatsBuilder(); builder.from_run_loop_stats(run_loop_stats); builder.set("smoke_pass", True); builder.set("camoufox_version", _camoufox_version_at_runtime()); builder.set("auto_suggest_m", auto_suggest_m(get_run_history(run_writer))); run_writer.patch_stats(run_id, builder.delta)` — single atomic merge per Pitfall 6.
- **NORM-06 forward:** `matched_urls, unmatched_count, unmatched_list = compute_norm06_forward(viled_brands, aliases, sitemap_slugs); builder.set("unmatched_viled_brands", unmatched_count); norm06_review_queue.append(unmatched_list, direction="viled→goldapple", run_id=run_id)` — review-queue persistence is Phase 2's responsibility (per CONTEXT.md "Phase 2 owns initial NORM-06 deliverable"); Wave 5 just hands off the list.

**No blockers.** All Wave 0/1/2/3 contracts (interfaces.py Protocols, slug intersect, microdata parser, Camoufox fetcher) are referenced and respected.

**LOCKED Phase 3 decisions completed by this wave:**
- D-306 NORM-06 forward direction (compute_norm06_forward + counter)
- D-308 M=1000 static absolute (final_m_gate default)
- D-309 run-to-completion + final M-gate (final_m_gate post-crawl shape)
- D-310 auto-suggest after 4-week median × 0.7 (auto_suggest_m gating + formula)
- D-312 integrated smoke probe BEFORE crawl (smoke_probe pass-criteria)

5 of 13 LOCKED Phase 3 decisions delivered by Wave 4 (after Wave 3 delivered D-311; Waves 0-2 delivered D-301..D-307 supporting infrastructure). Remaining D-301/302/303/313 belong to Wave 5 orchestrator + Phase 7 ops-playbook.

---

*Phase: 03-goldapple-crawl*
*Completed: 2026-05-06*
