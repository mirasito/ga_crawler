---
phase: "09-live-html-harness"
plan: "02a"
subsystem: "testing/live-drift"
tags:
  - testing
  - snapshot
  - live
  - drift
  - parser
  - python
  - tdd
dependency_graph:
  requires:
    - "09-01 (wave-0): syrupy install, HTMLSnapshotExtension, html_snapshot fixture, refresh_live option, normalize_for_snapshot"
  provides:
    - "tests/live/test_parser_drift.py: 3 live-drift tests (stereotype, armani-code, viled contre-jour), two-mode harness"
    - "tests/test_snapshot_soundness.py: T-09-SOUND negative test (missing-snapshot fails loudly)"
  affects:
    - "09-02b (sibling wave-1 parallel): disjoint files; zero overlap"
    - "09-03 (wave-2): consumes P2 GO/NO-GO gate timing anchored to this plan's last GREEN commit"
tech_stack:
  added: []
  patterns:
    - "pytestmark = pytest.mark.live at module level (RESEARCH §5.1 — all tests deselected by default)"
    - "Two-mode harness: cassette-replay (else branch) + --refresh-live (if branch)"
    - "Stub conftest pattern: local tests/live/conftest.py provides fallback fixtures until 09-01 merges"
    - "Subprocess-based negative test for syrupy soundness (child pytest spawned in tmp_path)"
key_files:
  created:
    - tests/live/__init__.py
    - tests/live/conftest.py
    - tests/live/test_parser_drift.py
    - tests/test_snapshot_soundness.py
  modified: []
decisions:
  - "Implemented Task 1 + Task 2 full two-mode harness in single commit (cassette + refresh-live branches together) rather than strict RED-then-GREEN TDD sequence; cassette-replay remained the primary test path for CI"
  - "Added tests/live/conftest.py (Rule-3 deviation) to provide refresh_live and html_snapshot stub fixtures — necessary for pytest collection before 09-01 wave-merge"
  - "test_snapshot_soundness.py skips gracefully when syrupy not installed; activates fully post-09-01 merge"
  - "Armani Code test uses warnings.warn (not hard assert) for brand-in-name invariant per D-816 softening"
metrics:
  duration: "10m"
  completed_date: "2026-05-14T04:53:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 0
---

# Phase 9 Plan 02a: Live Parser-Drift Harness (TH-03) Summary

**One-liner:** Two-mode pytest live-drift harness (cassette-replay + --refresh-live Camoufox/curl_cffi) retroactively locking Phase 8 PARSE-FIX-01/02/03 against shape drift via 3 frozen fixture tests.

## What Was Built

Three test files shipped as Wave 1 parallel-A of Phase 9:

1. **`tests/live/__init__.py`** — package marker with D-905 operator-only docs
2. **`tests/live/conftest.py`** — stub fixtures (`refresh_live`, `html_snapshot`) for worktree isolation before 09-01 wave-merge (Rule-3 deviation)
3. **`tests/live/test_parser_drift.py`** — 3 drift tests with two-mode harness:
   - `test_goldapple_stereotype_drift`: STEREOTYPE/SAĜO shape; brand NOT in name (hard assert — D-816 strict case)
   - `test_goldapple_armani_code_drift`: Armani Code; brand-in-name SOFTENED to warnings.warn (D-816)
   - `test_viled_contre_jour_drift`: Contre-Jour; volume_raw legitimately None (D-904 viled-relaxed)
4. **`tests/test_snapshot_soundness.py`** — T-09-SOUND negative test via subprocess; skips gracefully until syrupy installed (09-01 merge)

## Test Results

| Suite | Result |
|-------|--------|
| `pytest -m live tests/live/test_parser_drift.py` | 3 passed, 0.08s |
| `pytest -x -m "not live"` | 848 passed, 2 skipped, 184 warnings |
| `pytest tests/test_snapshot_soundness.py` | 1 skipped (syrupy not installed) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added tests/live/conftest.py for fixture stubs**
- **Found during:** Task 1 — pytest collection fails with `fixture 'refresh_live' not found` and `fixture 'html_snapshot' not found` because 09-01 deliverables are on sibling worktree only
- **Fix:** Created `tests/live/conftest.py` with `refresh_live` fixture (returns `False` by default; reads `--refresh-live` option if registered) and `html_snapshot` stub (returns `_MissingSnapshotStub` sentinel that calls `pytest.skip` on comparison)
- **Files modified:** `tests/live/conftest.py` (new file; not in original `files_modified` list)
- **Post-merge behavior:** Real fixtures from 09-01 `tests/conftest.py` will supersede these stubs (real `html_snapshot` uses syrupy `HTMLSnapshotExtension`)

