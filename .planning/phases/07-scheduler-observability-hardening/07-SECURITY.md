---
phase: 7
slug: scheduler-observability-hardening
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-13
---

# Phase 7 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Phase 7 ("Scheduler & Observability Hardening") shipped 6 production artifacts:
2 deploy templates (cron + logrotate), 3 bash scripts (`weekly-run.sh`,
`test-failure-alert.sh`, plus existing `backup.sh` unchanged), 1 `.env.example`
addition (`HC_PING_URL=` placeholder), 1 `README.md` (10-section RU operator
runbook). Zero new Python. Seven source-lock test files (`tests/test_phase07_*.py`)
canary-enforce the security invariants below at file-content level.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Repo → operator → VPS filesystem (`/etc/cron.d/`, `/etc/logrotate.d/`) | `deploy/*` templates copied via `sudo cp` (README §2). Templates are static config-as-code; do not execute. | Cron schedule directives, file-ownership/mode hints |
| `.env.example` → operator → `.env` on VPS (0600 ga_crawler:ga_crawler) | Template ships blank placeholders only; operator fills `.env` (gitignored). | Secrets: `TG_BOT_TOKEN`, `TG_*_CHAT_ID`, `HC_PING_URL` |
| cron daemon (root) → `bin/weekly-run.sh` (as `ga_crawler` user) | Cron invokes wrapper with minimal env; wrapper loads `.env` via `set -a; source; set +a`. | All four required ENV |
| `bin/weekly-run.sh` → Healthchecks.io (HTTPS `hc-ping.com`) | curl over TLS; UUID in `${HC_PING_URL}` is bearer-token-equivalent secret. | Ping URL with UUID; on `/fail` body: `exit=$EXIT` integer |
| `bin/weekly-run.sh` → `uv run python -m ga_crawler weekly-run` | stdout+stderr redirected to `/var/log/ga_crawler/weekly-run-YYYY-MM-DD.log`; exit code preserved through set -e dance. | Structured JSON log events |
| `bin/test-failure-alert.sh` → `bin/weekly-run.sh` + `python -m ga_crawler deliver-run` | Manual operator-invoked; reuses production CLI surface only. | Forced sanity-gate trip; run_id extraction |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-07-01 | STRIDE: I (Information Disclosure) | cron MAILTO leak — stdout/stderr → `root@localhost` mailbox | mitigate | (a) `deploy/etc-cron-d-ga_crawler:22` ships `MAILTO=""`; (b) `bin/weekly-run.sh:82` redirects `>> "$LOG_FILE" 2>&1`; (c) `README.md:102` documents the invariant verbatim. | closed |
| T-07-02 | STRIDE: T (Tampering) | flock race / double-run → SQLite DB corruption | mitigate | `bin/weekly-run.sh:67-72`: `exec 9>/var/lock/ga_crawler-weekly.lock` + `flock -n 9` (non-blocking) + reserved `exit 5` on refusal. HC `/fail` ping sent before exit so operator distinguishes lock-contention from generic exit-1. | closed |
| T-07-03 | STRIDE: T (Tampering) | Cron command injection via crafted ENV in `.env` | mitigate | `README.md:51` (§2 step 7) operator step `sudo -u ga_crawler chmod 0600 .env`; `README.md:44` ships cron template as root-owned 0644 (no unprivileged write path). No `.env` write capability for non-`ga_crawler` users. | closed |
| T-07-04 | STRIDE: I (Information Disclosure) | Healthchecks.io UUID committed to source / leaked in logs | mitigate | (a) `.env.example:13` ships `HC_PING_URL=` (blank); (b) `bin/weekly-run.sh` references `${HC_PING_URL}` only (regex grep for UUID + literal `hc-ping.com` returns zero matches); (c) `README.md:69` marks `HC_PING_URL` Required YES; `README.md:115` §5 step 6 instructs operator to keep URL in `.env`. | closed |
| T-07-05 | DoS (data) / ASVS V12 Files & Resources | logrotate `create` mode mismatch / world-writable rotated logs | mitigate | `deploy/etc-logrotate-d-ga_crawler:27` contains `create 0644 ga_crawler ga_crawler`. `README.md:236` §9 documents the logrotate-during-write edge case (Open Q #3) as an operationally accepted condition for extended-runtime weeks. | closed |
| T-07-07 | DoS | flock lock-file world-writable (`/var/lock/ga_crawler-weekly.lock`) | accept | Advisory lock (not authorization). `/var/lock/` is root-managed tmpfs (symlink to `/run/lock` on Ubuntu 24.04, auto-clean at reboot). `exec 9>` at `bin/weekly-run.sh:67` creates the lock file owned by `ga_crawler` user (run-time). Accepted per 07-CONTEXT.md threat 8; see Accepted Risks Log below. | closed |
| T-07-08 | Code Injection | `source .env` evaluates malicious shell content | accept | Threat model assumes operator+VPS-root not compromised. In-scope defensive controls present: (a) `.env.example` lines 5-13 ship only blank placeholders — no `#`, no quotes, no newlines (typo-canary `test_env_example_values_have_no_hash_no_quotes_no_newlines`); (b) `README.md:51` enforces `chmod 0600 .env`; (c) `README.md:87` Pitfall #4 documents ENV value rules. Accepted per 07-CONTEXT.md threat 8; see Accepted Risks Log below. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Numbering note: `T-07-06` is intentionally skipped (gap in numbering only — no
threat was registered against that ID across plans 07-01..07-05).

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-07-01 | T-07-07 | flock at `/var/lock/ga_crawler-weekly.lock` is an **advisory** lock, not an authorization control. The lock file is created by `exec 9>` in `bin/weekly-run.sh` as `ga_crawler` user; `/var/lock/` is root-managed tmpfs with reboot-time auto-cleanup. World-writability of the lock file would, at worst, let an attacker who already has shell access on the box take or release the advisory lock — they already have stronger primitives at that point. ASVS L1 does not require authorization on advisory locks. | gsd-secure-phase (auto), 2026-05-13 | 2026-05-13 |
| AR-07-02 | T-07-08 | `set -a; source .env; set +a` in `bin/weekly-run.sh:51-53` executes `.env` as bash — values containing shell metacharacters would be evaluated. The Phase 7 threat model assumes the operator + VPS root are not compromised. In-scope mitigations: `.env` is `chmod 0600 ga_crawler:ga_crawler` (README §2 step 7); `.env.example` documents Pitfall #4 (no `#`, no quotes, no newlines); operator typo canary in `tests/test_phase07_env_example_shape.py`. A compromised operator account or root user can already execute arbitrary code as `ga_crawler`; this threat is outside the Phase 7 trust boundary. | gsd-secure-phase (auto), 2026-05-13 | 2026-05-13 |

