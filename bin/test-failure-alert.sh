#!/usr/bin/env bash
# Deliberate-failure orchestrator — Phase 7 D-706. Verifies SC#5 end-to-end.
#
# Source: 07-CONTEXT.md D-706 (5-step recipe); 07-RESEARCH.md Example 4 verbatim;
#         bin/backup.sh (project bash convention).
#
# Sequence (manual operator tool — NOT scheduled in cron per D-706):
#   1) Force sanity-N gate fail via bin/weekly-run.sh --viled-only --sanity-gate-n 999999
#      (viled-only crawl ~2 min; sanity gate count<999999 trips → runs.status='failed').
#      Wrapper pings HC /fail on exit ≠ 0 — tests SCHED-03 end-to-end.
#   2) Extract run_id from the latest weekly-run log (JSON event in structlog stream).
#   3) Invoke deliver-run --run-id $RID directly (no wrapper, no HC ping). Gate trips
#      on read_run_status='failed' → route=ops_only → ops chat alert. Tests
#      DELIVER-02 (ops chat receives alert) and DELIVER-03 (pre-send gate routing).
#   4) Emit operator verification checklist (ops chat / business chat / HC dashboard /
#      DB runs.status / DB stats.deliver.delivery_status).
#   5) NO cleanup — failed run persists in DB as evidence; script is idempotent.
#
# Reuses existing CLI surface only:
#   --viled-only (Plan 02-05 D-212), --sanity-gate-n (Plan 04-05),
#   deliver-run --run-id N (Phase 6 D-608).
# NO new production Python code paths.
#
# Usage:
#   sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh
#
# Exit codes:
#   0 — checklist emitted (operator validates visually)
#   ≠0 — script setup failed (e.g. log file missing, run_id unparseable);
#        does NOT indicate pipeline failure (pipeline failure is the intended state).

set -euo pipefail
cd /opt/ga_crawler

echo "==> Step 1: Forced sanity-N gate fail (viled-only crawl, ~2 min)"
# Wrapper will exit non-zero (sanity gate trip → undelivered or upstream fail);
# `|| true` swallows it — we WANT a failed run as test input.
bin/weekly-run.sh --viled-only --sanity-gate-n 999999 || true

echo "==> Step 2: Extract last run_id from log"
LOG_FILE="/var/log/ga_crawler/weekly-run-$(date +%F).log"
RID=$(tail -200 "$LOG_FILE" | grep -o '"run_id":[0-9]*' | tail -1 | grep -o '[0-9]*')
echo "    run_id=$RID"

echo "==> Step 3: Invoke deliver-run for ops alert (no HC ping — separate invocation)"
# Скрипт уже запущен от ga_crawler (README §7: sudo -u ga_crawler …test-failure-alert.sh);
# inner sudo -u ga_crawler был бы (а) семантически redundant и (б) невозможен — system
# user (useradd -r) не имеет sudoers entry и sudo aborted бы скрипт здесь.
/opt/ga_crawler/.venv/bin/python -m ga_crawler deliver-run --run-id "$RID"

echo "==> Step 4: Verification checklist (operator runs visually)"
cat <<EOF
  [ ] Telegram ops chat: alert message visible with reason='upstream pipeline failed' for run #$RID
  [ ] Telegram business chat: NO new message
  [ ] Healthchecks.io dashboard: /start + /fail pings logged
  [ ] DB: sqlite3 /opt/ga_crawler/prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=$RID'
        Expected: failed | sanity_gate_n_failed:120<999999
  [ ] DB stats: sqlite3 ... "SELECT json_extract(stats,'\$.deliver.delivery_status') FROM runs WHERE run_id=$RID"
        Expected: delivered_ops_only
EOF