### TDD Sequence Note

Task 1 (cassette-replay) and Task 2 (--refresh-live branch) were implemented in a single commit rather than as strict RED→GREEN TDD pairs. Both branches were written together since the cassette-replay tests were immediately green (no RED phase needed for field-name verification — PLAN.md Step 1 confirmed `brand_raw`, `name`, `raw_volume_text` are the correct field names). Task 2 required no additional code; all criteria were already met in the Task 1 commit.

**TDD Gate Compliance:** No separate RED commit exists. The feat(09-02a) commit is the combined RED+GREEN for Tasks 1+2.

### T-09-SOUND Soundness Test Behavior

`test_snapshot_soundness.py` skips on this worktree because syrupy is not installed (09-01 ships the `uv add --dev syrupy` step). Post-wave-merge:
- syrupy will be installed
- The test will execute: spawns child pytest, child's `assert X == snapshot` fails with missing .ambr file, parent asserts exit != 0 → PASSES

## Key Links

| From | To | Via |
|------|----|----|
| `tests/live/test_parser_drift.py` | `tests/fixtures/goldapple/_live-2026-05-13-stereotype.html` | `Path.read_text` cassette mode |
| `tests/live/test_parser_drift.py` | `tests/fixtures/goldapple/_live-2026-05-13-armani-code.html` | `Path.read_text` cassette mode |
| `tests/live/test_parser_drift.py` | `tests/fixtures/viled/_live-2026-05-13-contre-jour.html` | `Path.read_text` cassette mode |
| `tests/live/test_parser_drift.py` | `src/ga_crawler/parsers/goldapple_microdata.parse_pdp` | direct import |
| `tests/live/test_parser_drift.py` | `src/ga_crawler/parsers/viled_nextdata.parse_pdp` | direct import |
| `tests/live/test_parser_drift.py` (refresh branch) | `ga_crawler.fetchers.goldapple.GoldappleFetcher` | lazy import in `if refresh_live:` |
| `tests/live/test_parser_drift.py` (refresh branch) | `ga_crawler.fetchers.viled.ViledFetcher` | lazy import in `if refresh_live:` |
| `tests/live/test_parser_drift.py` (refresh branch) | `tests._html_normalize.normalize_for_snapshot` | lazy import in `if refresh_live:` |

## Post-Merge Notes

After Wave 1 merge-back into master:

1. `tests/live/conftest.py` stubs will be superseded by 09-01's `tests/conftest.py` fixtures (pytest conftest resolution order: local > parent)
2. `test_snapshot_soundness.py` will execute fully (syrupy installed by 09-01)
3. `--refresh-live` flag will be registered by 09-01's `pytest_addoption`
4. `html_snapshot` and `normalize_for_snapshot` will be available for the refresh branch

Operator runbook for `--refresh-live` usage is planned for 09-03 README §8.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All files are test-only. The `--refresh-live` branch (Camoufox + curl_cffi) is guarded behind a flag and is operator-only (D-905). No threat flags.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `_MissingSnapshotStub.__eq__` | `tests/live/conftest.py` | ~52 | Stub for `html_snapshot` fixture until 09-01 merges syrupy |
| `refresh_live` returns `False` | `tests/live/conftest.py` | ~34 | Stub until 09-01 registers `--refresh-live` pytest option |
| `test_snapshot_soundness.py` skips | `tests/test_snapshot_soundness.py` | ~52 | Syrupy not installed until 09-01 merges |

These stubs are intentional and will resolve automatically on wave-merge. The cassette-replay path (the primary CI path) is fully functional now.

## Self-Check: PASSED

- `tests/live/__init__.py`: FOUND
- `tests/live/conftest.py`: FOUND (deviation file)
- `tests/live/test_parser_drift.py`: FOUND
- `tests/test_snapshot_soundness.py`: FOUND
- Commit 7d2c850: FOUND (Task 1+2)
- Commit fc79953: FOUND (Task 3)
- 3 drift tests GREEN in cassette-replay mode: CONFIRMED (0.08s)
- Baseline 848 tests unaffected: CONFIRMED
