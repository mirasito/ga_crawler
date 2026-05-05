---
tags: [integration, telegram, delivery]
date: 2026-05-05
---

# Telegram Bot API — канал доставки отчёта

Канал доставки еженедельного отчёта команде viled. См. [[Канал доставки — Telegram + Excel вложение]] для обоснования выбора.

## Библиотека

**aiogram 3.27** — async-нативная, чистый API.

Альтернатива (отвергнута): `python-telegram-bot` 22.x — тоже работает, но aiogram моложе и активнее в 2026.

## Метод

`bot.send_document(chat_id, FSInputFile("reports/2026-W18.xlsx"), caption=summary_text)`

## Лимиты

- **50 MB** — потолок размера документа от Bot API. Мы поднимаем явную ошибку при ≥45 MB. См. [[Excel больше 45 MB — Telegram отбросит]]
- **Rate limits** — при 429 уважаем `retry-after` header
- Telegram unreachable → отчёт остаётся на диске, помечается недоставленным

## Конфигурация

ENV:
- `TG_BOT_TOKEN`
- `TG_BUSINESS_CHAT_ID` — куда идут успешные отчёты
- `TG_OPS_CHAT_ID` — куда идут алерты о падениях

См. [[Два Telegram чата — ops и business]] — почему именно два.

## Pre-send sanity-gate

Если `runs.status != 'success'` — в business-чат **не отправляется ничего**, в ops уходит алерт. См. [[Run-level sanity-gate перед доставкой]].
