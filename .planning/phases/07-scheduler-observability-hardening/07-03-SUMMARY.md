---
phase: 07-scheduler-observability-hardening
plan: 03
subsystem: ops-wrappers
tags: [bash, cron-wrapper, healthchecks-io, flock, observability]
requires: [07-01]
provides:
  - "bin/weekly-run.sh production cron wrapper (D-709 contract)"
  - "bin/test-failure-alert.sh operator orchestrator (D-706 SC#5 recipe)"
affects:
  - "SCHED-03 (HC.io pings + flock + fail-loud HC_PING_URL) — closed at source"
  - "SCHED-04 (stdout/stderr redirect to datestamped logfile) — closed at source"
  - "Wave 0 canaries: wrapper_contract + test_failure_alert_shape RED → GREEN"
tech-stack:
  added: []
  patterns:
    - "Bash wrapper as env-loading authority for cron (set -a; source; set +a)"
    - "flock -n 9 advisory lock with explicit exit 5 (Pitfall #3 — disambiguate from generic exit 1)"
    - "set +e/EXIT=$?/set -e dance to preserve Python exit code through HC fail-ping branch"
    - "Healthchecks.io ping triad: /start (pre), bare URL (success), /fail with exit body"
key-files:
  created:
    - "bin/weekly-run.sh — D-709 production cron wrapper (77 lines, 100755)"
    - "bin/test-failure-alert.sh — D-706 SC#5 orchestrator (57 lines, 100755)"
  modified: []
decisions:
  - "Shebang reconciled to '#!/usr/bin/env bash' (project convention, bin/backup.sh:1) — divergence from CONTEXT.md D-709 verbatim '#!/bin/bash' documented in this SUMMARY."
  - "LOG_DIR/LOG_FILE split (plan body) collapsed into single-line LOG_FILE assignment to satisfy canary source-grep for the exact path substring '/var/log/ga_crawler/weekly-run-$(date +%F).log'."
metrics:
  duration: "~6 minutes"
  completed: "2026-05-12"
  tasks_completed: 2
  files_changed: 2
  canaries_flipped: 23  # 14 wrapper_contract + 9 test_failure_alert_shape
---

# Phase 07 Plan 03: Bash Wrappers (D-709 + D-706) Summary

