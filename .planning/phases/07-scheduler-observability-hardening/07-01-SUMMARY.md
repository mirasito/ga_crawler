---
phase: 07-scheduler-observability-hardening
plan: 01
subsystem: scheduler-observability
tags: [wave-0, red-gate, source-lock, shape-canary, tests-only]
requires: []
provides:
  - tests/test_phase07_cron_template_shape.py
  - tests/test_phase07_logrotate_template_shape.py
  - tests/test_phase07_wrapper_contract.py
  - tests/test_phase07_test_failure_alert_shape.py
  - tests/test_phase07_readme_structure.py
  - tests/test_phase07_env_example_shape.py
  - tests/test_phase07_structural_canaries.py
affects:
  - tests/ (top-level convention; parents[1] for REPO_ROOT)
tech-stack:
  added: []
  patterns:
    - stdlib + pytest + tomllib only — zero new deps
    - REPO_ROOT = Path(__file__).resolve().parents[1] (top-level tests/ idiom from Phase 6)
    - read_text + substring assert (source-lock); markdown H2 list assert; tomllib parse + namespace set assert
key-files:
  created:
    - tests/test_phase07_cron_template_shape.py (5 tests, 58 lines)
    - tests/test_phase07_logrotate_template_shape.py (8 tests, 59 lines)
    - tests/test_phase07_wrapper_contract.py (17 tests, 168 lines)
    - tests/test_phase07_test_failure_alert_shape.py (9 tests, 86 lines)
    - tests/test_phase07_readme_structure.py (3 tests, 66 lines)
    - tests/test_phase07_env_example_shape.py (6 tests, 84 lines)
    - tests/test_phase07_structural_canaries.py (8 tests, 163 lines)
  modified: []
decisions:
  - Mirror Phase 6 convention parents[1] for top-level tests/ (vs unit/ depth parents[2])
  - structural_canaries enforces "zero production Python" by inverted invariants (these PASS now, RED only if Phase 7 breaks them)
  - Wrapper shebang reconciled to '#!/usr/bin/env bash' per project convention (bin/backup.sh:1); D-709 verbatim '#!/bin/bash' is overridden
metrics:
  duration: ~5 minutes (single-pass)
  completed-date: 2026-05-12
requirements: [SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05]
threat-refs: [T-07-01, T-07-02, T-07-04, T-07-05, T-07-08]
---

# Phase 7 Plan 01: Wave 0 RED-Gate Canaries Summary

**One-liner:** Seven RED-gate pytest stubs lock the shape of every Phase 7 operator-facing artifact (cron, logrotate, bash wrappers, README, .env.example) BEFORE Plans 07-02..07-04 ship them — establishing a ≤5s pytest feedback loop and the "zero production Python" structural invariant.

## What Shipped

| File | Tests | Lines | Coverage |
|------|-------|-------|----------|
| `tests/test_phase07_cron_template_shape.py` | 5 | 58 | SCHED-01 + SCHED-02 + Pitfall #1 (deploy/etc-cron-d-ga_crawler) |
| `tests/test_phase07_logrotate_template_shape.py` | 8 | 59 | SCHED-04 + T-07-05 (deploy/etc-logrotate-d-ga_crawler) |
| `tests/test_phase07_wrapper_contract.py` | 17 | 168 | SCHED-03 + SCHED-04 + D-709 + T-07-01/02/04 (bin/weekly-run.sh) |
| `tests/test_phase07_test_failure_alert_shape.py` | 9 | 86 | SCHED-05 + D-706 5-step orchestrator (bin/test-failure-alert.sh) |
| `tests/test_phase07_readme_structure.py` | 3 | 66 | SCHED-05 + D-707 10-section RU order (README.md) |
| `tests/test_phase07_env_example_shape.py` | 6 | 84 | SCHED-05 + D-703 + Pitfall #4 + T-07-04 (.env.example) |
| `tests/test_phase07_structural_canaries.py` | 8 | 163 | Cross-phase invariants: zero-Python, no new namespace, 5-way disjoint, load_dotenv-only-cli |
| **Total** | **56** | **684** | All 5 SCHED requirements + 5 threats; zero new deps |

## RED vs GREEN State at Plan Close

