---
tags: [priority, phase-6, telegram, delivery, active]
date: 2026-05-12
status: active
---

# Текущие приоритеты — Phase 6 contexted, plan next

Phase 6 (Telegram Delivery + Ops/Business Split) **CONTEXT GATHERED** `/gsd-discuss-phase 6` 2026-05-12. 16 решений **D-601..D-616** locked в 5 категориях. Phase 5 cascade invariants (D-514/D-515/D-405) honored verbatim.

## Прямо сейчас

`/clear` затем `/gsd-plan-phase 6`.

Опции до plan:
- Review `06-CONTEXT.md` если хочется — все 16 решений в `Decisions` блоке, mirror-patterns обоснованы в Discussion log
- `/gsd-code-review 5 --fix` — закрыть WR-01/WR-02 (Phase 5 advisory findings) до Phase 6 plan, если хочется чистый baseline
- `/gsd-secure-phase 5` — Phase 5 security gate (если workflow.security_enforcement=true)

## Что зафиксировано в Phase 6

### Tech stack
- **aiogram 3.27.x** (D-601 — CLAUDE.md lock); pin `aiogram>=3.27,<4.0`
- sync `delivery_run.py` оборачивает `asyncio.run(_send_async(...))` mirror goldapple (D-602)
- tenacity 3-retry с backoff 5/15/45s + explicit `TelegramRetryAfter` (D-603)

### Pre-send gate (DELIVER-03)
4 проверки first-fail-wins (D-604) — REUSES `matcher.strict_key.read_run_status`:
1. `runs.status == 'success'`
2. `runs.stats.report.xlsx_path` non-empty (D-515 caveat)
3. `runs.stats.report.size_guard_passed == True` (D-515 cascade NON-NEGOTIABLE)
4. `runs.stats.report.summary_text` non-empty

### Delivery state machine (DELIVER-04 idempotency)
6-value `delivery_status` enum (D-606):
- `pending` / `delivered_business` / `delivered_ops_only` / `undelivered_telegram_unreachable` / `skipped_no_credentials` / `skipped_already_delivered`

`runs.stats.deliver.*` 8-key namespace (D-607) mirror D-514 discipline; single atomic `patch_stats` (Pitfall 6).

CLI `deliver-run --run-id N [--force] [--dry-run]` per-enum branching (D-608 mirror D-509).

### Ops alert + ENV (DELIVER-02 + DELIVER-05)
- HTML parse_mode (D-609); single template с reason-keyed placeholder (D-610)
- Asymmetric ENV (D-611): TG_BOT_TOKEN fatal-loud; chat_id missing degrades по route
- `.env.example` + `.gitignore` (D-612); python-dotenv уже в deps

### Architecture (D-605 — ключевое)
**Delivery failure DECOUPLED от runs.status.** Telegram unreachable → `runs.status='success'` + `delivery_status='undelivered_telegram_unreachable'` + xlsx на диске. Manual recovery через `deliver-run --run-id N`. Uncaught exception в delivery → outer try/except → run_writer.fail (DATA-05 invariant). Phase 7 Healthchecks two-tier monitoring (runs.status + deliver.delivery_status).

## Frozen invariants от Phase 5 (Phase 6 НЕ нарушает)

- **D-514:** Phase 6 caption = `runs.stats.report.summary_text` VERBATIM (никогда не regenerate; structural canary)
- **D-515:** Phase 6 reads `report.size_guard_passed`, oversize → ops-chat (NON-NEGOTIABLE)
- **D-405:** KPI match.rate уже cite-ed в summary_text от reporter; no separate handling
- **D-411/D-507:** skip-protocol mirror через D-604 gate check #1
- **Plan 05-05:** pre-init outcome vars + explicit gate above downstream skip-protocol
- **Pitfall 6:** single-call atomic patch_stats для всех 8 deliver.* keys
- **DATA-05:** delivery exception → run_writer.fail; normal Telegram outage stays success

## Ожидаемая plan-структура (mirror Phase 5)

| Wave | Содержание |
|---|---|
| 0 | foundation — `[tool.ga_crawler.deliver]` namespace + aiogram dep + `delivery/{config,stats}.py` + conftest fixtures |
| 1 | builders — `delivery/{telegram_client,message_builder,gate}.py`; template source-locked + golden file canary |
| 2 | skip (no filesystem output — Phase 5 archive precedent не нужен) |
| 3 | orchestrator — `runners/delivery_run.py` sync pipeline + `asyncio.run(...)` |
| 4 | composition + CLI — `main_run.py` add run_delivery_phase + `cli.py` add `deliver-run` subcommand |
| 5 | doc cascade — REQUIREMENTS DELIVER-01..05 closed + STATE.md D-605/D-606 + ROADMAP Phase 6 |

