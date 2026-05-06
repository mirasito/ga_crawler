---
phase: 03-goldapple-crawl
plan: 07
subsystem: testing
tags: [live-smoke, anti-bot, camoufox, gold-card, norm-06, ops]

requires:
  - phase: 03-goldapple-crawl/01..06
    provides: complete Phase 3 fetch + parse + gates + orchestrator pipeline; smoke probe wired into D-312 gate
provides:
  - Live operational validation against goldapple.kz from KZ-laptop
  - Production-relevant parser hardening (gold-card heuristic + min-value selection)
  - Three operational findings captured in checklist + Phase 7 ops-playbook backlog
affects: [phase-04-matcher, phase-07-hosting]

tech-stack:
  added: []
  patterns:
    - "Gold-card detection: direct-sibling + label-tag-only + shallow-text (was: walk-up + recursive text)"
    - "Multi-bare-priceMeta selection: PARSE-04 sanity range applied early, then min-value within offer"

key-files:
  created:
    - .planning/phases/03-goldapple-crawl/live-smoke-checklist.md
    - .planning/phases/03-goldapple-crawl/03-07-SUMMARY.md
  modified:
    - src/ga_crawler/parsers/goldapple_microdata.py (gold-card heuristic + selection rule)
    - tests/unit/test_goldapple_microdata_parser.py (2 regression tests)

key-decisions:
  - "Gold-card heuristic narrowed to direct siblings + label tags + shallow text — bonus-button text no longer poisons price classification"
  - "Min-value selection deterministic when offer emits multiple bare priceMeta tags without StrikethroughPrice markup"
  - "Phase 3 production code shipped as live-verified-with-issues — orchestrator fail-fast on D-312 gate working as designed; 3 operational findings deferred to backlog (1 critical NORM-06 design fix, 2 ops cooldown items)"

patterns-established:
  - "Live-smoke checkpoints catch fixture-blind parser bugs and surface real anti-bot/operational behavior that mocked tests cannot"
  - "60-second cooldown between manual smoke probe runs is required to avoid transient gate-shell from rapid Camoufox cold-spawns"

requirements-completed: [CRAWL-02]

duration: ~50min
completed: 2026-05-06
---

# Phase 3 Plan 07: Live Smoke Verification Summary

**Live operational validation against goldapple.kz on KZ-laptop surfaced 1 real parser bug (FIXED in commit `277a40a`), 1 NORM-06 brand-intersect design bug (BACKLOG), and 1 anti-bot transient cooldown ops behavior (BACKLOG).**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-05-06T06:45:00Z
- **Completed:** 2026-05-06T07:00:00Z
- **Tasks:** 1/1 (checkpoint:human-verify)
- **Files modified:** 4 (parser + tests + checklist + summary)

## Accomplishments

- Smoke probe (D-312) live-verified PASS on 3 hardcoded Givenchy URLs after parser fix + 60-sec cooldown
- Parser hardened against bonus-badge button text leakage and multi-bare-price ambiguity (commit `277a40a`)
- Two regression tests added: `test_bonus_button_with_login_text_does_not_poison_price`, `test_zero_filler_price_is_skipped`
- 181/181 unit + integration tests green after fix (was 179/179)
- Sitemap fetcher confirmed working at production scale: **45,490 unique slugs** indexed in <2.5 seconds (vs spike estimate of ~1,461; multiple shards aggregated)
- Camoufox profile cleanup verified live (`__aexit__` cleared `camoufox-run-42-*` from `$env:TEMP`)
- structlog JSON `run_id` binding verified across every event in the live run-42 pipeline
- D-312 fail-fast behavior verified: orchestrator aborted run-42 with `reason=smoke_probe_failed` instead of wasting fetch loop on a broken gate

## Task Commits

1. **Live-smoke parser fix (Finding #1)** — `277a40a` (fix(03-07): harden gold-card heuristic + min-value selection — live-smoke regression)

(Wave 6 has a single checkpoint task — the live verification work itself; checklist + this SUMMARY ship in the plan-completion commit.)

## Files Created/Modified

### Created
- `.planning/phases/03-goldapple-crawl/live-smoke-checklist.md` — operator-completed verification log with 7 outcome rows, 3 root-caused findings, 5 Phase 7 backlog items
- `.planning/phases/03-goldapple-crawl/03-07-SUMMARY.md` — this file

### Modified
- `src/ga_crawler/parsers/goldapple_microdata.py` — gold-card heuristic narrowed to direct siblings + label tags + shallow text; `_extract_top_level_offer` now picks min-value among PARSE-04-valid candidates inside one offer
- `tests/unit/test_goldapple_microdata_parser.py` — +2 regression tests covering both surfaces of the live finding

## Decisions Made

- **Honest verdict over green-washed PASS** — verdict is `PHASE 3 LIVE-VERIFIED-WITH-ISSUES`, not unconditional `LIVE-VERIFIED`. The smoke probe pass was earned only on Run 3 after a 60-sec cooldown; Run 2 of the orchestrator hit transient gate-shell again before the cooldown window had reset. Pretending the gate is unconditionally clean would have hidden the cooldown requirement from Phase 7 ops-playbook.
- **NORM-06 intersect bug deferred, not silently shipped** — the brand-intersect produces zero matches by design (sitemap indexes by product-slug, intersect does exact-match on brand-slug). Code shipped is honest about this; remediation will be a `gap_closure: true` plan, separately reviewed and tested.
- **Parser fix landed in this checkpoint, not deferred to gap-closure** — the bug is a Wave 2 regression that any fixture-future-update can re-trigger; better to land the fix and the regression tests immediately than to leave a known-broken parser in main.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical] Live smoke probe surfaced parser bug not covered by spike fixtures**
- **Found during:** Step 1 (smoke probe Run 1)
- **Issue:** Microdata parser returned None on Givenchy Gentleman Reserve Privee EDP (URL[2]) despite valid 200 + 199 KB PDP response. Root cause: gold-card heuristic walking DOM with recursive `Node.text()` picked up "при авторизации" copy from a deep-nested bonus-badge button, falsely classifying every price in the offer as Gold Card; PARSE-04 sanity range then caught the price=0 filler and parser returned None instead of the valid 43,212 KZT current price.
- **Fix:** Narrow gold-card heuristic to direct siblings of `price_meta`, restrict to label tags (span/div/p/etc.), use shallow text only. Add deterministic min-value selection among non-priceType candidates within an offer (sale price < was price). Apply PARSE-04 sanity range early so price=0 filler metas cannot be picked.
- **Files modified:** `src/ga_crawler/parsers/goldapple_microdata.py`, `tests/unit/test_goldapple_microdata_parser.py`
- **Verification:** 181/181 unit + integration tests green (179 baseline + 2 new regression tests). Smoke probe Run 3 PASS with `price_extracted=true` on the previously failing URL[2].
- **Committed in:** `277a40a`

