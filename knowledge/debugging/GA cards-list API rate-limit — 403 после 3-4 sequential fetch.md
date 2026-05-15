---
tags: [debugging, anti-bot, rate-limit, cards-list]
date: 2026-05-16
---

# GA cards-list API rate-limit — 403 после 3-4 sequential fetch

## Симптом
Через `page.evaluate('fetch /front/api/catalog/cards-list')` в Camoufox-сессии:
- pages 1-3 проходят 200 OK за ~500ms каждая
- **page 4 возвращает HTTP 403** даже с 2.8s паузой между запросами
- 12s cooldown + retry не помогает
- pageSize > 20 игнорируется (сервер всегда даёт 20 карточек)

## Что НЕ работает
- Прямой `curl_cffi` POST с impersonate=chrome — 403 сразу (нет cookies)
- `page.request.post()` с body — 403 после 3 calls
- Increase `pageSize` — silently ignored, сервер режет до 20

## Что работает
- **Brand-page scroll** — SPA сам стучит cards-list через Intersection Observer, наследует cookies + timing. Эта же сессия даёт 12-15 cards-list calls без 403 если водить мышкой / скроллить медленно.
- **product-card/base/v3** не имеет такого rate-limit (probe-confirmed; SPA fires once per PDP, мы могли вызывать 45+ раз подряд на Bobbi Brown без отказов)

## Workaround в enumerator
1. Hybrid mode: scroll-based как primary (`enumerate_brand`), API top-up как fallback для крупных брендов через `enumerate_brand_hybrid`
2. Для multi-variant capture используем product-card API (без rate-limit issues)
3. consecutive_403 counter + 12s cooldown + retry-once в API path — частично спасает мелкие бренды

## Не закрыто
- Bobbi Brown: рейт-лимит на странице 4 cards-list (8 страниц всего). Получили 60 / 115 SKU чистым API. Hybrid режим (scroll сначала, API top-up) — пока compromise.
- Возможные пути: rotate Camoufox sessions per N brands, добавить mouse-move events в scroll-цикле, использовать `page.mouse.wheel()` вместо `window.scrollBy()`.

## Связано
- [[cards-list возвращает 1 itemId на семью variant-ов]]
- [[Brand-pages discovery через cards-list + product-card API]]

## Сорс
matcher-review-2026-05-15..16 probe-sequence: `inbox/ga_brand_xhr/`, `inbox/ga_cards_api/`.
