---
tags: [priorities, current-focus, phase-1]
date: 2026-05-06
---

# Текущие приоритеты — Phase 1 спайк

**Сейчас:** Phase 1 на 6/12 планов + Camoufox-side-spike. **Tier-стратегия перевёрнута** — см. session [[2026-05-06 — Camoufox побеждает GroupIB, Phase 1 re-route]]. Осталось ~1.5 ч wall-clock до закрытия Phase 1.

## Что осталось (минимум для закрытия)

1. **01-08 переписать на Camoufox** + прогнать на 100 URLs (D-13 ≥95/100, D-14 JSON-LD, D-15 challenge-rate). 30-60 мин.
2. **01-11 MEMO finalize** с обновлённым verdict: Tier 2 = Camoufox direct, no proxy.
3. **01-12 wrap-up** — Obsidian copy MEMO в `knowledge/decisions/`, project skill, STATE update.

## Что НЕ делаем (snapped из плана)

- ❌ **01-03 IPRoyal trial** — прокси не нужен, Camoufox без него работает ([[Camoufox а не Patchright — engine для goldapple]])
- ❌ **01-09 EU-proxy multi-geo** — value-of-info низкий когда фингерпринт сам решает
- ❌ **01-10 Tier 3 escalation** — триггер не сработает (Tier 2 = Camoufox проходит)

## Что уже готово (closed)

| Plan | Что дало |
|---|---|
| 01-01 ✓ | spike skeleton |
| 01-02 ✓ | uv project + curl_cffi 0.15 + patchright 1.59 + selectolax + chromium |
| 01-04 ✓ | RECON-04: viled чистый robots/ToS, goldapple глобально gated. Rate-limits committed. |
| 01-05 ✓ | RECON-03 part 1: sitemap.xml plain-deliverable, 112k URLs, ~600 MB/week budget |
| 01-06 ✓ | JSON-endpoint hunt: Tier 0 мёртв для product data ([[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]]); vendor ID = GroupIB |
| 01-07 ✓ | RECON-02: viled 15/15 HTTP 200, `__NEXT_DATA__` extraction patterns заморожены |
| 01-06b spike ✓ | Camoufox 3/3 instantly. **THE big finding.** |

## Ключевые решения (живущие)

- [[Camoufox а не Patchright — engine для goldapple]] — engine для Phase 3 production
- [[Goldapple anti-bot — это GroupIB FACCT, не Cloudflare]] — vendor ID
- [[Tier 0 для goldapple — мёртв, JSON endpoints за gate'ом]] — но sitemap живой → hybrid stack
- [[Multi-geo измерение в спайке — laptop KZ плюс один proxy]] — multi-geo gap признаётся в MEMO (не выполнялся, см. [[Camoufox...]] rationale)
- [[JSON-endpoint hunt — явный deliverable Phase 1]] — выполнено, Tier 0 не виабелен

## Superseded решения (сохранены как audit trail)

- ~~[[Tier 2 Patchright — стартовый tier для goldapple]]~~ — см. supersedes header в файле

## Phase 3 stack preview (после MEMO finalize)

```
goldapple enumeration   : curl_cffi + sitemap.xml      (Tier 0 ✓)
goldapple product render: Camoufox + JSON-LD parse     (Tier 2 ✓)
viled enumeration       : curl_cffi + sitemap.xml      (Tier 0 ✓)
viled product render    : curl_cffi + __NEXT_DATA__    (Tier 0 ✓)
proxy budget            : $0 baseline
host (Phase 7)          : Hetzner-EU candidate; обязательно проверить Camoufox+EU перед locking
maintenance risk        : daijro/camoufox upstream — periodic health-check в playbook
```

## Команда продолжения

После решения "rewrite-в-place vs формальный re-plan" для 01-08:

```
/gsd-execute-phase 1
```

Контекст: `.planning/phases/01-goldapple-reconnaissance-spike/01-CONTEXT.md` (16 D-XX decisions всё ещё валидны кроме D-01 и D-08 — см. supersedes).

## Timebox

D-02 = 1 неделя. День 2 из 7. Текущий темп: вердикт по anti-bot tier — ясный. Spike реально окупился.
