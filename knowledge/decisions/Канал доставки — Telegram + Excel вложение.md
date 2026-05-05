---
tags: [decision, delivery, ux]
date: 2026-05-05
---

# Канал доставки — Telegram + Excel вложение

Текстовая сводка в Telegram-сообщении + xlsx-вложение тем же постом. Никаких email, дашбордов, веб-UI на v1.

## Почему

- **Команда живёт в Telegram** — выбор пользователя, не догадка
- **Excel — стандарт для коммерческой работы** — фильтры, сортировка, ad-hoc анализ за 30 секунд
- **Сводка в тексте** — даёт understanding на ходу, без открытия файла
- **Один канал** — нет фрагментации внимания

## Что в сводке (текст)

`viled_count` · `goldapple_count` · `match_count` · **`match_rate %`** ([[Match-rate — KPI с первой недели]]) · размер ассортиментного разрыва · top-3 наибольшие дельты · число промо у goldapple

## Что в xlsx (файл)

Листы: `Summary` · `Per-SKU deltas` · `Assortment gaps` · `Goldapple promos`. Conditional formatting (зелёный — viled дешевле, красный — viled дороже), frozen panes, autofilter, русские заголовки.

## Альтернативы (отвергнуты)

- **Email** — медленнее, теряется в потоке, requires SMTP infra
- **Slack** — команда не в Slack
- **PDF** — не редактируется, ad-hoc не сделать
- **Web dashboard** — overkill для weekly batch reporting

## Связанные

- [[Telegram Bot API — канал доставки отчёта]]
- [[Два Telegram чата — ops и business]]
