---
phase: 07-scheduler-observability-hardening
plan: 02
subsystem: scheduler-ops
tags: [deploy, cron, logrotate, env-template, wave-2, sched-01, sched-02, sched-03, sched-04]
requires: [07-01]
provides:
  - "deploy/etc-cron-d-ga_crawler — cron config-as-code template (D-708)"
  - "deploy/etc-logrotate-d-ga_crawler — logrotate config-as-code template (D-705)"
  - ".env.example HC_PING_URL= placeholder (D-703 fail-loud input)"
affects: []
tech_added: []
patterns:
  - "config-as-code in deploy/ — first `deploy/*` directory in repo; deployed via `cp` to /etc/cron.d/ and /etc/logrotate.d/ per README §2/§4"
  - "comment-header source citation (CONTEXT.md D-NNN + RESEARCH.md Pitfall #N) — single-grep reverse-lookup from artifact to design rationale"
key_files:
  created:
    - "deploy/etc-cron-d-ga_crawler (24 lines, 1065 bytes)"
    - "deploy/etc-logrotate-d-ga_crawler (28 lines, 1067 bytes)"
  modified:
    - ".env.example (+6 lines: blank + 3 comment + blank + HC_PING_URL=; 14 lines total, 452 bytes)"
decisions: [D-705, D-708, D-703]
requirements: [SCHED-01, SCHED-02, SCHED-04]
threat_refs: [T-07-01, T-07-04, T-07-05]
metrics:
  duration: "~5 min"
  completed: "2026-05-12T17:57:17Z"
  tasks: 3
  files_touched: 3
  commits: 3
---

# Phase 7 Plan 02: Deploy Templates + .env.example Backfill Summary

**One-liner:** Three static deployment artifacts (cron + logrotate config-as-code templates, `.env.example` HC_PING_URL placeholder) shipped verbatim from CONTEXT.md D-705/D-708/Action-Items locked decisions — closes 3 of 7 Wave 0 canaries (SCHED-01/02/04 at template-shape level).

## Tasks Completed

| # | Task | Files | Commit | Status |
|---|------|-------|--------|--------|
| 1 | Cron template — `deploy/etc-cron-d-ga_crawler` (D-708 verbatim) | `deploy/etc-cron-d-ga_crawler` | `683262d` | done |
| 2 | Logrotate template — `deploy/etc-logrotate-d-ga_crawler` (D-705 verbatim) | `deploy/etc-logrotate-d-ga_crawler` | `ae00dec` | done |
| 3 | `.env.example` — append HC_PING_URL= placeholder block | `.env.example` | `bb13f9d` | done |

## What Shipped

