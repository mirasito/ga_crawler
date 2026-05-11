---
tags: [decision, phase-6, delivery, telegram, aiogram, async]
date: 2026-05-12
decision_id: D-601, D-602
phase: 06-telegram-delivery
status: locked
---

# aiogram 3.27 + asyncio.run() sync wrapper — SDK для Telegram delivery

## Утверждение

Phase 6 использует **aiogram 3.27.x** как Telegram SDK. Sync `runners/delivery_run.py` оборачивает асинхронный send через `asyncio.run(_send_delivery_async(...))` — mirror goldapple precedent в `main_run.py:224` (`g_result = asyncio.run(run_goldapple_phase(...))`).

Pin: `aiogram>=3.27,<4.0`.

## Контекст

CLAUDE.md §Stack уже зафиксировал aiogram («async-native; cleaner API for send file + caption; type-hinted; FSInputFile»). Альтернативы рассмотрены и отвергнуты:

| Альтернатива | Почему отвергнута |
|---|---|
| python-telegram-bot 22 (sync) | Sync API доступен, но второй толстый dep вместо переиспользования aiogram async pattern, который уже используется через goldapple_run |
| Raw httpx.post к Bot API | Экономия ~5 MB и 0 deps; но теряем retry-after parsing + manual multipart `send_document` + error mapping. 30 LOC ergonomic loss, не стоит риска |
| asyncio в main_run полностью | Большой рефакторинг — превращать sync matcher/reporter в async; единственная польза — убрать nested event loop |

## Почему

- **CLAUDE.md lock:** stack table уже зафиксирован — minimal cognitive overhead для оператора
- **Type safety:** `aiogram.exceptions.TelegramRetryAfter`, `TelegramNetworkError`, `TelegramServerError` — distinct exception classes для разной обработки (D-603 retry policy use)
- **FSInputFile pattern:** `send_document(chat_id, FSInputFile(xlsx_path), caption=summary)` — single line; raw httpx требует multipart construction
- **Goldapple precedent:** `main_run.py:224` уже делает `asyncio.run(run_goldapple_phase(...))`. Phase 6 mirror — second nested event loop в том же sync pipeline OK, протестировано Phase 3+
- **DefaultBotProperties(parse_mode="HTML"):** один bot config для всех messages (D-609 HTML lock)

## Когда применять

- Внутри `delivery/telegram_client.py`: `async with Bot(token, default=DefaultBotProperties(parse_mode="HTML")) as bot:` context manager — auto-close session
- Внутри `runners/delivery_run.py` (sync): `d_result = asyncio.run(_send_delivery_async(...))` — пятая domain phase в sync orchestrator, симметрия с goldapple_run

## Связано

- [[2026-05-12 — Phase 6 contexted — Telegram delivery decisions D-601..D-616]] *(session)*
- [[Telegram Bot API — канал доставки отчёта]] *(integration ref)*
- [[Tier 2 Patchright — стартовый tier для goldapple]] *(superseded — но goldapple_run async pattern всё ещё актуален как precedent)*

## Test pattern

Mock `aiogram.Bot.send_message` + `send_document` напрямую через pytest-mock; respx НЕ подходит (aiogram использует internal aiohttp session, не httpx). Synthetic Run fixture mirror Plan 05-04 `synthetic_report_run` — populated с `runs.stats.report.*` для gate-pass/gate-fail scenarios.

## Source

`.planning/phases/06-telegram-delivery/06-CONTEXT.md` §Decisions §"SDK + sync/async integration" D-601 + D-602.
