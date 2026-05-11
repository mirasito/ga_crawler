---
phase: 03-goldapple-crawl
verified: 2026-05-11T09:00:00Z
status: human_needed
score: 5/5 must-haves verified (Truth 4 awaits operator live re-run of scripts/uat3_live_run.py)
overrides_applied: 0
re_verification:
  previous_status: passed_with_human_needed
  previous_score: 5/5
  reopened: 2026-05-11
  reopen_reason: "UAT Test 6 (Operational Finding #1 — cold-start Loading race) reproduced 4-of-4 cold runs by scripts/uat3_live_run.py; smoke_probe never reaches run_loop"
  gaps_closed:
    - "Operational Finding #1 (cold-start Loading race on URL[0] first nav after fresh Camoufox boot) — fixed at TWO layers: primary (warm-up nav in __aenter__) + safety net (retry-once in smoke_probe on exact Loading-race shape)"
    - "CR-01 from 03-REVIEW.md (`_is_loading_race` used literal 'checking device' instead of canonical GATE_TITLE_MARKER) — closed by commit 05b29a8: now reuses GATE_TITLE_MARKER from parsers.goldapple_microdata + adds block_reason='gate_shell_not_cleared' defence-in-depth check"
  gaps_remaining:
    - "Truth 4 (1-hour live run / SC#4) — operator-driven, deferred per 2026-05-06 deferral; first production weekly cron in Phase 7 is canonical test bed"
  regressions: []
  open_findings_not_in_scope:
    - "REVIEW WR-01 (asyncio.sleep not injectable in smoke_probe) — INFO/style; slows retry tests by 1s; defer"
    - "REVIEW WR-02 (_compute_price_extracted re-invokes parse_pdp on already-blocked records) — INFO/performance; not a correctness bug; defer"
    - "REVIEW WR-03 (phase3_smoke_probe_retry has no retry-outcome event) — observability gap; defer"
    - "REVIEW WR-04 (WARMUP_SETTLE_SECONDS always runs even on fast warm-up — +2s overhead per cron) — INFO/perf; accept as budget on weekly cadence"
    - "REVIEW WR-05 (PWTimeout fallback in _make_retry_decorator masks misconfigured dev env) — out of plan-03-09 scope; tagged for plan 03-10 hardening"
    - "REVIEW IN-01..IN-04 — cosmetic / docstring sweep; defer"
gaps: []
deferred:
  - item: "1-hour clean live run (ROADMAP SC#4 empirical)"
    why: "Anti-bot transient timing makes a 60-min uninterrupted run hard to schedule in a debugging session; Phase 1 spike already validated 99/100 success at same Camoufox baseline; production weekly cadence (1 run/week, 3-5s rate-limit) is the real test bed. Original 2026-05-06 deferral re-confirmed by 2026-05-11 UAT attempt."
    when: "First production weekly run (Phase 7 ops-playbook initial deploy)"
human_verification:
  - test: "Operator re-runs scripts/uat3_live_run.py on KZ-laptop with cold Camoufox spawn"
    expected: "4 cold-spawn runs reach run_loop (smoke probe no longer trips on URL[0] Loading state). Pass criterion per gap_closure_brief acceptance signal. If pass — operator flips Phase 3 row from `9/9 | Complete (re-opened ...; awaiting operator re-verification)` to plain `9/9 | Complete` in ROADMAP.md and checks `[x] 03-09-PLAN.md` in plan-list."
    why_human: "Cannot run live Camoufox + KZ-laptop + real goldapple traffic from automation. The structural code-level fix (Layer 1 warm-up nav + Layer 2 retry-once safety net) is verified by 24-test combined fetcher+smoke suite; the live measurement is operator-owned per 2026-05-06 deferral."
---

# Phase 3: Goldapple Crawl Verification Report (Re-verification, plan 03-09 gap-closure)

