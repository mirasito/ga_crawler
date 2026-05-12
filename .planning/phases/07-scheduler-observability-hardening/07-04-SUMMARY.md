---
phase: 07-scheduler-observability-hardening
plan: 04
subsystem: documentation
tags: [documentation, operator-runbook, sched-05, d-707, readme, wave-3]
requires:
  - "Plan 07-01 (Wave 0 canaries — readme_structure scaffolded RED-gate stub)"
  - "Plan 07-02 (deploy/etc-cron-d-ga_crawler + deploy/etc-logrotate-d-ga_crawler — quoted verbatim in §4 + referenced in §2)"
  - "Plan 07-03 (bin/weekly-run.sh exit code semantics for §3 + bin/test-failure-alert.sh procedure for §7)"
provides:
  - "Single-file 10-section RU-primary operator + dev runbook at repo root"
  - "SC#1 cron timing verification procedure (smoke gate, §2 step 8)"
  - "SC#5 deliberate-failure procedure (§7 — invokes Plan 07-03 bin/test-failure-alert.sh)"
  - "SCHED-05 source-level closure"
affects:
  - "All future operators of this codebase — README is the canonical install + ops surface"
  - "Wave 0 canary tally: readme_structure flips RED → GREEN (full RED-GREEN turnover for Phase 7)"
tech-stack:
  added: []
  patterns:
    - "RU-primary prose / EN code conventions per CLAUDE.md (project-wide)"
    - "10-section D-707 ordering enforced by canary (lock against future drift)"
key-files:
  created:
    - "README.md (232 lines)"
  modified: []
decisions:
  - "README.md lives at repo root (canonical location); single file (not multi-doc) per D-707"
  - "No top-level H1 — first heading is `## Что это` (canary scans `## ` prefix)"
  - "verbatim cron content quoted from deploy/etc-cron-d-ga_crawler (single source of truth — deploy file is authoritative)"
  - "Operations runbook (§8) explicitly cites .venv/bin/python paths to match real VPS layout from §2"
metrics:
  duration: "~25 min"
  completed: "2026-05-12"
  tasks: 1
  files: 1
---

# Phase 07 Plan 04: README.md — Operator Runbook Summary

Single-task plan creating `README.md` at repo root: 232-line RU-primary 10-section operator + developer runbook per D-707, closing SCHED-05 at source level and flipping the last RED Wave-0 canary GREEN. Phase 7 documentation deliverable complete.

## What Was Built

Один файл — `README.md` (232 строки) — содержит ровно 10 H2 секций в порядке D-707:

