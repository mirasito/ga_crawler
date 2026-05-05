---
tags: [pattern, reliability, validation]
date: 2026-05-05
---

# Hard-fail invariants на обязательных полях

Если у >5% продуктов в snapshot отсутствует обязательное поле (название, цена, URL) — `runs.status = 'failed'`. Отчёт в business-чат не идёт.

## Обязательные поля

- `name` — без названия нечего матчить
- `brand` — без бренда нечего фильтровать
- `current_price` — без цены отчёт бессмысленен
- `url` — без URL аналитик не может проверить

## Опциональные

- `was_price` (может быть legitimately null если нет скидки)
- `volume_raw` (некоторые товары без объёма — например, аксессуары)

## Зачем 5%, а не 0%

Реальный мир — на любом сайте 1–2% страниц битые. Допуск — амортизатор. Но 5% это **уже** сигнал: либо парсер сломался, либо сайт изменил вёрстку.

## Где гейт

После всего краула, перед нормализацией / matchingом. Запись:

```
if (null_rate(snapshots, run_id, required_fields) > 0.05) {
    runs.update(run_id, status='failed', failure_reason='HARD_FAIL_INVARIANT')
}
```

## Связанные

- [[Run-level sanity-gate перед доставкой]]
- [[Per-SKU isolation вместо fail-on-first]]
- [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]
