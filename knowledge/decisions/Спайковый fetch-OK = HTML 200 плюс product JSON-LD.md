---
tags: [decision, phase-1, success-criteria, json-ld]
date: 2026-05-05
---

# Спайковый fetch-OK = HTML 200 плюс product JSON-LD

«Успешный fetch» в спайке = **HTML 200 + найден `<script type="application/ld+json">` с Product**. Threshold = **≥95/100** с разрешёнными 5xx/timeout-ретраями.

## Почему

Three options were on the table:
- HTML 200 без captcha — слишком мягко: парсер может упасть позже на пустом контенте
- current_price извлечён — слишком строго: выход за scope throwaway-спайка (это работа Phase 2/3 парсера)
- HTML 200 + JSON-LD найден — золотая середина: прокси для «прод реально сможет парсить», но без полноценного парсера

100/100 strict нереалистично для real-world краулеров 2026. ≥95/100 — норма для retry-able сетевого шума. <95% — tier failed, эскалация.

## Что это меняет в спайке

- Notebook-функция fetch'а возвращает не только HTML, но и `bool` «нашёл ли JSON-LD product»
- Memo фиксирует точные числа: «98/100 (97 с JSON-LD, 1 с HTML 200 без JSON-LD = парсер-fail signal)»
- Cloudflare/DataDome challenge, **auto-resolved** браузером, считается проходом — но challenge-rate отдельно логируется в memo

## Связанные

- [[JSON-LD первый, CSS резервный в парсерах]]
- [[Tier 2 Patchright — стартовый tier для goldapple]]
- [[Phase 1 — throwaway спайк до production-кода]]
- [[Run-level sanity-gate перед доставкой]]
