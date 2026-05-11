---
tags: [decision, phase-6, delivery, telegram, architecture, lifecycle]
date: 2026-05-12
decision_id: D-605
phase: 06-telegram-delivery
status: locked
---

# Delivery failure decoupled from runs.status — Telegram outage stays success

## Утверждение

**Phase 6 delivery failure НЕ flagipает `runs.status` на `'failed'`.** Telegram unreachable → `runs.status` остаётся `'success'`, `runs.stats.deliver.delivery_status='undelivered_telegram_unreachable'`, xlsx на диске для manual recovery через `deliver-run --run-id N`.

**Исключение:** uncaught exception внутри delivery (config error, programmer bug) → outer try/except в `main_run.run_weekly` (Plan 02-05 DATA-05 invariant) → `run_writer.fail(traceback)` → `runs.status='failed'`.

## Контекст

ARCHITECTURE.md «reporter independent of delivery» (Phase 5 D-507/D-515 anchor) расширена: «delivery independent of run-status correctness». Reporter уже произвёл валидный xlsx; Telegram outage — операционная проблема, не run-failure.

## Почему

- **Recovery без DB surgery:** Telegram outage в воскресенье ночью → утром в понедельник `python -m ga_crawler deliver-run --run-id 42` reads enum → re-attempts → done. NO `UPDATE runs SET status='success'` руками.
- **Phase 7 two-tier monitoring:** Healthchecks.io ping-нет на ДВА сигнала — `runs.status='failed'` (cron-level — bug or anti-bot failure) И `deliver.delivery_status in {undelivered_*, skipped_*}` (delivery-level — operational outage). Разделение помогает оператору диагностировать.
- **Data integrity:** xlsx сохранён, БД snapshot целая, matches persisted — нет смысла помечать всю работу как failed только потому что Telegram API недоступен 5 минут.
- **Test surface чище:** delivery tests assertion `runs.status='success'` + `deliver.delivery_status='undelivered_telegram_unreachable'` — два независимых invariant'а, легко проверять separately.

## Когда применять

Этот invariant cascade-нется в **Phase 7 Healthchecks integration**:
- `runs.status='failed'` → Healthchecks fail-ping
- `runs.status='success'` AND `deliver.delivery_status in {delivered_business, delivered_ops_only}` → Healthchecks success-ping
- `runs.status='success'` AND `deliver.delivery_status in {undelivered_*, skipped_*}` → отдельный delivery-health probe (Phase 7 SCHED-03 territory)

## Edge cases

- **Programmer bug в delivery code:** uncaught exception → outer try/except DATA-05 path → `run_writer.fail()` → status='failed'. Это правильно: bug не должен показывать success.
- **TG_BOT_TOKEN missing:** не запускает Telegram client вообще → `delivery_status='skipped_no_credentials'` + CLI exit 3 + `runs.status='success'` (preceeding phases succeeded). Phase 7 Healthchecks fail-ping ловит exit 3.
- **Gate-tripped (status != success upstream):** `delivery_status='delivered_ops_only'` (отправили alert ops chat); `runs.status` уже `'failed'` (upstream phase set it).

## Связано

- [[2026-05-12 — Phase 6 contexted — Telegram delivery decisions D-601..D-616]] *(session)*
- [[REPORT-06 size guard — delivery-time concern, не reporter-time]] *(D-515 предтеча — REPORT-06 size guard также не fail-ает run)*
- [[Reporter — source-of-truth для Telegram caption через runs.stats.report.summary_text]] *(D-514 cascade — Phase 6 наследует «file-on-disk-first» принцип)*
- [[Pre-finalize-before-matcher в run_weekly — D-411 skip-on-running ловушка]] *(Plan 04-05 — same composition pattern Phase 6 D-615 inherits)*

## Test canary

`tests/integration/test_delivery_telegram_outage_stays_success.py`: monkey-patch `aiogram.Bot.send_message` to raise `TelegramNetworkError` 3 times; assert `runs.status='success'` + `runs.stats.deliver.delivery_status='undelivered_telegram_unreachable'` + xlsx file exists. Negative test для invariant.

## Source

`.planning/phases/06-telegram-delivery/06-CONTEXT.md` §Decisions §"Pre-send gate composition + run-status policy" D-605.
