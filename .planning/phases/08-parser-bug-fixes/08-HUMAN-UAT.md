---
status: partial
phase: 08-parser-bug-fixes
source: [08-VERIFICATION.md]
started: 2026-05-14T03:00:00Z
updated: 2026-05-14T03:00:00Z
---

## Current Test

[awaiting Phase 11 operator-deployed live dry-run on Yandex Cloud kz1]

## Tests

### 1. Operator-deployed live dry-run produces matched pairs
expected: After cron tick on Yandex Cloud kz1 (Phase 11), `runs.stats.goldapple.volume_null_rate` ≤ 0.5; matches table has rows; Excel report has `match_count > 0`. Concretely: Plan 08-02 volume helper + 08-03 brand/name h1-spans + 08-04 viled volume helper produce clean records that the matcher's strict-key `JOIN` actually pairs.
result: blocked — Phase 11 (DEPLOY-01..08) prerequisite. Infrastructure structurally complete; only live-execution remains.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 1

## Gaps

(none — this is operator-track, not code-gap. Phase 8 closes structurally; live-run validation surfaces during Phase 11 cron tick.)