| File | State | Reason |
|------|-------|--------|
| `test_phase07_cron_template_shape.py` | **4 RED + 1 GREEN** | 4 fail on missing `deploy/etc-cron-d-ga_crawler`; 1 passes (filename-constant has no dot, lives only in Python) |
| `test_phase07_logrotate_template_shape.py` | **8 RED** | All fail on missing `deploy/etc-logrotate-d-ga_crawler` (Plan 07-02 ships) |
| `test_phase07_wrapper_contract.py` | **17 RED** | All fail on missing `bin/weekly-run.sh` (Plan 07-03 ships) |
| `test_phase07_test_failure_alert_shape.py` | **9 RED** | All fail on missing `bin/test-failure-alert.sh` (Plan 07-03 ships) |
| `test_phase07_readme_structure.py` | **3 RED** | All fail on missing `README.md` (Plan 07-04 ships) |
| `test_phase07_env_example_shape.py` | **1 RED + 5 GREEN** | RED: `HC_PING_URL=` not yet appended (Plan 07-02). GREEN: Phase 6 TG_* placeholders survive + value hygiene OK |
| `test_phase07_structural_canaries.py` | **8 GREEN** | All inverted invariants satisfied by frozen Phase 6 state (Phase 7 mustn't break) |

**Aggregate:** 14 pass + 42 fail/error at plan close — exactly the contract described by VALIDATION.md sampling rate (RED-gate established before artifacts land).

## Phase 1-6 Regression Check

```
uv run pytest tests/ <exclude phase07> -m "not live"
→ 746 passed, 1 skipped, 181 warnings in 137.72s
```

**Zero regression.** Wave 0 adds tests only; touches no production source.

## Deviations from Plan

None — plan executed exactly as written. All 7 files match the spec, line counts meet or exceed `min_lines`, test counts meet or exceed plan's "done" criteria for each task.

| Plan claim | Actual | Notes |
|------------|--------|-------|
| `cron_template_shape.py` ≥5 tests | 5 | exact |
| `logrotate_template_shape.py` ≥8 tests | 8 | exact |
| `wrapper_contract.py` ~14 tests | 17 | exceeded |
| `test_failure_alert_shape.py` ~9 tests | 9 | exact |
| `readme_structure.py` ≥3 tests | 3 | exact |
| `env_example_shape.py` ≥6 tests | 6 | exact |
| `structural_canaries.py` ≥7 tests | 8 | exceeded |

## Commits

- `8dfd451` test(07-01): add cron + logrotate shape canaries (Task 1)
- `293409c` test(07-01): add wrapper/orchestrator/README source-lock canaries (Task 2)
- `6e2ec88` test(07-01): add env.example + structural cross-phase canaries (Task 3)

## Convention Established

**Filename convention:** `tests/test_phase07_*.py` at top-level (mirror `tests/test_delivery_source_lock.py` / `tests/test_delivery_stats.py` Phase 6 convention). All 7 files use `REPO_ROOT = Path(__file__).resolve().parents[1]` — distinct from `tests/unit/*.py` which uses `parents[2]`.

**Source-lock idiom:** `read_text(encoding="utf-8")` + substring asserts with D-NNN citations in failure messages. Negative asserts use forbidden-substring lists.

## Threat Coverage (Wave 0 disposition)

| Threat ID | Mitigation in this plan |
|-----------|------------------------|
| T-07-01 (cron MAILTO leak) | `test_cron_contains_mailto_empty` + `test_wrapper_redirects_stdout_stderr_to_logfile` |
| T-07-02 (flock race) | `test_wrapper_uses_flock_non_blocking` + `test_wrapper_reserves_exit_5_for_flock` |
| T-07-04 (HC UUID leak) | `test_wrapper_does_not_hardcode_uuid` + `test_env_example_all_known_placeholders_blank` |
| T-07-05 (logrotate mode mismatch) | `test_logrotate_has_create_directive` |
| T-07-08 (operator-controlled .env injection) | `test_env_example_values_have_no_hash_no_quotes_no_newlines` — Pitfall #4 typo guard (accept disposition for root-compromise) |

## Self-Check: PASSED

**Files exist (verified via `wc -l`):**
- tests/test_phase07_cron_template_shape.py (58 lines)
- tests/test_phase07_logrotate_template_shape.py (59 lines)
- tests/test_phase07_wrapper_contract.py (168 lines)
- tests/test_phase07_test_failure_alert_shape.py (86 lines)
- tests/test_phase07_readme_structure.py (66 lines)
- tests/test_phase07_env_example_shape.py (84 lines)
- tests/test_phase07_structural_canaries.py (163 lines)

**Commits exist (verified via `git log`):**
- 8dfd451 (Task 1)
- 293409c (Task 2)
- 6e2ec88 (Task 3)

**Test contract verified:**
- `uv run pytest tests/test_phase07_*.py --collect-only -q` → 56 tests collected (target: ≥35 ✓).
- `uv run pytest tests/test_phase07_*.py` → 14 pass + 42 fail/error (RED gate established for Plans 07-02..07-04 ✓).
- Phase 1-6 suite still GREEN: 746 passed, 1 skipped ✓.
