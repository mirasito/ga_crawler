---
phase: 07-scheduler-observability-hardening
verified: 2026-05-13T00:00:00Z
status: human_needed
score: 5/5 must-haves verified (3 in CI, 2 by design require operator post-deploy)
overrides_applied: 0
requirements_met: 5/5
requirements:
  - id: SCHED-01
    status: VERIFIED
    evidence: "deploy/etc-cron-d-ga_crawler:24 (`0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh`); README.md:96 documents deploy procedure; test_phase07_cron_template_shape.py::test_cron_contains_weekly_run_row GREEN. Runtime confirmation (SC#1 manual gate) deferred to operator after VPS provisioning."
  - id: SCHED-02
    status: VERIFIED
    evidence: "deploy/etc-cron-d-ga_crawler:21 (`CRON_TZ=Asia/Almaty` first non-comment line); test_phase07_cron_template_shape.py::test_cron_contains_cron_tz_almaty + test_cron_contains_mailto_empty GREEN; README.md:100 documents SCHED-02 invariant."
  - id: SCHED-03
    status: VERIFIED
    evidence: "bin/weekly-run.sh: /start ping line 77, success ping line 88, /fail with --data-raw line 90; explicit `exit 4` line 60 (D-703 fail-loud after CR-01 fix commit ed07007); flock-refused HC /fail line 70 (WR-09 fix commit c1e732b). 17/17 wrapper_contract canaries GREEN; README.md §5 documents Healthchecks.io setup."
  - id: SCHED-04
    status: VERIFIED
    evidence: "bin/weekly-run.sh:74,82 (`LOG_FILE=/var/log/ga_crawler/weekly-run-$(date +%F).log` + `>> \"$LOG_FILE\" 2>&1` redirect); deploy/etc-logrotate-d-ga_crawler:20-28 (7 directives: weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create 0644). All 8 logrotate canaries + log-redirect wrapper canaries GREEN. structlog `run_id` binding inherited from Phase 4..6 (D-704: `_configure_logging()` source unchanged — test_cli_surface_remains_five_subcommands confirms cli.py anchors preserved)."
  - id: SCHED-05
    status: VERIFIED
    evidence: "README.md (247 lines, 10 H2 sections per D-707 verbatim order); bin/test-failure-alert.sh (61 lines, 5-step D-706 orchestrator). test_readme_h2_order_matches_d707 + 9/9 test_failure_alert_shape canaries GREEN. Reuses --viled-only + --sanity-gate-n + deliver-run --run-id existing CLI surface only (zero new production Python — confirmed by test_no_simulate_failure_substring_in_production)."
success_criteria:
  - sc: 1
    description: "Cron entry uses CRON_TZ=Asia/Almaty; first scheduled run lands at expected Almaty time"
    status: human_needed
    reason: "Operator-manual gate per 07-CONTEXT.md and VALIDATION.md. CI verifies the cron config template shape; the actual firing on a real VPS at the expected wall-clock time cannot be validated in CI."
  - sc: 2
    description: "Healthchecks.io receives /start, /success, /fail pings; missed run triggers external alert"
    status: VERIFIED
    reason: "Wrapper code shape source-locked (17/17 wrapper_contract canaries GREEN: /start, bare URL on success, /fail with --data-raw, fail-soft `|| true`). Dead-man's-switch validation depends on operator HC.io account + grace-period config — documented in README §5 + §7."
  - sc: 3
    description: "Structured JSON logs (structlog) on disk with rotation; tail/grep shows progress with run_id"
    status: VERIFIED
    reason: "Wrapper redirects stdout/stderr to datestamped log file; logrotate config 7 directives present; structlog run_id binding pre-existing from Phase 4..6 (canary test_main_run_orchestrator_unchanged_anchors confirms); README §9 documents grep/jq workflow."
  - sc: 4
    description: "README documents from-scratch VPS setup + deliberate-failure procedure"
    status: VERIFIED
    reason: "README.md 10 H2 sections per D-707 order; §2 covers full VPS setup (CR-02 fix commit ef526f8: dropped useradd -m; CR-03 fix commit 9b1ac17: explicit PATH for uv); §7 covers deliberate-failure procedure. All 3 readme_structure canaries GREEN."
  - sc: 5
    description: "End-to-end deliberate-failure: ops chat alert, business chat silent, HC failure recorded, runs row failed"
    status: human_needed
    reason: "Operator-manual gate per 07-CONTEXT.md and VALIDATION.md. CI source-locks bin/test-failure-alert.sh 5-step recipe + checklist text + expected DB state strings (delivered_ops_only, sanity_gate_n_failed:120<999999). Actual Telegram chat verification + HC dashboard inspection + sqlite DB inspection require operator post-deploy."
