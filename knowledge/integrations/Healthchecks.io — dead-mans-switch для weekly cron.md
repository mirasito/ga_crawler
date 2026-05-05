---
tags: [integration, monitoring, ops, healthchecks]
date: 2026-05-05
---

# Healthchecks.io — dead-mans-switch для weekly cron

Внешний сторож, который кричит, когда наш cron **не запустился**. Обязательно для weekly job — без него пропуск запуска заметишь только в понедельник, когда команда не получит отчёт.

## Зачем

Cron-задача может молча не сработать. Самой задаче не из чего сказать "я не запустилась". Решение — внешняя система ждёт пинг.

## Эндпоинты

В run-loop:

```
curl https://hc-ping.com/<uuid>/start    # на старте
curl https://hc-ping.com/<uuid>          # на success
curl https://hc-ping.com/<uuid>/fail     # на любой failure
```

Schedule в Healthchecks: weekly на Asia/Almaty, grace period 2h.

## Алерты

- Email + Telegram-алерт в ops-чат при пропущенном пинге
- Алерты на `/fail` пинги тоже летят в ops

## Связанные

- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]]
- [[Cron не сработал — проверь CRON_TZ и Healthchecks ping]]
- [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]
