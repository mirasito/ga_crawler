---
tags: [decision, stack, python]
date: 2026-05-05
---

# Стек Python — стандарт для скрейпинга

Выбор языка зафиксирован: Python 3.12. См. конкретные библиотеки в [[Стек — Python 3.12 + curl_cffi + Playwright + SQLite]].

## Почему

- **Самая богатая экосистема** — Playwright, curl_cffi, Patchright, Camoufox, selectolax, Scrapy — всё нативно
- **pandas + xlsxwriter** — индустриальный стандарт для Excel-генерации
- **Простота хостинга** — uv + venv, никакой компиляции, легко на любом VPS
- **aiogram** — first-class Telegram bot library

## Альтернативы (отвергнуты)

- **Node.js / TypeScript** — Playwright тоже есть, но curl_cffi-аналог хуже, экосистема Excel слабее
- **Go** — быстро, но anti-bot тулинг беднее
- **Rust** — overkill для batch скрипта

## Версия

3.12 — потому что 3.13 ещё не везде стабилен с native-deps вроде Playwright; 3.11 — устаревает.

## Связанные

- [[Стек — Python 3.12 + curl_cffi + Playwright + SQLite]]
- [[Архитектура — модульный монолит на pipe-and-filter]]