human_verification:
  - test: "SC#1 — Cron timing verification"
    expected: "After first Sunday post-deploy, system cron fires Sunday 23:00 Asia/Almaty (Sunday 18:00 UTC); operator confirms via `sudo grep CRON /var/log/syslog` that the weekly-run row executed in the Almaty 23:00 window (not UTC 23:00). Report arrives in business chat Monday morning Almaty (~02:00–03:00 after 3–4h run)."
    why_human: "Real cron timing on a real VPS at a real wall-clock time cannot be verified by CI; requires Hetzner CX22 provisioned + .env populated + first Sunday tick observed by operator."
  - test: "SC#5 — Deliberate-failure end-to-end"
    expected: "After `sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh`: (a) Telegram ops chat receives alert with reason `upstream pipeline failed` for run #N; (b) Telegram business chat receives NO new message; (c) Healthchecks.io dashboard shows /start + /fail pings; (d) `sqlite3 prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=N'` returns `N | failed | sanity_gate_n_failed:120<999999`; (e) `runs.stats.deliver.delivery_status = delivered_ops_only`."
    why_human: "Telegram chat inspection + HC.io dashboard inspection + live sqlite DB inspection on the VPS — none verifiable in CI. Procedure documented in README §7 + script header."
  - test: "Smoke gate (`bin/weekly-run.sh --viled-only --sanity-gate-n 1`)"
    expected: "Mini-run completes successfully; HC dashboard shows /start + /success pings; business chat receives a mini-report; exit 0."
    why_human: "Setup-green check on real VPS after `useradd`+`uv install`+`uv sync`+`playwright install firefox`+`cp deploy/*` steps. Documented as README §2 step 8."
  - test: "HC.io Telegram integration"
    expected: "Invite `@my_hc_bot` in ops chat → `/start@my_hc_bot` activation → trigger a deliberate failure → Telegram alert from `@my_hc_bot` arrives in ops chat."
    why_human: "External-service Telegram integration in HC.io UI + Telegram bot acceptance — not testable in CI. Documented as README §5."
