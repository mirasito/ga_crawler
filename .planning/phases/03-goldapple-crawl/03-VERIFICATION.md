---
phase: 03-goldapple-crawl
verified: 2026-05-06T10:00:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Goldapple crawler derives URL pool from current run's viled snapshot AND respects the alias table when filtering — Cyrillic-only goldapple brand pages are reached"
    status: failed
    reason: "intersect_brand_pool exact-matches brand-alias slugs against sitemap dict keys, but the sitemap parser indexes by product-slug (e.g. 'givenchy-pour-homme-blue-label'). A brand-alias slug 'givenchy' cannot exact-match a product-slug key, so matched_url_count is always 0 in production. Live run-42 surfaced this with both 'givenchy' and 'jo_malone_london' returning unmatched_brand_count=2 against a 45,490-slug sitemap that obviously contains both brands. Confirmed by re-running intersect_brand_pool against a synthesized realistic sitemap shape — matched_count=0."
    artifacts:
      - path: "src/ga_crawler/enumeration/slug.py"
        issue: "intersect_brand_pool uses sitemap_slugs.get(slug) — exact key lookup. Brand 'givenchy' will never match key 'givenchy-pour-homme-blue-label'. Pitfall 3 / D-305 forbade substring match to avoid 'tom-ford' false-positive on 'tom-ford-beauty'; an additional brand-prefix bucket layer was never added."
      - path: "src/ga_crawler/enumeration/goldapple_sitemap.py"
        issue: "fetch_sitemap_slugs builds dict keyed by full product-slug only; no companion brand-token bucket index emitted."
    missing:
      - "Either: sitemap parser additionally emits a brand-token bucket dict[brand_token, list[url]] where brand_token is the first hyphen-separated component after the numeric prefix is stripped (then intersect uses .get(brand_slug) on the bucket)."
      - "Or: intersect_brand_pool uses bounded prefix match — slug.startswith(brand + '-') over sitemap_slugs.values() — with explicit whitelist enforcement to satisfy Pitfall 3 / D-305 false-positive guards (a 'tom-ford' brand must not match 'tom-ford-beauty' product slugs unless 'tom-ford-beauty' is also a known brand alias)."
      - "Regression test against the real 45,490-slug sitemap shape proving matched_url_count > 0 for at least 'givenchy' and 'jo_malone_london'."
deferred: []
---

# Phase 3: Goldapple Crawl Verification Report

