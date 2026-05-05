---
tags: [decision, anti-bot, phase-1, methodology]
date: 2026-05-05
---

# Multi-geo измерение в спайке — laptop KZ плюс один proxy

Спайк меряет Patchright **с двух IP-геолокаций**: лэптоп пользователя (KZ-IP, Asia/Almaty) и один residential proxy (RU или EU через IPRoyal/Decodo trial).

## Почему

Single-geo даёт одну цифру и ноль уверенности, что tier воспроизведётся в проде. Goldapple — KZ-домен российского ритейлера; вероятно, KZ/RU IP получает либеральнее treatment, чем EU IP с Hetzner. Прод по research/STACK живёт на Hetzner EU — и если спайк смерил только KZ-laptop, мы выбираем tier для геолокации, которой в проде не будет.

Memo выдаёт **два числа** (например, «KZ-laptop: 98/100 без challenges, EU-proxy: 84/100, 6 challenges»). Это снимает неопределённость по prod-IP и даёт основание для финального вердикта.

## Что это меняет в спайке

- Перед стартом — регистрация IPRoyal или Decodo trial-аккаунта (не реактивно, заранее)
- Каждый Patchright-сценарий гонится дважды: один раз с laptop, один раз через proxy
- В memo появляется отдельная секция «IP geo sensitivity» с двумя метриками

## Связанные

- [[Tier 2 Patchright — стартовый tier для goldapple]]
- [[Residential proxies — нужны только для goldapple]]
- [[Деплой — Hetzner CX22 + system cron в Asia Almaty]]
- [[Phase 1 — throwaway спайк до production-кода]]
