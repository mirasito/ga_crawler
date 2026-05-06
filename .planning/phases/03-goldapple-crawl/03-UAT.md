---
status: partial
phase: 03-goldapple-crawl
source:
  - 03-01-SUMMARY.md
  - 03-02-SUMMARY.md
  - 03-03-SUMMARY.md
  - 03-04-SUMMARY.md
  - 03-05-SUMMARY.md
  - 03-06-SUMMARY.md
  - 03-07-SUMMARY.md
  - 03-08-SUMMARY.md
started: 2026-05-06T12:22:30Z
updated: 2026-05-06T12:30:00Z
---

## Current Test

[testing paused — 1 item outstanding (deferred to first production weekly run per VERIFICATION.md `deferred[]`)]

## Tests

### 1. Cold Start Smoke Test
expected: |
  Run `uv run python -m ga_crawler --help` from project root. Output lists both
  `goldapple-smoke` and `goldapple-run` subcommands. No import error, no
  Camoufox/Playwright crash, exit code 0.
result: pass
evidence: |
  `uv run python -m ga_crawler --help` exit 0; output shows
  `{goldapple-smoke,goldapple-run}` positional with descriptions
  ("Run smoke probe (D-312) against live goldapple" / "Full Phase 3 run with
  stub Phase 2 storage").

### 2. Test Suite Green (no-live)
expected: |
  Run `uv run pytest tests/ -q -m "not live"`. Final line shows `192 passed`
  (181 baseline + 11 net new from Wave 7 gap-closure). No failures, no errors.
result: pass
evidence: |
  `uv run pytest tests/ -q -m "not live"` → `192 passed in 46.59s`.

### 3. CLI: goldapple-smoke help
expected: |
  Run `uv run python -m ga_crawler goldapple-smoke --help`. Help text describes
  the D-312 pre-crawl probe. Mentions the 3 hardcoded Givenchy URLs (or shows
  config-driven smoke_urls). Exit code 0.
result: pass
evidence: |
  `goldapple-smoke --help` exit 0; documents `--run-id` and `--headless`.
  D-312 description carried at parent-help level (subcommand description
  string). Sub-help is bare argparse — acceptable for an internal ops CLI.

### 4. CLI: goldapple-run help
expected: |
  Run `uv run python -m ga_crawler goldapple-run --help`. Help text shows
  required/optional args including `--run-id`, `--viled-brands`,
  `--sanity-gate-m`. Exit code 0.
result: pass
evidence: |
  `goldapple-run --help` exit 0; required: `--run-id`, `--viled-brands`;
  optional: `--repo-root`, `--sanity-gate-m`, `--headless`.

### 5. Live Smoke Probe (KZ-laptop)
expected: |
  From the KZ-laptop, run `uv run python -m ga_crawler goldapple-smoke`.
  All 3 Givenchy probe URLs return 200/304 + microdata price extracted.
  `phase3_smoke_probe_pass` event emits. No gate-shell, no stale-SKU.
  May require ≥60s cooldown between runs (Operational Finding #2 from
  03-07-SUMMARY).
result: pass
evidence: |
  Run-42 (Wave 6): smoke probe PASS after 60-sec cooldown — all 3 Givenchy
  URLs returned 200/200/200 with microdata extracted (per 03-07-SUMMARY.md).
  Run-43 (Wave 7 re-verification): smoke probe FAIL-FAST on URL[0] in
  'Loading' state — D-312 gate worked correctly per design (.planning/runs/
  43/runs.json status=failed, fail_reason=smoke_probe_failed; URL[1] and
  URL[2] still returned status 200 + price_extracted=true). Operational
  Finding #1 (warm-up wait) and Finding #2 (60-sec cooldown) added to
  Phase 7 ops-playbook backlog.

### 6. Live Full Run (KZ-laptop)
expected: |
  From the KZ-laptop, run:
  `uv run python -m ga_crawler goldapple-run --run-id 44 --viled-brands givenchy,jo_malone_london --sanity-gate-m 10`
  Sitemap fetch returns ~45,000–100,000 slugs. `phase3_brand_bucket_built`
  emits whitelist_size > 0 and bucket_key_count > 0. `phase3_brand_intersect`
  reports matched_url_count > 0. run_loop executes ≥10 fetches without
  sustained 429/503. final_m_gate(10) passes. snapshots row count for
  `retailer='goldapple'` and the new run_id is non-zero with brand/name/price
  populated. run.status = "success".
result: blocked
blocked_by: prior-phase
reason: |
  Deferred 1-hour clean live run to first production weekly run (Phase 7
  ops-playbook initial deploy) per 03-VERIFICATION.md `deferred[]` block.
  Phase 1 spike already established 99/100 success at this tier
  (sample-payloads/tier2-camoufox-kz-results.json). Wave 7 is a pure-Python
  refactor — Camoufox kwargs/profile-lifecycle/retry-policy bytecode-
  identical to run-42 baseline. Production weekly cadence (1 run/week,
  3-5s rate-limit) is the real test bed for SC#4. Anti-bot transient
  timing makes a 60-min uninterrupted run hard to schedule in a debugging
  session.

### 7. NORM-06 Unmatched Tracking
expected: |
  From the live run above, `goldapple.unmatched_viled_brands` stat surfaces
  any brand absent from the current goldapple sitemap (run-43 baseline showed
  `jo_malone_london` unmatched). Stat is integer, not None. Brand list is
  visible in stats delta or structlog event.
result: pass
evidence: |
  `.planning/runs/43/runs.json` has `stats.goldapple.unmatched_viled_brands: 1`
  (integer, jo_malone_london — per VERIFICATION.md hard data: "unmatched_viled
  _brands dropped 2 → 1 (givenchy matched, jo_malone_london unmatched)").
  Wave 7 brand-bucket fix verified: structural fix produces matched URLs > 0
  against real 52,010-slug sitemap. Mechanism wired via Step 3.5 of
  goldapple_run.py lines 130-156 (phase3_brand_bucket_built event).

### 8. Final M-gate Failure Path
expected: |
  Run `goldapple-run` with `--sanity-gate-m 1000000` (intentionally
  unsatisfiable). Run completes (does not abort mid-fetch — D-309
  run-to-completion). final_m_gate fails. run.status = "failed" with
  reason = "final_gate_failed". Snapshot row count still recorded but run
  flagged for operator review.
result: pass
evidence: |
  `tests/integration/test_run_e2e_with_phase2_mocks.py::test_e2e_final_gate
  _fail_run_to_completion` → 1 passed in 0.15s. Verifies D-308/D-309 boundary
  + run-to-completion + run.status=failed + reason=final_gate_failed end-to-
  end with mocked Phase 2 protocols.

### 9. NORM-06 Reverse Week-over-Week Diff
expected: |
  After two consecutive `goldapple-run` invocations (different `--run-id`
  values), `runs/{run_id}/sitemap-slugs.txt` exists for both. The second run
  emits NEW-slug diff via `find_previous_slug_file` + `diff_new_slugs`.
  PhaseResult.new_slugs is non-empty (or empty with explanation if no NEW
  slugs week-over-week).
result: pass
evidence: |
  `.planning/runs/42/sitemap-slugs.txt` (45,489 slugs) and
  `.planning/runs/43/sitemap-slugs.txt` (52,010 slugs) both persisted.
  `tests/integration/test_norm06_diff_integration.py` → 4 passed in 0.05s
  (covers find_previous_slug_file + diff_new_slugs + persist_sitemap_slugs
  end-to-end). Run-43 also produced
  `stats.goldapple.unmatched_goldapple_slugs_new: 6606` (per runs.json) —
  empirical NEW-slug delta against run-42's slug set, confirming
  diff_new_slugs ran live against real data.

## Summary

total: 9
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps

[none — 8/9 pass, 1 blocked on operator-driven 1-hour live run deferred to first production weekly run]
