---
tags: [decision, viled, crawl, pagination, api, breakthrough]
date: 2026-05-15
phase: 10
supersedes: "v1 limitation: viled SSR ignores page=N (10 URL variants probed 2026-05-07)"
---

# Viled API endpoint найден — items_content paginated через page+pageSize params

## TL;DR

`https://viled.kz/api/viled-catalog/v2/items/content?gender={men|women}&catalogId=1310&page=N&pageSize=60` — реальный backend endpoint который возвращает **полную пагинацию** AND **полные product fields** для viled catalog. Discovered 2026-05-15 через Camoufox click-page-2 + network intercept.

## Что узнали

| Endpoint | Status |
|---|---|
| `/men/catalog/1310?page=N` (SSR HTML) | **broken** — always returns page 1 |
| `/_next/data/{buildId}/.../catalog/1310.json?page=N` | **broken** — always returns page 1 |
| `/api/viled-catalog/v2/catalogs` | navigation tree, не paginated items |
| `/api/viled-catalog/v2/items` | 404 |
| **`/api/viled-catalog/v2/items/content?page=N&pageSize=60`** | **works** — full pagination + full data |

## Структура response

```json
{
  "content": [
    {
      "id": 408872,
      "brandName": "Frederic Malle",
      "groupName": "Парфюмерная вода Contre-Jour",
      "minPrice": 47400,
      "realMinPrice": 47400,
      "enableDiscount": false,
      "currency": "₸",
      "attributes": [
        {"name": "Размер", "value": "10 мл"},
        ...
      ]
    }
  ],
  "pageNumber": 2,
  "totalPages": 33,
  "total": 1971,
  "pageSize": 60
}
```

Total beauty viled: **7,602 items** (1971 men + 5631 women) через 127 catalog pages.

## Архитектурное последствие

`bin/viled_fast_crawl.py` использует этот endpoint для **bypass ViledFetcher.run_loop** (которая делает PDP fetches с 2s pause). Crawl полного viled каталога:
- **Old path:** 7,602 PDP × 2s pause = **4 часа 13 минут**
- **New path:** 127 API pages × 0.5s pause = **2 минуты 54 секунды**

API response уже содержит ВСЁ что extractит PDP parser (PARSE-01..06 fields). PDP fetch теперь избыточен для viled.

## Где применяется

- `bin/viled_fast_crawl.py` — operator-only standalone script
- Production weekly-run остаётся на ViledFetcher PDP path (CRAWL-01..06 contract не изменён)
- v1.4 / v2 backlog: интегрировать fast-API в production weekly-run за flag

## Почему 2026-05-07 probe ошибся

Probe 2026-05-07 проверял URL pagination на HTML/`_next/data` endpoints — оба сломаны. Probe **не пробовал** `/api/viled-catalog/v2/items/content` потому что endpoint грепом из static JS bundles не находился (webpack-encoded runtime URL construction). Discovered только через Camoufox click + network intercept.

## Как probe был неверен

Я (LLM) утверждал пользователю 2026-05-15 что "viled pagination fundamentally non-functional" после headless test который проверял неправильный endpoint. User поправил: "Нет все меняется вот я кликаю на сайте 2,3,4 все товары меняются не надо врать". Re-investigated → нашёл true endpoint.

Lesson: **client-side JS XHR endpoints не извлекаются grep'ом из static bundles** — webpack rewrites their paths. Always do real-browser click + network capture для confirmation.

## Связано

- [[2026-05-15 — Phase 10 closed + viled pagination unlocked + 4 production bugs fixed]] — session note
- [[Viled fast-API path bypasses PDP fetcher — 4hr → 3min]]
- Memory: `project_viled_crawl_scope.md` — scope locked to 2 catalogs (men+women), pagination unlocked 2026-05-15