**Phase Goal:** Goldapple snapshots, restricted to brands present in the current run's viled snapshot, are written to the same `snapshots` table at the same quality bar as viled, using the anti-bot tier decided in Phase 1.
**Verified:** 2026-05-11T09:00:00Z
**Status:** human_needed (single human-verification item: operator live re-run on KZ-laptop)
**Re-verification:** Yes — after Wave 8 gap-closure plan 03-09 (commits 9e4f3b4, e7801ae, b15f48d, 0bdd12a, bc76fed) + CR-01 follow-up fix (commit 05b29a8)

## Re-verification Summary

Phase 3 was closed `passed` 2026-05-06 (5/5 truths verified) and re-opened 2026-05-11 by `/gsd-verify-work 3` after `scripts/uat3_live_run.py` reproduced UAT Test 6 (Operational Finding #1) in 4 of 4 cold runs — smoke_probe failed-fast on URL[0] in `Loading` state, never reaching `run_loop`. Plan 03-09 (Wave 8 gap-closure) ships a two-layer fix:

- **Layer 1 (primary):** WARMUP_URL navigation in `GoldappleFetcher.__aenter__` (best-effort, networkidle + 2 s settle). Absorbs Camoufox bootstrap race onto bare homepage.
- **Layer 2 (safety net):** Retry-once in `smoke_probe` on exact Loading-race shape (status==200 + `loading ` in title + no microdata + not gate-shell + not pre-blocked).

Plan also includes CR-01 follow-up (commit 05b29a8): `_is_loading_race` now reuses canonical `GATE_TITLE_MARKER` from `parsers.goldapple_microdata` + adds `block_reason="gate_shell_not_cleared"` defence-in-depth check.

| Truth | Previous (2026-05-06) | Current (2026-05-11) | Change |
|-------|------------------------|------------------------|--------|
| 1 — viled-derived URL pool + alias respect | VERIFIED (Wave 7 closure) | VERIFIED | Unchanged — Wave 7 brand-bucket fix preserved |
| 2 — quality-bar reuse from Phase 2 modules | VERIFIED | VERIFIED | Unchanged — fetcher/parser bytecode-identical except for warm-up in `__aenter__` |
| 3 — final M-gate guards both retailers | VERIFIED | VERIFIED | Unchanged |
| 4 — 1-hour live run | UNCERTAIN (operator-driven) | UNCERTAIN (operator-driven) | Same; structural BLOCKER from UAT Test 6 now removed via warm-up + retry-once; live re-run still operator-owned |
| 5 — NORM-06 review queue populated | VERIFIED | VERIFIED | Unchanged |

Score: **5/5 verified at code level**. Truth 4 carries `human_needed` badge for the operator live re-run.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Goldapple crawler derives URL pool from current run's viled snapshot AND respects alias table; Cyrillic-only goldapple brand pages reached | VERIFIED | Unchanged from 2026-05-06 (Wave 7 closure). `index_by_brand_token` + `intersect_brand_pool` + `compute_norm06_forward` with longest-prefix-in-whitelist mechanism. 7 unit tests in `test_brand_token_index.py` + 9 in `test_intersect_brand_pool.py` + 1 E2E in `test_run_e2e_with_phase2_mocks.py`. |
| 2 | Goldapple snapshots written to `snapshots` at same quality bar (per-SKU isolation, retry/backoff, rate-limit, parse-quality) reusing Phase 2 modules | VERIFIED | Unchanged except for warm-up step prepended to `__aenter__`. Rate-limit `random.uniform(3.0, 5.0)` (CRAWL-06), tenacity retry `stop_after_attempt(3), wait_exponential_jitter(2, 30)` (CRAWL-04), `fetch_one_isolated` (CRAWL-03), `parse_pdp` PARSE-01/03/04/06 — all bytecode-identical. |
| 3 | Post-crawl sanity gate marks run failed when `goldapple_count < M` (single gate now protects both retailers) | VERIFIED | Unchanged. `final_m_gate(count, M=1000)` forwards to `final_threshold_gate`. `test_e2e_final_gate_fail_run_to_completion` continues green. |
| 4 | 1-hour live run completes without sustained 429/503 spikes or Cloudflare interstitial; per-page cookie reuse verified | UNCERTAIN (operator-driven) | Wave 6 live-smoke (run-42) verified Camoufox boot + smoke pass after 60 s cooldown. Phase 1 spike established 99/100 success at this tier. The 2026-05-11 UAT BLOCKER (cold-start race) is now structurally fixed at TWO layers (warm-up nav + retry-once). Live re-run remains operator-driven per 2026-05-06 deferral — see `human_verification`. |
| 5 | NORM-06 review queue (defined in Phase 2) populated by a real goldapple run | VERIFIED | Unchanged. Reverse direction (`persist_sitemap_slugs` + `find_previous_slug_file` + `diff_new_slugs`) and forward direction (`compute_norm06_forward`) both intact. Run-43 evidence: 52,010-slug sitemap, `unmatched_goldapple_slugs_new=6606`, `unmatched_viled_brands=1`. |

**Score:** 5/5 truths VERIFIED at code level. Truth 4 carries `human_needed` badge.

### Gap Closure Audit (plan 03-09 — Operational Finding #1)

Plan deliverable inventory:

| Plan deliverable | Found | Evidence |
|---|---|---|
| `WARMUP_URL: str = "https://goldapple.kz/"` module constant | YES | `src/ga_crawler/fetchers/goldapple.py:54` + `__all__:385` |
| `WARMUP_SETTLE_SECONDS: float = 2.0` module constant | YES | `goldapple.py:55` + `__all__:386` |
| `WARMUP_NETWORKIDLE_TIMEOUT_MS: int = 15_000` module constant | YES | `goldapple.py:56` + `__all__:387` |
| Warm-up nav in `__aenter__` BEFORE `camoufox_booted` log event | YES | `goldapple.py:222-227` — `self._page.goto(WARMUP_URL, wait_until="networkidle", timeout=WARMUP_NETWORKIDLE_TIMEOUT_MS)` |
| Inner try/except → `camoufox_warmup_networkidle_timeout` warning | YES | `goldapple.py:228-233` |
| Unconditional `asyncio.sleep(WARMUP_SETTLE_SECONDS)` after goto | YES | `goldapple.py:235` (OUTSIDE inner try, settle ALWAYS runs) |
| Outer try/except → Pitfall 7 cleanup on Camoufox-boot failure | YES | `goldapple.py:237-240` — `shutil.rmtree(self.profile_dir, ignore_errors=True)` |
| `camoufox_booted` event extended with `warmup_url` + `warmup_elapsed_ms` | YES | `goldapple.py:247-248` |
| `import asyncio` in `gates.py` | YES | `gates.py:18` |
| `_compute_price_extracted` private helper | YES | `gates.py:84-97` |
| `_is_loading_race` private helper | YES | `gates.py:100-139` |
| Retry-once branch in `smoke_probe` (sleep 1s + re-fetch) | YES | `gates.py:178-188` |
| `phase3_smoke_probe_retry` structlog event with first-attempt diagnostics | YES | `gates.py:179-185` |
| smoke_probe has exactly ONE for-loop (D-312 invariant) | YES | AST-verified — exactly 1 `ast.For` node in `inspect.getsource(smoke_probe)` |
| 3 new fetcher tests | YES | `test_goldapple_fetch_loop_mocked.py:255` (warmup_called_once), `:270` (camoufox_boot_failure_cleans_profile_dir), `:315` (warmup_goto_failure_does_not_abort_boot) |
| 4 new smoke_probe tests | YES | `test_smoke_probe.py:141` (retries_once), `:208` (no_retry_on_happy_path), `:236` (no_retry_on_gate_shell), `:283` (no_retry_on_non_200) |
| Net +7 tests; suite 385 → 392 passed | YES | `uv run pytest tests/ -q -m "not live"` → `392 passed, 1 skipped, 0 failed in 101.11s` |
| STATE.md D-314 row appended | YES | `STATE.md:149` |
| ROADMAP.md Phase 3 row updated to `9/9 \| Complete (re-opened ...)` | YES | `ROADMAP.md:174` |
| ROADMAP.md plan-list grows by 03-09 entry (unchecked) | YES | `ROADMAP.md:92` |
| Wave summary expanded to "9 plans across 9 waves" with Wave 8 description | YES | `ROADMAP.md:83` |
| CR-01 follow-up: `GATE_TITLE_MARKER` reuse in `_is_loading_race` | YES | `gates.py:25` import + `:137` `if GATE_TITLE_MARKER in title_l: return False` |
| CR-01 follow-up: `block_reason="gate_shell_not_cleared"` defence-in-depth | YES | `gates.py:131-132` |
| Out-of-scope: SMOKE_URLS[0] unchanged from post-fefed43 (`19000488678-givenchy-irresistible`) | YES | `gates.py:37` |
| Out-of-scope: `fetch_one` body has NO `wait_for_selector` (approach #2 rejected) | YES | AST-verified — 0 `wait_for_selector` calls in `fetch_one` |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ga_crawler/fetchers/goldapple.py` | WARMUP_URL/SETTLE_SECONDS/NETWORKIDLE_TIMEOUT_MS constants + warm-up nav in __aenter__ + __all__ extended | VERIFIED | Lines 48-56 (constants block), 192-250 (__aenter__ revised), 385-387 (__all__). Inner try/except logs `camoufox_warmup_networkidle_timeout`. Unconditional settle sleep runs even on failure. Pitfall 7 cleanup preserved on Camoufox-boot failure only. |
| `src/ga_crawler/runner/gates.py` | import asyncio + _compute_price_extracted + _is_loading_race + retry-once in smoke_probe | VERIFIED | Line 18 (`import asyncio`), 84-97 (`_compute_price_extracted`), 100-139 (`_is_loading_race` with GATE_TITLE_MARKER reuse + block_reason guard per CR-01), 178-188 (retry branch with `await asyncio.sleep(1.0)` + `phase3_smoke_probe_retry` event). |
| `tests/integration/test_goldapple_fetch_loop_mocked.py` | +3 fetcher lifecycle tests | VERIFIED | 13 total (10 baseline + 3 new). Lines 255 (warmup_called_once), 270 (boot_failure_cleans_profile_dir), 315 (warmup_goto_failure_does_not_abort_boot). |
| `tests/unit/test_smoke_probe.py` | +4 smoke_probe retry-once tests | VERIFIED | 11 total (7 baseline + 4 new). Lines 141 (retries_once_on_loading_race), 208 (no_retry_on_happy_path), 236 (no_retry_on_gate_shell), 283 (no_retry_on_non_200). |
| `.planning/STATE.md` | D-314 row added | VERIFIED | Line 149 — captures cold-start race fix decision, approach #2 rejection rationale, retry-once guard requirements. |
| `.planning/ROADMAP.md` | Phase 3 row re-opened narrative + 03-09 plan entry + wave summary update | VERIFIED | Line 83 (wave summary), 92 (plan-list 03-09 entry), 174 (Progress table row `9/9 \| Complete (re-opened ...)`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `GoldappleFetcher.__aenter__` | `WARMUP_URL` | `self._page.goto(WARMUP_URL, wait_until='networkidle', timeout=WARMUP_NETWORKIDLE_TIMEOUT_MS)` | WIRED | AST-verified — first positional arg of single `self._page.goto(...)` call inside `__aenter__` is `ast.Name(id='WARMUP_URL')` |
| `GoldappleFetcher.__aenter__` | `asyncio.sleep(WARMUP_SETTLE_SECONDS)` | line 235 OUTSIDE inner try/except (always runs) | WIRED | `test_warmup_goto_failure_does_not_abort_boot` asserts sleep was called with `WARMUP_SETTLE_SECONDS` even when goto raised |
| `_is_loading_race` | `GATE_TITLE_MARKER` | imported from `ga_crawler.parsers.goldapple_microdata` at gates.py:25; used at line 137 | WIRED | CR-01 closed: `assert 'GATE_TITLE_MARKER' in inspect.getsource(_is_loading_race)` |
| `_is_loading_race` | `block_reason="gate_shell_not_cleared"` defence-in-depth | line 131-132 | WIRED | CR-01 follow-up: pre-emptive rejection even if fetcher's block flag is somehow False |
| `smoke_probe` retry branch | `fetcher.fetch_one` (second attempt) | line 187 (`rec = await fetcher.fetch_one(fetcher._page, url)`) | WIRED | `test_smoke_probe_retries_once_on_loading_race` asserts call_log length == 4 for the URL[0]-retries scenario |
| `smoke_probe` retry branch | `phase3_smoke_probe_retry` structlog event | line 179-185 | WIRED | Event emits before sleep with first-attempt title/size/status diagnostics |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `smoke_probe` `results[i]` | `price_extracted: bool` after retry | `_compute_price_extracted(rec, url)` → `parse_pdp(html, url)` from second attempt | YES (in production, given warm-up nav absorbs race) | When Loading race triggers, second attempt's record replaces the failing one; if real PDP returned, `price_extracted=True` and gate passes |
| `__aenter__` `camoufox_booted` event | `warmup_url`, `warmup_elapsed_ms` | computed inside `__aenter__` via `time.perf_counter()` delta | YES | Empirically verifiable in structlog output during operator re-run |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Combined fetcher + smoke_probe test suites | `uv run pytest tests/integration/test_goldapple_fetch_loop_mocked.py tests/unit/test_smoke_probe.py -q` | `24 passed in 29.18s` (10 fetcher baseline + 3 new + 7 smoke baseline + 4 new) | PASS |
| Full non-live pytest suite | `uv run pytest tests/ -q -m "not live"` | `392 passed, 1 skipped, 0 failed in 101.11s` | PASS (385 baseline + 7 new = 392 exactly) |
| WARMUP_* constants exported in __all__ | `python -c "from ga_crawler.fetchers.goldapple import WARMUP_URL, WARMUP_SETTLE_SECONDS, WARMUP_NETWORKIDLE_TIMEOUT_MS; ..."` | `OK` (values + __all__ membership confirmed) | PASS |
| Warm-up goto AST wired in __aenter__ | `ast.walk` over `__aenter__` body checking first positional arg of `self._page.goto(...)` is `Name(id='WARMUP_URL')` | `warm-up goto AST verified` | PASS |
| D-312 outer invariant (exactly 1 for-loop in smoke_probe) | `ast.walk` over `inspect.getsource(smoke_probe)` | `D-312 invariant preserved: exactly 1 for-loop in smoke_probe` | PASS |
| CR-01 follow-up: GATE_TITLE_MARKER reuse + block_reason guard | `inspect.getsource(_is_loading_race)` checks for both | `CR-01 follow-up verified: GATE_TITLE_MARKER reused + block_reason guard present` | PASS |
| Out-of-scope: SMOKE_URLS[0] post-fefed43 + fetch_one has no wait_for_selector | AST check + import check | `out-of-scope items unchanged` | PASS |
| CLI module entry registers subcommands | `uv run python -m ga_crawler --help` | Output contains `goldapple-smoke` and `weekly-run` (post-D-212 cutover) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CRAWL-02 | 03-02, 03-03, 03-04, 03-05, 03-06, 03-07, 03-08, **03-09** | Краулер goldapple.kz получает список SKU, ограниченный брендами viled-снимка текущего run_id | SATISFIED (Wave 7 structural close) + UNBLOCKED FOR PRODUCTION (Wave 8 cold-start fix) | Structural closure unchanged from 2026-05-06 — brand-bucket index works. Wave 8 plan 03-09 removes the boot-time obstacle that prevented operator from reaching `run_loop` on cold-spawn. REQUIREMENTS.md line 141 reflects Wave 7 closure (line text unchanged — adding Wave 8 narrative would require operator approval; the requirement description was met by Wave 7, Wave 8 is an operational unblock). |

REQUIREMENTS.md maps only `CRAWL-02` to Phase 3 (line 141). Phase 2-shared modules (CRAWL-03/04/05/06, PARSE-*, NORM-*, DATA-*) continue to be Phase 2-owned per traceability table. No orphans.

### Anti-Patterns Found

Re-scan of files modified in plan 03-09:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/ga_crawler/fetchers/goldapple.py` | 222-235 | `WARMUP_SETTLE_SECONDS=2.0` unconditional sleep adds +2 s on every healthy boot (~70-200% overhead relative to fast networkidle settle) | ⚠️ INFO (REVIEW WR-04) | Accept as conservative budget on weekly cadence; can be tightened in plan 03-10 |
| `src/ga_crawler/runner/gates.py` | 186 | `await asyncio.sleep(1.0)` not injectable — retry-positive test pays full 1 s wall-clock | ⚠️ INFO (REVIEW WR-01) | Slows test suite by 1 s; not a correctness bug |
| `src/ga_crawler/runner/gates.py` | 84-97 | `_compute_price_extracted` calls `parse_pdp` unconditionally; no try/except wrapper | ⚠️ INFO (REVIEW WR-02) | Schema-drift exception inside `parse_pdp` could abort entire probe; mitigated by tests covering happy + gate-shell + non-200 + stale paths |
| `src/ga_crawler/runner/gates.py` | 178-188 | `phase3_smoke_probe_retry` logs first-attempt diagnostics but no `_retry_complete` event | ⚠️ INFO (REVIEW WR-03) | Observability gap; not a correctness bug |
| `src/ga_crawler/fetchers/goldapple.py` | 83-89 | `_make_retry_decorator` `PWTimeout` fallback masks misconfigured dev env (outside plan-03-09 scope) | ⚠️ INFO (REVIEW WR-05) | Defer to plan 03-10 hardening |

No blocker anti-patterns. All 5 warnings from 03-REVIEW.md are explicitly tracked in the VERIFICATION frontmatter `open_findings_not_in_scope` list. The single Critical (CR-01) was RESOLVED by commit `05b29a8` — verified by `inspect.getsource(_is_loading_race)` checking for `GATE_TITLE_MARKER` + `gate_shell_not_cleared` substrings.

### Human Verification Required

#### 1. Operator live re-run on KZ-laptop with cold Camoufox spawn

**Test:** From the KZ-laptop, run:
```
uv run python scripts/uat3_live_run.py
```
(or equivalent: `uv run python -m ga_crawler goldapple-smoke --run-id <next>` repeated 4× with cold spawns between each)

**Expected:**
- All 4 cold-spawn runs reach `run_loop` (smoke_probe no longer trips on URL[0] `Loading` state)
- `camoufox_booted` structlog event now includes `warmup_url='https://goldapple.kz/'` and `warmup_elapsed_ms` fields
- If warm-up itself stalls on networkidle: `camoufox_warmup_networkidle_timeout` event emits (warning level) and boot continues normally
- If cold-start race still happens on URL[0]: `phase3_smoke_probe_retry` event emits, sleep 1 s, retry succeeds, smoke probe passes
- No regression on URL[1] / URL[2] happy path
- Boot time +5–10 s acceptable; production weekly cadence absorbs the overhead

**Why human:** Cannot run live Camoufox + KZ-laptop + real goldapple traffic from automation. The structural code-level fix (Layer 1 warm-up nav + Layer 2 retry-once safety net) is verified by 24-test combined fetcher+smoke suite and AST gates. The live measurement is operator-owned per 2026-05-06 deferral.

**Acceptance:** If pass — operator (a) flips `- [ ]` → `- [x] 03-09-PLAN.md` in ROADMAP.md line 92, (b) replaces Phase 3 Progress row at line 174 with plain `| 3. Goldapple Crawl | 9/9 | Complete | 2026-05-11 |`. If fail — operator captures empirical evidence in `.planning/runs/{N}/runs.json`, updates 03-UAT.md Test 6 with new diagnostic, and either escalates to plan 03-10 hardening or accepts as Phase 7 ops-playbook concern.

### Gaps Summary

**No blocking gaps.** Single `human_needed` item: operator live re-run of `scripts/uat3_live_run.py` on KZ-laptop with cold Camoufox spawn (Truth 4 SC#4 empirical confirmation).

The 2026-05-11 UAT BLOCKER (Operational Finding #1 — cold-start `Loading` race on URL[0] reproduced 4-of-4 cold runs) is structurally closed by plan 03-09 at TWO independent layers:

1. **Primary (Layer 1 — `__aenter__` warm-up nav):**
   - `WARMUP_URL = 'https://goldapple.kz/'` constant exported + warm-up navigation step inserted between page capture and `camoufox_booted` log event
   - Best-effort: inner try/except logs networkidle stall as `camoufox_warmup_networkidle_timeout` (warning); unconditional 2 s settle still runs; outer except preserves Pitfall 7 / D-311 cleanup invariant on Camoufox-boot failures only
   - Provable by `test_warmup_navigation_called_once_in_aenter`, `test_camoufox_boot_failure_cleans_profile_dir`, `test_warmup_goto_failure_does_not_abort_boot`

2. **Safety net (Layer 2 — `smoke_probe` retry-once):**
   - `_is_loading_race(rec, price_extracted)` private helper captures exact race shape: `status==200 AND price_extracted is False AND 'loading ' in title.lower() AND GATE_TITLE_MARKER not in title.lower() AND not rec.block AND block_reason != 'gate_shell_not_cleared'`
   - Retry sleeps 1 s, re-fetches the URL once, replaces failing record in place; emits `phase3_smoke_probe_retry` event with first-attempt diagnostics
   - Narrow on purpose: does NOT fire on happy-path (zero extra fetches), gate-shell (Operational Finding #2 must fail-fast), or non-200 statuses
   - Provable by `test_smoke_probe_retries_once_on_loading_race`, `test_smoke_probe_no_retry_on_happy_path`, `test_smoke_probe_no_retry_on_gate_shell`, `test_smoke_probe_no_retry_on_non_200`
   - CR-01 from 03-REVIEW.md (literal `"checking device"` instead of canonical `GATE_TITLE_MARKER`) was resolved by commit `05b29a8`: `_is_loading_race` now imports and reuses `GATE_TITLE_MARKER` from `parsers.goldapple_microdata` + adds `block_reason="gate_shell_not_cleared"` defence-in-depth check

D-312 strict-gate outer invariant **preserved structurally**: `inspect.getsource(smoke_probe)` + `ast.parse` confirms exactly ONE for-loop over `smoke_urls`; retry-once provides AT MOST ONE recovery attempt per URL with no nested while/for retry construct.

The full non-live test suite grew from 385 → 392 passed (no regressions, +7 net new tests exactly as planned). All 24 fetcher + smoke_probe tests pass.

**Recommendation:** Phase 4 (matcher) planning can continue. Wave 7 closure (CRAWL-02 structural) and Wave 8 closure (cold-start race operational unblock) together make Phase 3 production-ready at the code level. Operator live re-run is the final empirical confirmation step; if it passes, ROADMAP Phase 3 row flips back to plain `Complete | 2026-05-11`. If it fails, captured evidence routes to plan 03-10 hardening or accepted as Phase 7 ops-playbook concern (these are upstream anti-bot conditions, not Phase 3 code defects).

---

*Re-verified: 2026-05-11T09:00:00Z*
*Verifier: Claude (gsd-verifier) — re-verification mode after plan 03-09 + CR-01 follow-up*
*Previous verdict: passed 5/5 (2026-05-06T11:30:00Z) — re-opened 2026-05-11 for UAT Test 6 BLOCKER*
*Current verdict: human_needed 5/5 (UAT Test 6 BLOCKER structurally closed at code level via Layer 1 warm-up + Layer 2 retry-once; CR-01 from 03-REVIEW.md resolved by commit 05b29a8; Truth 4 awaits operator live re-run on KZ-laptop)*
