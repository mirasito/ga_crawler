---
tags: [integration, proxies, anti-bot]
date: 2026-05-05
---

# Residential proxies — нужны только для goldapple

Datacenter IP (включая Hetzner EU) даёт 40–60% успеха против Cloudflare/DataDome. Residential — 85–99%. Ценовая разница оправдана только там, где это нужно.

## Когда применять

| Сайт | Прокси | Причина |
|------|--------|---------|
| viled.kz | нет | Tier 0, [[Тиры anti-bot эскалации]] |
| goldapple.kz | **да, residential** | Tier 3+, almost certainly нужно |

## Провайдеры (2026)

Кандидаты, без коммитмента до Phase 1 спайка:

- **Decodo** (бывший Smartproxy) — recommended, ~$3–8/GB
- **IPRoyal** — дешевле, ~$1.75/GB
- **Bright Data** — дороже, более стабильный

Geo: KZ или RU residential. Бюджет: ~$0.50–$2 на один еженедельный запуск (предварительная оценка).

## Чего не использовать

- Datacenter proxies для goldapple — будут забаниваться
- Free / public proxies — сгорают быстрее, чем подключатся
- Captcha-solving сервисы — это уже enemy territory; лучше эскалировать tier ([[Тиры anti-bot эскалации]])

## Связанные

- [[goldapple.kz — источник цен конкурента]]
- [[Goldapple показывает Cloudflare-челлендж — эскалация tier]]
- [[Goldapple anti-bot — определяющий риск проекта]]
