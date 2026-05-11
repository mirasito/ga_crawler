# Phase 6: Telegram Delivery + Ops/Business Split - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 6-telegram-delivery
**Areas discussed:** SDK + sync/async glue, Pre-send gate + run-status policy, Идемпотентность + delivered-state, Ops alert: контент + формат + ENV-edge cases
**Mode:** discuss (auto-mode activated после Area 1; Areas 2/3/4 закрыты по mirror-patterns без interactive прохода — D-604..D-616)

---

## Area 1 — SDK + sync/async glue

### Sub-question 1: SDK choice

| Option | Description | Selected |
|--------|-------------|----------|
| aiogram 3.27 + asyncio.run() | CLAUDE.md зафиксирован; consistent с goldapple_run sync→async pattern; встроенный retry-after handling в aiogram.exceptions.TelegramRetryAfter; type-hinted send_document(FSInputFile) | ✓ |
| python-telegram-bot 22 sync | Доступен sync API, не нужен asyncio.run; но добавляет второй толстый dep помимо curl_cffi/aiogram patterns | |
| Raw httpx.post к Bot API | Без SDK, экономия ~5MB и 0 deps; нужно вручную multipart для send_document + retry-after parsing + error mapping. Не стоит риска | |

**User's choice:** aiogram 3.27 + asyncio.run() (Recommended)
**Notes:** Locked в **D-601** + **D-602** в CONTEXT.md. Pin `aiogram>=3.27,<4.0`. Wrapper зеркалит `main_run.py:224` goldapple precedent.

### Sub-question 2: Retry-budget + 'unreachable' semantics (DELIVER-04)

| Option | Description | Selected |
|--------|-------------|----------|
| tenacity 3 retry с backoff + respect retry-after | Mirror viled fetcher pattern (tenacity 3-retry); явно ловим TelegramRetryAfter (спим ровно .retry_after); TelegramNetworkError→backoff 5s/15s/45s; после 3-х = undelivered. Общий budget ≤ 75s + retry-after | ✓ |
| aiogram built-in middleware-retry | aiogram имеет свои retry-хуки; но они design'эны под polling-bot и long-running app, не под one-shot CLI. Сложнее тестировать | |
| 5 retry, total wait ≤ 5 min | Более агрессивно — но weekly job не критичен по времени, отчёт всё равно на диске. Имеет смысл если cron в 03:00 и Telegram outage ждём | |

**User's choice:** tenacity 3 retry с backoff + respect retry-after (Recommended)
**Notes:** Locked в **D-603** в CONTEXT.md. wait_exponential(multiplier=5, min=5, max=45) → backoff 5/15/45; TelegramRetryAfter обрабатывается отдельно через asyncio.sleep(exc.retry_after). После 3 retry → delivery_status=undelivered_telegram_unreachable.

---

## Area 2 — Pre-send gate + run-status policy (DELIVER-03)

**Mode shift:** Auto-mode активирован — Area 2/3/4 решены автономно по mirror-patterns из Phase 4/5 без interactive прохода.

### Decision: Gate composition (4 проверки first-fail-wins)

| Option | Description | Selected |
|--------|-------------|----------|
| Композиция 4 проверок first-fail-wins (mirror D-411/D-507) | runs.status==success → xlsx_path non-empty → size_guard_passed → summary_text non-empty; GateDecision dataclass с route + failed_check + reason | ✓ |
| Single-check on runs.status (минимум — DELIVER-03 буквально) | Только проверка status; size-guard / xlsx-presence игнорируются — но это нарушает D-515 cascade invariant | |
| Boolean AND всех проверок (не first-fail) | Проще тестировать, но теряем structured reason для ops alert | |

**Auto-decision:** D-604 — 4-check composition. Rationale: D-515 cascade требует size_guard check; D-514 source-of-truth требует summary_text presence; first-fail-wins даёт structured reason для DRY ops-alert template (D-610).

### Decision: Delivery failure → runs.status policy

