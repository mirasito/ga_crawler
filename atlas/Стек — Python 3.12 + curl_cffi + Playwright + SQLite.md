---
tags: [atlas, stack, python]
date: 2026-05-05
---

# Стек — Python 3.12 + curl_cffi + Playwright + SQLite

Опинионированно скучный стек везде, кроме anti-bot слоя.

## Ядро

| Слой | Выбор | Версия | Зачем |
|------|-------|--------|-------|
| Runtime | Python | 3.12 | Стандарт 2026 |
| Deps | uv | latest | 10–100× быстрее pip+venv |
| HTTP | curl_cffi | 0.15 | TLS/JA3 fingerprinting; defeat дешёвого anti-bot |
| Headless | Playwright + Patchright | 1.57 | См. [[Тиры anti-bot эскалации]] |
| Парсинг HTML | selectolax | latest | 10–30× быстрее BeautifulSoup |
| ORM | SQLModel | latest | Тонкий слой над SQLAlchemy |
| БД | SQLite (WAL) | 3.x | См. [[БД — append-only snapshots с run_id]] |
| Excel | pandas + xlsxwriter | 2.x | Conditional formatting, frozen panes |
| Telegram | aiogram | 3.27 | `send_document` async |
| Logging | structlog | latest | JSON-логи с `run_id` контекстом |
| Schedule | system cron | — | См. [[Деплой — Hetzner CX22 + system cron в Asia Almaty]] |

## Не использовать

- `requests` (нет TLS-imitation), `cloudscraper` (заброшен), `playwright-stealth v1.x` (не работает в 2026)
- Selenium (медленно, заметно), undetected-chromedriver
- Celery / Prefect / APScheduler (overkill для одного weekly job)
- Heroku / Fly.io / Render для batch cron — не их юзкейс

## Связанные

- [[Стек Python — стандарт для скрейпинга]]
- [[Residential proxies — нужны только для goldapple]]
- `.planning/research/STACK.md`
