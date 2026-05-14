---
phase: 09-live-html-harness
plan: 01
subsystem: test-harness
tags:
  - testing
  - snapshot
  - pii-canary
  - syrupy
  - python
  - tdd
dependency_graph:
  requires:
    - 08-parser-bug-fixes/08-01 (live fixtures: stereotype, armani, contre-jour)
  provides:
    - syrupy 4.9.1 dev dep
    - HTMLSnapshotExtension class
    - FixtureMetadata + write_sidecar/read_sidecar
    - normalize_for_snapshot helper
    - _assert_fixture_clean PII canary (conftest)
    - refresh_live + html_snapshot fixtures (conftest)
  affects:
    - tests/conftest.py (3 live-fixture loaders wrapped, 2 new fixtures added)
tech_stack:
  added:
    - syrupy==4.9.1 (dev dep, HTML snapshot diffing, SingleFileSnapshotExtension)
  patterns:
    - RED+GREEN TDD commit pairs (D-811 Phase 8 inheritance)
    - append-only conftest.py extension (D-222 pattern)
    - pytest_addoption custom flag pattern (pytest 8 docs verbatim)
    - pytest.fail.Exception (not Exception) for canary failures
key_files:
  created:
    - tests/_snapshot_extension.py
    - tests/_fixture_metadata.py
    - tests/_html_normalize.py
    - tests/test_snapshot_extension.py
    - tests/test_live_fixtures_pii_canary.py
    - tests/test_fixture_metadata.py
    - tests/test_html_normalize.py
    - tests/test_pytest_addoption.py
  modified:
    - tests/conftest.py (PII helpers + 3 loader wrappers + 3 new fixtures)
    - pyproject.toml (syrupy>=4.7,<5.0 in dev group)
    - uv.lock (syrupy 4.9.1 + transitive deps)
decisions:
  - "pytest.fail.Exception is not a subclass of Exception — canary tests use pytest.raises(pytest.fail.Exception) alias"
  - "UUID v4 standalone pattern removed from _PII_PATTERNS — goldapple buildId is UUID-format (false-positive on Phase 8 fixtures)"
  - "_html_normalize.py _BUILD_HASH_RE uses plan spec (title__heading|title__brand|title__name|brand|name) for full goldapple CSS class coverage"
metrics:
  duration: "14m"
  completed: "2026-05-14"
  tasks: 4
  files_created: 8
  files_modified: 3
  test_count_delta: "+21 (870 total vs 849 baseline)"
  syrupy_version_resolved: "4.9.1"
---

# Phase 09 Plan 01: Wave 0 Substrate — syrupy + HTMLSnapshotExtension + PII Canary + Normalize Summary

**One-liner:** syrupy 4.9.1 installed + HTMLSnapshotExtension (WriteMode.TEXT) + FixtureMetadata sidecar JSON + normalize_for_snapshot (csrf-token/cf_clearance/CSS-hash/buildId) + _assert_fixture_clean PII canary (D-907 dual enforcement) + --refresh-live pytest_addoption fixture wiring.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Install syrupy 4.9.x dev dep | 7a99405 | pyproject.toml, uv.lock |
| 2 (RED) | HTMLSnapshotExtension + sidecar + normalize stubs | 468c7d2 | test_snapshot_extension.py, test_fixture_metadata.py, test_html_normalize.py |
| 2 (GREEN) | HTMLSnapshotExtension + FixtureMetadata + normalize_for_snapshot | a12b6ef | _snapshot_extension.py, _fixture_metadata.py, _html_normalize.py |
| 3 (RED) | PII canary standalone test stub | 3ac13dc | test_live_fixtures_pii_canary.py |
| 3 (GREEN) | _assert_fixture_clean + loader integration + PII canary | 86a28d1 | conftest.py, test_live_fixtures_pii_canary.py |
| 4 (RED) | refresh_live + html_snapshot fixture wiring stubs | 5dfce1e | test_snapshot_extension.py, test_pytest_addoption.py |
| 4 (GREEN) | pytest_addoption + refresh_live + html_snapshot | c492026 | conftest.py |

## TDD Gate Compliance

All 4 tasks followed RED+GREEN discipline per D-811 (Phase 8 inheritance):

1. RED commits: test(09-01): ... stubs — ImportError / fixture-not-found
2. GREEN commits: feat(09-01): ... — production code makes tests pass
3. REFACTOR: not needed (code is clean as written)

Total: 7 commits (1 feat + 3 RED + 3 GREEN pairs)

## Success Criteria Verification

