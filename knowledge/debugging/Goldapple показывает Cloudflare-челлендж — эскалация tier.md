---
tags: [debugging, anti-bot, goldapple]
date: 2026-05-05
---

# Goldapple показывает Cloudflare-челлендж — эскалация tier

## Симптом

- Page content содержит `cf-mitigated`, `Just a moment...`, `cf_chl_jschl`
- HTTP 403 / 503 со специфичным cookie `__cf_bm`
- Страница рендерится, но без целевого контента
- Отвечает быстро, но всегда одной и той же "ждите" страницей

## Диагностика

```python
if "cf-chl" in response.text or response.status_code == 403:
    log.warning("cloudflare_challenge", url=url, tier=current_tier)
    raise CloudflareChallenge()
```

## Решение

Эскалация на следующий tier — см. [[Тиры anti-bot эскалации]]:

| Если был | Стало |
|----------|-------|
| Tier 1 (vanilla Playwright) | Tier 2 (Patchright) |
| Tier 2 | Tier 3 (+ residential proxy) |
| Tier 3 | Tier 4 (Camoufox) |

## Чего не делать

- **Не покупать captcha-solving сервис** — корни проблемы не решает, прячет
- **Не повышать concurrency** — наоборот, снижает
- **Не использовать datacenter proxies** — забанят сразу
- **Не подмешивать `playwright-stealth v1.x`** — не работает

## Превентивно

В Phase 1 спайке нужно **эмпирически** определить минимальный рабочий tier и зафиксировать его. Не угадывать.

## Связанные

- [[Тиры anti-bot эскалации]]
- [[Residential proxies — нужны только для goldapple]]
- [[Goldapple anti-bot — определяющий риск проекта]]
