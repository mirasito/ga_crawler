---
tags: [priorities, v1-complete, milestone-close, operator-deploy, phase-7-done]
date: 2026-05-13
---

# Текущие приоритеты — Phase 7 done, v1 milestone close + operator deploy next

**Статус v1:** code-ship COMPLETE 2026-05-13. 7/7 phases, 50/50 plans, 47/48 requirements. Phase 7 (Scheduler + Observability Hardening) закрыт — SCHED-01..05 verified.

## Два параллельных трека

### Track A — Operator deploy (real work, не код)

Hetzner CX22 EU provisioning → README §2 setup → 4 UAT items в `07-HUMAN-UAT.md`:

1. SC#1 — cron timing (первое воскресенье после deploy, Asia/Almaty 23:00)
2. SC#5 — deliberate-failure E2E (`sudo -u ga_crawler /opt/ga_crawler/bin/test-failure-alert.sh`)
3. Smoke gate (`bin/weekly-run.sh --viled-only --sanity-gate-n 1`)
4. HC.io Telegram integration (`@my_hc_bot` в ops chat)

Procedure: README.md §2 (VPS setup) → §5 (HC.io) → §7 (deliberate-failure). После прохождения — `/gsd-verify-work 7` чтобы flush UAT в resolved.

### Track B — Planning hygiene (recommended next в GSD)

`/gsd-complete-milestone v1` — milestone audit + archival. Промотит INFRA-V2-04 (Docker, D-710) в v2 backlog. Очистит `.planning/` для следующего milestone cycle.

Также available:
- `/gsd-secure-phase 7` — security gate (no SECURITY.md yet для Phase 7)
- `/gsd-audit-uat` — surface 4 operator-manual UAT items cross-phase
- `/gsd-progress --next` — auto-advance routing

## v2 backlog locked

- INFRA-V2-04 — Docker image (D-710, deferred per system-user simplicity win)
- RECON-01 conditional plans (Phase 1 residential proxy escalation, only if Camoufox breaks)
- Прочее v2 — см. REQUIREMENTS.md §v2

## Connections

[[Phase 7 ships zero production Python — ops layer over frozen pipeline]] — Phase 7 архитектурный пойнт
[[Code review ловит deploy-blocking defects невидимые plan-checker'у — uv PATH, useradd -m collision, sudo без sudoers]] — boomerang lessons
[[2026-05-13 — Phase 7 executed end-to-end + code review fixes, v1 milestone code-ship complete]] — последняя сессия