deferred: []
artifacts:
  - path: "bin/weekly-run.sh"
    status: VERIFIED
    lines: 95
    notes: "D-709 contract; exit 4 explicit on missing HC_PING_URL (CR-01 fix line 60); export PATH for uv (CR-03 fix line 47); flock-refused HC /fail ping (WR-09 fix line 70); shebang #!/usr/bin/env bash (project convention)."
  - path: "bin/test-failure-alert.sh"
    status: VERIFIED
    lines: 61
    notes: "D-706 5-step orchestrator; CR-04 fix commit 9c2ec20 — inner `sudo -u ga_crawler` removed (was impossible since `useradd -r` creates non-sudo system user); reuses existing CLI surface only."
  - path: "deploy/etc-cron-d-ga_crawler"
    status: VERIFIED
    lines: 25
    notes: "D-708 cron config-as-code; CRON_TZ=Asia/Almaty + MAILTO=\"\" + PATH= directive (CR-03 fix) + weekly-run row Sunday 23:00 + daily backup row 01:00."
  - path: "deploy/etc-logrotate-d-ga_crawler"
    status: VERIFIED
    lines: 28
    notes: "D-705 logrotate config-as-code; 7 directives (weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create 0644 ga_crawler ga_crawler)."
  - path: ".env.example"
    status: VERIFIED
    lines: 13
    notes: "Phase 6 TG_BOT_TOKEN + TG_BUSINESS_CHAT_ID + TG_OPS_CHAT_ID placeholders preserved; Phase 7 HC_PING_URL= placeholder added (SCHED-03 D-703)."
  - path: "README.md"
    status: VERIFIED
    lines: 247
    notes: "10 H2 sections per D-707 verbatim order; RU-primary prose; EN code blocks; sections cover SCHED-01..05 + reserved exit codes + deliberate-failure procedure + recovery runbook + grep/jq examples. CR-02/CR-03/WR-01/WR-02/WR-03 fixes applied (commits ef526f8, 9b1ac17, 9e886d7, 6f66b64, 81fe1cb)."
  - path: "tests/test_phase07_*.py"
    status: VERIFIED
    count: 7
    notes: "57 canaries total; 57/57 GREEN. Files: test_phase07_cron_template_shape.py (5), test_phase07_logrotate_template_shape.py (8), test_phase07_wrapper_contract.py (17), test_phase07_test_failure_alert_shape.py (9), test_phase07_readme_structure.py (3), test_phase07_env_example_shape.py (6), test_phase07_structural_canaries.py (8)."
key_links:
  - from: "bin/weekly-run.sh"
    to: "Healthchecks.io"
    via: "curl -fsS ... ${HC_PING_URL}/start | bare URL | /fail --data-raw exit=$EXIT"
    status: WIRED
    detail: "Three ping points present (line 77, 88, 90); fail-soft via || true; HC outage MUST NOT block production exec."
  - from: "bin/weekly-run.sh"
    to: "uv run python -m ga_crawler weekly-run"
    via: "line 82, with $@ pass-through + stdout/stderr redirect to LOG_FILE"
    status: WIRED
    detail: "Production exec preserves exit code via set +e/EXIT=$?/set -e dance; passes through to caller (cron)."
  - from: "bin/test-failure-alert.sh"
    to: "bin/weekly-run.sh + cli deliver-run"
    via: "step 1: bin/weekly-run.sh --viled-only --sanity-gate-n 999999; step 3: .venv/bin/python -m ga_crawler deliver-run --run-id"
    status: WIRED
    detail: "Reuses existing CLI surface; no new Python paths; CR-04 fix removed redundant inner sudo."
  - from: "/etc/cron.d/ga_crawler"
    to: "/opt/ga_crawler/bin/weekly-run.sh"
    via: "Sunday 23:00 Almaty schedule + ga_crawler user column"
    status: WIRED
    detail: "Config template at deploy/etc-cron-d-ga_crawler; operator deploys via `cp` per README §4."
  - from: "/etc/logrotate.d/ga_crawler"
    to: "/var/log/ga_crawler/*.log"
    via: "weekly + rotate 13 + compress + create 0644 ga_crawler ga_crawler"
    status: WIRED
    detail: "Config template at deploy/etc-logrotate-d-ga_crawler; operator deploys via `cp` per README §2."
---

# Phase 7: Scheduler + Observability Hardening — Verification Report

**Phase Goal:** A weekly cron entry in Asia/Almaty fires reliably on Sunday night with the report arriving Monday morning, dead-man's-switch monitoring catches missed runs, and a deliberate-failure test confirms ops alerts route correctly end-to-end.

