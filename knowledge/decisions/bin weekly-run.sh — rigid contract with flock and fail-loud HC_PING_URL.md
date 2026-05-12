---
tags: [decision, phase-7, bash, wrapper, flock, observability]
date: 2026-05-12
decision-id: D-709
status: active
---

# bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL

D-709 rigid invariants для `bin/weekly-run.sh`:

1. **`set -euo pipefail`** — undefined var = exit (поймает опечатку в ENV name)
2. **`cd /opt/ga_crawler`** — fixed working directory
3. **`set -a; source .env; set +a`** — auto-export все vars в child env (idiomatic cron-wrapper; bypass Phase 6 RESEARCH caveat #4 — python-dotenv only in `cli.py`, bash wrapper это другой language, инвариант сохраняется)
4. **`: "${HC_PING_URL:?HC_PING_URL missing — refusing to run per D-703}"`** — fail-loud: missing HC → exit 4, не запускаем (CLAUDE.md «без mon не запускаем»)
5. **`exec 9>/var/lock/ga_crawler-weekly.lock; flock -n 9 || exit 5`** — non-blocking single-writer lock; defense vs manual+cron overlap; `/var/lock` → `/run/lock` tmpfs (clean on reboot)
6. **HC `/start` ping fail-soft (`|| true`)** — HC.io outage НЕ должен блочить production run
7. **`set +e ... uv run ... EXIT=$? ... set -e`** — preserve exit code from production run for HC routing
8. **HC `/success` или `/fail` ping fail-soft (`|| true`)** — `--data-raw "exit=$EXIT"` на /fail для dashboard payload
9. **`exit $EXIT`** — pass-through Python's exit code

## Reserved exit codes (Phase 6 D-616 + Phase 7)

- `0` delivered/idempotent → HC `/success`
- `2` undelivered (TG outage, gate failed)
- `3` skipped (no credentials)
- `4` HC_PING_URL missing (Phase 7 NEW)
- `5` flock-double-run-refused (Phase 7 NEW)
- любой non-zero → HC `/fail`

## Shebang divergence

CONTEXT.md D-709 written с `#!/bin/bash`. Project convention (`bin/backup.sh:1`) использует `#!/usr/bin/env bash`. **Plan 07-03 reconciles to `#!/usr/bin/env bash`** для consistency; divergence documented в 07-03-SUMMARY.

## Connected

- [[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]] *(D-701 — wrapper ownership rationale)*
- [[Phase 7 ships zero production Python — ops layer over frozen pipeline]] *(architectural frame)*
- [[Asymmetric ENV handling — fail-loud для bot token, degrade для chat_id]] *(Phase 6 D-611 — same pattern: HC_PING_URL fail-loud per «minimum viable operation» rule)*
