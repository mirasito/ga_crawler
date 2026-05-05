---
tags: [integration, goldapple, scraping, anti-bot]
date: 2026-05-05
---

# goldapple.kz — источник цен конкурента

Крупный российский ритейлер косметики, расширившийся в Казахстан. Десятки тысяч SKU.

## Что мы извлекаем

- Название, бренд, объём/вес, текущая цена, цена до скидки, наличие, URL
- **Только публичная цена** (без логина) — см. [[Фиксируем только публичную цену, без Gold Card]]

## Что мы НЕ парсим

- Цены под Gold Card / личным кабинетом — риск блокировки аккаунта
- Полный каталог — фокус только на брендах, присутствующих на viled.kz. См. [[Парсим viled целиком, goldapple только по пересекающимся брендам]]
- Картинки и описания — не нужны для ценового сравнения

## Anti-bot

Crepe-paper assumption: Cloudflare или DataDome. **Не подтверждено** до Phase 1 спайка.

См. [[Goldapple anti-bot — определяющий риск проекта]] и [[Тиры anti-bot эскалации]].

## Ключевые гипотезы под проверку в Phase 1

1. Какой именно anti-bot vendor (Cloudflare / DataDome / custom)
2. Есть ли JSON catalog endpoint, минующий UI (огромная экономия на Playwright)
3. Брендовые страницы вида `goldapple.kz/brand/<slug>` — существуют?
4. Сколько страниц у типичного бренда (бюджет прокси)
5. Достаточно ли EU-IP с Hetzner или нужны KZ/RU residential

## Идентичность товара

`(brand_norm, name_norm, volume_norm)` hash. **Не URL** — слаги меняются. См. [[Append-only snapshots без in-place update]].

## Связанные

- [[Residential proxies — нужны только для goldapple]]
- [[Goldapple показывает Cloudflare-челлендж — эскалация tier]]
- [[viled.kz — собственный каталог и источник пересекающихся брендов]]
