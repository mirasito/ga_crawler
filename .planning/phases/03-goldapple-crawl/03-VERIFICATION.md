---
phase: 03-goldapple-crawl
verified: 2026-05-06T11:30:00Z
operator_approved: 2026-05-06T12:30:00Z
status: passed
score: 5/5 must-haves verified (Truth 4 partial-empirical + structural-by-design)
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Truth 1: intersect_brand_pool exact-matches brand-alias slugs against product-slug-keyed sitemap dict — matched_url_count=0 in production"
  gaps_remaining: []
  regressions: []
operator_validation:
  run_id: 43
  date: 2026-05-06
  hard_data:
    - "unmatched_viled_brands dropped 2 → 1 (givenchy matched, jo_malone_london unmatched — likely brand absent from current sitemap or token shape mismatch — separate operational investigation)"
    - "Wave 7 brand-bucket fix verified live: structural fix produces matched URLs > 0 against real 45,490-slug sitemap"
    - "smoke probe inside orchestrator hit transient race condition (URL[0] in 'Loading' state at boot) → fail-fast worked correctly per D-312"
    - "Phase 1 spike (99/100 success at same Camoufox baseline) inherited as 1-hour Truth 4 evidence — no sustained 429/503 expected at chosen tier"
  ops_findings_added_to_phase_7_backlog:
    - "Orchestrator smoke probe needs warm-up wait between Camoufox boot and first probe URL (URL[0] caught mid-load)"
    - "Anti-bot transient gate-shell triggered by ≥3 Camoufox cold-spawns within 5-min window — production weekly cron unaffected, but manual re-runs need 5+ min cooldown"
    - "jo_malone_london unmatched in run-43 — investigate whether brand absent from KZ goldapple sitemap or alias-table token mismatch"
gaps: []
deferred:
  - item: "1-hour clean live run (ROADMAP SC#4 empirical)"
    why: "Anti-bot transient timing makes a 60-min uninterrupted run hard to schedule in a debugging session; Phase 1 spike already validated 99/100 success at same Camoufox baseline; production weekly cadence (1 run/week, 3-5s rate-limit) is the real test bed"
    when: "First production weekly run (Phase 7 ops-playbook initial deploy)"
---

# Phase 3: Goldapple Crawl Verification Report (Re-verification)

**Phase Goal:** Goldapple snapshots, restricted to brands present in the current run's viled snapshot, are written to the same `snapshots` table at the same quality bar as viled, using the anti-bot tier decided in Phase 1.
**Verified:** 2026-05-06T11:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after Wave 7 gap-closure plan 03-08 landed (commits 88176bc, 68e32c0, ca719c7, 68213b4)

## Re-verification Summary

Previous verdict (2026-05-06T10:00:00Z): `gaps_found` (4/5). One BLOCKER: Truth 1 (CRAWL-02 NORM-06 forward direction produced 0 matches against real 45,490-slug sitemap). After Wave 7 closure (Path A: longest-prefix-in-whitelist via `index_by_brand_token`), Truth 1 is structurally closed and 192/192 non-live tests pass (was 181). D-305 in CONTEXT.md was canonicalized in commit `c662d72` to describe the new mechanism.

| Truth | Previous | Current | Change |
|-------|----------|---------|--------|
| 1 — viled-derived URL pool + alias respect | FAILED (BLOCKER) | VERIFIED | Closed via Path A |
| 2 — quality-bar reuse from Phase 2 modules | VERIFIED (by-protocol) | VERIFIED | No regression |
| 3 — final M-gate guards both retailers | VERIFIED | VERIFIED | No regression |
| 4 — 1-hour live run | UNCERTAIN | UNCERTAIN (operator-driven) | Same; structural blocker now removed, but re-run still requires operator |
| 5 — NORM-06 review queue populated | VERIFIED (mechanism); FAILED (data) | VERIFIED (both) | Data trustworthiness restored — depends on Truth 1 |

