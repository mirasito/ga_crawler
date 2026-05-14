---
phase: 09-live-html-harness
plan: "03"
subsystem: testing/cli/docs
tags:
  - testing
  - cli
  - docs
  - p2-bundle
  - python
  - readme
dependency_graph:
  requires:
    - "09-02a (Wave 1a): live drift harness"
    - "09-02b (Wave 1b): Pydantic write-boundary schemas"
  provides:
    - "tests/test_brand_coverage_canary.py: TH-04 brand-coverage quota canary (3 tests)"
    - "src/ga_crawler/cli.py: capture-fixtures subcommand + _scrub_html_for_fixture + _camoufox_version_runtime (TH-05)"
    - "tests/integration/test_capture_fixtures_cli.py: TH-05 CLI integration tests (5 tests)"
    - "README.md §8 'Live HTML harness': RU-primary operator runbook (TH-03 D-905)"
    - "Phase 9 COMPLETE: 6/6 TEST-HARNESS reqs Closed"
  affects:
    - "REQUIREMENTS.md: Phase 9 all 6 reqs Closed"
    - "STATE.md: Phase 9 COMPLETE, Phase 10 NEXT"
    - "ROADMAP.md: Phase 9 4/4 plans complete"
    - "tests/test_phase07_readme_structure.py: 10→11 sections (D-905 extension)"
tech_stack:
  added: []
  patterns:
    - "DB query via Session + select + .distinct() + .order_by(desc) for brand-coverage lookup"
    - "subprocess.run(..., capture_output=True) for CLI integration tests"
    - "argparse subparser pattern (matches _cmd_smoke/_cmd_deliver shape)"
    - "async def _cmd_* handler + asyncio.run() dispatch (mirrors goldapple-smoke)"
    - "re.compile patterns list for scrub-on-write (D-907 belt-and-suspenders)"
key_files:
  created:
    - tests/test_brand_coverage_canary.py
    - tests/integration/test_capture_fixtures_cli.py
  modified:
    - src/ga_crawler/cli.py
    - README.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - tests/test_phase07_readme_structure.py
decisions:
  - "D-902 GO: elapsed W0+W1 = 16m40s (0.28h) — well under 8h gate; Variant A executed (TH-04 + TH-05 shipped)"
  - "test_each_active_brand_has_a_fixture correctly fires on operator dev box with production prices.db; this is the canary working as designed — in CI (no DB) it skips vacuously"
  - "hc-ping scrub regex requires >=32 hex chars; test string adjusted to 32 chars (one extra char from plan spec was 31)"
  - "README structure canary updated 10→11 sections (D-905 Phase 9 extension to D-707)"
  - "ViledFetcher(run_id=-1) kwargs-only constructor — capture-fixtures CLI uses run_id=-1 sentinel"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-14"
  tasks: 4
  files_created: 2
  files_modified: 6
  test_count_delta: "+8 (3 TH-04 + 5 TH-05 integration tests)"
  phase9_reqs_closed: "6/6 (TEST-HARNESS-01..06 all closed)"
  d902_variant: "A (GO — elapsed 16m40s < 8h gate)"
  d902_elapsed_seconds: "1000"
---

# Phase 09 Plan 03: P2 GO — TH-04 Brand-Coverage Canary + TH-05 Capture-Fixtures CLI + README §8 Summary

**One-liner:** D-902 GO (elapsed 0.28h < 8h) — shipped TH-04 brand-coverage quota canary + TH-05 `capture-fixtures` CLI subcommand with D-907 scrub-on-write + README §8 «Live HTML harness» RU-primary operator runbook; Phase 9 closed 6/6 requirements.

## Wave Executed

Wave 2 (sequential, user confirmed GO per D-902 elapsed check). Variant A executed.

## D-902 P2 GO/NO-GO Measurement

| Anchor | Commit | Epoch |
|--------|--------|-------|
| 09-01 first RED | 468c7d2 | 1778733773 |
| 09-02a last GREEN | 7d2c850 | 1778734096 |
| 09-02b last GREEN | 32c6093 | 1778734773 |
| **GREEN_TS (max)** | 32c6093 | **1778734773** |
| **Elapsed** | — | **1000s = 16m40s = 0.28h** |

