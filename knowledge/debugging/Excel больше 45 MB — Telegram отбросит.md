---
tags: [debugging, telegram, delivery]
date: 2026-05-05
---

# Excel больше 45 MB — Telegram отбросит

## Симптом

- В ops-чат: `Telegram Bot API error: file_too_large` или `400 Bad Request`
- В business-чат: ничего

## Причина

Telegram Bot API лимит — **50 MB** на attachment. Pre-send проверка `REPORT-06` валит при ≥45 MB.

## Что делать

1. Открой xlsx локально — почему он такой большой?
2. Возможные виновники:
   - Conditional formatting на огромных диапазонах (`A1:A1048576` вместо `A1:A<last_row>`)
   - Embedded картинки (мы не должны их класть, см. anti-features в REQUIREMENTS)
   - Гигантская history-таблица на одном листе

## Solutions

- **Сократить scope листа** — только текущий run, не весь history
- **Использовать `xlsxwriter` constant_memory mode**, если строк > 100k
- **Разбить на несколько файлов** (один per лист) — крайний случай

## Превентивно

В Phase 5 Reporter сразу пишет так, чтобы файл был < 10 MB на типичный run. Если еженедельный объём растёт — сигнал, что отчёт надо переосмыслить (пагинация, фильтрация по top-N).

## Связанные

- [[Telegram Bot API — канал доставки отчёта]]
- [[Канал доставки — Telegram + Excel вложение]]
