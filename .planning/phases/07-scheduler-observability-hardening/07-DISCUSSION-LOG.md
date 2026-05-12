# Phase 7: Scheduler + Observability Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `07-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 7-scheduler-observability-hardening
**Areas discussed:** Healthchecks integration, Log rotation strategy, Deliberate-failure test + README, VPS layout + wrapper script

User instruction mid-discussion (after D-705): "work without stopping for clarifying questions; make the reasonable call and continue."

---

## Area 1 — Healthchecks integration

### Sub-question 1: Where do /start, /success, /fail pings live?

| Option | Description | Selected |
|--------|-------------|----------|
| Bash wrapper | `bin/weekly-run.sh` pings /start before exec, /success on exit=0, /fail on any non-zero (covers hard crash/OOM/segfault). Doesn't see D-606 enum directly — uses CLI exit code. | ✓ |
| Python in-process | `main_run/run_weekly` calls `httpx.get(...)` per D-606 enum mapping. Exact enum→ping mapping but hard-crash blind spot. | |
| Hybrid bash + Python | bash for /start + /fail (catch hard crashes), Python for /success only on `delivered_business`/`delivered_ops_only`. Both worlds but double surface. | |

**User's choice:** Bash wrapper (recommended).
**Notes:** Hard-crash coverage decisive — Camoufox + 4GB RAM Hetzner CX22 OOM-killer is a realistic failure mode. CLI exit codes from Phase 6 already semantically map enum→exit (0=delivered, 2=undelivered, 3=skipped_no_credentials), so wrapper-level routing on exit code is functionally equivalent to Python-level routing on enum, but covers the cases Python can't (process killed, segfault).

### Sub-question 2: Healthchecks provider

| Option | Description | Selected |
|--------|-------------|----------|
| Healthchecks.io SaaS free | https://healthchecks.io free tier (up to 20 checks, email + Telegram + webhook integrations). Zero operational load. | ✓ |
| Self-hosted Healthchecks | Docker compose on same VPS. Full control, but dead-man's-switch on the same host = SPOF; requires 2nd VPS. | |
| Simple webhook → Telegram ops bot | Skip HC entirely. bash sends curl message to ops Telegram on fail. NO dead-man's-switch — SCHED-03 violation. | |

**User's choice:** Healthchecks.io SaaS free.
**Notes:** SaaS-only for v1; self-hosted considered for v2 if scaling to 10+ scheduled jobs.

### Sub-question 3: Grace period + missing-ENV behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Grace 2h, fail-on-missing-ENV | Grace 2h matches typical weekly run + retry budget; missing `HC_PING_URL` → wrapper FAIL loud (no HC, no run). Safest. | ✓ |
| Grace 6h, warn-on-missing-ENV | More buffer; missing ENV → warn+continue. Compromise: monitoring degrades but business value continues. | |
| Grace 4h, fail-on-missing-ENV | Middle ground 1.5x typical run + retry. | |

**User's choice:** Grace 2h, fail-loud on missing ENV.
**Notes:** Matches CLAUDE.md principle "without monitoring we don't run"; mirrors Phase 6 D-611 asymmetric handling for TG_BOT_TOKEN (token required = fail loud).

---

## Area 2 — Log rotation strategy

### Sub-question 1: Rotation mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Bash wrapper + logrotate(8) | Wrapper writes stdout+stderr to `/var/log/ga_crawler/weekly-run-YYYY-MM-DD.log`; `/etc/logrotate.d/ga_crawler` rotates weekly. Linux-idiomatic. | ✓ |
| Python RotatingFileHandler | structlog binds to stdlib logging + RotatingFileHandler. Cross-platform, no logrotate dep. But loses Camoufox subprocess stdout/stderr. | |
| Tee → stdout + journald | systemd-journald captures cron stdout; `journalctl -u cron` reads. Rotation native. SCHED-04 "tail/grep session" becomes journalctl semantics — works but less ergonomic. | |

