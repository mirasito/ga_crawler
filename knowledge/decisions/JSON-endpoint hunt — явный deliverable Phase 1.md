---
tags: [decision, phase-1, architecture, anti-bot]
date: 2026-05-05
---

# JSON-endpoint hunt — явный deliverable Phase 1

Спайк обязан **активно искать** у goldapple открытые JSON-источники: catalog API, `__NEXT_DATA__` script-tag, GraphQL, sitemap.xml. 30-60 минут в DevTools / mitmproxy.

## Почему

Если найдём рабочий JSON-эндпоинт без anti-bot — проект **полностью обходит** browser-tier. Phase 3 stack режется до Tier 0 (curl_cffi + JSON-парсинг), без Playwright, без Patchright, без proxy. Экономика проекта улучшается на порядок.

Дёшево по времени (час), огромный upside (вся архитектура Phase 3). Не делать это — оставить деньги на столе.

## Что это меняет в спайке

- Перед запуском Patchright-теста — обход sitemap и view-source 5-10 product/category-страниц с DevTools-Network
- Если JSON найден — memo пишет **новый сценарий** «Tier 0 + curl_cffi» как **primary** для Phase 3, Patchright становится резервом
- Если не найден — продолжаем по browser-tier плану без потерь

## Связанные

- [[Тиры anti-bot эскалации]]
- [[Tier 2 Patchright — стартовый tier для goldapple]]
- [[JSON-LD первый, CSS резервный в парсерах]]
- [[Стек Python — стандарт для скрейпинга]]