### deploy/etc-cron-d-ga_crawler (NEW — 24 lines, 1065 bytes)
Cron config-as-code template per **D-708** verbatim. Operator deploys via `sudo cp deploy/etc-cron-d-ga_crawler /etc/cron.d/ga_crawler` (README §4). Contains:
- `CRON_TZ=Asia/Almaty` (SCHED-02 no-drift invariant — without this, system cron defaults to UTC → Sunday 23:00 Almaty mis-fires as Sunday 18:00 UTC).
- `MAILTO=""` (Pitfall #2 — explicitly disables cron mailbox leak; T-07-01 Information Disclosure mitigation).
- `0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh` (SCHED-01 weekly Sunday 23:00 Almaty crawl).
- `0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh` (DATA-06 cascade — daily 01:00 backup; two spaces between `1` and `* * *` per D-708 verbatim).

Filename `etc-cron-d-ga_crawler` (no dot, no extension) per Pitfall #1 — Vixie cron silently ignores `/etc/cron.d/*` with non-[A-Za-z0-9_-] characters.

### deploy/etc-logrotate-d-ga_crawler (NEW — 28 lines, 1067 bytes)
Logrotate config-as-code template per **D-705** verbatim. 7 directives on `/var/log/ga_crawler/*.log`:
- `weekly` — rotation cadence
- `rotate 13` — keep 13 archives (~3 months history; ~65MB total on Hetzner CX22)
- `compress` + `delaycompress` — gzip rotated files; keep last rotation uncompressed for diagnosis
- `missingok` + `notifempty` — first-run safety + skip 0-byte logs
- `create 0644 ga_crawler ga_crawler` — post-rotation file owner+mode (T-07-05 mitigation — no world-writable rotated logs)

Pitfall #5 enforcement (system user must exist **before** first logrotate run) deferred to README §2 setup order (`useradd -r -m -d /opt/ga_crawler ga_crawler` BEFORE this `cp`).

### .env.example (MODIFIED — +6 lines → 14 total, 452 bytes)
Appended Phase 7 SCHED-03 placeholder block after existing Phase 6 TG_* block:
```
# Healthchecks.io dead-man's-switch (Phase 7 — SCHED-03)
# Create check at healthchecks.io → copy ping URL (full URL incl. scheme)
# Required: bash wrapper bin/weekly-run.sh refuses to run if missing (exit 4 per D-703).

HC_PING_URL=
```
Conventions preserved (Pitfall #4 — bash `source .env` vs python-dotenv parser parity):
- Empty value after `=` (no placeholder text, no quotes).
- No `#` inside value, no embedded newlines.
- One blank line between Phase 6 and Phase 7 logical groups (visual grouping).
- 3 TG_* placeholders preserved (T-07-04 mitigation — no real secrets in git; HC.io UUID lives in operator-managed gitignored `.env`).

## Wave 0 Canary Flip (3 of 7 RED → GREEN)

| Canary file | Tests before | Tests after | Status |
|-------------|--------------|-------------|--------|
| `tests/test_phase07_cron_template_shape.py` | 1 passed / 4 errors (FileNotFound) | **5 passed** | RED → GREEN |
| `tests/test_phase07_logrotate_template_shape.py` | 0 passed / 8 errors (FileNotFound) | **8 passed** | RED → GREEN |
| `tests/test_phase07_env_example_shape.py` | 5 passed / 1 failed (HC_PING_URL missing) | **6 passed** | RED → GREEN |

**Total Phase 7 canary tests flipped:** 19 (5 + 8 + 6).
**Phase 6 regression suite:** `tests/unit/test_phase06_wave0_pyproject_envexample.py` — **5 passed** (3 TG_* placeholders retained, secret-blank invariant preserved for new HC_PING_URL key).
**Remaining 4 Wave 0 canaries still RED** (addressed by Plans 07-03 wrapper / 07-04 test-failure-alert + readme + structural-canaries).

## Decisions Implemented (verbatim from CONTEXT.md)

- **D-705 (logrotate weekly keep 13 + 7 directives)** — exact directive list reproduced; retention 3 months balances diagnostic capacity vs SSD space.
- **D-708 (cron `/etc/cron.d/ga_crawler` root-owned with user column)** — repo template at `deploy/etc-cron-d-ga_crawler` per "config-as-code in deploy/" convention; both schedule rows (weekly + backup) in same file so `CRON_TZ` applies to both.
- **D-703 (fail-loud HC_PING_URL)** — `.env.example` placeholder line + comment block marks variable as required (exit code 4 reserved); README §3 will document at Plan 07-04.

## Threat Surface — Mitigations Applied

| Threat ID | Component | Mitigation |
|-----------|-----------|------------|
| T-07-01 | cron MAILTO leak (stdout → root@localhost) | `MAILTO=""` line in `deploy/etc-cron-d-ga_crawler` (canary `test_cron_contains_mailto_empty` asserts substring). |
| T-07-04 | HC.io UUID committed to git | `.env.example` ships `HC_PING_URL=` blank only; canary `test_env_example_all_known_placeholders_blank` enforces. |
| T-07-05 | World-writable rotated logs (V12 Files) | `create 0644 ga_crawler ga_crawler` directive in logrotate template (canary asserts substring presence). |

No new threat surface introduced (no network endpoints, no auth paths, no schema changes; static config-as-code only).

## Deviations from Plan

None — plan executed exactly as written. All three artifacts contain verbatim content from CONTEXT.md D-705/D-708 blocks and PATTERNS.md `.env.example` insertion form. No auto-fix rules triggered (no bugs found, no missing critical functionality, no blocking issues).

**Notable details:**
- `bin/backup.sh` cron row spacing — preserved D-708 verbatim two-space form (`0 1  * * *`), matching the canary substring check at `tests/test_phase07_cron_template_shape.py:56`.
- `.env.example` final newline — Edit tool preserved file structure; `grep -c '^HC_PING_URL=$' .env.example` returns exactly `1` per done-criteria. `wc -l` reports 13 (POSIX semantics count complete newlines; 14 logical lines including final placeholder).
- CRLF warning on Windows commit — informational only, not blocking; cron/logrotate config files survive line-ending translation in the target Ubuntu deployment via standard `git checkout` newline normalization.

## Verification

```
$ uv run pytest tests/test_phase07_cron_template_shape.py \
                tests/test_phase07_logrotate_template_shape.py \
                tests/test_phase07_env_example_shape.py \
                tests/unit/test_phase06_wave0_pyproject_envexample.py -q
........................                                                 [100%]
24 passed in 0.06s
```

Done-criteria grep counts (all match expected):
- `grep -c '^CRON_TZ=Asia/Almaty$' deploy/etc-cron-d-ga_crawler` → 1
- `grep -c '^MAILTO=""$' deploy/etc-cron-d-ga_crawler` → 1
- `grep -c '^HC_PING_URL=$' .env.example` → 1

## Commits

- `683262d` — feat(07-02): deploy/etc-cron-d-ga_crawler — D-708 cron template
- `ae00dec` — feat(07-02): deploy/etc-logrotate-d-ga_crawler — D-705 logrotate template
- `bb13f9d` — feat(07-02): .env.example — HC_PING_URL= placeholder (SCHED-03)

## Self-Check: PASSED

All claimed artifacts and commits verified to exist:
- `deploy/etc-cron-d-ga_crawler` — FOUND (1065 bytes, 24 lines)
- `deploy/etc-logrotate-d-ga_crawler` — FOUND (1067 bytes, 28 lines)
- `.env.example` — FOUND (452 bytes, 14 lines incl. HC_PING_URL placeholder)
- Commits `683262d`, `ae00dec`, `bb13f9d` — all present in `git log --oneline`.
- All 19 Phase 7 canary tests + 5 Phase 6 regression tests = 24 passed.
