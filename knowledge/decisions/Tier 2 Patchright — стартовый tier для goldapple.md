---
tags: [decision, anti-bot, phase-1, patchright, superseded]
date: 2026-05-05
superseded_by: "Camoufox а не Patchright — engine для goldapple"
superseded_date: 2026-05-06
---

# Tier 2 Patchright — стартовый tier для goldapple

> **⚠ SUPERSEDED 2026-05-06 (день после принятия) — см. [[Camoufox а не Patchright — engine для goldapple]].**
>
> Эмпирический результат спайка: **Patchright + KZ-laptop = 0/7 gate-pass** против goldapple. Anti-bot vendor оказался **GroupIB / F.A.C.C.T.**, а не Cloudflare/DataDome (см. [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]]) — Patchright-бенчмарки в CLAUDE.md targetят Cloudflare/DataDome/Akamai и для GroupIB не транслируются. **Camoufox** (Firefox stealth) проходит 3/3 instantly без прокси.
>
> Замена tier-стратегии: skip Tier 1, **skip Tier 2 (Patchright)**, **start at Camoufox**. Tier 4 managed unblocker — контингенция если Camoufox сломается под vendor update.
>
> Историческая часть ниже сохранена как audit trail логики на момент принятия решения.

---

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
