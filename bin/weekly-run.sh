#!/usr/bin/env bash
# Weekly cron wrapper — Phase 7 D-709 contract. SCHED-03 + SCHED-04.
#
# Source: 07-CONTEXT.md D-709 (lines 92–131, verbatim shape);
#         07-RESEARCH.md §Pattern 1 + Pitfall #3 (exit 5 reserved for flock-refused);
#         bin/backup.sh (project bash convention).
#
# Responsibilities (in order):
#   1. Load .env (set -a; source; set +a) — bash is the env-loading authority for cron
#      context. python-dotenv stays only in cli.py per Phase 6 RESEARCH caveat #4.
#   2. Fail-loud if HC_PING_URL missing (exit 4 per D-703) — CLAUDE.md "without mon
#      we don't run".
#   3. Acquire flock advisory lock /var/lock/ga_crawler-weekly.lock; exit 5 on refusal
#      (Pitfall #3 — explicit exit 5 to disambiguate from generic exit 1).
#   4. /start ping to Healthchecks.io (fail-soft).
#   5. Exec `uv run python -m ga_crawler weekly-run "$@"`; redirect stdout+stderr to
#      datestamped LOG_FILE (SCHED-04). Preserve exit code through set -e dance.
#   6. /success (bare URL) or /fail (with --data-raw "exit=$EXIT") ping (fail-soft).
#   7. exit $EXIT (passthrough to caller / cron).
#
# Threat refs (mitigations in this file):
#   T-07-01 — stdout/stderr redirect to LOG_FILE (no cron MAILTO leak)
#   T-07-02 — flock -n single-writer guard (DB corruption prevention)
#   T-07-04 — ${HC_PING_URL} from .env (gitignored); no UUID hardcoded
#   T-07-07 — /var/lock/ created by exec 9> as ga_crawler user (advisory lock; not auth)
#
# Usage:
#   sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh             # cron entry
#   sudo -u ga_crawler /opt/ga_crawler/bin/weekly-run.sh --viled-only --sanity-gate-n 1
#   (smoke test per README §2)
#
# Exit codes:
#   0   — Python production exec returned success (delivered or skipped-idempotent)
#   2   — Python production exec returned undelivered (Telegram unreachable; retryable)
#   3   — Python production exec returned missing TG_BOT_TOKEN (config error)
#   4   — HC_PING_URL missing in env (Phase 7 D-703 fail-loud)
#   5   — another weekly-run instance holds the flock (Phase 7 D-709 / Pitfall #3)
#   ≠0  — any other Python exit code → /fail ping with exit=$EXIT body, then exit $EXIT

set -euo pipefail
cd /opt/ga_crawler

# 1. ENV load (bash is the env-loading authority for cron context;
#    python-dotenv lives only in cli.py per Phase 6 RESEARCH caveat #4).
set -a
source .env
set +a

# 2. D-703 fail-loud: HC_PING_URL is required; refuse to run if absent.
#    Explicit guard (not ${VAR:?}) — :? expansion under set -e exits 1, conflating
#    HC_PING_URL-missing with generic bash error. D-703 reserves exit 4.
if [[ -z "${HC_PING_URL:-}" ]]; then
  echo "HC_PING_URL missing — refusing to run per D-703" >&2
  exit 4
fi

# 3. Single-writer flock guard (defense vs double-run from cron+manual overlap).
#    /var/lock is tmpfs (symlink to /run/lock on Ubuntu 24.04) — auto-cleanup at reboot.
exec 9>/var/lock/ga_crawler-weekly.lock
flock -n 9 || { echo "Another weekly-run holds the lock — refusing" >&2; exit 5; }

LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"

# 4. /start ping (fail-soft — HC.io outage MUST NOT block production exec).
curl -fsS -m 10 --retry 3 "${HC_PING_URL}/start" > /dev/null || true

# 5. Exec production; preserve exit code through set -e dance.
#    stdout+stderr → LOG_FILE for SCHED-04 (logrotate weekly rotate 13).
set +e
uv run python -m ga_crawler weekly-run "$@" >> "$LOG_FILE" 2>&1
EXIT=$?
set -e

# 6. Success or fail ping (fail-soft).
if [[ $EXIT -eq 0 ]]; then
  curl -fsS -m 10 --retry 3 "${HC_PING_URL}" > /dev/null || true
else
  curl -fsS -m 10 --retry 3 --data-raw "exit=$EXIT" "${HC_PING_URL}/fail" > /dev/null || true
fi

# 7. Passthrough exit code to caller (cron logs it; HC.io recorded it in step 6).
exit $EXIT
