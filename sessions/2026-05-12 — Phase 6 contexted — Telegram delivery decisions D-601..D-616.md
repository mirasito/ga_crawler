---
tags: [session, phase-6, telegram, delivery, discuss, context]
date: 2026-05-12
session_type: discuss
phase: 06-telegram-delivery
verdict: context-gathered-ready-for-plan
---

# 2026-05-12 — Phase 6 contexted — Telegram delivery decisions D-601..D-616

## Что произошло

`/gsd-discuss-phase 6` отработал. 16 решений **D-601..D-616** зафиксированы в `06-CONTEXT.md` в 5 категориях (SDK+integration / pre-send gate + run-status policy / idempotency + delivered-state / ops-alert + ENV / module-structure). Из 4 обсуждённых областей две решены интерактивно (Area 1 — SDK + retry), две — автономно по mirror-patterns после активации auto-mode (Area 2/3/4).

## Discussion flow

| Шаг | Действие | Исход |
|---|---|---|
| 1 | AskUserQuestion — выбор серых зон | User выбрал все 4 области |
| 2 | Area 1 — SDK + sync/async glue (sub-question 1) | **aiogram 3.27 + asyncio.run()** (Recommended; mirror goldapple `main_run.py:224`) |
| 3 | Area 1 — retry policy (sub-question 2) | **tenacity 3-retry с backoff 5/15/45s + explicit TelegramRetryAfter handling** (Recommended; mirror viled fetcher) |
| 4 | Auto-mode активирован | Areas 2/3/4 закрыты автономно |
| 5 | Area 2 — pre-send gate + run-status | 4-check first-fail-wins composition (D-604); delivery_status DECOUPLED от runs.status (D-605) |
| 6 | Area 3 — idempotency + delivered-state | 6-value delivery_status enum (D-606); 8-key deliver.* namespace (D-607); per-enum CLI re-send branching + --force flag (D-608) |
| 7 | Area 4 — ops alert + ENV | HTML parse_mode (D-609); single template с reason-keyed placeholder (D-610); asymmetric ENV-handling — TG_BOT_TOKEN fatal-loud, chat_id missing degrades (D-611); .env.example + .gitignore (D-612) |
| 8 | Module structure | delivery/ package mirror D-513 (D-613); [tool.ga_crawler.deliver] pyproject (D-614); main_run composition mirror Plan 05-05 explicit-gate (D-615); MainRunResult +2 fields (D-616) |
| 9 | Commit + STATE.md update | 2 commits: `24ae933 docs(06): capture phase context` + `ef1e035 docs(state): record Phase 6 context-gathered session` |

## Locked invariants Phase 6 inherits from Phase 5

| Invariant | Cascade rule |
|---|---|
| D-514 reporter source-of-truth | Phase 6 caption = `runs.stats.report.summary_text` VERBATIM; never regenerate |
| D-515 size-guard delivery-time | Phase 6 reads `report.size_guard_passed`; oversize → ops-chat alert (NON-NEGOTIABLE) |
| D-405 KPI verbatim | Phase 6 цитирует match.rate через summary_text (reporter уже cite-ed); no separate KPI handling |
| D-411/D-507 skip-protocol | Phase 6 D-604 gate check #1 REUSES `matcher.strict_key.read_run_status` |
| D-413/D-513 module split | Phase 6 D-613 mirrors с `delivery/` package |
| D-414/D-514 stats namespace | Phase 6 D-607 mirrors с `deliver.*` 8-key (5-way disjoint invariant) |
| D-412/D-509 standalone CLI | Phase 6 D-608 mirrors с `deliver-run --run-id N` |
| D-516 pyproject namespace | Phase 6 D-614 mirrors с `[tool.ga_crawler.deliver]` |
| Plan 05-05 composition | Phase 6 D-615 mirrors с explicit gate `if r_result.status == "success" and r_result.xlsx_path:` |
| DATA-05 lifecycle | Phase 6 D-605: normal Telegram outage stays success; uncaught exception → run_writer.fail |
| Pitfall 6 atomic patch_stats | Phase 6 D-607: single-call для всех 8 deliver.* keys |

## Ключевые архитектурные решения

### D-605 — delivery failure DECOUPLED from runs.status

ARCHITECTURE.md «reporter independent of delivery» расширена: «delivery independent of run-status correctness». Telegram outage в воскресенье ночью → `runs.status='success'` + `delivery_status='undelivered_telegram_unreachable'` + xlsx на диске. Manual recovery утром понедельник: `python -m ga_crawler deliver-run --run-id 42` reads enum → re-attempts → done. NO data loss, NO DB surgery.

**Exception:** Uncaught exception внутри delivery (config error, programmer bug) → outer try/except в `main_run.run_weekly` → `run_writer.fail(traceback)` → status='failed'. То есть «нормальный Telegram outage» ≠ run-failure; «программный bug» = run-failure.

Phase 7 Healthchecks.io будет ping-ать на ДВА сигнала: `runs.status='failed'` (cron-level) И `deliver.delivery_status in {undelivered_*, skipped_*}` (delivery-level). Two-tier monitoring.

### D-606 — 6-value delivery_status enum

