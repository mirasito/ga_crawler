---
tags: [pattern, reliability, observability]
date: 2026-05-05
---

# Run-level sanity-gate перед доставкой

Между завершением matchingа и отправкой отчёта в Telegram — серия assertion-ов на `runs` row. Если какой-то не пройден — отчёт **не отправляется в business-чат**, в ops-чат идёт алерт.

## Что проверяется

```
viled_count > N             (конфигурируется)
goldapple_count > M         (конфигурируется)
match_count > P             (конфигурируется)
null_rate < 5%              (Hard-fail invariants)
match_rate ≥ baseline-X%    (опционально, v2)
```

## Что происходит при провале

```
runs.status = 'failed'
runs.failure_reason = 'SANITY_GATE_VIOLATION: <details>'
ops_chat.alert(run_id, reason)
business_chat.send → ничего (skipped)
healthchecks.fail()
```

## Почему важно

Главный риск weekly-cron'а — "понедельничный пустой отчёт": сайт изменился → парсер вернул 0 SKU → matching сделал 0 совпадений → отчёт прошёл бы как "успех". Команда смотрит, не понимает, теряет доверие к инструменту.

Sanity-gate **гарантирует**, что бизнес видит либо настоящий отчёт, либо **ничего**. Промежуточные состояния идут только в ops.

## Связанные

- [[Два Telegram чата — ops и business]]
- [[Hard-fail invariants на обязательных полях]]
- [[Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать]]
- [[Match-rate — KPI с первой недели]]
