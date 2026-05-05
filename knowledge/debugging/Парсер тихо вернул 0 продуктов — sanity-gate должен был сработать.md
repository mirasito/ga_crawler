---
tags: [debugging, parsing, silent-failure]
date: 2026-05-05
---

# Парсер тихо вернул 0 продуктов — sanity-gate должен был сработать

## Симптом — два варианта

**Хороший:** sanity-gate сработал, в ops-чат пришёл алерт `runs.failure_reason = SANITY_GATE_VIOLATION`. Бизнес ничего не получил. ✓

**Плохой:** business-чат получил отчёт со словами "viled: 0 SKU, goldapple: 0 SKU, match: 0". Гейт пропустил. ✗

## Что делать в плохом сценарии

1. **Срочно** — найти, где gate не сработал
   ```sql
   SELECT * FROM runs WHERE run_id = <bad>;
   -- Должны были быть выставлены status='failed', failure_reason
   ```
2. **Корни** — почему получили 0 SKU?
   - Сайт изменил HTML / DOM? — посмотри сохранённый HTML-фикстуру
   - Cloudflare блокнул? — см. [[Goldapple показывает Cloudflare-челлендж — эскалация tier]]
   - Парсер упал в exception, но per-SKU isolation проглотил всё? — проверь логи
3. **Прокачать gate** — добавь миссинг-инвариант

## Корневая причина шире

Это **silent failure** — главный риск scraping-проектов. Вся [[Run-level sanity-gate перед доставкой]] архитектура придумана именно для этой ситуации.

Если happens — добавь регрессионный тест в test-suite (на синтетический пустой snapshot gate должен валить run).

## Превентивно

- **Nieder thresholds** — `viled_count > 1000` (а не `> 0`)
- **Match-count gate** — `match_count > 100` (а не просто > 0)
- **Hard-fail на null_rate** — см. [[Hard-fail invariants на обязательных полях]]
- **Deliberate-failure тест** — `SCHED-05`, прогоняй раз в квартал

## Связанные

- [[Run-level sanity-gate перед доставкой]]
- [[Hard-fail invariants на обязательных полях]]
- [[Per-SKU isolation вместо fail-on-first]]
- [[Два Telegram чата — ops и business]]