| Enum value | Semantics |
|---|---|
| `pending` | Default after `runs.create()` |
| `delivered_business` | summary text + xlsx в business chat (gate passed) |
| `delivered_ops_only` | gate-tripped → alert в ops chat |
| `undelivered_telegram_unreachable` | После 3 retry; xlsx на диске; manual recovery via `deliver-run` |
| `skipped_no_credentials` | TG_BOT_TOKEN отсутствует; CLI exit 3; Healthchecks fail-ping |
| `skipped_already_delivered` | Idempotency: `delivered_business` re-run no-op без --force |

### D-611 — asymmetric ENV-handling

| ENV var | Missing → behavior |
|---|---|
| `TG_BOT_TOKEN` | **Fatal-loud**: structlog error + CLI exit 3 + delivery_status=skipped_no_credentials. Без токена ни одной alert нельзя послать. |
| `TG_BUSINESS_CHAT_ID` | **Degrade**: если gate route=business → ops alert «config error» + delivery_status=delivered_ops_only. Если route=ops_only — продолжаем. |
| `TG_OPS_CHAT_ID` | **Degrade**: если gate route=business → log warning + business-only mode. Если route=ops_only → fail-loud + exit 3. |

## Auto-mode rationale

Auto-mode активирован после Area 1 (системное сообщение). Решено: Areas 2/3/4 закрываются по mirror-patterns Phase 4/5 без интерактивного прохода. Аргументация:
- D-604 (4-check gate): D-515 cascade требует size_guard check; D-514 requires summary_text presence; D-507 mirror reuses read_run_status — все 4 проверки структурно мотивированы
- D-605 (decoupling): ARCHITECTURE invariant + Plan 02-05 DATA-05 lifecycle + Plan 05-05 «file-on-disk-first» — convergent
- D-606 (6-value enum): explicit state machine для idempotent recovery; mirror Pitfall 4 sentinel rejection discipline
- D-607 (8-key namespace): mirror D-514 7-key discipline + 1 extra key для business 2-message split (caption + document)
- D-610 (HTML + single template): MarkdownV2 escape — 16 спецсимволов; HTML — 3 (`<>&`); DRY single template
- D-611 (asymmetric ENV): DELIVER-02 буквально требует «ops alert on missing ENV» — если ops_chat валидный, можем послать; token = критичный без альтернатив

## Phase 6 готов к planning

Wave-structure expectation (mirror Phase 5):
- **Wave 0**: foundation — `[tool.ga_crawler.deliver]` namespace + aiogram dep + `delivery/{__init__,config,stats}.py` + conftest fixtures (`mock_aiogram_bot`, `mock_tg_env`, `synthetic_delivered_run`)
- **Wave 1**: builders — `delivery/{telegram_client,message_builder,gate}.py` (gate.py REUSES `read_run_status`; message_builder template source-locked + golden file)
- **Wave 2**: skip (no filesystem output; reporter precedent's Wave 2 was archive — Phase 6 не нужен)
- **Wave 3**: orchestrator — `runners/delivery_run.py` 7-step sync pipeline + asyncio.run(_send_delivery_async(...))
- **Wave 4**: composition + CLI — `main_run.py` add run_delivery_phase after reporter (D-615) + `cli.py` add `deliver-run` subcommand (D-608)
- **Wave 5**: doc cascade — REQUIREMENTS DELIVER-01..05 closed + STATE.md cascade rows D-605/D-606 + ROADMAP Phase 6 plans 5/5

Ожидается ~5 plans (Phase 5 был 6 — Phase 6 без filesystem-archive wave). Planner может разделить Wave 1 на 2-3 plans если LOC exceeds threshold.

## Connected notes

- [[2026-05-12 — Phase 5 executed — reporter shipped через 6 waves]] *(prior session)*
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] *(D-514 cascade входит в Phase 6 D-601)*
- [[REPORT-06 size guard — delivery-time concern, не reporter-time]] *(D-515 cascade входит в Phase 6 D-604 gate check #3)*
- [[Skip-path ReporterPhaseResult — size_guard_passed расходится между DB и memory]] *(WR-01 — Phase 6 gate.py reads `get_stats` not MainRunResult)*
- [[CLI stdout UTF-8 на Windows — sys.stdout.buffer.write вместо print]] *(Plan 05-05 inheritance для deliver-run CLI dry-run JSON output)*
- [[Telegram Bot API — канал доставки отчёта]] *(integration ref — Phase 6 implements это)*
- [[Delivery failure decoupled from runs.status — Telegram outage stays success]] *(NEW D-605)*

## Git state

```
ef1e035 docs(state): record Phase 6 context-gathered session
24ae933 docs(06): capture phase context
ed163e2 docs(phase-05): add security threat verification — SECURED 24/24
eb76e93 docs(05-verification): flip status human_needed → passed
ded82a7 test(05): close human UAT — OOXML inspection passes all 3 visual checks
```

## Next

`/clear` затем `/gsd-plan-phase 6` (Telegram Delivery + Ops/Business Split — DELIVER-01..05; ожидаемая длительность планирования 15-25 мин mirror Phase 5).
