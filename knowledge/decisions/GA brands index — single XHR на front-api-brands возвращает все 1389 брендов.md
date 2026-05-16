---
tags: [decision, anti-bot, goldapple, brand-slugs, api-discovery]
date: 2026-05-16
---

# GA brands index — это single XHR на `/front/api/brands` возвращает все 1389 брендов

## Что

`https://goldapple.kz/brands` рендерит SPA, и в момент initial load выполняет **один** XHR-вызов `GET https://goldapple.kz/front/api/brands?locale=ru`, который возвращает JSON со всеми **1 389 брендами** магазина:

```json
{
  "data": {
    "brands": [
      {
        "id": "29171",
        "label": "100BON",
        "labelOriginal": "100BON",
        "url": "/brands/100bon"
      },
      …
    ]
  }
}
```

`url` — каноническая slug-форма (`/brands/<slug>`); `label` / `labelOriginal` — display-имя. Search-input на странице фильтрует **клиентски** (search-typing наблюдалось как XHR delta = 1, и тот один — debounced refire того же `/front/api/brands?query=tom`, не critical для discovery).

## Почему это важно

До 2026-05-16 vault содержал «8 unresolved brand-slug-ов» (Tom Ford, Kiehl's, Givenchy, Jo Malone, Ex Nihilo, Kenzo, Amouage, Creed, Starskin). Probe v1 (`scripts/probe_ga_brands_index.py`) пытался regex-scrape `href="/brands/..."` ссылок из rendered HTML — захватывал только 8 Cyrillic-name slugs потому что список виртуализирован (React-windowed) и в DOM присутствуют только visible cards.

Authoritative API list позволяет **за один request** разрешить любые slug-mismatch'и через normalized-label lookup (`scripts/resolve_unmatched_brands_v2.py`).

## Как применять

1. Запустить `uv run python scripts/probe_ga_brands_index_v2.py` — за ~20 сек захватит `/front/api/brands` в `inbox/ga_brands_index/v2_xhr_bodies/`.
2. Запустить `uv run python scripts/resolve_unmatched_brands_v2.py` против Norm06-review-queue → emits proposed override lines для `data/ga_brand_slugs.yaml`.
3. Default-kebab failure mode почти всегда — это suffix mismatch: viled добавляет `-beauty`/`-perfume`/`-london`, GA snima. Resolver знает эти suffixes.

## Что не работает

- Camoufox-detection всё ещё применяется к `/front/api/brands` если бить напрямую через curl_cffi — endpoint защищён теми же anti-bot правилами что cards-list. Поэтому ходим через `page.evaluate('fetch(...)')` либо через response-listener при `goto('/brands')`. См. [[Brand-pages discovery через cards-list + product-card API]] — паттерн идентичный.
- 13 viled brand_norms по которым resolver вернул zero hits — действительно отсутствуют на goldapple.kz. Дальнейшая slug-археология бесполезна.

## Связанные коммиты

- `e73ebe7 feat(brand-slugs): resolve 8 unmatched viled brands via /front/api/brands index` — добавил 8 overrides в `data/ga_brand_slugs.yaml`, оба probe-скрипта.

## Связано

- [[Brand-pages discovery через cards-list + product-card API]] — тот же anti-bot маршрут (`page.evaluate('fetch(...)')`)
- [[Production wiring drift — runner ссылается на устаревшую функцию когда добавляется новая variant]]
