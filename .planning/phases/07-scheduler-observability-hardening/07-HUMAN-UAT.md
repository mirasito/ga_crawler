---
status: partial
phase: 07-scheduler-observability-hardening
source: [07-VERIFICATION.md]
started: 2026-05-13T00:15:00Z
updated: 2026-05-13T00:15:00Z
---

## Current Test

[awaiting operator post-deploy verification on Hetzner CX22]

## Tests

### 1. SC#1 — Cron timing verification
expected: After first Sunday post-deploy, system cron fires Sunday 23:00 Asia/Almaty (Sunday 18:00 UTC); operator confirms via `sudo grep CRON /var/log/syslog` that the weekly-run row executed in the Almaty 23:00 window (not UTC 23:00). Report arrives in business chat Monday morning Almaty (~02:00–03:00 after 3–4h run).
result: [pending]
why_human: Real cron timing on a real VPS at a real wall-clock time cannot be verified by CI; requires Hetzner CX22 provisioned + .env populated + first Sunday tick observed by operator.

### 2. SC#5 — Deliberate-failure end-to-end
expected: After `sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh`: (a) Telegram ops chat receives alert with reason `upstream pipeline failed` for run #N; (b) Telegram business chat receives NO new message; (c) Healthchecks.io dashboard shows /start + /fail pings; (d) `sqlite3 prices.db 'SELECT run_id, status, reason FROM runs WHERE run_id=N'` returns `N | failed | sanity_gate_n_failed:120<999999`; (e) `runs.stats.deliver.delivery_status = delivered_ops_only`.
result: [pending]
why_human: Telegram chat inspection + HC.io dashboard inspection + live sqlite DB inspection on the VPS — none verifiable in CI. Procedure documented in README §7 + script header.

### 3. Smoke gate (`bin/weekly-run.sh --viled-only --sanity-gate-n 1`)
expected: Mini-run completes successfully; HC dashboard shows /start + /success pings; business chat receives a mini-report; exit 0.
result: [pending]
why_human: Setup-green check on real VPS after `useradd`+`uv install`+`uv sync`+`playwright install firefox`+`cp deploy/*` steps. Documented as README §2 step 8.

### 4. HC.io Telegram integration
expected: Invite `@my_hc_bot` in ops chat → `/start@my_hc_bot` activation → trigger a deliberate failure → Telegram alert from `@my_hc_bot` arrives in ops chat.
result: [pending]
why_human: External-service Telegram integration in HC.io UI + Telegram bot acceptance — not testable in CI. Documented as README §5.

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