| Option | Description | Selected |
|--------|-------------|----------|
| runs.status stays 'success' on Telegram outage (D-605) | ARCHITECTURE «reporter independent of delivery» extends; xlsx на диске; deliver-run --run-id N recovers; uncaught exception всё ещё → run_writer.fail per DATA-05 | ✓ |
| runs.status flips to 'partial' on delivery fail | Нет такого статуса в текущей schema (Phase 2 D-201 только success/failed/running/partial — partial есть но используется только для viled_count<N gate-tripped); расширение не нужно | |
| runs.status flips to 'failed' on Telegram outage | Conflicts с ARCHITECTURE invariant; xlsx уже произведён успешно — это не run-failure | |

**Auto-decision:** D-605 — decouple. Rationale: ARCHITECTURE.md «reporter independent of delivery» переносится на delivery layer; Telegram outage = recovery-able state, not run-failure. Phase 7 Healthchecks ловит через отдельный `deliver.delivery_status` probe.

---

## Area 3 — Идемпотентность + delivered-state

### Decision: delivery_status enum

| Option | Description | Selected |
|--------|-------------|----------|
| 6-value enum (pending / delivered_business / delivered_ops_only / undelivered_telegram_unreachable / skipped_no_credentials / skipped_already_delivered) | Mirror D-514 7-key namespace discipline; покрывает все recovery scenarios; sentinels "" rejected per Pitfall 4 | ✓ |
| 3-value enum (pending / delivered / undelivered) | Слишком грубое: теряем business-vs-ops route в state; recovery CLI не может различать «надо повторить» vs «уже доставлено» | |
| Boolean delivered_business + boolean delivered_ops | Не enum, no Pitfall-4 sentinel discipline; коммутативные ошибки возможны (true/true состояние что значит?) | |

**Auto-decision:** D-606 — 6-value enum. Rationale: explicit state machine для idempotent recovery; Phase 7 Healthchecks может matchать enum values для health pings.

### Decision: stats namespace shape

| Option | Description | Selected |
|--------|-------------|----------|
| 8 deliver.* keys (delivery_status / route / business_caption_message_id / business_document_message_id / ops_message_id / attempt_count / last_error / delivered_at) | Mirror D-514 7-key discipline (1 extra для business 2-message split caption+document); Pitfall 4 sentinels ("" for str, -1 for int) | ✓ |
| 5 deliver.* keys (minimal) | Не хватает business_document_message_id / ops_message_id (Phase 7 cron может pin/unpin сообщения через ID — actionable artifact) | |
| 12 deliver.* keys (verbose) | Слишком много мелких полей; нарушает D-514 discipline | |

**Auto-decision:** D-607 — 8 keys. Single atomic patch_stats call (Pitfall 6 invariant); test canary 5-way namespace disjoint invariant.

### Decision: CLI re-send semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Per-enum branching: delivered_business → no-op (need --force); delivered_ops_only → re-send (ops чат tolerant); undelivered_* → full retry; skipped_no_credentials → re-validate ENV | Mirror D-412/D-509 standalone CLI + idempotency-aware; primary recovery scenario covered | ✓ |
| Always full re-send | Operator может дважды слать в business чат → confusion («что актуально?»); --force нужен explicit | |
| Always skip if delivery_status != pending | No recovery possible после Telegram outage; ломает DELIVER-04 manual recovery | |

**Auto-decision:** D-608 — per-enum branching + --force flag. Rationale: primary recovery scenario (Telegram outage воскресенье, ручной запуск в понедельник) работает без DB surgery.

---

## Area 4 — Ops alert: контент + формат + ENV-edge cases

### Decision: parse_mode

| Option | Description | Selected |
|--------|-------------|----------|
| HTML (escape только <>&) | html.escape() — одна вызов на dynamic field; Telegram HTML mode поддерживает <b>/<i>/<code>/<pre>/<a> | ✓ |
| MarkdownV2 | 16 спецсимволов нуждаются в escape (\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!); traceback с backticks вернёт ошибку парсинга | |
| Plain text (no parse_mode) | Теряем визуальный hierarchy (bold for run number, code for status); ops alerts становятся wall-of-text | |

**Auto-decision:** D-609 — HTML. Rationale: simplest correct escape model; aiogram DefaultBotProperties(parse_mode="HTML") единый для всех messages.

### Decision: alert structure

