---
tags: [decision, phase-7, architecture, ops, structural-invariant]
date: 2026-05-12
status: active
---

# Phase 7 ships zero production Python — ops layer over frozen pipeline

Phase 7 (Scheduler + Observability Hardening) deliverables — pure shell + cron + logrotate + Markdown:
- `bin/weekly-run.sh` + `bin/test-failure-alert.sh` — bash wrappers
- `deploy/etc-cron-d-ga_crawler` + `deploy/etc-logrotate-d-ga_crawler` — config-as-code
- `README.md` — operator runbook
- `.env.example` — `HC_PING_URL=` line added

**Структурный canary `tests/test_phase07_structural_canaries.py`** ловит любое изменение в `src/ga_crawler/*.py` между Phase 6 close-out commit и Phase 7 HEAD. Также assert'ит:
- no new `runs.stats.*` namespace (5-way `viled/goldapple/match/report/deliver` preserved — Phase 6 D-607)
- no new `pyproject.toml` deps; no new `[tool.ga_crawler.*]` namespace
- no `simulate-failure` / `fail.mode` substrings в production source

## Зачем

Wrapper-owned HC pings (D-701) + cron/logrotate/flock (system-level) — все эти capabilities **уже existing** в Linux ops layer; добавлять Python ради этого = duplicate functionality в худшем месте (hard-crash blind spot, integration test surface).

Phase 2..6 frozen invariants (5 CLI subcommands, `_configure_logging()` JSONRenderer→stdout, `main_run.py` composition) — Phase 7 wraps вокруг них, не extends.

## Connected

- [[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]] *(D-701 — primary architectural driver)*
- [[bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL]] *(D-709 — implementation surface)*
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] *(Phase 5 D-514 — 5-way namespace invariant Phase 7 preserves)*
- [[Delivery failure decoupled from runs.status — Telegram outage stays success]] *(Phase 6 D-605 — exit code semantics Phase 7 wrapper consumes)*