*Accepted risks do not resurface in future audit runs.*

---

## Verification Evidence (file:line grep matches)

| Threat | Grep target | Found |
|--------|-------------|-------|
| T-07-01 (a) | `MAILTO=""` in `deploy/etc-cron-d-ga_crawler` | line 22 |
| T-07-01 (b) | `>> "$LOG_FILE" 2>&1` in `bin/weekly-run.sh` | line 82 |
| T-07-01 (c) | `MAILTO=""` documented in `README.md` | line 95, line 102 |
| T-07-02 | `flock -n 9` + `exit 5` in `bin/weekly-run.sh` | lines 67-72 |
| T-07-03 | `chmod 0600 .env` in `README.md` | line 51 |
| T-07-03 | `chmod 0644 /etc/cron.d/ga_crawler` (root-owned cron) | line 44 |
| T-07-04 (a) | `HC_PING_URL=` (blank) in `.env.example` | line 13 |
| T-07-04 (b) | UUID regex `[0-9a-f]{8}-[0-9a-f]{4}-...` in `bin/weekly-run.sh` | **0 matches (good)** |
| T-07-04 (b) | literal `hc-ping.com` in `bin/weekly-run.sh` | **0 matches (good)** |
| T-07-04 (c) | `HC_PING_URL` Required YES in `README.md` ENV table | line 69 |
| T-07-04 (c) | `HC_PING_URL=https://hc-ping.com/<uuid>` operator instruction in §5 | line 115 |
| T-07-05 | `create 0644 ga_crawler ga_crawler` in `deploy/etc-logrotate-d-ga_crawler` | line 27 |
| T-07-05 | logrotate-during-write edge case in `README.md` §9 | line 236 |
| T-07-07 | `exec 9>/var/lock/ga_crawler-weekly.lock` in `bin/weekly-run.sh` | line 67 |
| T-07-08 | `chmod 0600 .env` in `README.md` §2 step 7 | line 51 |
| T-07-08 | Pitfall #4 "no `#`, no quotes" in `README.md` §3 | line 87 |
| T-07-08 | blank placeholders only in `.env.example` | lines 5-7, 13 |

---

## Unregistered Flags

None. All 5 sub-plan SUMMARIES (`07-01..07-05`) explicitly mapped their
implementation back to declared `T-07-NN` IDs. No `## Threat Flags` section
appeared in any SUMMARY indicating undeclared attack surface. 07-05-SUMMARY.md
§Threat Model Surface confirms: "No new threats introduced by this plan."

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-13 | 7 | 7 | 0 | gsd-security-auditor (gsd-secure-phase) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-07-01, AR-07-02)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-13