| § | Heading | Назначение | Min coverage |
|---|---------|-----------|--------------|
| 1 | `## Что это` | 5-line summary из PROJECT.md (RU prose, что/что делает/что доставляет/когда/кому) | RU primary; Cyrillic в heading |
| 2 | `## VPS setup from-scratch` | 8-шаговый install на Hetzner CX22 EU; **useradd ПЕРЕД logrotate cp** (Pitfall #5/#6); ends со smoke test (SC#1) | `useradd -r -m -d /opt/ga_crawler` line 19, `cp deploy/etc-logrotate` line 36 |
| 3 | `## ENV vars` | Таблица 4 required ENV + reserved exit codes table (0/2/3/4/5) + Pitfall #4 ENV value rules | exit codes 3 / 4 / 5 документированы; `HC_PING_URL` × 4 |
| 4 | `## Cron entry` | Verbatim-копия `deploy/etc-cron-d-ga_crawler` + объяснение `CRON_TZ=Asia/Almaty` invariant + `MAILTO=""` mitigation T-07-01 | `CRON_TZ=Asia/Almaty` × 2; `deploy/etc-cron-d-ga_crawler` × 3 |
| 5 | `## Healthchecks.io setup` | 6-шаговая инструкция: UUID ping URL формата `https://hc-ping.com/<uuid>`, schedule `0 23 * * 0` / Asia/Almaty, grace period **2h** (D-703), Telegram integration `@my_hc_bot` в ops chat, Pitfall #7 (alert template на free tier) | UUID + grace 2h + Telegram integration |
| 6 | `## Telegram bot setup` | 5-шаговая инструкция: @BotFather token, business chat + ops chat admin, `@userinfobot` для chat_ids, опциональная консолидация ops signals | 4 ENV вписываются обратно в `.env` |
| 7 | `## Deliberate-failure test` | Invocation `bin/test-failure-alert.sh` + 5-item operator verification checklist (ops chat alert / business chat silent / HC pings / DB runs / DB stats.deliver) + note про expected HC alert | `bin/test-failure-alert.sh` × 2; checklist 5 items |
| 8 | `## Operations runbook` | Recovery recipes: undelivered_telegram_unreachable / reporter bug / matcher bug / DB restore from backup / quick runs query — все цитируют Phase 4..6 standalone CLI surface (`deliver-run --run-id N`, `report-run --run-id N`, `matcher-run --run-id N --sanity-gate-p P`) | 4 recovery scenarios |
| 9 | `## Логи` | Datestamped path `/var/log/ga_crawler/weekly-run-YYYY-MM-DD.log[.gz]`; logrotate policy (weekly + rotate 13 + compress + delaycompress); grep/jq примеры; 3 edge cases (Pitfall #5 inheritance, notifempty, T-07-05 accept) | grep + jq examples; rotation policy документирована |
| 10 | `## Dev setup` | Минимальный onboarding (`uv sync` + `uv run pytest -x`) + указатель на `CLAUDE.md` для архитектурных деталей | Pointer to CLAUDE.md |

## Verification

### Canaries (Wave 0)

Все 3 теста в `tests/test_phase07_readme_structure.py` GREEN:

| Test | Result |
|------|--------|
| `test_readme_has_exactly_10_h2_sections` | PASSED (count==10) |
| `test_readme_h2_order_matches_d707` | PASSED (exact list match per D-707) |
| `test_readme_is_ru_primary` | PASSED (`## Что это` + `## Логи` Cyrillic headings присутствуют) |

### Wave-0 canary tally — full RED-GREEN turnover

После 07-04 **все 7 Wave-0 canary tests** для Phase 7 GREEN:
- 07-01 scaffolded all canaries (structural baseline GREEN; readme/cron/logrotate/wrapper/test-failure-alert RED).
- 07-02 flipped cron + logrotate canaries GREEN.
- 07-03 flipped wrapper + test-failure-alert canaries GREEN.
- 07-04 (this plan) flips **readme_structure** canary GREEN.

### Spot-check (grep markers)

```
H2 count:                       10
deploy/etc-cron-d-ga_crawler:   3 hits
bin/test-failure-alert.sh:      2 hits
HC_PING_URL:                    4 hits
CRON_TZ=Asia/Almaty:            2 hits
useradd -r -m -d /opt/ga_crawler: 1 hit (line 19)
chmod 0600 .env:                2 hits
Total line count:               232 lines
```

### Pitfall #5 ordering verification

- `useradd -r -m -d /opt/ga_crawler ga_crawler` — README line **19** (§2 step 2).
- `sudo cp deploy/etc-logrotate-d-ga_crawler /etc/logrotate.d/ga_crawler` — README line **36** (§2 step 6).
- 19 < 36 → operator создаёт user **до** деплоя logrotate config. Pitfall #5 (`create 0644 ga_crawler ga_crawler` фейлится молча, если пользователя нет) mitigated.

### Full test suite

```
802 passed, 1 skipped, 181 warnings in 137.12s
```

Zero regressions across Phase 1–6 (виледовый crawler, goldapple-scraper, matcher, reporter, delivery), Phase 7 Wave 0 canaries, integration tests.

## Manual-Only Verifications (handed off to operator)

Per `07-VALIDATION.md` Manual-Only Verifications, эти проверки **не покрываются CI** и выполняются на реальном Hetzner CX22 после deploy:

| Verification | How (per README) | When |
|--------------|------------------|------|
| **SC#1** Cron timing — Sunday 23:00 Almaty fires | `sudo grep CRON /var/log/syslog` после Sunday 23:00 Almaty; check first run lands в expected window | После первого Sunday post-deploy |
| **SC#5** Deliberate-failure end-to-end | `sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh` → operator проходит 5-item checklist | После deploy + после major code changes |
| HC.io Telegram integration | Invite `@my_hc_bot` в ops chat → `/start@my_hc_bot` → trigger smoke fail → expect Telegram alert | После §5 setup |
| Smoke gate (`--viled-only --sanity-gate-n 1`) | README §2 step 8 | После install, до production cron enable |

README §7 explicitly tags HC alert from `test-failure-alert.sh` как `expected` в HC UI — оператор должен это сделать руками, чтобы alert не считался production incident.

## Deviations from Plan

**None** — план выполнен exactly как написано. D-707 verbatim 10-section structure ordering canary-enforced; никаких реальных вариаций возможных не было.

## Threat Mitigations

- **T-07-01** (Info Disclosure — cron mail leak): README §4 documents `MAILTO=""` invariant + объясняет почему верботим в cron file.
- **T-07-04** (HC.io UUID + bot tokens leak): README §5 phrase URL только в `.env`; §3 marks `HC_PING_URL` как required ENV (значение НИКОГДА не появляется в git).
- **T-07-05** (logrotate-during-write): README §9 documents edge case openly (Open Q #3 — T-07-05 disposition `accept`), даёт operator action для подозрения extended run.
- **T-07-08** (.env code injection): README §2 шаг 7 включает `sudo -u ga_crawler chmod 0600 .env`; §3 documents «no `#`, no quotes» ENV value rules (Pitfall #4).

## Commits

- `a226017` — `docs(07-04): README.md — 10-section RU operator runbook (SCHED-05 / D-707)` — single atomic commit (1 file, 232 insertions)

## Self-Check: PASSED

- README.md exists at repo root: **FOUND**
- All 3 readme_structure canaries GREEN: **CONFIRMED**
- Commit `a226017` in git log: **CONFIRMED**
- Full test suite (802 passed, 1 skipped, 0 failed): **CONFIRMED**
- Pitfall #5 ordering (useradd line 19 < logrotate cp line 36): **CONFIRMED**
- All success criteria from plan: **ALL CHECKED**
