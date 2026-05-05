---
tags: [decision, schema, stock]
date: 2026-05-05
---

# Stock state — enum в схеме, bool в отчёте

В схеме храним полное состояние через enum, в отчёте v1 сводим к булю "в наличии / нет".

## Enum

```
IN_STOCK
OUT_OF_STOCK
UNAVAILABLE        # сайт не вернул статус, но страница существует
DELISTED           # 404 — товар снят с продажи
URL_CHANGED        # старый URL редиректит куда-то новое
UNKNOWN            # парсер не смог определить
```

## Почему не bool в схеме

Схлопывая всё в "in/out" мы теряем три разных downstream-бага:
- `OOS` ≠ `DELISTED` — для assortment gap-репорта это разные истории
- `URL_CHANGED` маскируется под `OOS`, что даёт false delisting
- `UNKNOWN` ≠ `OOS` — это debug-сигнал парсера

## Почему bool в отчёте v1

Команде viled на v1 не нужны 6 состояний — нужно "купить или нельзя". Сводим: `IN_STOCK` → true, всё остальное → false.

## Дешевизна сейчас, дорогизна потом

Backfill enum'а из исторического `bool` невозможен — нужно re-crawling. Лучше capture сразу, surface потом.

## Связанные

- [[БД — append-only snapshots с run_id]]
- [[was_price хранится в схеме v1, даже если не выводится]]