**User's choice:** Bash wrapper + logrotate(8).
**Notes:** Camoufox subprocess output capture is the deciding factor — Python in-process handler can't see Firefox/playwright child process logs. SCHED-04 calls out "tail/grep session" explicitly = file-based, not journald.

### Sub-question 2: Retention + structlog config

| Option | Description | Selected |
|--------|-------------|----------|
| Weekly rotation, keep 13 weeks, gzip | 3 months of history; `_configure_logging()` unchanged (JSONRenderer→stdout); wrapper redirects. | ✓ |
| Weekly rotation, keep 26 weeks, gzip | Half-year history. Files small (~3-5MB/run gzipped × 26 = ~80MB total — negligible). | |
| Daily rotation, keep 90 days, gzip | Daily rotation but weekly run → 90% files empty. Excessive for weekly schedule. | |

**User's choice:** Weekly rotation, keep 13 weeks, gzip.
**Notes:** 3 months gives 12 weekly runs of history — enough to investigate "did this start failing last quarter?" without bloat.

---

## Area 3 — Deliberate-failure test + README

### Sub-question 1: How does operator verify SC#5?

| Option | Description | Selected |
|--------|-------------|----------|
| `bin/test-failure-alert.sh` script | Shell orchestrator: weekly-run with forced sanity-N fail → captures run_id → deliver-run → ops alert sent. Verification checklist echoed. Idempotent. | ✓ |
| Sanity-gate-p=999999 override | Manually invoke `weekly-run --sanity-gate-p 999999` — runs full 4h crawl just to fail at matcher gate. | |
| Synthetic-run + deliver-run | Inject fake `runs` row via sqlite3 → deliver-run. ~30 seconds but misses cron+wrapper path. | |

**User's choice:** `bin/test-failure-alert.sh` script.
**Notes:** Reuses existing CLI surface (`--viled-only --sanity-gate-n 999999` + `deliver-run --run-id N`) — NO new production code path; covers cron→wrapper→Python→DB→Telegram→Healthchecks end-to-end in 2-3 min.

### Sub-question 2: README scope + structure
**[Decided autonomously per user "work without stopping" instruction.]**

| Option | Description | Selected |
|--------|-------------|----------|
| Single README.md, RU primary, 10 sections | What this is / VPS setup / ENV / Cron / HC.io setup / Telegram bot setup / Deliberate-failure test / Ops runbook / Logs / Dev setup. Code blocks EN, prose RU. | ✓ |
| Split OPERATOR.md + DEVELOPER.md | Two files for two audiences. | |
| Phase-7-only README (cron+HC+ENV only) | Minimal — no architecture / dev. | |
| Bilingual RU+EN | Same content, two languages. | |

**Claude's pick:** Single README.md, RU primary, 10 sections.
**Notes:** Operator team is RU-speaking (PROJECT.md anchor); operator IS developer initially (small team); single file = no "where to look?" friction; code blocks/CLI flags stay EN for grep-ability.

---

## Area 4 — VPS layout + wrapper script
**[Decided autonomously per user "work without stopping" instruction.]**

### Sub-question 1: Path / user / cron placement

| Option | Description | Selected |
|--------|-------------|----------|
| `/opt/ga_crawler` + system user `ga_crawler` + `/etc/cron.d/ga_crawler` | CLAUDE.md anchor; root-edited cron file with user column; git-tracked as `deploy/etc-cron-d-ga_crawler`. | ✓ |
| `~/ga_crawler` + operator user + user-crontab | Simpler ad-hoc; loses ops visibility. | |
| `/srv/ga_crawler` + system user + systemd timer | Modern but adds .service + .timer + journalctl tooling. | |

**Claude's pick:** `/opt/ga_crawler` + `ga_crawler` system user + `/etc/cron.d/ga_crawler`.
**Notes:** CLAUDE.md §Deployment locks /opt path; cron locked per STATE.md "Accumulated Key Decisions" line 138. `/etc/cron.d/` over user-crontab for ops visibility + git-checkin'able config-as-code.

### Sub-question 2: Wrapper script structure
**[Decided autonomously.]**