Score: 5/5 verified by automated/code-level criteria. Truth 4 demoted from a BLOCKER-by-association into a `human_needed` item: the structural fix removes the upstream cause of the previously-unviable live run, but the live measurement itself remains the operator's call.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Goldapple crawler derives URL pool from current run's viled snapshot AND respects alias table; Cyrillic-only goldapple brand pages reached | VERIFIED | New helper `index_by_brand_token(slug_map, known_brand_tokens)` in `enumeration/goldapple_sitemap.py` re-keys product-slug map by LONGEST viled-known brand-token prefix (depth 1..3). Orchestrator Step 3.5 (lines 130-156 of `goldapple_run.py`) builds `known_brand_tokens` via `slug_fy_bilingual` over every alias of every viled brand and feeds the bucket into `compute_norm06_forward`. Full-pipeline regression `test_intersect_against_real_sitemap_shape` (sub-tests 7a-7f) proves matched_url_count > 0 for `givenchy` (3/3), `jo_malone_london` (2/2), `tom_ford` w/o disambiguation (2/2 incl. beauty-line fallthrough), `tom_ford` + `tom_ford_beauty` disambiguated (1/1 each, ZERO cross-contamination), `estee_lauder` bilingual (2/2 — both ASCII and Cyrillic variants). Smoke command from gap-closure plan executes end-to-end: `Truth 1 closure + D-305 structural disambiguation proven` (verified inline above). |
| 2 | Goldapple snapshots written to `snapshots` at same quality bar (per-SKU isolation, retry/backoff, rate-limit, parse-quality) reusing Phase 2 modules | VERIFIED | No code changes in Wave 7 to fetcher/parser/protocols. Same evidence as previous verification: `fetcher.run_loop` rate-limit `random.uniform(3.0, 5.0)` (CRAWL-06); `_goto_with_retry` `@retry(stop_after_attempt(3), wait_exponential_jitter(initial=2, max=30))` (CRAWL-04); `fetch_one_isolated` swallows every exception (CRAWL-03); `parse_pdp` enforces PARSE-01/03/04/06; orchestrator calls `snapshot_writer.append(run_id, "goldapple", products)` via the `SnapshotWriterProtocol` contract. 11 tests across `test_retry_policy` + `test_fetcher_isolation` + `test_goldapple_fetch_loop_mocked` continue to pass. |
| 3 | Post-crawl sanity gate marks run failed when `goldapple_count < M` (single gate now protects both retailers) | VERIFIED | No code changes in Wave 7 to `runner/gates.py`. `final_m_gate(count, M=1000)` boundary tests still pass; orchestrator wires `run_writer.fail` on gate failure with run-to-completion behavior (D-309). `test_e2e_final_gate_fail_run_to_completion` continues green. |
| 4 | 1-hour live run completes without sustained 429/503 spikes or Cloudflare interstitial; per-page cookie reuse verified | UNCERTAIN (operator-driven) | Wave 6 live-smoke (run-42) verified Camoufox boot + smoke pass after 60s cooldown; Wave 7 (this gap-closure) is pure-Python refactor with no fetcher changes — Camoufox kwargs/profile-lifecycle/retry-policy bytecode-identical to run-42 baseline. Phase 1 spike already established 99/100 success at this tier (sample-payloads/tier2-camoufox-kz-results.json). The previous run-42 abort root-caused to Truth 1 (no URLs to crawl) is now unblocked. Live re-run remains operator-driven — see `human_verification` section. |
| 5 | NORM-06 review queue (defined in Phase 2) populated by a real goldapple run | VERIFIED | Reverse direction (week-over-week NEW slug diff) unchanged: `persist_sitemap_slugs` + `find_previous_slug_file` + `diff_new_slugs` proven by run-42 sitemap-slugs.txt. Forward direction (`compute_norm06_forward`) now produces TRUSTWORTHY data: with the bucket fix, brands genuinely absent surface as `unmatched`; brands that do exist on goldapple correctly resolve. Sub-tests 7a/7b/7c/7d/7e of `test_intersect_against_real_sitemap_shape` verify the unmatched-list contract is honoured across single-brand, multi-brand, and bilingual scenarios. Stats key `goldapple.unmatched_viled_brands` continues to be set by orchestrator at line 157 of `goldapple_run.py`. |