Decision: **GO** — 0.28h << 8h gate. Variant A (ship TH-04 + TH-05) executed.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| Task 1 | P2 GO/NO-GO decision gate (D-902) | — | (measurement-only, no commit) |
| Task 2 | TH-04 brand-coverage canary (Variant A) | 3919f69 | tests/test_brand_coverage_canary.py |
| Task 3 | TH-05 capture-fixtures CLI + integration tests (Variant A) | 3969420 | src/ga_crawler/cli.py, tests/integration/test_capture_fixtures_cli.py |
| Task 4 | README §8 «Live HTML harness» (both variants) | 2e4db15 | README.md |
| Task 5 | Variant B status flip cascade | SKIPPED | (Variant B not applicable) |

## What Was Built

### tests/test_brand_coverage_canary.py (TH-04, greenfield)

Three-test canary:

1. `test_each_active_brand_has_a_fixture`: reads distinct goldapple brands from last 4 weekly `run_id`s in `prices.db`; matches against `_live-*.html` fixture stem slugs. Skips vacuously if no DB (CI env). Fails with actionable message + capture-fixtures CLI command on operator box with unmatched brands.
2. `test_phase8_shape_buckets_covered`: asserts stereotype/armani/contre-jour Phase 8 shape bucket fixtures exist (always-green regression guard on SKILL.md L28-32).
3. `test_canary_handles_empty_db_gracefully`: verifies empty/missing DB → empty brand set → passes.

### src/ga_crawler/cli.py (TH-05, modified)

Three new artifacts added:
- `_cmd_capture_fixtures(args) -> int`: async handler reusing `GoldappleFetcher(run_id=-1)` for goldapple or `ViledFetcher(run_id=-1)` for viled; scrubs HTML via `_scrub_html_for_fixture`; writes fixture + sidecar JSON via `tests._fixture_metadata.write_sidecar`; --dry-run path.
- `_scrub_html_for_fixture(html: str) -> str`: D-907 scrub patterns (cf_clearance, bot tokens, hc-ping paths).
- `_camoufox_version_runtime() -> str`: importlib.metadata version lookup.
- `capture-fixtures` argparse subparser: `--retailer {goldapple,viled}`, `--url`, `--slug`, `--dry-run`, `--headless`.

### tests/integration/test_capture_fixtures_cli.py (TH-05 integration, greenfield)

5 tests:
1. `test_capture_fixtures_help_exits_zero`: subprocess `--help` exits 0; argparse args in stdout.
2. `test_capture_fixtures_invalid_retailer_exits_nonzero`: `--retailer unknown` → exit != 0.
3. `test_scrub_strips_cf_clearance`: `_scrub_html_for_fixture` removes `cf_clearance=...`.
4. `test_scrub_strips_bot_token`: Telegram bot token pattern scrubbed.
5. `test_scrub_strips_hc_ping_path`: hc-ping.com/UUID (32 hex chars) scrubbed.

### README.md §8 «Live HTML harness» (TH-03 D-905 docs, mandatory for both variants)

New `## Live HTML harness` section between `## Логи` and `## Dev setup`:
- «Когда запускать»: pre-deploy / post-drift / quarterly check
- «Cassette-replay»: `pytest -m live -x` (no network)
- «Refresh»: `pytest -m live --refresh-live -x` (Camoufox + curl_cffi)
- «Принять drift»: `pytest -m live --refresh-live --snapshot-update -x`
- «Capture новой fixture»: `capture-fixtures` CLI for goldapple + viled
- «Stale-fixture warning»: 30-day sidecar date UserWarning
- «Что НЕ делает harness»: no cron, no Telegram, no parser edits

## Phase 9 Closure Record

| Requirement | Plan Closed | Status |
|-------------|-------------|--------|
| TEST-HARNESS-01 | 09-01 | Complete 2026-05-14 |
| TEST-HARNESS-02 | 09-01 | Complete 2026-05-14 |
| TEST-HARNESS-03 | 09-02a | Complete 2026-05-14 |
| TEST-HARNESS-04 | 09-03 (P2 GO) | Complete 2026-05-14 |
| TEST-HARNESS-05 | 09-03 (P2 GO) | Complete 2026-05-14 |
| TEST-HARNESS-06 | 09-02b | Complete 2026-05-14 |

