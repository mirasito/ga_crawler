---
tags: [pattern, anti-bot, scraping]
date: 2026-05-05
---

# Тиры anti-bot эскалации

Не выбираем стратегию заранее — эскалируем тир по мере необходимости. Дешевле всего проще всего, потом сложнее по нарастающей.

## Тиры

| Tier | Что | Цена | Пример сайта |
|------|-----|------|--------------|
| 0 | `curl_cffi` (TLS-imitation), без прокси | бесплатно | viled.kz |
| 1 | Vanilla Playwright + realistic UA | бесплатно | большинство e-commerce |
| 2 | **Patchright** (drop-in для Playwright) | бесплатно | сайты с Cloudflare easy mode |
| 3 | Patchright + residential proxy (Decodo / IPRoyal) | $0.50–$2/run | Cloudflare hard / DataDome |
| 4 | Camoufox / Scrapling StealthyFetcher / managed unblocker (ZenRows / Bright Data) | $5–50/run | сайты с активной CAPTCHA |

## Принципы

1. **Никакого playwright-stealth v1.x** — заброшен, не работает в 2026
2. **Никаких datacenter proxies для goldapple** — банят моментально
3. **Один tier на всё goldapple, не per-page** — иначе сложно дебажить
4. **Tier выбирается в Phase 1 спайке** — эмпирически, не по чтению блогов

## Эскалация в эксплуатации

Если сайт начал ловить нас на текущем tier — повышаем. **Не** идём в captcha-solving сервисы — это сигнал, что мы на enemy territory.

## Связанные

- [[Phase 1 — throwaway спайк до production-кода]]
- [[Residential proxies — нужны только для goldapple]]
- [[Goldapple показывает Cloudflare-челлендж — эскалация tier]]
- [[Goldapple anti-bot — определяющий риск проекта]]