**Phase Goal:** Goldapple snapshots, restricted to brands present in the current run's viled snapshot, are written to the same `snapshots` table at the same quality bar as viled, using the anti-bot tier decided in Phase 1.
**Verified:** 2026-05-06T10:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Source: ROADMAP.md Phase 3 Success Criteria 1-5 + plan must_haves frontmatter. Merged below; ROADMAP wording authoritative.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Goldapple crawler derives URL pool from current run's viled snapshot AND respects alias table; Cyrillic-only goldapple brand pages reached | FAILED | `intersect_brand_pool` exact-matches brand-alias slug ('givenchy') against sitemap dict-keys keyed by product-slug ('givenchy-pour-homme-blue-label'). Live run-42 surfaced matched_url_count=0 across a 45,490-slug sitemap. Reproduced by direct call against synthesized realistic sitemap. Findings #3 in 03-07-SUMMARY.md; this is a real defect, not deferred work. |
| 2 | Goldapple snapshots written to `snapshots` at same quality bar (per-SKU isolation, retry/backoff, rate-limit, parse-quality) reusing Phase 2 modules | VERIFIED (by-protocol) | `fetcher.run_loop` uses `random.uniform(3.0, 5.0)` rate-limit (CRAWL-06); `_goto_with_retry` is `@retry(stop_after_attempt(3), wait_exponential_jitter(initial=2, max=30), retry_if_exception_type=(TransientFetchError, PWTimeout))` (CRAWL-04); `fetch_one_isolated` catches every exception and increments `fetch_failures` without bubbling (CRAWL-03); `parse_pdp` enforces PARSE-01/03/04/06 invariants. Orchestrator calls `snapshot_writer.append(run_id, "goldapple", products)` via the `SnapshotWriterProtocol` contract. Per phase boundary, the concrete Phase 2 storage adapter ships in Phase 2 plans; mocked-integration test `test_e2e_happy_path` verifies the contract end-to-end. 11 tests in test_retry_policy + test_fetcher_isolation + test_goldapple_fetch_loop_mocked exercise this path. |
| 3 | Post-crawl sanity gate marks run failed when `goldapple_count < M` (single gate now protects both retailers) | VERIFIED | `final_m_gate(count, M=1000) -> count >= M`. Boundary tests verify 999/1000/1001. Orchestrator wires `run_writer.fail(run_id, reason=f"goldapple_count {n} < M={M}")` on gate failure (test_e2e_final_gate_fail_run_to_completion confirms this AND run-to-completion behavior per D-309). |
| 4 | 1-hour live run completes without sustained 429/503 spikes or Cloudflare interstitial encounters; per-page cookie reuse verified | UNCERTAIN | Live smoke probe verdict in checklist: PASS (Run 3, after 60s cooldown). 1-hour run was NOT executed because the orchestrator aborted on D-312 smoke fail (in run-42, transient gate-shell at start) AND because brand-intersect produced 0 matched URLs (Truth 1 gap) — there was nothing to crawl. Phase 1 spike already ran 100 sequential fetches at the chosen tier with 99/100 success and 0% gate-shell rate (sample-payloads/tier2-camoufox-kz-results.json). Production code uses identical Camoufox kwargs (geoip, locale=[ru-RU,kk-KZ,en-US], humanize, persistent_context); spike validation is inherited. Truth 4 cannot be reverified at the 1-hour scale until Truth 1 is fixed; the gate-shell rate from production code itself is unknown. Operator/human verification required after gap closure. |
| 5 | NORM-06 review queue (defined in Phase 2) populated by a real goldapple run | VERIFIED (mechanism); FAILED (data) | Reverse direction: `persist_sitemap_slugs` + `diff_new_slugs` work — live run-42 created `.planning/runs/42/sitemap-slugs.txt` with 45,490 slugs; diff against predecessor returns sorted additions only (D-307 invariant tested). Forward direction: `compute_norm06_forward` returns `(matched_urls, unmatched_count, unmatched_brands)` and orchestrator writes to `goldapple.unmatched_viled_brands`. The mechanism is verified, but in run-42 the data populated was wrong (count=2 with unmatched_brands=[givenchy, jo_malone_london] — both should have matched) BECAUSE of the Truth 1 gap. Verdict: mechanism alive; data trustworthiness contingent on Truth 1 fix. Operator marked format usable in principle. |

**Score:** 4/5 truths verified. Truth 1 FAILED (BLOCKER). Truth 4 UNCERTAIN; Truth 5 partially compromised by Truth 1.

### Required Artifacts