**Verified:** 2026-05-13
**Status:** human_needed (3/5 SCs verifiable in CI; 2/5 are operator-manual gates by design — SC#1 cron-timing, SC#5 end-to-end deliberate-failure)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A system cron entry with `CRON_TZ=Asia/Almaty` runs `python -m ga_crawler` Sunday→Monday; first scheduled run lands at expected Almaty time | HUMAN_NEEDED | Config template VERIFIED (`deploy/etc-cron-d-ga_crawler` Sunday 23:00 row + CRON_TZ=Asia/Almaty first non-comment line; cron canaries 5/5 GREEN). Actual firing on real VPS at real wall-clock time — operator post-deploy. |
| 2 | Healthchecks.io receives /start, /success, /fail pings; missed run triggers external alert | VERIFIED | `bin/weekly-run.sh` lines 77, 88, 90 implement the three pings; CR-01 fix (commit `ed07007`) added explicit `exit 4` for missing HC_PING_URL; WR-09 fix (commit `c1e732b`) added HC /fail ping on flock-refused. 17/17 wrapper_contract canaries GREEN. External alert wiring (HC.io grace period + Telegram integration) documented in README §5. |
| 3 | Structured JSON logs (structlog) on disk with rotation; tail/grep shows run progress + retries + errors with run_id | VERIFIED | Wrapper line 82 redirects stdout/stderr to `/var/log/ga_crawler/weekly-run-$(date +%F).log`; `deploy/etc-logrotate-d-ga_crawler` has 7 required directives (weekly + rotate 13 + compress + delaycompress + missingok + notifempty + create 0644). structlog `run_id` binding preserved from Phase 4..6 (D-704 — `_configure_logging()` source unchanged, confirmed by `test_cli_surface_remains_five_subcommands`). README §9 documents grep/jq workflow with WR-02/WR-03 fixes (zgrep -h + pre-filter for non-JSON lines). |
| 4 | README documents from-scratch VPS setup + deliberate-failure procedure | VERIFIED | README.md 10 H2 sections per D-707 verbatim; §2 has 8-step VPS setup (Hetzner CX22 + Ubuntu 24.04 LTS); §7 covers deliberate-failure procedure; CR-02 fix (commit `ef526f8`) repaired the unrunnable `useradd -m` + `git clone` collision; CR-03 fix (commit `9b1ac17`) added explicit uv PATH everywhere. All 3 readme_structure canaries GREEN. |
| 5 | End-to-end deliberate failure: ops chat alert, business chat silent, HC failure recorded, runs row failed | HUMAN_NEEDED | `bin/test-failure-alert.sh` 5-step orchestrator source-locked (9/9 canaries GREEN); CR-04 fix (commit `9c2ec20`) removed impossible inner sudo. Actual Telegram chat inspection + HC dashboard inspection + sqlite verification — operator post-deploy per checklist in script step 4. |

**Score:** 5/5 must-haves verified in code (3 verified end-to-end in CI; 2 verified at source level + handed off to operator for runtime verification per design).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `bin/weekly-run.sh` | D-709 cron wrapper (HC pings + flock + log redirect + exit passthrough) | VERIFIED | 95 lines; mode 100755; all D-709 invariants present after CR-01/CR-03/WR-09 fixes. |
| `bin/test-failure-alert.sh` | D-706 5-step orchestrator | VERIFIED | 61 lines; mode 100755; reuses existing CLI surface only; CR-04 fix applied. |
| `deploy/etc-cron-d-ga_crawler` | CRON_TZ=Asia/Almaty + weekly-run row Sunday 23:00 + backup row daily 01:00 + MAILTO="" + PATH | VERIFIED | 25 lines; D-708 verbatim + CR-03 PATH addition. |
| `deploy/etc-logrotate-d-ga_crawler` | 7 directives on /var/log/ga_crawler/*.log | VERIFIED | 28 lines; D-705 verbatim. |
| `.env.example` | HC_PING_URL= placeholder added; Phase 6 TG_* preserved | VERIFIED | 13 lines, 452 bytes; all values blank (no secrets in git). |
| `README.md` | 10 H2 sections in D-707 order; RU primary | VERIFIED | 247 lines; canary `test_readme_h2_order_matches_d707` GREEN. |
| `tests/test_phase07_*.py` (7 files) | Shape canaries source-locking artifacts | VERIFIED | 57/57 canaries GREEN. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `bin/weekly-run.sh` | Healthchecks.io | curl ${HC_PING_URL}/start, bare URL on success, /fail --data-raw exit=$EXIT | WIRED | Three pings on lines 77/88/90; fail-soft (`|| true`); HC outage MUST NOT block exec. |
| `bin/weekly-run.sh` | `python -m ga_crawler weekly-run` | `uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1` | WIRED | Line 82; pass-through args; preserves exit code via set +e/EXIT=$?/set -e. |
| `bin/test-failure-alert.sh` | bin/weekly-run.sh + cli deliver-run | step 1 (forced sanity-N fail) + step 3 (.venv/bin/python -m ga_crawler deliver-run --run-id $RID) | WIRED | Reuses existing CLI surface only; no new Python paths. |
| `/etc/cron.d/ga_crawler` | `/opt/ga_crawler/bin/weekly-run.sh` | Sunday 23:00 Asia/Almaty user-column row | WIRED | Template at `deploy/etc-cron-d-ga_crawler`. |
| `/etc/logrotate.d/ga_crawler` | `/var/log/ga_crawler/*.log` | weekly + rotate 13 + compress + create 0644 ga_crawler ga_crawler | WIRED | Template at `deploy/etc-logrotate-d-ga_crawler`. |

### Data-Flow Trace (Level 4)

Phase 7 produces operator-facing artifacts (bash wrappers + config files + docs); no dynamic-data-rendering components. Data-flow trace not applicable — wiring verified at Level 3 above.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 7 canaries all GREEN | `uv run pytest tests/test_phase07_*.py -q` | `57 passed in 0.11s` | PASS |
| Full project suite GREEN | `uv run pytest -q` | `803 passed, 1 skipped, 181 warnings in 130.37s` | PASS |
| Structural invariants (zero new Python, no new namespace, etc.) | `uv run pytest tests/test_phase07_structural_canaries.py -v` | `8 passed in 0.05s` | PASS |
| Wrapper contract canaries (17 tests for D-709 invariants) | `uv run pytest tests/test_phase07_wrapper_contract.py -v` | `17 passed` (subset of 57 above) | PASS |
| Wrapper has explicit `exit 4` (CR-01 fix) | `grep "^  exit 4$" bin/weekly-run.sh` | line 60 hit | PASS |
| Wrapper has explicit PATH export (CR-03 fix) | `grep "export PATH" bin/weekly-run.sh` | line 47 hit | PASS |
| Wrapper has HC /fail ping on flock-refused (WR-09 fix) | `grep "reason=flock-refused" bin/weekly-run.sh` | line 70 hit | PASS |
| test-failure-alert has no inner sudo (CR-04 fix) | `grep -nE "^sudo|/sudo " bin/test-failure-alert.sh` | only in comments; no executable sudo | PASS |
| Cron template files have no dot (Pitfall #1) | filenames `etc-cron-d-ga_crawler`, `etc-logrotate-d-ga_crawler` | both extensionless | PASS |
| Real cron firing at expected Almaty time | n/a — operator post-deploy | n/a | SKIP (human) |
| Real Healthchecks.io alert end-to-end | n/a — operator post-deploy | n/a | SKIP (human) |
| Real Telegram chat delivery (business + ops) | n/a — operator post-deploy | n/a | SKIP (human) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SCHED-01 | 07-02, 07-04 | Системный cron на VPS запускает `python -m ga_crawler` раз в неделю в ночь воскресенья (Asia/Almaty) | SATISFIED | `deploy/etc-cron-d-ga_crawler` line 24 (Sunday 23:00 ga_crawler row); README §4 documents deploy procedure; runtime gate is operator-manual per SC#1. |
| SCHED-02 | 07-02 | Cron-запись использует `CRON_TZ=Asia/Almaty` | SATISFIED | `deploy/etc-cron-d-ga_crawler` line 21; canary `test_cron_contains_cron_tz_almaty` GREEN. |
| SCHED-03 | 07-03, 07-04 | Healthchecks.io dead-man's-switch получает start/success/fail-пинги | SATISFIED | `bin/weekly-run.sh` lines 77, 88, 90 implement triad; CR-01 fix added explicit `exit 4` for D-703 fail-loud; WR-09 fix added HC /fail ping on flock-refused; README §5 documents HC.io setup. |
| SCHED-04 | 07-03, 07-02 | Структурированные JSON-логи на диск с ротацией | SATISFIED | Wrapper redirects to datestamped LOG_FILE; `deploy/etc-logrotate-d-ga_crawler` 7 directives. README §9 grep/jq workflow with WR-02/WR-03 fixes. structlog `run_id` binding pre-existing (D-704: `_configure_logging` source unchanged). |
| SCHED-05 | 07-04, 07-03 | Документация по setup + deliberate-failure тест | SATISFIED | `README.md` 10 H2 sections per D-707; `bin/test-failure-alert.sh` 5-step D-706 orchestrator. CR-02/CR-03/WR-01/WR-02/WR-03 fixes ensure README setup procedure is actually runnable on a clean VPS. |

**Coverage:** 5/5 SCHED requirements SATISFIED. No orphaned requirements; no contradicting evidence.

### Anti-Patterns Scan

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | Source-grep on Phase 7 production artifacts shows no TODO/FIXME/PLACEHOLDER comments, no `return null`/`return []` stubs, no empty handlers, no `console.log`-only implementations. `test_no_simulate_failure_substring_in_production` confirms no testing-mode toggle in `src/ga_crawler`. `test_no_schedule_stats_namespace_in_source` confirms no orphan stats keys. |

Phase 7 specifically commits to "zero production Python" — structural canaries (`tests/test_phase07_structural_canaries.py`) enforce this:
- No new pyproject namespaces (PASS)
- No new dependencies (PASS)
- 5-way stats namespace disjoint preserved (PASS)
- No schedule.* stats key in source (PASS)
- load_dotenv only in cli.py (PASS)
- CLI surface unchanged — 5 subcommands (PASS)
- main_run.py orchestrator unchanged anchors (PASS)
- No simulate-failure / fail.mode substrings (PASS)

### Code Review Findings

The phase underwent a standard code review (07-REVIEW.md) on 2026-05-12 that surfaced 4 Critical + 9 Warning + 4 Info findings. All 4 Critical fixes + 4 of 9 Warning fixes were applied via `/gsd-code-review --fix` (commits ed07007..d591c06):

| Finding | Severity | Status | Commit |
|---------|----------|--------|--------|
| CR-01 wrapper exits 4 on missing HC_PING_URL | Critical | FIXED | ed07007 |
| CR-02 README §2 useradd -m + git clone collision | Critical | FIXED | ef526f8 |
| CR-03 uv PATH explicit in wrapper + cron + README | Critical | FIXED | 9b1ac17 |
| CR-04 drop inner sudo -u ga_crawler in test-failure-alert.sh | Critical | FIXED | 9c2ec20 |
| WR-01 README §3 disambiguate wrapper vs Python child exit codes | Warning | FIXED | 9e886d7 |
| WR-02 zgrep -h in README §9 | Warning | FIXED | 6f66b64 |
| WR-03 tail \| jq pre-filter for non-JSON lines | Warning | FIXED | 81fe1cb |
| WR-09 HC /fail ping on flock-refused (exit 5) | Warning | FIXED | c1e732b |
| WR-04 exit-code-2 description widened | Warning | ABSORBED into WR-01 | n/a |
| WR-05/06/07/08, IN-01..04 | Warning/Info | DEFERRED with documented rationale | n/a |

All 4 Critical issues were deployment-breaking (the documented from-scratch deploy would not have worked end-to-end before the fixes). Post-fix verification: 57/57 Phase 7 canaries + 803/803 full suite GREEN with zero regressions.

### Human Verification Required

Two Success Criteria are explicitly **operator-manual gates by design** per 07-CONTEXT.md (SC#1, SC#5). CI verifies the code/config shape; the operator verifies real-world behavior post-deploy. Plus two additional setup-time human checks documented in README:

1. **SC#1 — Cron timing verification (post-first-Sunday)**
   - **Test:** After first Sunday post-deploy, `sudo grep CRON /var/log/syslog` and confirm `weekly-run.sh` row executed in the Almaty 23:00 window.
   - **Expected:** Cron fires at Sunday 23:00 Asia/Almaty (=Sunday 18:00 UTC); report arrives in business chat Monday ~02:00-03:00 Almaty (after 3–4h run).
   - **Why human:** Real wall-clock cron timing on a real VPS — not testable in CI.

2. **SC#5 — Deliberate-failure end-to-end**
   - **Test:** `sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh` + 5-item operator visual checklist (script step 4).
   - **Expected:** (a) ops chat receives alert with reason `upstream pipeline failed` for run #N; (b) business chat receives NO new message; (c) HC dashboard shows /start + /fail pings; (d) `sqlite3 prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=N'` → `N | failed | sanity_gate_n_failed:120<999999`; (e) `runs.stats.deliver.delivery_status = delivered_ops_only`.
   - **Why human:** Telegram chat inspection + HC dashboard inspection + live sqlite DB inspection — not verifiable in CI.

3. **Smoke gate (post-install, pre-production)**
   - **Test:** `sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh --viled-only --sanity-gate-n 1` (README §2 step 8).
   - **Expected:** Mini-run completes; HC dashboard shows /start + /success; business chat receives mini-report; exit 0.
   - **Why human:** Setup-green check on real VPS depending on uv install + playwright install firefox + Camoufox cache priming.

4. **HC.io Telegram integration**
   - **Test:** Invite `@my_hc_bot` in ops chat → `/start@my_hc_bot` → trigger a deliberate failure → expect Telegram alert from `@my_hc_bot`.
   - **Expected:** Telegram message from HC.io bot appears in ops chat within 2h grace window.
   - **Why human:** External HC.io Telegram integration + Telegram bot acceptance — not testable in CI. Documented as README §5 step 5.

### Gaps Summary

**No gaps blocking goal achievement.** All five SCHED requirements (SCHED-01..05) closed at source level with file-and-line evidence. All artifacts present and substantive. All key links wired. The 4 Critical code-review findings (which would have prevented end-to-end deployment) were auto-fixed before this verification.

Two Success Criteria (SC#1 cron-timing + SC#5 end-to-end deliberate-failure) require operator post-deploy verification by design — this is the intended phase contract per 07-CONTEXT.md and 07-VALIDATION.md «Manual-Only Verifications». They are surfaced in the `human_verification` section above for operator action.

The phase ships **zero production Python** (structurally enforced by 8 cross-phase canaries) and **zero new dependencies**. Phase 6 functionality preserved (Telegram delivery + ops/business split unchanged); full project test suite GREEN with zero regressions (803 passed, 1 skipped — the 1 skipped is a pre-existing Phase 3 artificial-mutation test, not Phase 7-related).

**Phase 7 closes v1 milestone effectively:** 47/48 v1 requirements satisfied (only Phase 1 RECON-01 conditional plans remain — operator-deferred per Phase 1 spike MEMO Camoufox-direct lock).

---

*Verified: 2026-05-13*
*Verifier: Claude (gsd-verifier)*
*Outcome: status `human_needed` — code/config verified in CI; SC#1 and SC#5 await operator post-deploy verification per phase design.*