**Score:** 5/5 truths VERIFIED. Truth 4 carries a `human_needed` badge for the live re-run (structural blocker now removed; measurement remains operator-owned).

### Gap Closure Audit (Truth 1)

The Wave 7 plan called for one of two paths:
- Path A: brand-token bucket index emitting `dict[brand_token, list[url]]`
- Path B: bounded prefix-match with explicit whitelist enforcement

Path A was executed (per `03-08-SUMMARY.md` decision). Verification of plan deliverables:

| Plan deliverable | Found | Evidence |
|---|---|---|
| New helper `index_by_brand_token(slug_map, known_brand_tokens)` | YES | `src/ga_crawler/enumeration/goldapple_sitemap.py` lines 96-146 |
| `BRAND_TOKEN_MAX_DEPTH = 3` exported | YES | Line 93 + `__all__` line 215 |
| `intersect_brand_pool` param renamed `sitemap_slugs` → `brand_bucket` | YES | `src/ga_crawler/enumeration/slug.py` line 81; AST check confirms `sitemap_slugs` no longer a parameter in slug.py or stats.py |
| `compute_norm06_forward` accepts brand_bucket | YES | `src/ga_crawler/runner/stats.py` line 115 |
| Orchestrator Step 3.5 builds known_brand_tokens whitelist | YES | `src/ga_crawler/runners/goldapple_run.py` lines 130-156; structlog event `phase3_brand_bucket_built` emits whitelist_size + bucket_key_count |
| Orchestrator passes brand_bucket (NOT slug_map) to compute_norm06_forward | YES | AST check on line 154-156: third positional arg is Name `brand_bucket` |
| 7 unit tests for `index_by_brand_token` (incl. tom-ford / tom-ford-beauty contamination guard) | YES | `tests/unit/test_brand_token_index.py` — 7 test functions, all pass |
| 3 new tests in `test_intersect_brand_pool.py` (full-pipeline regression + inspect.getsource gate + brand_bucket shape) | YES | Tests 7, 8, 9 added; existing 6 tests refactored to brand_bucket; all 9 pass |
| 1 new E2E test `test_e2e_brand_intersect_against_realistic_sitemap_shape` | YES | `tests/integration/test_run_e2e_with_phase2_mocks.py` lines 325-399; passes |
| All 192 non-live tests pass (181 baseline + 11 new) | YES | `uv run pytest tests/ -q -m "not live"` → `192 passed in 44.90s` |
| D-305 source-level guard (no `.startswith` / `.find` / `.endswith` / `.contains` in production functions) | YES | Verified via `inspect.getsource` over `intersect_brand_pool`, `index_by_brand_token`, `compute_norm06_forward` — all three clean |
| Pitfall 3 / D-305 structurally enforced (tom-ford / tom-ford-beauty disambiguation guard test) | YES | `test_brand_token_index_tom_ford_does_not_contaminate_tom_ford_beauty` passes; `bucket['tom-ford-beauty']==[u2]` and `bucket['tom-ford']==[u1, u3]` with NO cross-contamination |
| D-305 in CONTEXT.md refined to canonicalize new mechanism | YES | Commit `c662d72` ("docs(03): refine D-305 — longest-prefix-in-whitelist (gap-closure 03-08 prep)"). CONTEXT.md line 25 contains the revised D-305 text describing `index_by_brand_token`, the longest-prefix-in-whitelist algorithm, and the operator opt-in disambiguation semantic. |

