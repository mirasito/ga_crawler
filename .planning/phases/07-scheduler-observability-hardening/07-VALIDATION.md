---
phase: 7
slug: scheduler-observability-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` §"Validation Architecture" (lines 523–569).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (inherited Phase 2..6) — used for shape-canary tests on ops artifact files |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_phase07_*.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~5 sec quick (pure shape canaries, no network) · ~30 sec full suite |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_phase07_*.py -x` (≤ 5 sec; pure shape canaries on template files; no network, no subprocess)
- **After every plan wave:** Run `uv run pytest -x` (full suite; ~30 sec; ensures Phase 2..6 frozen modules stay green; verifies `git diff src/ga_crawler/` is empty between Phase 6 head and Phase 7 close-out — Phase 7 ships zero production Python)
- **Before `/gsd-verify-work`:** Full suite must be green + manual operator runbook checklist (SC#1 + SC#5 from README §2 + §7) executed on the VPS
- **Max feedback latency:** 5 seconds for per-task quick run; 30 seconds for per-wave full suite

---

## Per-Task Verification Map

> Generated from `07-RESEARCH.md` §Validation Architecture → "Phase Requirements → Test Map" + "Wave 0 Gaps".
> Concrete task IDs (`07-XX-NN`) will be filled by the planner during plan generation; this table lists requirements → test-file mapping that plans MUST honor.

| Req ID | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| SCHED-01 | Cron entry deploys to `/etc/cron.d/ga_crawler` and template matches verbatim (root-owned 0644; user column) | V4 Access Control | non-root cron user `ga_crawler` per user-column | unit (shape-canary on `deploy/etc-cron-d-ga_crawler`) | `uv run pytest tests/test_phase07_cron_template_shape.py -x` | ❌ Wave 0 | ⬜ pending |
| SCHED-02 | Cron template contains `CRON_TZ=Asia/Almaty` line + Sunday-23:00 weekly-run row + Daily-01:00 backup row + `MAILTO=""` | V14 Configuration | `MAILTO=""` disables cron-email leak | unit (string-grep canary) | same as SCHED-01 | ❌ Wave 0 | ⬜ pending |
| SCHED-03 | `bin/weekly-run.sh` source contains `${HC_PING_URL}/start`, `${HC_PING_URL}`, `${HC_PING_URL}/fail`, `${HC_PING_URL:?...}` substrings | V2 Authentication (HC_PING_URL bearer) | fail-loud if `HC_PING_URL` missing (exit 4) | unit (source-lock canary) | `uv run pytest tests/test_phase07_wrapper_contract.py -x` | ❌ Wave 0 | ⬜ pending |
| SCHED-03 | `bin/weekly-run.sh` source contains `flock -n 9`, HC pings `\|\| true`, `exit 5` reserved on flock-refused, `set -euo pipefail` | V11 Business Logic | single-writer flock guards `runs` table | unit (source-lock canary on D-709 invariants) | same as above | ❌ Wave 0 | ⬜ pending |
| SCHED-04 | `deploy/etc-logrotate-d-ga_crawler` contains directives: `weekly`, `rotate 13`, `compress`, `delaycompress`, `missingok`, `notifempty`, `create 0644 ga_crawler ga_crawler` | V12 Files & Resources | no world-writable logs | unit (shape-canary) | `uv run pytest tests/test_phase07_logrotate_template_shape.py -x` | ❌ Wave 0 | ⬜ pending |
| SCHED-04 | `bin/weekly-run.sh` redirects stdout+stderr to `/var/log/ga_crawler/weekly-run-$(date +%F).log` | V7 Error Handling | structlog JSON to disk for forensics | unit (source-lock canary on `>> "$LOG_FILE" 2>&1` pattern) | same as wrapper_contract | ❌ Wave 0 | ⬜ pending |
| SCHED-05 | `README.md` contains 10 required sections in order per D-707 | — | — | unit (markdown-heading-shape canary; ordered headings 1..10) | `uv run pytest tests/test_phase07_readme_structure.py -x` | ❌ Wave 0 | ⬜ pending |
| SCHED-05 | `bin/test-failure-alert.sh` source contains `--viled-only`, `--sanity-gate-n 999999`, `deliver-run --run-id`, verification checklist (D-706 step 4) | V7 Error Handling | deliberate-failure verification path | unit (source-lock canary on D-706 invariants) | `uv run pytest tests/test_phase07_test_failure_alert_shape.py -x` | ❌ Wave 0 | ⬜ pending |
| SCHED-05 | `.env.example` contains `HC_PING_URL=` placeholder line; values are bare (no `#`, no quotes) — Pitfall #4 canary | V8 Data Protection | `.env` template hygiene | unit (line-presence + value-format canary) | `uv run pytest tests/test_phase07_env_example_shape.py -x` | ❌ Wave 0 | ⬜ pending |
| Structural canaries (cross-phase invariant) | `git diff src/ga_crawler/cli.py` empty; `git diff src/ga_crawler/runners/main_run.py` empty; no new `runs.stats.*` keys; no `simulate-failure` / `fail.mode` substrings in production source | V14 Configuration | Phase 7 ships zero production Python | unit (file-hash + grep-based source-lock canaries) | `uv run pytest tests/test_phase07_structural_canaries.py -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase07_cron_template_shape.py` — covers SCHED-01 + SCHED-02 (shape-canary on `deploy/etc-cron-d-ga_crawler`)
- [ ] `tests/test_phase07_logrotate_template_shape.py` — covers SCHED-04 directive grep on `deploy/etc-logrotate-d-ga_crawler`
- [ ] `tests/test_phase07_wrapper_contract.py` — covers SCHED-03 + SCHED-04 source-locks on `bin/weekly-run.sh` (HC pings + flock + log redirect + exit codes 4/5)
- [ ] `tests/test_phase07_test_failure_alert_shape.py` — covers SCHED-05 source-lock on `bin/test-failure-alert.sh` (D-706 steps 1–4)
- [ ] `tests/test_phase07_readme_structure.py` — covers SCHED-05 README 10-section ordered-heading shape (D-707)
- [ ] `tests/test_phase07_env_example_shape.py` — covers `HC_PING_URL=` placeholder + Pitfall #4 «no `#` or quotes in values» bash/python-dotenv parser-agreement canary
- [ ] `tests/test_phase07_structural_canaries.py` — Phase 7 "zero production Python" invariant + namespace-disjoint preservation (5-way `runs.stats.*` Phase 6 D-607 inherited)
- [ ] Framework install: **none** — Phase 7 adds zero deps; reuses pytest 8.x + uv from Phase 2..6

*No `pyproject.toml` changes per D-710 + CONTEXT.md Action Items (line 308).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cron tick lands at Almaty Sunday 23:00 (no UTC drift) | SC#1 (ROADMAP) | Requires runtime observation of a real cron tick — CI cannot wait a week | Post-deploy: monitor `/var/log/ga_crawler/weekly-run-$(date +%F).log` first Monday after deploy; mini-smoke before that — `sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh --viled-only --sanity-gate-n 1` produces a fresh logfile + 1 sanity-passing run in <2 min |
| End-to-end deliberate-failure: ops chat alerts, business chat silent, HC records /fail, `runs.status='failed'` | SC#5 (ROADMAP) | Requires real Telegram + HC.io network round-trips — not CI-suitable | `sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh` then verify (a) ops chat got alert with reason `upstream pipeline failed`, (b) business chat silent, (c) HC dashboard shows /start + /fail pings, (d) `sqlite3 prices.db 'SELECT run_id, status, reason FROM runs ORDER BY run_id DESC LIMIT 1'` → `failed \| sanity_gate_n_failed:120<999999`, (e) `runs.stats.deliver.delivery_status` = `delivered_ops_only` |
| logrotate weekly rotation produces `.log.gz` archives and keeps last 13 | SC#3 / SCHED-04 | Cannot wait 13 weeks in CI | Post-deploy: `sudo logrotate -d /etc/logrotate.d/ga_crawler` (dry-run; expect: «rotating pattern .../weekly-run-*.log forced from command line» if `-f` added); `sudo logrotate -f /etc/logrotate.d/ga_crawler` then `ls -la /var/log/ga_crawler/` shows `.log.gz` of prior week |
| HC.io Telegram integration routes alerts to ops chat | SC#2 / SCHED-03 | Requires HC.io web UI + Telegram bot setup | Operator clicks Healthchecks.io dashboard → Integrations → adds Telegram + binds to ops chat; verifies by clicking "Send test notification" in HC UI |
| First-deploy smoke: `bin/weekly-run.sh --viled-only --sanity-gate-n 1` completes green | SC#4 (README §2 closing step) | Runtime verification of VPS setup correctness | After README §2 setup commands, operator runs the smoke and expects exit 0 + HC `/start` + `/success` pings on dashboard + new row in `/var/log/ga_crawler/` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (7 test files listed above)
- [ ] No watch-mode flags (pytest invoked with `-x`, single-shot)
- [ ] Feedback latency < 5 s (quick) / 30 s (full)
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 stubs land green)

**Approval:** pending — planner consumes this file and writes the matching Wave 0 test stubs in plan 07-01.
