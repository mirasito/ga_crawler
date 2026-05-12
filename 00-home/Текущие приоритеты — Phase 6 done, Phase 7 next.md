---
tags: [priority, phase-7, scheduler, observability, active]
date: 2026-05-12
status: active
---

# Текущие приоритеты — Phase 6 done, Phase 7 next

Phase 6 (Telegram Delivery + Ops/Business Split) закрыт `/gsd-plan-phase 6` + `/gsd-execute-phase 6 --auto --no-transition` 2026-05-12. 6 plans across 5 waves, 30 commits, 746→746 (Phase 3 artificial-mutation остался единственным skipped), 0 failed. Verifier PASSED 4/4 SC + все архитектурные инварианты с runtime canaries.

## Прямо сейчас

`/clear` → `/gsd-discuss-phase 7` (Scheduler + Observability Hardening — финальная фаза v1).

Опции до Phase 7:
- `/gsd-code-review 6 --fix` — review delivery package + delivery_run + cli.py amend на стандартные класс defects
- `/gsd-secure-phase 6` — `workflow.security_enforcement=true`, threat models в каждом 06-XX-PLAN.md, но SECURITY.md не создан
- `uv run python -m ga_crawler weekly-run` + real `.env` с реальным TG-bot → end-to-end smoke с реальной Telegram доставкой (proof of life раньше cron-deploy)

## Phase 7 scope (SCHED-01..05)

- **SCHED-01:** Hetzner CX22 VPS provision (Ubuntu 24.04 LTS, Falkenstein/EU) + uv + Python 3.12 + Camoufox + Playwright system deps installed
- **SCHED-02:** system cron entry `CRON_TZ=Asia/Almaty 0 23 * * 0 cd /opt/ga_crawler && uv run python -m ga_crawler weekly-run`
- **SCHED-03:** Healthchecks.io two-tier integration — (1) cron alive pinger через uuid в crontab `&& curl …/ping/XXX`; (2) **delivery health** через отдельный probe `runs.stats.deliver.delivery_status` (D-606 cascade — `delivered_*` = healthy, остальные = unhealthy)
- **SCHED-04:** structlog production deployment — JSON output к `/var/log/ga_crawler/run-YYYY-WNN.jsonl`; logrotate; persistence для post-mortem
- **SCHED-05:** README ops chapter — @BotFather setup + @userinfobot для chat_id + `.env` provisioning + deliberate-failure procedure (drop TG_BOT_TOKEN → cron → ops alert visible)

## Cascading invariants Phase 7 ДОЛЖНА соблюдать

- **D-605 delivery decoupled from runs.status** — Healthchecks two-tier (SCHED-03) обязательно; только cron-alive ping не ловит Telegram outage сценарии
- **D-606 6-value enum classification** — monitoring должен mapить enum value на health state, не на runs.status
- **D-607 8-key `deliver.*` namespace** — ops dashboards читают `runs.stats.deliver.*` keys как любые другие namespace через `get_stats(run_id)` (single source-of-truth)
- **CLAUDE.md §Telegram Delivery (aiogram 3.27 locked)** — Phase 7 не меняет SDK; только cron-wrap + monitoring
- **`weekly-run` self-contained** — Phase 7 cron вызывает existing CLI; orchestrator unchanged
- **D-220 no-alembic invariant** — Phase 7 не меняет схему `runs`/`snapshots`/`matches`; observability через structlog + Healthchecks, не через DB

## Frozen modules от Phase 6

Phase 7 не модифицирует:
- `src/ga_crawler/delivery/*` (полностью frozen)
- `src/ga_crawler/runners/{main_run,delivery_run,reporter_run}.py` (composition frozen)
- `src/ga_crawler/cli.py` (subcommand surface frozen; Phase 7 = ops wrapper НАД CLI, не extension)
- Все Phase 2-5 frozen modules сохраняются

Phase 7 = `ops/` layer + crontab + Healthchecks integration. Никакого нового Python prod code в `src/ga_crawler/` (возможно `src/ga_crawler/observability/` если structlog config выносится в модуль, но дискутируется в discuss-phase).

## State of play

- **ROADMAP**: phases 1-6 complete; phase 7 next (SCHED-01..05); v1 ship после
- **v1 requirements**: 42/48 → планируется **47/48** после Phase 7 (5 SCHED- IDs); +1 (или 0) если есть deferred requirement
- **Plans complete**: 45 (6 + 9 + 6 + 6 + 9 + 6 + 3 spike-skipped не считаются)
- **Test suite**: 746 passed / 1 skipped / 0 failed
- **Branch**: `master`, clean modulo untracked `.claude/settings.local.json` + `docs/`

## Connected notes

- [[2026-05-12 — Phase 6 planned + executed end-to-end, Telegram delivery shipped]] *(итог Phase 6)*
- [[Delivery failure decoupled from runs.status — Telegram outage stays success]] *(D-605, теперь runtime-verified)*
- [[aiogram 3.27 + asyncio.run() sync wrapper — SDK для Telegram delivery]] *(D-601/D-602, runtime-verified)*
- [[tenacity wait_chain explicit backoff, не wait_exponential для дискретных N/M/L секунд]] *(RESEARCH caveat #2 — pattern для любых retry с конкретными N/M/L delays)*
- [[Asymmetric ENV handling — fail-loud для bot token, degrade для chat_id]] *(D-611 — pattern для secrets vs config differentiation)*
- [[Healthchecks.io — dead-mans-switch для weekly cron]] *(существующий integration ref — Phase 7 wires up + extends с two-tier)*
- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]] *(существующий atlas note — Phase 7 implements)*

## Что НЕ делать

- **Не модифицировать `delivery/`/`runners/`/`cli.py`** — Phase 6 frozen; observability — это ops layer over существующего entry-point
- **Не добавлять Telegram self-hosted server** — 50 MB Bot API limit достаточен; D-515 size_guard + D-604 gate уже отбрасывает oversized xlsx в ops chat
- **Не строить custom monitoring dashboard в v1** — Healthchecks.io + structlog JSON logs (grep) достаточно; team — пара человек, не SRE org
- **Не делать parallel waves в Phase 7** — SCHED-01..05 — linear dependency chain (VPS → cron → monitoring → logs → docs); parallel не даст экономии
- **Не делать `--dry-run` cron mode** — operator может вручную через `python -m ga_crawler weekly-run` если нужен dry; cron всегда production

## Git state

```
644e590 docs(06-06): close Phase 6 — STATE cascade + SUMMARY
0055d9f docs(06-06): ROADMAP Phase 6 close-out — 6/6 Complete 2026-05-12
b681969 docs(06-06): close DELIVER-01..05 with verbose plan citations
45e327d fix(06-06): B5 D-603 formula drift — wait_exponential→wait_chain in CONTEXT.md
... (30 commits total за Phase 6 plan→execute→verify cycle)
5396317 docs(06): create phase plan (6 plans, waves 0-5, D-601..D-616 + DELIVER-01..05 covered)
```
