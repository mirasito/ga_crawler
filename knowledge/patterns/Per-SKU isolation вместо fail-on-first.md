---
tags: [pattern, reliability, error-handling]
date: 2026-05-05
---

# Per-SKU isolation вместо fail-on-first

Падение одного product fetch / parse не валит весь запуск. Ошибки логируются с `sku_id`, остальные SKU продолжают обрабатываться.

## Реализация

```python
for url in product_urls:
    try:
        snapshot = parse(fetch(url))
        store(run_id, snapshot)
    except ParseError as e:
        log.warning("sku_failed", sku=url, error=str(e), run_id=run_id)
        runs_table.increment_counter(run_id, "failed_skus")
```

## Когда всё-таки падать

Per-SKU isolation **не отменяет** sanity-gate. См. [[Run-level sanity-gate перед доставкой]] и [[Hard-fail invariants на обязательных полях]]:

- Если 5%+ SKU имеют пустые обязательные поля — `runs.status = 'failed'`
- Если total_count ниже порога — `runs.status = 'failed'`

То есть: продолжаем обрабатывать всё, потом смотрим итог в целом.

## Антипаттерн

```python
# плохо
for url in product_urls:
    snapshot = parse(fetch(url))  # crash here = весь запуск умер
    store(run_id, snapshot)
```

При тысячах SKU **гарантированно** один из них сломается на странной странице. Без isolation — теряем весь weekly snapshot.

## Связанные

- [[Append-only snapshots без in-place update]]
- [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]