---

**Total deviations:** 1 auto-fixed (1 missing critical from a Wave 2 fixture blind spot)
**Impact on plan:** Necessary for parser correctness; would have caused silent zero-price drops on similarly-structured PDPs in production. No scope creep — fix is strictly within the surface area Wave 2 was supposed to cover.

## Issues Encountered

### Finding #2 — Anti-bot transient gate-shell on rapid Camoufox cold-spawns (OPS, not code)
- **Surfaced by:** Smoke probe Run 2 (3rd cold-spawn within ~10 min of Runs 1+2)
- **Behavior:** All 3 URLs returned size~18 KB with title `Gold Apple … checking device`, classified as gate-shell. After 60-second cooldown Run 3 returned full PDPs (449 / 419 / 202 KB).
- **Resolution:** Backlog — Phase 7 ops-playbook to enforce ≥60s cooldown between manual smoke probe runs.
- **Production impact:** None expected. Production cron is 1 run / week at 3-5s rate-limit per fetch; this rate is far below the rapid-cold-spawn pattern that triggered the transient gate.

### Finding #3 — NORM-06 brand-intersect produces zero matches (DESIGN BUG, BACKLOG)
- **Surfaced by:** `phase3_brand_intersect` `matched_url_count=0` for both `givenchy` and `jo_malone_london` despite both brands clearly present in 45,490-slug sitemap.
- **Root cause:** `intersect_brand_pool` does `sitemap_slugs.get(brand_slug)` — exact match. Sitemap parser indexes by product-slug (e.g. `givenchy-pour-homme-blue-label`), not brand-alias. Brand `givenchy` cannot exact-match a product-slug key; Pitfall 3 / D-305 forbade substring matching to prevent false positives, and an additional brand-prefix bucket layer was never added.
- **Resolution:** Backlog — `gap_closure: true` plan recommended. Two fix paths (operator picks at plan time): (a) sitemap parser additionally emits a `dict[brand_token, list[url]]` index where `brand_token` is the first hyphen-separated token after numeric prefix is stripped, or (b) `intersect_brand_pool` uses bounded `startswith(slug + "-")` over `sitemap_slugs.values()` with whitelist enforcement.
- **Production impact:** Phase 4 matcher will receive empty matched_urls until this is fixed. Phase 3 production code is correct in isolation — fetcher, parser, gates, stats namespace all working — but the orchestrator currently has nothing to crawl.

## User Setup Required

None additional beyond the standard Phase 3 setup (Camoufox cached, KZ-laptop direct, no proxy).

## Next Phase Readiness

**Ready (Phase 3 production code):**
- Goldapple fetcher pipeline live-verified end-to-end against real anti-bot
- Parser hardened against multi-bare-price + bonus-button edge cases
- Smoke probe + final M-gate fail-fast behavior verified
- structlog observability working: every event carries `run_id` binding
- Camoufox profile lifecycle (D-311) verified — no leaked tmp dirs

**Blocked (downstream phases):**
- Phase 4 matcher cannot demonstrate end-to-end crawl→match flow until NORM-06 brand-intersect bug (Finding #3) is closed. Recommended: write `/gsd-plan-phase 03 --gaps` plan that adds a brand-token bucket index + corresponding `intersect_brand_pool` lookup, plus regression test against the live 45,490-slug sitemap.

**Phase 7 ops-playbook items captured (5):**
1. Minimum 60s cooldown between manual smoke probe runs
2. Smoke-URL rotation procedure when SMOKE_URLS go stale (`7680100018-very-irresistible-givenchy` showed intermittent landing-page fallback)
3. Weekly cron alert if `goldapple.gate_shell_count / fetch_count > 5%`
4. Camoufox upstream tracking (`daijro/camoufox` vs maintained `coryking/camoufox` fork)
5. **NORM-06 fix plan** — brand-intersect bucketing repair (highest priority for Phase 4)

---
*Phase: 03-goldapple-crawl*
*Plan: 07*
*Completed: 2026-05-06*