Two bash scripts under `bin/` close SCHED-03 (Healthchecks.io dead-man's-switch monitoring) and SCHED-04 (log redirect) at source level, plus orchestrate SC#5 deliberate-failure verification. First additions to `bin/` since Plan 02-06 `bin/backup.sh`.

## What Was Built

### 1. `bin/weekly-run.sh` — D-709 production cron wrapper (77 lines, mode 100755)

Verbatim shape from CONTEXT.md D-709 (lines 92–131). Owns seven responsibilities in strict order:

1. **ENV load** via `set -a; source .env; set +a` (bash is the env-loading authority for cron context per Phase 6 RESEARCH caveat #4).
2. **Fail-loud guard** via `: "${HC_PING_URL:?...}"` — exit 4 if missing (D-703 / T-07-04).
3. **flock advisory lock** on `/var/lock/ga_crawler-weekly.lock`; explicit `exit 5` on refusal (Pitfall #3 / T-07-02).
4. **HC.io /start ping** via `curl -fsS -m 10 --retry 3 ... || true` (fail-soft).
5. **Production exec** `uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1` with `LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"` (SCHED-04).
6. **HC.io success/fail ping** via `set +e/EXIT=$?/set -e` dance — bare URL on 0, `/fail` with `--data-raw "exit=$EXIT"` body otherwise.
7. **Passthrough** via `exit $EXIT`.

### 2. `bin/test-failure-alert.sh` — D-706 SC#5 orchestrator (57 lines, mode 100755)

Verbatim 5-step recipe from CONTEXT.md D-706 / RESEARCH.md Example 4:

1. Invoke `bin/weekly-run.sh --viled-only --sanity-gate-n 999999 || true` (force sanity-N gate trip; we WANT a failed run).
2. Extract `run_id` from `/var/log/ga_crawler/weekly-run-$(date +%F).log` via `tail -200 | grep -o '"run_id":[0-9]*' | tail -1 | grep -o '[0-9]*'`.
3. Invoke `sudo -u ga_crawler /opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"` (DELIVER-02 / DELIVER-03 routing test).
4. Emit operator visual checklist (ops chat / business chat / HC dashboard / DB runs.status / DB stats.deliver.delivery_status with expected `delivered_ops_only` enum and `sanity_gate_n_failed:120<999999` reason).
5. **No cleanup** — failed run persists as DB evidence (idempotent invariant).

Reuses existing CLI surface only (`--viled-only` D-212, `--sanity-gate-n` Plan 04-05, `deliver-run --run-id` D-608). Zero new Python code paths.

## Canaries Flipped RED → GREEN

| Suite | Count | Pre-state | Post-state |
|-------|-------|-----------|------------|
| `tests/test_phase07_wrapper_contract.py` | 17 (14 plan-listed + 3 fixture-collection items) | ERROR (file missing) | **17 PASSED** |
| `tests/test_phase07_test_failure_alert_shape.py` | 9 | ERROR (file missing) | **9 PASSED** |

Combined: **26 passed in 0.05s**.

Remaining Wave 0 RED canaries (out of scope for this plan):
- `test_phase07_readme_structure.py` — owned by Plan 07-04.
- `test_phase07_env_example_shape.py` + `test_phase07_cron_template_shape.py` — owned by Plan 07-02 (Wave 2 sibling, runs in parallel; their failures are expected from this worktree's perspective).

Phase 6 suite remains GREEN: 214 passed, 1 skipped (the 1 failure + 1 error seen in full-suite run are both 07-02 canaries, not 07-03 regressions).

## Decisions Made

### D-1: Shebang divergence — `#!/usr/bin/env bash` (NOT `#!/bin/bash`)

CONTEXT.md D-709 verbatim specifies `#!/bin/bash` (lines 92–131). Project convention (`bin/backup.sh:1`) uses `#!/usr/bin/env bash`, and the canary `test_wrapper_shebang_is_env_bash` enforces `#!/usr/bin/env bash` explicitly. Planner annotated this reconciliation in PLAN frontmatter `wave_strategy_note` and Task 1 `<action>` body.

**Resolution:** Use `#!/usr/bin/env bash` for both scripts. Documented here as required by the planner's frontmatter note and the plan's success criterion.

### D-2: `LOG_DIR` + `LOG_FILE` split collapsed to single-line assignment

The plan body (Task 1 action block) writes:
```bash
LOG_DIR=/var/log/ga_crawler
LOG_FILE="$LOG_DIR/weekly-run-$(date +%F).log"
```

But `test_wrapper_log_file_path_has_datestamp` source-greps for the substring `/var/log/ga_crawler/weekly-run-$(date +%F).log` literally in one expression. The split form fails the canary (substring spans two lines). Applied Rule 3 (auto-fix blocking issue): collapsed to `LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"`. Semantics unchanged — only the literal-source representation matters to the dead-man source-lock.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Collapsed LOG_DIR/LOG_FILE two-line split into single line**
- **Found during:** Task 1 canary run after initial Write.
- **Issue:** Canary `test_wrapper_log_file_path_has_datestamp` requires literal substring `/var/log/ga_crawler/weekly-run-$(date +%F).log` in source; plan body split it across `LOG_DIR=` + `LOG_FILE="$LOG_DIR/..."`.
- **Fix:** Replaced two-line split with single-line assignment matching the canary's expected substring. Runtime semantics identical.
- **Files modified:** `bin/weekly-run.sh`
- **Commit:** Squashed into Task 1 commit `d4c813f` (fix applied before staging).

## Threat Model — Mitigations Verified

| Threat ID | Where Mitigated in This Plan | Canary |
|-----------|------------------------------|--------|
| T-07-01 (cron MAILTO leak) | `bin/weekly-run.sh` Step 5: `>> "$LOG_FILE" 2>&1` redirect | `test_wrapper_redirects_stdout_stderr_to_logfile` |
| T-07-02 (double-run DB corruption) | `bin/weekly-run.sh` Step 3: `flock -n 9` + `exit 5` | `test_wrapper_uses_flock_non_blocking`, `test_wrapper_reserves_exit_5_for_flock` |
| T-07-04 (HC.io UUID leak) | `bin/weekly-run.sh`: `${HC_PING_URL}` from `.env`; no hardcoded UUID | `test_wrapper_does_not_hardcode_uuid` (regex scan) |
| T-07-07 (lock-file world-writable) | Accepted per CONTEXT.md threat 8; advisory lock not auth | n/a (accepted) |
| T-07-08 (`source .env` code injection) | Accepted — operator+root not compromised threat model | n/a (accepted) |
| T-07-03 (cron command injection) | Wrapper file root-owned 0644 + `.env` 0600 (operator-controlled, README Plan 07-04) | not enforced by Phase 7 canaries (deployment-time invariant) |

## Self-Check: PASSED

**Files exist:**
- `bin/weekly-run.sh` — FOUND (77 lines, mode 100755 in git index)
- `bin/test-failure-alert.sh` — FOUND (57 lines, mode 100755 in git index)
- `.planning/phases/07-scheduler-observability-hardening/07-03-SUMMARY.md` — being written now

**Commits exist:**
- `d4c813f feat(07-03): bin/weekly-run.sh — D-709 contract` — FOUND in `git log`
- `3ac9599 feat(07-03): bin/test-failure-alert.sh — D-706 orchestrator (SC#5)` — FOUND in `git log`

**Canaries GREEN:**
- 17/17 in `tests/test_phase07_wrapper_contract.py`
- 9/9 in `tests/test_phase07_test_failure_alert_shape.py`

**Phase 6 not regressed:** 214 passed, 1 skipped in full suite. Two Phase 7 failures observed in full-suite run are both owned by Plan 07-02 (Wave 2 sibling — `.env.example` HC_PING_URL placeholder + cron template TZ); they are out of scope for this plan and expected from this worktree's perspective.

## Operator Notes

- **Wrapper is NOT executed by tests.** All 26 canaries are pure source-grep against file contents; no actual `curl` / `flock` / `cron` runtime in CI. Runtime verification (real Healthchecks.io endpoint, real Telegram delivery, real flock contention) is operator-runbook concern per VALIDATION.md.
- **Both scripts are mode 100755 in the git index** (verified via `git ls-files --stage`). On Linux executor (Hetzner), `chmod +x` is preserved; on Windows/Git Bash, the executable bit is recorded in the git index and propagates to checkout on Unix targets.
- **Git CRLF warning** observed on Windows worktree (`LF will be replaced by CRLF the next time Git touches it`) — this is Git-for-Windows default `core.autocrlf=true` behavior, not a file content issue. File content on disk is LF; checkout-on-Linux preserves LF.
- **Next plan in Wave 2:** Plan 07-02 (cron template + logrotate + `.env.example`) completes in parallel. After Wave 2 closes: Plan 07-04 (README ops playbook) + Plan 07-05 (runbook) in Wave 3.

## Closure

SCHED-03 closed at source level. SCHED-04 closed at source level. SC#5 procedure closed at source level. All three depend on operator deploy + manual smoke per VALIDATION.md for runtime certification.

2 of 7 Wave 0 source-lock canaries flipped RED → GREEN by this plan.