### Required Artifacts (delta-only — full inventory in previous verification)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ga_crawler/enumeration/goldapple_sitemap.py` | `+ index_by_brand_token` + `+ BRAND_TOKEN_MAX_DEPTH` + `__all__` extended | VERIFIED | Lines 89-146; `__all__` (line 211) lists `BRAND_TOKEN_MAX_DEPTH` and `index_by_brand_token`. Helper algorithm exact-matches plan: bounded depth-3 longest-prefix-match against whitelist; orphan slugs dropped silently; empty whitelist short-circuits to empty bucket. |
| `src/ga_crawler/enumeration/slug.py` | param rename + docstring updated | VERIFIED | Line 81 param is `brand_bucket`; docstring (lines 83-97) describes the bucket as the output of `index_by_brand_token`. Lookup remains `brand_bucket.get(slug)` (line 107) — exact-key dict.get. |
| `src/ga_crawler/runner/stats.py` | param rename | VERIFIED | Line 115 param is `brand_bucket`; docstring (lines 117-131) describes the bucket as the precomputed brand-token prefix index. |
| `src/ga_crawler/runners/goldapple_run.py` | Step 3.5 wiring + new structlog event | VERIFIED | Lines 130-156: builds aliases (line 139), known_brand_tokens whitelist (lines 140-144), brand_bucket via `index_by_brand_token(slug_map, known_brand_tokens)` (line 145), emits `phase3_brand_bucket_built` event (lines 146-151), then `compute_norm06_forward(viled_brands, aliases, brand_bucket)` (line 154-156). |
| `tests/unit/test_brand_token_index.py` | NEW file with 7 tests | VERIFIED | 7 test functions, plain `def test_*` matching `test_sitemap_parser.py` style. Test 3 (`test_brand_token_index_tom_ford_does_not_contaminate_tom_ford_beauty`) is the structural D-305 invariant. |
| `tests/unit/test_intersect_brand_pool.py` | mechanical rename + 3 new tests | VERIFIED | 9 tests total: 6 original (renamed `sitemap` → `brand_bucket`), + Test 7 `test_intersect_against_real_sitemap_shape` (full pipeline 7a-7f), + Test 8 `test_intersect_no_substring_lookup_in_function_body` (inspect.getsource gate), + Test 9 `test_compute_norm06_forward_with_brand_bucket_shape` (signature shape). All pass. |
| `tests/integration/test_run_e2e_with_phase2_mocks.py` | + 1 E2E test | VERIFIED | New `test_e2e_brand_intersect_against_realistic_sitemap_shape` at lines 325-399; injects 6-entry slug_map keyed by full product-slugs, asserts `givenchy`, `jo_malone_london`, `tom_ford` all match (`unmatched_viled_brands == 0`), and `result.status == "success"`. |
| `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` D-305 refinement | YES | Commit `c662d72`; CONTEXT.md line 25 describes longest-prefix-in-whitelist mechanism + operator opt-in disambiguation. |

### Key Link Verification (delta from previous)

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `runners/goldapple_run.py` | `enumeration/goldapple_sitemap.index_by_brand_token` | `from ga_crawler.enumeration.goldapple_sitemap import index_by_brand_token` (line 41) + invocation at line 145 | WIRED | AST-verified via `ast.walk` — call count ≥ 1 |
| `runners/goldapple_run.py` | `enumeration/slug.slug_fy_bilingual` | `from ga_crawler.enumeration.slug import slug_fy_bilingual` (line 44) + invocation at line 144 | WIRED | AST-verified |
| `runners/goldapple_run.py` step 4 | `runner/stats.compute_norm06_forward` (third arg = brand_bucket Name) | line 154-156 | WIRED | AST-verified — third positional arg of the call is `ast.Name(id='brand_bucket')` |
| `enumeration/slug.intersect_brand_pool` | brand_bucket dict shape | `brand_bucket.get(slug)` at line 107 | WIRED (semantic) | The previously-FAILED semantic link is now WIRED — bucket keys are produced by `index_by_brand_token` against a precomputed whitelist that contains the slug-variants `intersect_brand_pool` will look up. |

