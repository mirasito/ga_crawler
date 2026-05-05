---
tags: [pattern, delivery, observability]
date: 2026-05-05
---

# Два Telegram чата — ops и business

Один бот, **два разных `chat_id`**. В business-чат летят успешные отчёты команде viled. В ops-чат летят падения, sanity-gate violations, missing ENV.

## Зачем разделять

Если падения и отчёты в одном чате:
- Команда привыкает к шуму и перестаёт читать
- Реальный отчёт теряется среди алертов
- Бизнес видит "[ERROR] Cron failed" — теряет доверие к инструменту

С двумя чатами:
- Бизнес видит **только** валидные отчёты
- Ops видит **только** проблемы
- Тишина в ops-чате = всё хорошо

## ENV

```
TG_BOT_TOKEN=...
TG_BUSINESS_CHAT_ID=...
TG_OPS_CHAT_ID=...
```

## Маршрутизация

```python
if runs.status == 'success':
    business.send_document(report_path, caption=summary)
else:
    ops.send_message(f"FAILED run {run_id}: {failure_reason}")
```

См. также [[Run-level sanity-gate перед доставкой]] — он принимает решение, куда направлять.

## Связанные

- [[Telegram Bot API — канал доставки отчёта]]
- [[Канал доставки — Telegram + Excel вложение]]
