---
tags: [decision, anti-bot, phase-1, patchright]
date: 2026-05-05
---

# Tier 2 Patchright — стартовый tier для goldapple

Спайк начинается **сразу с Tier 2 (Patchright)**. Vanilla Playwright (Tier 1) скипаем как заведомо проваленный.

## Почему

Research/PITFALLS и research/STACK сходятся: vanilla Playwright в 2026 детектится Cloudflare и DataDome из коробки. День, потраченный на ожидаемо-проваленный Tier 1, — впустую.

Patchright — drop-in замена Playwright с пропатченным fingerprint'ом. Если он проходит, Phase 3 живёт без proxy. Если фейлит — эскалируем на Tier 3 (+residential).

## Что это меняет в спайке

- Первый код — `from patchright.async_api import async_playwright`, не `from playwright...`
- Если Patchright блокируется на 5 подряд запросах или встречает captcha — **немедленная** эскалация на Tier 3
- Tier 4 (Camoufox / managed unblocker) — только если и Tier 3 не справится

## Связанные

- [[Тиры anti-bot эскалации]]
- [[Goldapple anti-bot — определяющий риск проекта]]
- [[Phase 1 — throwaway спайк до production-кода]]
- [[Multi-geo измерение в спайке — laptop KZ плюс один proxy]]
