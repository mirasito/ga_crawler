---
tags: [decision, env, secrets, telegram, deliver, fail-mode]
date: 2026-05-12
status: live
---

# Asymmetric ENV handling — fail-loud для bot token, degrade для chat_id

Phase 6 D-611: missing ENV variables НЕ обрабатываются одинаково — `TG_BOT_TOKEN` отсутствие = fail-loud (exit code 3 + Healthchecks fail-ping); missing `TG_BUSINESS_CHAT_ID` / `TG_OPS_CHAT_ID` = degrade mode (продолжаем, что можем — sends ops alert о config error, либо warn + business-only).

## Asymmetric matrix

| ENV variable          | Missing → behaviour                                                                                                  |
|-----------------------|----------------------------------------------------------------------------------------------------------------------|
| `TG_BOT_TOKEN`        | **Fail-loud:** bot нельзя инициализировать вообще, никаких alert не отправить. `delivery_status=skipped_no_credentials` + structlog error + CLI exit code 3. Healthchecks ловит fail-ping. |
| `TG_BUSINESS_CHAT_ID` | **Conditional fail:** если gate-decision route был бы `business` И ops_chat present → ops alert «config error: TG_BUSINESS_CHAT_ID missing for run #N» + `delivery_status=delivered_ops_only`. Если gate route=ops_only — продолжаем normally. |
| `TG_OPS_CHAT_ID`      | **Degrade:** если gate route=business + business_chat present → warn в structlog + продолжаем business-only (ops alerts невозможны, но business send безопасен). Если gate route=ops_only И ops_chat missing → fail-loud (то же, что TG_BOT_TOKEN missing). |

## Зачем асимметрия

**Bot token = критичный secret** без которого Telegram bot literally не существует — fail-loud правильно. Healthchecks dead-mans-switch (Phase 7) сразу заметит missing ping.

**Chat IDs = config endpoints** — частичная работоспособность лучше total failure:
- Operator может потерять `TG_OPS_CHAT_ID` (Telegram чат удалён случайно) — business reports важнее ops alerts на одной неделе пропустить
- Operator может потерять `TG_BUSINESS_CHAT_ID` (pricing team уволилась) — ops alert о потере chat_id всё равно полезен для recovery

**Fail-fast vs graceful degrade — это не universal rule**. Зависит от:
1. **Recoverability:** missing token → нечего слать ВООБЩЕ; missing chat → есть partial path
2. **Cost of false-positive failure:** если оператор по факту хочет business-only режим (e.g., во время отпуска) — degrade удобнее чем «починить env и перезапустить»
3. **Observability:** Healthchecks ловит fail-loud цеп, но degrade-warning ловится только через structlog grep (ops practice)

## Generalize: pattern для secrets vs config

| Type                      | ENV miss policy | Example                          |
|---------------------------|-----------------|----------------------------------|
| **Авторизационный secret**| fail-loud       | API tokens, DB passwords, signing keys |
| **Endpoint config**       | degrade (по контексту) | chat IDs, fallback URLs, alert recipients |
| **Behavioral toggle**     | default-on/off  | `DEBUG=true`, `DRY_RUN=true`     |

Decision rule: **«Без этого ENV можно ли вообще запустить minimum viable operation?»** Нет → fail-loud. Да → degrade.

## Where в кодовой базе

- **`src/ga_crawler/delivery/config.py::DeliverEnvConfig.from_env`** — Phase 6:
  ```python
  if not bot_token:
      raise StatsNamespaceError("TG_BOT_TOKEN required")  # fail-loud
  # business_chat_id / ops_chat_id loaded as Optional[str]
  ```
- **`src/ga_crawler/runners/delivery_run.py::run_delivery_phase` Step 6b** — Phase 6:
  ```python
  if decision.route == "business" and not env.business_chat_id:
      decision = decision._replace(route="ops_only", reason="missing_env_TG_BUSINESS_CHAT_ID")
  if decision.route == "business" and not env.ops_chat_id:
      log.warning("ops_chat_id absent; ops alerts unavailable, business send safe")  # degrade
  ```
- **`src/ga_crawler/cli.py::_cmd_deliver`** — exit code 3 на `skipped_no_credentials` (fail-loud branch ловится здесь через `delivery_status` check).

## Подкреплено тестами

- `tests/integration/test_delivery_run.py::test_business_route_with_missing_ops_chat_proceeds_5c` — degrade path с caplog assertion на warn event
- `tests/integration/test_cli_deliver.py` — exit code 3 на missing TG_BOT_TOKEN
- `tests/test_delivery_config.py` — D-611 asymmetric handling unit tests

## Phase 7 cascade

Phase 7 Healthchecks two-tier (SCHED-03) использует эту асимметрию:
- **Cron-alive ping** (uuid в crontab) — ловит fail-loud TG_BOT_TOKEN сценарий (process exit code 3 → cron entry заканчивается non-zero → ping omitted → Healthchecks alert)
- **Delivery health probe** (отдельный, читает `runs.stats.deliver.delivery_status`) — ловит degrade сценарии (`delivered_ops_only` вместо `delivered_business` → возможно chat_id missing → operator investigation)

## Когда применять (decision rule)

Дизайн ENV-loading для нового модуля:
1. Перечислить все ENV vars
2. Для каждого спросить: «Без этого ENV — minimum operation возможен?»
3. Если нет → required, fail-loud
4. Если да → optional, degrade с явным structlog event и observable state в DB (для Phase 7-стиль two-tier monitoring)
