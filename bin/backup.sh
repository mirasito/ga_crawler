#!/usr/bin/env bash
# Online SQLite backup + 4-rotate retention. D-219.
#
# Source: 02-RESEARCH.md §"Don't Hand-Roll Backup" + §Pitfall 3 (WAL-safe atomic backup);
#         02-CONTEXT.md D-219 (online .backup chosen over VACUUM INTO for atomicity + WAL).
#
# Phase 7 ops-playbook adds cron entry: `0 1 * * * /opt/ga_crawler/bin/backup.sh`
# (daily 01:00 KZ — runs AFTER weekly Sunday-night batch completes; DB checkpointed).
#
# Usage:
#   bin/backup.sh                          # uses defaults: prices.db -> backups/
#   bin/backup.sh path/to/db.sqlite        # custom source DB
#   bin/backup.sh path/to/db.sqlite dest/  # custom source + target dir
#
# Exit codes:
#   0 — backup written successfully
#   1 — source DB not found
#   2 — backup file empty or missing after sqlite3 .backup

set -euo pipefail

DB_PATH="${1:-prices.db}"
BACKUP_DIR="${2:-backups}"

if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: source DB not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y-%m-%d)
TARGET="$BACKUP_DIR/$TIMESTAMP.db"

# Online .backup is atomic + WAL-safe (RESEARCH §Pitfall 3 mitigation).
# This is the canonical SQLite hot-backup mechanism — it locks pages briefly,
# copies them to the target file, and releases — safe to run while writers
# (e.g. weekly cron) are active or recently completed.
sqlite3 "$DB_PATH" ".backup '$TARGET'"

if [ ! -s "$TARGET" ]; then
  echo "ERROR: backup file empty or missing: $TARGET" >&2
  exit 2
fi

# Retention rotation: keep 4 most recent (DATA-06 minimum).
# `ls -t` sorts newest-first; `tail -n +5` skips the first 4; `xargs -r rm -f`
# deletes the rest. `-r` (no-run-if-empty) suppresses the rm call when there
# are <4 files, keeping the script idempotent on first runs.
ls -t "$BACKUP_DIR"/*.db 2>/dev/null | tail -n +5 | xargs -r rm -f

echo "OK: backup written to $TARGET"