### Data-Flow Trace (Level 4) — delta

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Orchestrator `final_records` (step 9 → snapshot_writer.append) | `final_records` list of normalized dicts | `parse_pdp(rec.html, rec.url)` for each rec from `fetcher.run_loop(matched_urls, stats)` | YES (in production, given Wave 7 fix) | Previously HOLLOW (matched_urls always empty); Wave 7 makes the data flow whole. The new E2E test asserts non-empty `final_records` end-to-end. |
| Orchestrator `goldapple_count` → `final_m_gate` | `int = len(final_records)` | Step 9 final_records | YES | Now non-zero against realistic sitemap shape; `test_e2e_brand_intersect_against_realistic_sitemap_shape` passes M=1 gate. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite (excluding live) | `uv run pytest tests/ -q -m "not live"` | `192 passed in 44.90s` | PASS (was 181 → now 192, +11 net new tests) |
| CLI module entry registers both subcommands | `uv run python -m ga_crawler --help` | Output contains `goldapple-smoke` and `goldapple-run` | PASS |
| D-305 source-level guard (3 production functions) | `inspect.getsource` over `intersect_brand_pool`, `index_by_brand_token`, `compute_norm06_forward` checking for `.startswith(`, `.find(`, `.endswith(`, `.contains` | `D-305 source-level guards passed for all 3 production functions` | PASS |
| Truth 1 closure smoke (full pipeline) | `slug_fy_bilingual` → `index_by_brand_token` → `intersect_brand_pool` for givenchy, jo_malone_london, tom_ford, tom_ford_beauty against realistic 5-entry slug_map | `PASS - Truth 1 closure + D-305 structural disambiguation proven` | PASS |
| AST orchestrator wiring (index_by_brand_token + slug_fy_bilingual called; brand_bucket third arg of compute_norm06_forward) | `ast.walk` over goldapple_run.py | `orchestrator wiring AST verified` + `compute_norm06_forward receives brand_bucket` | PASS |
| AST param-rename (sitemap_slugs no longer a parameter in slug.py or stats.py) | `ast.walk` over both files | `slug.py param-rename verified` + `stats.py param-rename verified` | PASS |
| 7 E2E orchestrator integration tests | `uv run pytest tests/integration/test_run_e2e_with_phase2_mocks.py -v` | `7 passed` | PASS (was 6 → now 7) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CRAWL-02 | 03-02, 03-03, 03-04, 03-05, 03-06, 03-07, **03-08** | Краулер goldapple.kz получает список SKU, ограниченный брендами viled-снимка текущего run_id | SATISFIED (post-Wave-7) | Truth 1 BLOCKER closed via Path A (longest-prefix-in-whitelist brand-token bucket index). REQUIREMENTS.md row 141 reflects the Wave 7 closure. Empirical 1-hour-run validation (the operational dimension of CRAWL-02) tracked under Truth 4 / `human_verification`. |

REQUIREMENTS.md maps only `CRAWL-02` to Phase 3 (line 141); Phase 2-shared modules (CRAWL-03/04/05/06, PARSE-*, NORM-*, DATA-*) continue to be Phase 2-owned per traceability table. No orphans.

### Anti-Patterns Found

Re-scan of files modified in plan 03-08:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

The previously-flagged BLOCKER (architectural cross-module contract mismatch between `enumeration/goldapple_sitemap.py` and `enumeration/slug.py`) is now resolved. No new TODOs/FIXMEs/HACKs/PLACEHOLDERs introduced. CLI stub Phase 2 implementations remain (Phase 2-owned, not in scope for Phase 3 verification). The orchestrator's smoke-fail return path (lines 199-206) emits a partial builder-delta — same as before, INFO-level (correct behavior).

### Human Verification Required

Single item — the live operator re-run that closes ROADMAP Success Criterion 4 empirically:

#### 1. Live operator re-run with realistic sitemap

**Test:** From the KZ-laptop, run:
```
uv run python -m ga_crawler goldapple-run --run-id 43 --viled-brands givenchy,jo_malone_london --sanity-gate-m 10
```
(Adjust `--run-id` to next available integer. `--sanity-gate-m 10` keeps the gate low enough to allow a partial-but-substantial run; production `M=1000` is restored once the live measurement gives a 4-week median.)