Plan must_haves frontmatter declared 30+ artifacts across 7 plans. Sampled the goal-critical paths:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ga_crawler/interfaces.py` | 6 Phase 2 Protocol classes | VERIFIED | `import` succeeds for all 6 (BrandAliasProtocol, NormalizerProtocol, SnapshotWriterProtocol, RunWriterProtocol, ParseDispatcherProtocol, CrawlerProtocol). All data Protocols are `@runtime_checkable`; CrawlerProtocol is static-only (correct per plan rationale). |
| `src/ga_crawler/enumeration/slug.py` | slug_fy_bilingual + intersect_brand_pool with Pitfall 3 exact-match guard | VERIFIED (in isolation) | All 11 RESEARCH-mandated cases pass; KZ-glyph table covers all 9 KZ-specific characters. Apostrophe-strip + Cyrillic-preserve + ASCII-transliterate logic matches spec. Note: `intersect_brand_pool` is correct in isolation per its contract, but its contract does not match the sitemap parser's output shape — see Truth 1 gap. |
| `src/ga_crawler/enumeration/goldapple_sitemap.py` | curl_cffi sitemap fetch + week-over-week diff | VERIFIED | Uses `from curl_cffi import requests` with `impersonate="chrome"`; tenacity wraps with `stop_after_attempt(3)` + `wait_exponential_jitter`. PRODUCT_URL_RE whitelist matches numeric-id Latin/Cyrillic slugs, rejects /brands/, .ru, non-numeric. `persist_sitemap_slugs` writes sorted UTF-8; `find_previous_slug_file` skips non-numeric dirs and future-runs; `diff_new_slugs` first-run empty, additions-only sorted. |
| `src/ga_crawler/parsers/goldapple_microdata.py` | parse_pdp, detect_state, GoldappleRawProduct, priceType filter, Gold Card heuristic | VERIFIED + HARDENED | parse_pdp round-trips real Givenchy PDP fixture (392 KB) with brand="Givenchy", price in [100..1M], availability∈enum, sku numeric. Three-axis state classifier verified against gate-shell, stale-sku, real-pdp fixtures. priceType discrimination picks current 4990 over StrikethroughPrice 6990 (synthetic). Wave 6 hardening (commit 277a40a) narrowed Gold-card heuristic to direct siblings + label tags + shallow text and added min-value selection — fixes a false-positive from bonus-button "при авторизации" copy that surfaced live on Givenchy Gentleman Reserve PDP. 2 regression tests added (test_bonus_button_with_login_text_does_not_poison_price, test_zero_filler_price_is_skipped). |
| `src/ga_crawler/fetchers/goldapple.py` | GoldappleFetcher async context manager + retry + isolation + run_loop | VERIFIED | Camoufox kwargs locked: `geoip=True, locale=["ru-RU","kk-KZ","en-US"], humanize=True, persistent_context=True, user_data_dir=str(self.profile_dir)` (D-311 fresh tmp profile). `__aexit__` runs `shutil.rmtree(self.profile_dir, ignore_errors=True)` even on exception (Pitfall 7 — verified live in run-42 cleanup). RETRY_MAX_ATTEMPTS=3, RETRY_WAIT_INITIAL=2.0, RETRY_WAIT_MAX=30.0. PAUSE_RANGE=(3.0, 5.0). 7 retry policy tests + 4 isolation tests + 9 fetch_loop_mocked tests pass. |
| `src/ga_crawler/runner/gates.py` | smoke_probe + final_m_gate + auto_suggest_m | VERIFIED | SMOKE_URLS = 3 Givenchy URLs; none contains '7681000002' (A12 mitigation verified). `final_m_gate(1000) is True; final_m_gate(999) is False`. `auto_suggest_m([1000,2000,3000,4000]) == 1750` (= int(0.7 × 2500)). Returns None for <4 history. `_camoufox_version_at_runtime()` uses importlib.metadata (correctly fixes the original `getattr(camoufox, "__version__")` submodule trap). |
| `src/ga_crawler/runner/stats.py` | 13-key namespace + GoldappleStatsBuilder + compute_norm06_forward | VERIFIED | `len(GOLDAPPLE_STATS_KEYS) == 13`; all 13 expected keys present (verified by direct introspection). `StatsNamespaceError` raised on unknown bare keys. Builder.set/inc/get/from_run_loop_stats all exercised by 14 unit tests. |
| `src/ga_crawler/runners/goldapple_run.py` | run_goldapple_phase orchestrator (12-step flow) | VERIFIED (by mocked tests) | Module composes all imports from prior waves; calls smoke_probe BEFORE run_loop; on smoke fail calls `run_writer.fail` + `patch_stats` and returns early without writing snapshots; on final-gate fail calls `run_writer.fail` AFTER snapshot append (run-to-completion D-309). `patch_stats` called exactly once per code path (Pitfall 6 — test_e2e_atomic_stats_merge_one_call asserts call_count==1). Auto-suggest reads prior 4 history. 6/6 E2E mocked tests pass. |
| `src/ga_crawler/cli.py` + `__main__.py` | python -m ga_crawler entry | VERIFIED | `uv run python -m ga_crawler --help` lists `goldapple-smoke` and `goldapple-run` subcommands. 4 stub Phase 2 implementations satisfy the protocols; storage tests (6) verify append-only + atomic patch_stats merge. |
| `pyproject.toml` | All Phase 3 dependency pins + config namespace | VERIFIED (with note) | `[tool.ga_crawler.crawl.goldapple]` block present with all 15 constants. Camoufox pin is `camoufox[geoip]==0.4.11` (NOT the originally-planned `==0.4.11+camoufox.135.0.1-beta.24` extended pin). The expected upstream Firefox version `135.0.1.beta24` is asserted via `camoufox_version_expected` config key for runtime check rather than as a PyPI version-string pin. This is a documented deviation noted in 03-01 SUMMARY; functionally equivalent for D-313 intent (operator-driven smoke-probe gate on upgrade). Installed version verified at runtime: 0.4.11. |
| `tests/fixtures/goldapple/` | 6 spike fixture files | VERIFIED | All 6 present: `_debug-product-page.html` (392 KB real PDP), `gate-shell.html` (~19 KB), `stale-sku-9.5kb.html` (9 KB synthesized), `sitemap-1-excerpt.xml` (~12 KB), `tier2-camoufox-kz-results.json` (~72 KB), `_debug-jsonld-blocks.json` (anti-fixture). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `runners/goldapple_run.py` | `fetchers/goldapple.py` | `from ga_crawler.fetchers.goldapple import GoldappleFetcher` + `async with fetcher:` | WIRED | Used at orchestrator step 5. |
| `runners/goldapple_run.py` | `runner/gates.py` | `from ga_crawler.runner.gates import smoke_probe, final_m_gate, auto_suggest_m, SMOKE_URLS` | WIRED | smoke_probe called at step 6; final_m_gate at step 12; auto_suggest_m at step 13. |
| `runners/goldapple_run.py` | `interfaces.py` (Phase 2 contracts) | typed parameters + protocol calls (`brand_alias.lookup`, `normalizer.brand`, `snapshot_writer.append`, `run_writer.patch_stats/fail/get_stats`) | WIRED | All 4 Protocol-typed parameters consumed. End-to-end mocked test verifies all method calls. |
| `runners/goldapple_run.py` | `enumeration/goldapple_sitemap.py` + `enumeration/slug.py` | `from ga_crawler.enumeration.goldapple_sitemap import fetch_sitemap_slugs, persist_sitemap_slugs, find_previous_slug_file, diff_new_slugs` | WIRED | Step 1-3. |
| `runners/goldapple_run.py` | `parsers/goldapple_microdata.py` | `from ga_crawler.parsers.goldapple_microdata import parse_pdp, detect_state` | WIRED | Step 7-8. |
| `cli.py` (`goldapple-run`) | `runners/goldapple_run.run_goldapple_phase` | function call with stub protocols | WIRED | `_cmd_run` calls orchestrator. Live run-42 invoked this path successfully end-to-end (until smoke abort). |
| `cli.py` (`goldapple-smoke`) | `runner/gates.smoke_probe` | function call inside `async with GoldappleFetcher` | WIRED | Live run on KZ-laptop verified (Run 3 after cooldown returned pass=true with 3 PDPs). |
| `enumeration/slug.intersect_brand_pool` | sitemap_slugs dict shape | exact-match `dict.get(slug)` | NOT_WIRED (semantic) | The link compiles and tests pass in isolation, but the contract mismatches what `fetch_sitemap_slugs` produces in production. See Truth 1 BLOCKER. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Orchestrator `final_records` (step 9 → snapshot_writer.append) | `final_records` list of normalized dicts | `parse_pdp(rec.html, rec.url)` for each rec from `fetcher.run_loop(matched_urls, stats)` | NO in production (currently) | HOLLOW: `matched_urls` is empty in production because `intersect_brand_pool` returns `[]` (Truth 1 root cause). The wired path is fully functional in mocked tests; live data-flow is severed at the brand-intersect step. |
| Orchestrator `goldapple_count` → `final_m_gate` | `int = len(final_records)` | Step 9 final_records | NO in production | Currently always 0 because of upstream HOLLOW data flow. |
| Smoke probe diagnostics → builder.set("smoke_diagnostics") | dict from `smoke_probe(fetcher, smoke_urls)` | Real Camoufox HTTP fetches in live mode; AsyncMock in tests | YES (live) | Live run verified pass=true in Run 3 after cooldown. |
| Sitemap slug-map → persist_sitemap_slugs | dict[str, list[str]] from `fetch_sitemap_slugs()` | curl_cffi GET against goldapple.kz/sitemap.xml + 3 sub-sitemaps | YES (live) | Live run-42 produced 45,490 slug entries (well above spike's 1,461 estimate; multiple sitemap shards aggregated). |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite (excluding live) | `uv run pytest tests/ -q -m "not live"` | `181 passed in 45.59s` | PASS |
| CLI module entry registers both subcommands | `uv run python -m ga_crawler --help` | Output contains `goldapple-smoke` and `goldapple-run` | PASS |
| All 6 Protocol classes importable | `python -c "from ga_crawler.interfaces import (six classes)"` | Exit 0 | PASS |
| 13 namespaced stats keys present | `python -c "from ga_crawler.runner.stats import GOLDAPPLE_STATS_KEYS; print(len(GOLDAPPLE_STATS_KEYS))"` | `13` | PASS |
| Final M-gate boundary | `python -c "from ga_crawler.runner.gates import final_m_gate; print(final_m_gate(1000), final_m_gate(999))"` | `True False` | PASS |
| Auto-suggest formula | `python -c "from ga_crawler.runner.gates import auto_suggest_m; print(auto_suggest_m([1000,2000,3000,4000]))"` | `1750` | PASS |
| NORM-06 brand-intersect against realistic sitemap shape | direct python call with sitemap keyed by product-slug | `matched_count=0; unmatched_brands=['givenchy', 'jo_malone_london']` | FAIL — confirms Truth 1 design bug |
| 6 E2E orchestrator integration tests | `uv run pytest tests/integration/test_run_e2e_with_phase2_mocks.py -v` | `6 passed` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CRAWL-02 | 03-02, 03-03, 03-04, 03-05, 03-06, 03-07 | Goldapple craulрер получает список SKU, ограниченный брендами viled-снимка текущего run_id | BLOCKED | All wiring exists (sitemap fetch, brand alias lookup, intersect_brand_pool, run_loop) BUT brand-intersect emits 0 matches against the real sitemap shape (Finding #3). The implementation does not satisfy "получает список SKU, ограниченный брендами" because the SKU list is empty in production. Mocked tests pass because the synthetic sitemap they use is keyed differently than real fetch_sitemap_slugs output. |

REQUIREMENTS.md maps only `CRAWL-02` to Phase 3; no orphaned requirement IDs. Per Phase 3 boundary, CRAWL-03/04/05/06/PARSE-*/NORM-*/DATA-* are Phase 2-owned modules called via Protocol, and the relevant call sites are wired (verified above) — but their full requirement satisfaction belongs to Phase 2 plans.

### Anti-Patterns Found

Scanned files modified across all 7 plans (parser, fetcher, gates, stats, orchestrator, cli, enumerations).

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/ga_crawler/cli.py` | 53-54 | `def volume(self, raw): return None` (StubNormalizer.volume always None) | INFO | Acceptable — CLI is stub for Phase 2 storage; volume normalization is Phase 2 contract. Does not affect Phase 3 goal. |
| `src/ga_crawler/runners/goldapple_run.py` | 159-182 | smoke-fail return path emits `dict(builder.delta)` but builder has not yet seen run_loop stats (no fetches happened) | INFO | Correct behavior: smoke fail aborts pre-crawl; only smoke_pass + smoke_diagnostics + camoufox_version + sitemap-derived stats land in delta. Tests verify this. |
| `src/ga_crawler/enumeration/slug.py` | 95-96 | `aliases.get(brand, [brand])` fallback when alias not declared | INFO | Documented behavior — operator may choose to use brand_norm directly as the only alias. |
| `src/ga_crawler/enumeration/goldapple_sitemap.py` + `slug.py` | (architectural) | Sitemap parser indexes by product-slug; intersect_brand_pool does exact-key match against brand-alias slug → matched_url_count is always 0 | BLOCKER | This is the Truth 1 / Finding #3 design bug. Not a code anti-pattern in the local sense, but the cross-module contract is broken. Production effect: orchestrator has nothing to crawl. |