Per D-709: `#!/bin/bash`, `set -euo pipefail`, cd /opt/ga_crawler, `set -a; source .env; set +a`, fail-loud on missing `HC_PING_URL`, `flock -n 9` advisory lock, `curl ${HC_PING_URL}/start` (fail-soft), `uv run python -m ga_crawler weekly-run "$@" >> $LOG_FILE 2>&1`, capture exit code, /success or /fail/${exit} ping, exit code propagation. Lock at `/var/lock/ga_crawler-weekly.lock`.

### Sub-question 3: Docker scope

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to v2 (INFRA-V2-04) | Native install on Ubuntu 24.04 proven; Camoufox Firefox 135-pinned doesn't fit `mcr.microsoft.com/playwright/python` Chromium image. | ✓ |
| Custom Dockerfile in Phase 7 | Build custom Camoufox+uv image; bind-mount DB/reports/logs volumes. | |
| Native + Dockerfile both | Maintain two deployment paths. | |

**Claude's pick:** Defer to v2.
**Notes:** Custom Docker image = separate effort; native deploy proven through Phase 1 spike + STATE.md hosting recommendation.

---

## Claude's Discretion

- Cron MAILTO="" (no cron email — HC.io covers alerting; prevents stdout-before-redirect leaks to root@localhost).
- Lock file at `/var/lock/ga_crawler-weekly.lock` (Linux FHS tmpfs auto-cleanup on reboot).
- HC pings wrapped in `|| true` — HC.io outage must not mask real exit code or block production exec.
- `uv run python -m ga_crawler` (not `.venv/bin/python -m ga_crawler`) — uv restores pruned venv.
- README §2 mini-smoke check `bin/weekly-run.sh --viled-only --sanity-gate-n 1` for setup-green verification.
- No new `pyproject.toml [tool.ga_crawler.schedule]` namespace; no new `runs.stats.schedule.*` keys (5-way disjoint preserved).
- `_configure_logging()` source-diff invariant — Phase 7 MUST NOT touch (structural canary in planner).
- Exit code 4 reserved for HC_PING_URL missing (D-703); exit code 5 reserved for flock-double-run-refused (D-709).
- Cron file + logrotate file as git-tracked deploy templates (`deploy/etc-cron-d-ga_crawler` + `deploy/etc-logrotate-d-ga_crawler`).
- Daily backup cron entry added in same `/etc/cron.d/ga_crawler` file (Plan 02-06 backup.sh remains untouched).

## Deferred Ideas

- Docker image (v2 INFRA-V2-04).
- Self-hosted Healthchecks (SPOF risk on single VPS; may revisit if SaaS becomes paid-only or 10+ jobs scale).
- systemd timer instead of cron (STATE.md decision locked).
- Python in-process HC pings (hard-crash coverage rules it out).
- Per-step / per-phase HC pings (cognitive load > marginal observability gain).
- Multi-region failover / hot-standby VPS.
- Prometheus / Grafana / Loki observability stack.
- Cron retry on failure (operator decides via `deliver-run --run-id N`).
- `weekly-run --dry-run` (wastes anti-bot budget; `deliver-run --dry-run` already exists).
- Email alerts (ops Telegram + HC.io Telegram integration suffices).
- APScheduler 4 fallback.
- Auto-deployment / CI-driven VPS update.
- Log shipping to central aggregator.
- HC.io paid tier (>20 checks not needed).
- Backup off-site replication (v2 territory; local 4-rotate suffices for v1).
- Custom HC alert template.
- `bin/test-failure-alert.sh --auto-verify` programmatic assertion mode (Telegram message presence needs human eye).

## Cross-references not folded (per workflow rule)

- `gsd-sdk` not available in environment; `todo.match-phase` skipped silently.
- Phase 7 backlog items from STATE.md:
  - "Camoufox+EU smoke fetch" — covered partially by D-707 README §2 mini-smoke row; full smoke deferred to operator post-deploy.
  - "KZ-legal review" — orthogonal to scheduler/observability; remains in backlog.
  - "viled catalog pagination beyond page 1" — Phase 3/7 ops backlog; not scheduler-related; remains.