- [x] syrupy>=4.7,<5.0 added to pyproject.toml dev group, resolves to 4.9.1
- [x] tests/_snapshot_extension.py: HTMLSnapshotExtension(SingleFileSnapshotExtension), _file_extension="html", _write_mode=WriteMode.TEXT — TEST-HARNESS-01
- [x] tests/_fixture_metadata.py: FixtureMetadata frozen dataclass + write_sidecar + read_sidecar — TEST-HARNESS-02c
- [x] tests/_html_normalize.py: normalize_for_snapshot (idempotent) — T-09-DRIFT mitigation
- [x] _assert_fixture_clean + _PII_PATTERNS defined in tests/conftest.py — TEST-HARNESS-02a/b, D-907 #1
- [x] 3 live-fixture loaders wrapped (stereotype, armani, contre-jour) — D-907 enforcement point #1
- [x] tests/test_live_fixtures_pii_canary.py: 9 tests green — D-907 enforcement point #2
- [x] pytest_addoption("--refresh-live") + refresh_live fixture + html_snapshot fixture — D-906
- [x] uv run pytest -x -m "not live" GREEN: 870 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pytest.fail.Exception is BaseException, not Exception**
- **Found during:** Task 3 GREEN (first canary run)
- **Issue:** plan specified `pytest.raises(Exception)` but `pytest.fail()` raises `pytest.fail.Exception` which inherits from `BaseException`, not `Exception`. The tests would never catch canary failures.
- **Fix:** Defined `_CanaryError = pytest.fail.Exception` alias in test_live_fixtures_pii_canary.py; used `pytest.raises(_CanaryError)` throughout
- **Files modified:** tests/test_live_fixtures_pii_canary.py
- **Commit:** 86a28d1

**2. [Rule 1 - Bug] Standalone UUID v4 pattern false-positive on Phase 8 fixtures**
- **Found during:** Task 3 GREEN (test_clean_phase8_goldapple_stereotype_passes)
- **Issue:** The UUID v4 regex matched goldapple `buildId` in Nuxt __NEXT_DATA__ (e.g. `98eb8be3-3518-408c-9eaf-26bad2353acb`). This is a Nuxt deployment build identifier, NOT a session secret or hc-ping operator token. RESEARCH A6 verified fixtures are PII-clean by grepping `cf_clearance|set-cookie|x-bot-token|hc-ping` but did NOT check UUID v4 — which goldapple legitimately uses in build manifests.
- **Fix:** Removed standalone UUID v4 pattern from `_PII_PATTERNS`. The `hc-ping\.com/[0-9a-f-]{32,36}` pattern already covers the actual threat (operator healthcheck token in hc-ping URLs). Updated test_dirty_fixture_uuid_v4_fails to test_dirty_fixture_uuid_hc_ping_via_hc_pattern_fails with explicit documentation of the rationale.
- **Files modified:** tests/conftest.py, tests/test_live_fixtures_pii_canary.py
- **Commit:** 86a28d1

## Boundary-Language Note

The CONTEXT.md D-903 uses "persist" as the conceptual name for the writer method. The actual method in `src/ga_crawler/storage/sqlite.py:177` is `SqliteSnapshotWriter.append`. All downstream Phase 9 plans (09-02b, TH-06 Pydantic) must use `append` — not `persist` — when referencing the injection point.

## Key Technical Decisions

1. **pytest.fail.Exception vs Exception**: canary uses `pytest.fail()` for correct pytest integration (fail appears as test failure, not exception traceback). Callers must use `pytest.raises(pytest.fail.Exception)` or the `_CanaryError` alias defined in test_live_fixtures_pii_canary.py.

2. **UUID v4 pattern excluded from _PII_PATTERNS**: goldapple HTML legitimately contains UUID-format buildIds. The hc-ping-specific pattern covers the actual operator healthcheck token threat. Future phases should NOT add a standalone UUID pattern without verifying it doesn't false-positive on goldapple HTML.

3. **_html_normalize.py BUILD_HASH_RE scope**: covers `title__heading|title__brand|title__name|brand|name` per plan spec. If goldapple adds new CSS class namespaces with hash suffixes, extend this regex.

## D-902 P2 GO/NO-GO Anchor

First RED commit: 468c7d2 (test(09-01): RED — TH-01 HTMLSnapshotExtension + TH-02c sidecar + normalize stubs)
Time: ~2026-05-14T04:42 UTC (approximately)

This timestamp anchors the D-902 8h gate measurement: if 09-02 last GREEN commit lands within 8h of this, P2 GO condition is met.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All new files are test infrastructure only. The PII canary (`_assert_fixture_clean`) reads fixture files but does NOT emit their content — it logs only the matched pattern name on failure (T-09-PII no-content-leak enforcement).

## Self-Check: PASSED

Files exist:
- tests/_snapshot_extension.py: EXISTS
- tests/_fixture_metadata.py: EXISTS
- tests/_html_normalize.py: EXISTS
- tests/test_snapshot_extension.py: EXISTS
- tests/test_live_fixtures_pii_canary.py: EXISTS
- tests/test_fixture_metadata.py: EXISTS
- tests/test_html_normalize.py: EXISTS
- tests/test_pytest_addoption.py: EXISTS

Commits exist (verified via git log):
- 7a99405: feat(09-01): add syrupy>=4.7,<5.0 dev dep
- 468c7d2: test(09-01): RED — TH-01 HTMLSnapshotExtension + TH-02c sidecar + normalize stubs
- a12b6ef: feat(09-01): GREEN — HTMLSnapshotExtension + FixtureMetadata + normalize_for_snapshot
- 3ac13dc: test(09-01): RED — TH-02 PII canary + size budget stubs
- 86a28d1: feat(09-01): GREEN — _assert_fixture_clean + loader integration + standalone PII canary
- 5dfce1e: test(09-01): RED — refresh_live + html_snapshot fixture wiring tests
- c492026: feat(09-01): GREEN — pytest_addoption(--refresh-live) + html_snapshot fixture

Test count: 870 passed (was 849 pre-plan baseline per clean test run; +21 new tests)
