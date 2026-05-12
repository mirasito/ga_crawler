---
tags: [priority, phase-7, scheduler, observability, active]
date: 2026-05-12
status: active
---

# Текущие приоритеты — Phase 7 planned, execute next

`/gsd-plan-phase 7` отработал автономно 2026-05-12. Plan-checker PASSED. 5 plans across 4 waves готовы к execute. Phase 7 = финальная фаза v1.

## Прямо сейчас

`/clear` → `/gsd-execute-phase 7` (или `--auto --no-transition` для autonomous YOLO).

После Phase 7 close-out → v1 ship (47/48 v1 requirements закрыты; 1 deferred остаётся в backlog).

## Wave breakdown (5 plans, 13 tasks)

- **Wave 1 — `07-01`** (3 tasks, no deps): 7 RED canary test stubs. Закрывает source-lock surface для SCHED-01..05 + zero-production-Python structural canary.
- **Wave 2 — `07-02` ∥ `07-03`** (parallel, disjoint files):
  - `07-02` (3 tasks): `deploy/etc-cron-d-ga_crawler` (D-708 verbatim) + `deploy/etc-logrotate-d-ga_crawler` (D-705 verbatim) + `.env.example` add `HC_PING_URL=`. Closes SCHED-01/02/04.
  - `07-03` (2 tasks): `bin/weekly-run.sh` (D-709 contract) + `bin/test-failure-alert.sh` (D-706 5-step orchestrator). Closes SCHED-03.
- **Wave 3 — `07-04`** (1 task): `README.md` at repo root, 10 sections RU primary (D-707). Closes SCHED-05.
- **Wave 4 — `07-05`** (4 tasks): REQUIREMENTS/STATE/ROADMAP/CONTEXT doc cascade + SUMMARY.

## Locked invariants Phase 7 должен соблюдать

- **D-701** bash wrapper владеет HC pings, не Python (hard-crash coverage — OOM-killer, segfault Camoufox subprocess, kill -9 — все через wrapper exit code → /fail ping)
- **D-704** structlog `_configure_logging()` НЕ меняется — wrapper редиректит stdout/stderr в datestamped logfile
- **«Zero production Python»** — `git diff src/ga_crawler/` пустой Phase 6→7. Структурный canary в `tests/test_phase07_structural_canaries.py`
- **D-607 5-way `runs.stats.*` disjoint** — Phase 7 НЕ добавляет 6-й namespace (`schedule.*` — нет)
- **D-710** Docker defers to v2 — `INFRA-V2-04` в backlog (Camoufox Firefox 135-pinned не совместим с `mcr.microsoft.com/playwright/python:noble` Chromium-based)
- **CLI surface frozen** — Phase 7 НЕ добавляет субкоманд; wrapper вызывает existing `weekly-run`/`deliver-run` через `uv run python -m ga_crawler`

## Frozen modules от Phase 2..6

Phase 7 не модифицирует:
- `src/ga_crawler/cli.py` (5 субкоманд + `_configure_logging` frozen; canary asserts unchanged)
- `src/ga_crawler/runners/main_run.py` (Phase 6 composition frozen)
- `src/ga_crawler/delivery/*` (полностью Phase 6 frozen)
- `pyproject.toml` (no new deps; no new `[tool.ga_crawler.*]` namespace)

## Threat model (T-07-01..08)

6 mitigated standard controls (`MAILTO=""`, `flock -n 9`, `.env` 0600, gitignored, `delaycompress`, `create 0644`), 2 accepted (advisory lock world-writable, operator trust model для `source .env`). Каждый план имеет `<threat_model>` block.

## Что НЕ делать

- **Не менять `src/ga_crawler/*.py`** — structural canary ловит; Phase 7 = pure ops layer
- **Не добавлять `--simulate-failure` production flag** — `bin/test-failure-alert.sh` orchestrates через existing `--sanity-gate-n 999999` (D-218 path); никаких testing-only code paths в production binary
- **Не добавлять Python in-process HC pings** — D-701: hard-crash coverage requires bash-level pings
- **Не добавлять per-step HC pings** (отдельные UUIDs для viled/goldapple/matcher/reporter/deliver) — один weekly run = один HC check; D-702 limit 20 checks free tier
- **Не self-host Healthchecks** — SaaS HC.io free tier; self-hosted на том же VPS = SPOF
- **Не делать systemd timer** — STATE.md line 138 locked cron
- **Не Docker'ить Phase 7** — D-710 defers; Camoufox+Firefox≠Chromium image incompatible

## State of play

- **Phases 1-6**: complete (42/48 v1 requirements)
- **Phase 7**: planned (5 plans ready); will close SCHED-01..05 (47/48 v1 после)
- **Test suite**: 746 passed / 1 skipped / 0 failed (Phase 3 artificial-mutation; не Phase 7 concern)
- **Branch**: `master`, clean modulo untracked `.claude/settings.local.json` + `docs/`
- **Git head**: `55380d4 docs(07): plan Phase 7 — 5 plans across 4 waves`

## Connected notes

- [[2026-05-12 — Phase 7 planned end-to-end, 5 plans across 4 waves ready для execute]] *(текущая сессия итог)*
- [[Bash wrapper владеет Healthchecks pings, не Python — hard-crash coverage critical]] *(D-701)*
- [[Phase 7 ships zero production Python — ops layer over frozen pipeline]] *(архитектурный пойнт)*
- [[bin weekly-run.sh — rigid contract with flock and fail-loud HC_PING_URL]] *(D-709)*
- [[README 10 sections RU primary EN code — single file для operator-is-developer team]] *(D-707)*
- [[Healthchecks.io — dead-mans-switch для weekly cron]] *(existing — Phase 7 wires up)*
- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]] *(existing — Phase 7 implements)*

## Git state

```
55380d4 docs(07): plan Phase 7 — 5 plans across 4 waves
6b6e394 docs(07): map Phase 7 file patterns to closest analogs
9896cca docs(07): add validation strategy
83f9efe docs(07): research phase domain — scheduler + observability hardening
13e1325 docs(07): capture phase 7 context — Scheduler + Observability Hardening
8c03acb docs(vault): save session — Phase 6 shipped end-to-end
644e590 docs(06-06): close Phase 6 — STATE cascade + SUMMARY
```
