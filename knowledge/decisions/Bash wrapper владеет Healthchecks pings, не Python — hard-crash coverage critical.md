---
tags: [decision, phase-7, observability, healthchecks, monitoring]
date: 2026-05-12
decision-id: D-701
status: active
---

# Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical

`bin/weekly-run.sh` пингует `${HC_PING_URL}/start` перед `exec`, затем `${HC_PING_URL}` на exit=0 или `${HC_PING_URL}/fail` с `--data-raw "exit=$EXIT"` на любом non-zero exit. **НЕ Python в-process** — Camoufox+Firefox+4GB RAM scenario realistic для OOM-killer / segfault / `kill -9` — в этот момент Python уже мёртв, ping'ов не будет. Bash после `set +e` всегда доходит до cleanup.

Phase 6 D-606 6-value `delivery_status` enum mapping НЕ используется для HC routing напрямую — Phase 6 CLI exit codes (0=delivered/idempotent, 2=undelivered, 3=no_creds, 4=missing_HC_PING_URL, 5=flock-refused) уже семантически правильные, и любой non-zero → /fail-ping. `runs.stats.deliver.delivery_status` остаётся в БД для manual diagnostics + `deliver-run --run-id N` standalone recovery (Phase 6 D-608).

## Rejected alternatives

- **Python in-process pings** — hard-crash blind spot (OOM Camoufox, segfault, kill -9)
- **Hybrid bash+Python** — два места для одной responsibility, лишний integration test surface

## Connected

- [[bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL]] *(D-709 — implementation)*
- [[Delivery failure decoupled from runs.status — Telegram outage stays success]] *(D-605 — Phase 6 cascade, exit codes derived from delivery_status enum)*
- [[Healthchecks.io — dead-mans-switch для weekly cron]] *(integration target)*
- [[Phase 7 ships zero production Python — ops layer over frozen pipeline]] *(this decision = primary driver)*