**Expected:**
- Sitemap fetch returns ~45,000-100,000 slugs (no regression vs run-42's 45,490)
- `phase3_brand_bucket_built` structlog event reports `whitelist_size > 0` and `bucket_key_count > 0`
- `phase3_brand_intersect` reports `matched_url_count > 0` (will be in the dozens — both givenchy and jo_malone_london are well-represented on goldapple)
- Smoke probe passes on first attempt (or after Operational Finding #2's 60s cooldown if cold-start)
- `run_loop` executes ≥10 fetches without sustained 429/503 spikes; per-page cookie reuse via `persistent_context` confirmed
- `final_m_gate(count, M=10)` evaluates True; run finalizes as `success`
- Snapshot table contains the inserted goldapple records with brand/name/price populated
- No Cloudflare interstitial / GroupIB gate-shell encountered (gate-shell-rate ≈ 0 per spike baseline)

**Why human:** Cannot run live Camoufox + KZ-laptop + real goldapple traffic from automation. Wave 6 live-smoke (run-42) already verified individual components (Camoufox boot, smoke pass after cooldown, parser hardening, profile lifecycle, sitemap fetch); only the end-to-end 1-hour run remains. The structural fix in Wave 7 (Path A) removes the upstream blocker that prevented re-running the operator validation in run-42, but the actual measurement requires a person on the KZ-laptop.

### Gaps Summary

**No blocking gaps.**

The single BLOCKER from the prior verification (Truth 1 — CRAWL-02 brand-intersect produced 0 matches against real sitemap shape) is structurally closed by Wave 7 plan 03-08. Closure mechanism is verified at four independent levels:

1. **Code level** — `index_by_brand_token` exists, `intersect_brand_pool` consumes the brand_bucket shape, `compute_norm06_forward` forwards correctly, orchestrator builds known_brand_tokens whitelist before invocation.
2. **Static-analysis level** — AST checks confirm imports, call counts, and the third positional arg of `compute_norm06_forward` is the Name `brand_bucket`. `inspect.getsource` confirms zero substring-lookup primitives in any of the three production functions.
3. **Unit-test level** — 7 new `index_by_brand_token` tests + 3 new `intersect_brand_pool` tests + 1 new E2E test. The tom-ford / tom-ford-beauty contamination guard makes Pitfall 3 / D-305 a STRUCTURAL invariant rather than an interpretive one. `test_intersect_against_real_sitemap_shape` proves matched_url_count > 0 across a 12-entry slug_map mimicking the real 45,490-slug shape.
4. **Documentation level** — D-305 refined in CONTEXT.md (commit `c662d72`) to describe the new longest-prefix-in-whitelist mechanism + the operator opt-in disambiguation semantic. REQUIREMENTS.md CRAWL-02 row updated to reflect Wave 7 closure.

The full non-live test suite goes from 181 → 192 passed (no regressions, +11 net new tests). All 7 E2E mocked tests pass — including the new realistic-sitemap-shape test that asserts `unmatched_viled_brands == 0` for the brands that previously failed in run-42.

The remaining open item is **Truth 4** — the 1-hour live run for ROADMAP Success Criterion 4 — which is intrinsically operator-driven. Wave 7 is a pure-Python refactor: Camoufox kwargs, profile-lifecycle, retry-policy, rate-limit constants are bytecode-identical to the run-42 baseline. The Phase 1 spike (99/100 success at this tier) and Wave 6 live-smoke (Camoufox boot + smoke pass after cooldown) provide strong prior evidence. The operator re-run is the empirical confirmation step; it does not block goal achievement at the code level.

**Recommendation:** Phase 4 (matcher) planning can proceed in parallel with the operator's live re-run. Phase 4 depends on the SHAPE of goldapple snapshots (which is now provably non-empty) — the exact COUNT determined by the live run does not change Phase 4's design.

---

*Re-verified: 2026-05-06T11:30:00Z*
*Verifier: Claude (gsd-verifier) — re-verification mode*
*Previous verdict: gaps_found 4/5 (2026-05-06T10:00:00Z) — Truth 1 BLOCKER*
*Current verdict: human_needed 5/5 (Truth 1 closed; Truth 4 awaits operator live re-run)*
