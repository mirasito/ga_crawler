---
tags: [atlas, architecture, monolith]
date: 2026-05-05
---

# Архитектура — модульный монолит на pipe-and-filter

Один Python-пакет, один процесс, один запуск в неделю. Стадии — чистые функции; побочные эффекты только в Storage / Reporter / Delivery.

## Конвейер

```
Crawl → Parse → Normalize → Match → Snapshot → Report → Deliver
```

## Стадии

| Стадия | Чистая? | Ответственность |
|--------|---------|-----------------|
| Crawler (per-site) | да | URL discovery + HTML/JSON fetch |
| Parser (общий) | да | Извлечение полей через [[JSON-LD первый, CSS резервный в парсерах]] |
| Normalizer | да | Бренд через [[Brand-alias YAML — это v1 deliverable, не v2]], объём через [[Volume как value-object с multipack-флагом]] |
| Matcher | да | SQL JOIN по `(brand_norm, name_norm, volume_norm)` |
| Storage | нет | [[БД — append-only snapshots с run_id]] |
| Reporter | нет | xlsx + summary, читает только из БД |
| Delivery | нет | [[Telegram Bot API — канал доставки отчёта]], [[Два Telegram чата — ops и business]] |

## Почему монолит, не сервисы

- 1 запуск в неделю → нет повода масштабировать процессы
- БД — единая шина интеграции; любая фаза рестартуется по `run_id`
- See: [[Append-only snapshots без in-place update]]

## Почему не один скрипт

Чистые стадии = тестируемость через HTML-фикстуры. Без модульности парсер и матчер срастаются в спагетти.

См. также: `.planning/research/ARCHITECTURE.md`