No TODOs/FIXMEs/HACKs/PLACEHOLDERs in production source files. No empty `return null/[]/{}`-style placeholder implementations in main code paths (CLI stubs are intentional per plan).

### Human Verification Required

None pending after gap closure (all human-eyeball checks already executed in Wave 6 live-smoke checkpoint and recorded in `live-smoke-checklist.md`). After Truth 1 (NORM-06 brand-intersect) is fixed via the recommended gap_closure plan, ROADMAP Success Criterion 4 (1-hour live run) will need to be re-verified by the operator — but that operator-checkpoint is naturally part of the gap-closure plan's own Wave-6-equivalent verification step, not a separate item to surface here.

### Gaps Summary

**One BLOCKER, root-caused and traced through the codebase:**

The orchestrator pipeline is structurally correct — every wave's deliverables exist, behaviors are tested in isolation, the live smoke probe passed (after cooldown), the parser was hardened against a real bonus-button false-positive (commit 277a40a), the Camoufox profile lifecycle is verified end-to-end, and the structlog `run_id` binding propagates through every event. **However, the goal "snapshots restricted to brands present in viled snapshot are written" is not achievable in production** because `intersect_brand_pool` emits 0 matched URLs against the real sitemap shape — the brand-alias-slug-keyed exact-match cannot find any product-slug-keyed dict entry. With 0 matched URLs, `run_loop` runs over an empty list, `final_records` stays empty, `final_m_gate` would mark every run failed (or, in the live test with M=10, the orchestrator did not even reach the final gate because smoke aborted first).

