---
status: complete
phase: 09-live-html-harness
source:
  - 09-01-SUMMARY.md
  - 09-02a-SUMMARY.md
  - 09-02b-SUMMARY.md
  - 09-03-SUMMARY.md
started: 2026-05-14T06:46:57Z
updated: 2026-05-14T08:30:00Z
executed_by: orchestrator (user authorized "Сам все запусти")
---

## Current Test

number: 7
name: README §8 «Live HTML harness» operator runbook
expected: README has §8 + RU-primary content; structure canary passes
awaiting: complete (all tests executed)

## Tests

### 1. Cassette-replay drift tests (pytest -m live)
expected: |
  3 tests pass in ~2 seconds, no network required (replay of Phase 8 fixtures).
result: pass
actual: |
  3 passed, 907 deselected in 2.56s — stereotype, armani-code, contre-jour all PASSED.

### 2. capture-fixtures CLI dry-run
expected: |
  Exit 0; stdout shows `[dry-run] would write tests/fixtures/viled/_live-YYYY-MM-DD-uat-test.html (N bytes)`; no file written.
result: pass
actual: |
  exit=0; stdout="[dry-run] would write tests/fixtures/viled/_live-2026-05-14-uat-test.html (139671 bytes)"; no file created on disk.

### 3. PII canary catches dirty fixture
expected: |
  pytest tests/test_live_fixtures_pii_canary.py — fails loudly on PII pattern.
result: pass
actual: |
  9 passed in 0.14s — 5 dirty-fixture cases (cf_clearance, bot token, UUID hc-ping, hc-ping URL, Authorization Bearer) ALL fail _assert_fixture_clean correctly; 3 clean Phase 8 fixtures pass; oversize rejected. Independently dropped a dirty fixture into tests/fixtures/goldapple/ — canary tests are tmp_path-isolated, so dropped fixture confirmed via cleanup.

### 4. Brand-coverage canary shows actionable list
expected: |
  On dev box: fail with missing-brand list + capture-fixtures command hint + README §8 ref.
  On CI / no prices.db: vacuous skip.
result: pass
actual: |
  Fails with: "Active goldapple brands without _live-*.html fixture: ['calvin klein', 'creed', 'essential parfums paris', 'givenchy', 'karl lagerfeld', 'kilian paris', 'la sultane de saba', 'mac']. Capture via `python -m ga_crawler capture-fixtures --retailer goldapple --url <URL> --slug <slug>` (TH-05). See README §8 for runbook." — exactly the actionable message designed in Plan 09-03 §6.5.

### 5. Schema validation rejects invalid row
expected: |
  All schema + writer-gate + threshold-gate tests pass.
result: pass
actual: |
  27 passed in 0.30s across 3 test files — including critical D-904/D-903 invariants:
  - test_goldapple_strict_rejects_empty_volume (strict)
  - test_viled_relaxed_accepts_none_volume (relaxed, Contre-Jour case)
  - test_just_above_threshold_fails (6/100 > 0.05 → fail)
  - test_both_reject_zero_price + negative_price + empty_brand/name/sku_id/url

### 6. capture-fixtures CLI live write end-to-end
expected: |
  Real fetch to viled.kz, write HTML + sidecar JSON, scrub PII.
result: pass
actual: |
  exit=0; tests/fixtures/viled/_live-2026-05-14-uat-live-test.html = 196,845 bytes; sidecar JSON = 183 bytes with keys {camoufox_version, date, html_size, status, title, url}; PII scrub verified — 0 occurrences of cf_clearance OR csrf-token in HTML body. Cleaned up after test.

### 7. README §8 «Live HTML harness» operator runbook
expected: |
  README has §8 with RU-primary operator runbook; structure canary passes.
result: pass
actual: |
  README §8 «Live HTML harness» exists at line 238. Structure canary 3/3 passes:
  test_readme_has_exactly_10_h2_sections (NB: function name stale — actually asserts == 11 sections per D-905 Phase 9 extension), test_readme_h2_order_matches_d707, test_readme_is_ru_primary.

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none — all 7 tests passed]

## Findings (non-blocking)

1. **Stale test function name** — `tests/test_phase07_readme_structure.py::test_readme_has_exactly_10_h2_sections` was updated to assert `== 11` per D-905 (Phase 9 §8 README addition) but the function name still says `_10_`. Cosmetic; tracked here for future cleanup.

2. **Dev prices.db artifact** — Brand-coverage canary fires on the orchestrator's dev tree because `prices.db` (290KB, run_ids 8/10/12/13) accumulated 9 active goldapple brands from prior local crawls but only stereotype/armani fixtures are committed. Per Plan 09-03 §6.5 this is **canary working as designed** — operator response is to either capture the 8 missing fixtures via `capture-fixtures` CLI or accept the canary signal as ongoing operational reminder.

3. **dry-run vs live byte counts** — Test 2 dry-run preview reported 139,671 bytes but Test 6 live write produced 196,845 bytes for the same URL. Likely viled.kz served different content between fetches OR dry-run reports pre-scrub size while live reports post-scrub. Worth flagging for future investigation but no Phase 9 contract violated.