**6/6 Phase 9 requirements closed. Phase 9 COMPLETE.**

**Next phase:** Phase 10 (Audit Paperwork Carryover) — parallel-safe, no code dependencies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] hc-ping regex test string was 31 chars instead of 32**
- **Found during:** Task 3 integration test run
- **Issue:** Plan test spec used 31-char hex string (`abcdef0123456789abcdef012345678`) — one char short of the 32-char minimum in the regex `[0-9a-f\-]{32,36}`; test failed
- **Fix:** Corrected test string to 32 hex chars (`abcdef0123456789abcdef0123456789`)
- **Files modified:** tests/integration/test_capture_fixtures_cli.py
- **Commit:** 3969420

**2. [Rule 1 - Bug] README structure structural canary expected exactly 10 H2 sections**
- **Found during:** Full test suite run after Task 4
- **Issue:** `tests/test_phase07_readme_structure.py` asserted exactly 10 H2 sections (D-707 Phase 7 shape). Adding `## Live HTML harness` changed count to 11. Test failed with TypeError (count mismatch) and AssertionError (order mismatch)
- **Fix:** Updated `EXPECTED_HEADINGS` to include `## Live HTML harness` between `## Логи` and `## Dev setup`; changed count assert from 10 → 11; updated docstring to document D-905 extension
- **Files modified:** tests/test_phase07_readme_structure.py
- **Commit:** (included in final metadata commit)

**3. [Pre-existing] test_each_active_brand_has_a_fixture fires on operator box**
- **Found during:** Task 2 test run
- **Not a bug:** This is the canary working correctly. Operator dev machine has `prices.db` with brands (calvin klein, creed, givenchy, etc.) that don't have `_live-*.html` fixtures. The test correctly reports this and provides capture CLI command. In CI (no DB) the test skips vacuously.
- **Action:** Documented in SUMMARY; no code change needed

### Pre-existing Failures (Not Our Changes)

Two pre-existing Windows Unicode subprocess failures:
- `tests/integration/test_cli_deliver.py::test_deliver_run_help_lists_subcommand`
- `tests/integration/test_cli_report_subcommand.py::test_cli_help_lists_report_run`

Both fail with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97` when reading subprocess stdout on Windows — caused by Windows emoji/cp1252 encoding in the `—` em-dash in help text. Confirmed pre-existing via `git stash` verification. Not caused by Phase 9 changes.

## Known Stubs

None. All code paths are live with real behavior. The brand-coverage canary's vacuous-skip on empty DB is intentional design, not a stub.

## Threat Flags

None. The `_scrub_html_for_fixture` function mitigates T-09-PII (capture-fixtures writes live HTML that may carry anti-bot tokens). UUID v4 standalone pattern is intentionally NOT added per 09-01-SUMMARY deviation #2 (goldapple HTML legitimately contains UUID-format buildIds).

## Self-Check: PASSED

Files exist:
- tests/test_brand_coverage_canary.py: EXISTS (created)
- tests/integration/test_capture_fixtures_cli.py: EXISTS (created)
- src/ga_crawler/cli.py: EXISTS (modified — capture-fixtures subcommand)
- README.md: EXISTS (modified — §8 Live HTML harness)

Commits exist:
- 3919f69: feat(09-03): TH-04 brand-coverage canary (P2 GO Variant A)
- 3969420: feat(09-03): TH-05 capture-fixtures CLI subcommand + scrub-on-write (P2 GO Variant A)
- 2e4db15: docs(09-03): README §8 «Live HTML harness» RU-primary operator runbook (TH-03 D-905, P2 GO)

Phase 9 Requirements: 6/6 Closed in REQUIREMENTS.md
STATE.md: Phase 9 COMPLETE, Phase 10 NEXT
ROADMAP.md: Phase 9 4/4 plans Complete
