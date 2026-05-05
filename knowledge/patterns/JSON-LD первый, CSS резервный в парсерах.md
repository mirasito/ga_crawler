---
tags: [pattern, parsing]
date: 2026-05-05
---

# JSON-LD первый, CSS резервный в парсерах

Парсер всегда пробует достать поле из `<script type="application/ld+json">` (schema.org `Product`). Только если JSON-LD отсутствует или неполон — fallback на CSS-селекторы.

## Почему

- **Стабильнее** — JSON-LD меняется реже, чем DOM-структура
- **Точнее** — `Product.offers.price` — это **по определению** текущая цена, а не "поле с классом `.price-current`, которое разработчик может переименовать"
- **Меньше парсер-дрифта** — основной источник [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]

## Каскад извлечения

1. **JSON-LD** (`<script type="application/ld+json">`) — `name`, `brand.name`, `offers.price`, `offers.priceCurrency`, `offers.availability`
2. **`__NEXT_DATA__` / inline JSON** — для Next.js / SPA-сайтов
3. **CSS-селекторы** (через selectolax) — последний резерв

## Hard rejects на этапе CSS-fallback

См. также [[Wrong price field — Gold Card vs strikethrough vs from]]:

```
deny_classes = re.compile(r"(old|was|crossed|club|gold|member|loyalty|from)", re.I)
```

Любое поле, у которого хоть один CSS-класс матчится — отвергается, парсер ищет дальше.

## Связанные

- [[Hard-fail invariants на обязательных полях]]
- [[Run-level sanity-gate перед доставкой]]
- [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]