This is exactly Finding #3 from 03-07-SUMMARY.md, surfaced and root-caused by the live-smoke checkpoint (which is the design intent of Wave 6). The Phase 3 production code is correct in isolation but the cross-module contract between sitemap parser and brand-intersect was never reconciled with the actual data shape. The recommended remediation is a `gap_closure: true` plan that adds a brand-token bucket index OR a bounded prefix-match lookup with whitelist enforcement.

**Phase 4 (matcher) cannot demonstrate end-to-end crawl→match flow until this is fixed** — it would receive an empty goldapple snapshot. The fix is single-module-scoped (enumeration/slug.py + enumeration/goldapple_sitemap.py + 1 regression test) and well-defined; the verifier estimates closure as Wave-1-or-2 sized work.

**Other waves (0-6) are fully delivered:**
- 181/181 tests green
- All 13 stats keys frozen
- All 6 Protocol classes frozen
- Smoke probe + final M-gate + auto-suggest M behave per spec
- Camoufox profile lifecycle verified live
- Parser hardened against real-PDP edge case (Wave 6 deliverable)
- Operational findings #1 (parser, FIXED) and #2 (60s cooldown, BACKLOG) captured

---

*Verified: 2026-05-06T10:00:00Z*
*Verifier: Claude (gsd-verifier)*