Ожидается ~5 plans (один wave короче чем Phase 5).

## Frozen modules от Phase 5

Phase 6 НЕ модифицирует:
- `src/ga_crawler/reporter/*`
- `src/ga_crawler/runners/reporter_run.py`
- `src/ga_crawler/matcher/*`
- `src/ga_crawler/runner/{gates,stats}.py`
- Phase 3 `src/ga_crawler/{enumeration,fetchers,parsers}/goldapple_*.py`

`runners/main_run.py` + `cli.py` будут extended (как было в Plan 05-05 — composition + CLI subcommand mirror).

## State of play

- **ROADMAP**: Phases 1-5 complete; Phase 6 contexted (D-601..D-616); Phase 7 (Scheduler + Observability) — последняя
- **v1 requirements**: 37/48 → планируется **42/48** после Phase 6 (5 DELIVER-IDs)
- **Plans complete**: 39 (Phase 1=9 + Phase 2=6 + Phase 3=9 + Phase 4=6 + Phase 5=6)
- **Test suite**: 610 passed, 1 skipped (Phase 5 baseline)
- **Branch**: `master`, clean

## Operator prerequisites для production deploy (Phase 7)

Phase 6 plan может включить, Phase 7 README обязан:
1. Создать Telegram bot через @BotFather → `TG_BOT_TOKEN`
2. Создать 2 чата (business + ops), добавить bot, получить chat_id через @userinfobot → `TG_BUSINESS_CHAT_ID`, `TG_OPS_CHAT_ID`
3. Скопировать `.env.example` → `.env` (root project), заполнить три vars
4. Local dev: `uv run python -m ga_crawler deliver-run --run-id 1 --dry-run` для проверки routing decision без send

## Connected notes

- [[2026-05-12 — Phase 6 contexted — Telegram delivery decisions D-601..D-616]] *(session log)*
- [[Delivery failure decoupled from runs.status — Telegram outage stays success]] *(D-605 — ключевая архитектурная инновация Phase 6)*
- [[aiogram 3.27 + asyncio.run() sync wrapper — SDK для Telegram delivery]] *(D-601/D-602)*
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] *(D-514 cascade входит в D-601)*
- [[REPORT-06 size guard — delivery-time concern, не reporter-time]] *(D-515 cascade входит в D-604 gate check #3)*
- [[Skip-path ReporterPhaseResult — size_guard_passed расходится между DB и memory]] *(WR-01 — Phase 6 gate.py reads `get_stats` not MainRunResult)*
- [[Telegram Bot API — канал доставки отчёта]] *(integration ref)*

## После Phase 6

Phase 7 (Scheduler + Observability Hardening) — финальный VPS setup + cron `CRON_TZ=Asia/Almaty` + Healthchecks.io dead-mans-switch + structlog deployment + README. **Two-tier Healthchecks integration** через D-605 invariant: `runs.status='failed'` (cron-level) И `deliver.delivery_status in {undelivered_*, skipped_*}` (delivery-level). Никаких feature-фаз после; v1 ship.

## Что НЕ делать в Phase 6

- НЕ строить второй summary template — `report.summary_text` source-of-truth (D-514)
- НЕ recompute size в delivery-gate — `report.size_guard_passed` уже в БД (D-515)
- НЕ использовать `print(json.dumps(..., ensure_ascii=False))` для CLI вывода — Cyrillic+emoji ломаются на Windows cp1252 (Plan 05-05 Rule 1 lesson)
- НЕ модифицировать reporter modules — frozen после Phase 5
- НЕ flagipать `runs.status='failed'` на нормальный Telegram outage — только uncaught exception flagipает (D-605)

## Git state

```
ef1e035 docs(state): record Phase 6 context-gathered session
24ae933 docs(06): capture phase context
ed163e2 docs(phase-05): add security threat verification — SECURED 24/24
eb76e93 docs(05-verification): flip status human_needed → passed
ded82a7 test(05): close human UAT — OOXML inspection passes all 3 visual checks
```
