---
tags: [decision, matching, normalization]
date: 2026-05-05
---

# Brand-alias YAML — это v1 deliverable, не v2

Таблица соответствий Cyrillic ↔ Latin вариантов брендов входит в Phase 2 (Phase 4 для интеграции в matching), а не "когда-нибудь".

## Почему

Strict-key матчинг по `(brand_norm, name_norm, volume_norm)` теряет 30–50% реальных пересечений на этом рынке без alias-таблицы:

```
viled.kz:    Estée Lauder
goldapple:   Эсте Лаудер
```

Это **разные брендовые слаги**. Никакая нормализация типа "lowercase + accent strip" их не сольёт.

## Структура

```yaml
- canonical: estee_lauder
  aliases:
    - "Estée Lauder"
    - "Estee Lauder"
    - "ESTEE LAUDER"
    - "Эсте Лаудер"
    - "эсте лаудер"
- canonical: l_oreal
  aliases:
    - "L'Oréal"
    - "Loreal"
    - "Лореаль"
    - "Л'Ореаль"
```

## Seed

Топ-50 брендов viled — обязательный seed. Каждый бренд проверяется глазами на goldapple (10–15 минут работы).

## Рост

Лог "бренды на goldapple, не найденные в alias-таблице" — еженедельная очередь ручного review. Каждую неделю добавляются новые алиасы по мере появления.

## Связанные

- [[Strict-key матчинг вместо fuzzy в v1]]
- [[Match-rate — KPI с первой недели]]
- [[Match-rate резко упал — проверь brand-alias таблицу]]