| Option | Description | Selected |
|--------|-------------|----------|
| Один template с reason-field placeholder (DRY) | build_ops_alert принимает gate_failed_check + dictionary reason→short-text mapping; same skeleton покрывает 4 gate-fail + exception fallback | ✓ |
| Per-reason templates (5 templates) | Boilerplate violation; legkий drift между templates при evolution | |
| Streaming structlog dump в text | Не читаемо для оператора; ops chat — для human triage | |

**Auto-decision:** D-610 — single template, reason-keyed. Template source-locked (mirror D-504); golden-file regression test.

### Decision: ENV-edge cases (DELIVER-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Asymmetric: TG_BOT_TOKEN fatal-loud; chat_id missing degrades по route (D-611) | Real-world flexible: token = критичный для любой Telegram активности; chat_id missing = degradable (можно ops-only или business-only). Phase 7 Healthchecks ловит exit code 3 | ✓ |
| All three required, fail-loud at startup | Cleaner but inconsistent с DELIVER-02 «missing ENV → ops chat alert» (если TG_OPS_CHAT_ID present и token валидный — можем послать alert о business chat missing) | |
| All three optional, скип if not configured | Опасно: тихий fail на production cron; pricing team не получает отчёт без уведомления | |

**Auto-decision:** D-611 — asymmetric handling. Rationale: best-effort delivery + DELIVER-02 letter («ops chat alert on missing ENV») + DELIVER-05 letter («ENV configures чата»).

### Decision: ENV file management

| Option | Description | Selected |
|--------|-------------|----------|
| .env.example в git, .env в .gitignore (D-612) | Mirror Phase 1 spike .env.local pattern; standard Python convention | ✓ |
| .env в git (encrypted via git-crypt) | Overhead; weekly cron — internal infra, не distributed deployment | |
| Только ENV-vars без файла (только в shell-profile / systemd Environment=) | Менее портативно для local dev; .env-pattern уже стандарт через python-dotenv (уже в deps) | |

**Auto-decision:** D-612 — .env.example + .gitignore. python-dotenv уже в deps; convention well-established.

---

## Claude's Discretion

Per CONTEXT.md §Claude's Discretion (полный список):
- Business caption length handling (split if > 1024 chars — отдельный send_message перед send_document)
- HTML escaping всех dynamic fields через html.escape()
- Dry-run output format (JSON to stdout, Unicode-safe encode per Plan 05-05)
- business_message_id vs business_document_message_id semantics (две Telegram messages с разными message_id)
- Mock aiogram Bot для тестов (НЕ respx — aiohttp под капотом)
- Test secrets via tests/conftest.py с mock-tokens / mock-chat-ids
- Skip-no-xlsx route handling (gate check #2 ловит)
- No alembic migration (D-220 invariant preserved)

## Deferred Ideas

Per CONTEXT.md §Deferred Ideas (полный список 18 пунктов):
- Email-channel доставки (DELIVER-V2-01) — параллельный wrapper
- Webhook / Slack доставка — same pattern
- weekly-run --skip-delivery / --delivery-only flags — rejected (D-608 covers)
- Telegram self-hosted server (2 GB limit) — rejected (oversize → ops alert per D-515 cascade)
- Pin/unpin messages, threads, reply-to — out of scope v1
- Delivery audit log в отдельной таблице deliveries — rejected (8 keys + structlog достаточно)
- deliver-run --re-summary — rejected (D-514 invariant; report-run --run-id N regenerates)
- Per-chat parse_mode override — rejected (D-609 single HTML)
- Rich progress reporter в Telegram — out of scope (weekly cron batch)
- Multi-language ops alerts (RU+EN) — out of scope (PROJECT.md команда русскоязычная)
- Delivery scheduling / queuing separate от run time — rejected (Phase 7 cron + Almaty TZ покрывает)
- Encryption / password-protected xlsx — out of scope
- Webhook listener mode — out of scope v1 (Phase 6 = send-only)
- Customizable summary template per-chat — rejected (D-504 single source)
- A/B testing summary форматов — out of scope
- Live integration tests против real Telegram test-bot — rejected (mock достаточно; production smoke = первый cron-run)
