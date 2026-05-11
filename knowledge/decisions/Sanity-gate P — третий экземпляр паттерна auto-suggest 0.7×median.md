---
tags: [decision, phase-4, matcher, sanity-gate, observability, pattern-reuse]
date: 2026-05-11
phase: 04-matcher-match-rate-kpi
decision_id: [D-406, D-407, D-408, D-409]
---

# Sanity-gate P — третий экземпляр паттерна auto-suggest 0.7×median

Phase 4 sanity-gate для `match_count > P` использует **тот же** паттерн, что viled N-gate (Phase 2 D-201) и goldapple M-gate (Phase 3 D-308). Это третий retailer-domain экземпляр — паттерн **закрепляется как канонический** для дальнейших фаз.

## Триплет: static seed + auto-suggest + operator-PR

1. **Static seed (D-406):** `P = 20` в `pyproject.toml [tool.ga_crawler.match] sanity_gate_p` (D-408). Catastrophic-failure detector — ловит «normalizer сломан» или «один ритейлер пустой». ~30% от консервативного ожидаемого минимума.
2. **Auto-suggest после 4 успешных runs (D-407):** с 5-й недели run эмитит ops-Telegram сообщение `new P-rec for matcher: 0.7 × 4-week-median match_count = X`. Оператор PR-ит изменение `sanity_gate_p` если согласен.
3. **Никогда auto-tune:** silent drift вниз = silent KPI degradation = ложно-успешный отчёт. PR обязателен.

## Reuse retailer-agnostic helpers

Никакого дублирования кода — Phase 4 вызывает уже существующие helpers из `runner/gates.py`:
- `final_threshold_gate(count, threshold)` — D-203 retailer-agnostic после Phase 2 рефактора
- `auto_suggest_threshold(history, factor=0.7, min_runs=4)` — D-203 retailer-agnostic

## Gate-fail invariant (D-409)

`match_count <= P` → `run_writer.fail(reason='match_count_below_threshold:{count}<{threshold}')`. matches rows **всё равно остаются** в БД (audit-trail invariant — mirror DATA-03 immutable + D-218 gate-fail-but-snapshot-persists). Downstream (Phase 6 delivery) увидит `runs.status='failed'` и пропустит business-чат.

## Pattern triptych across the project

| Retailer | Gate | Seed | Decision | Auto-suggest |
|---|---|---|---|---|
| viled (CRAWL-05) | `viled_count > N` | N=100 | D-201 | 0.7×4-week-median (D-203) |
| goldapple (CRAWL-05) | `goldapple_count > M` | M=1000 | D-308 | 0.7×4-week-median (D-310) |
| matcher (MATCH-04) | `match_count > P` | P=20 | D-406 | 0.7×4-week-median (D-407) |

Все три:
- seed-значение reflects конкретный domain (N=100 для beauty/parfumery catalog scope, M=1000 для full goldapple sitemap, P=20 для intersection)
- formula identical (0.7 × median последних 4 успешных runs)
- mechanism identical (ops-Telegram message → operator-PR в `pyproject.toml`)
- gate-fail behavior identical (run.status='failed' + reason; downstream artifacts persist)

## Boundary semantics caveat (WARN-1 from plan-check)

REQUIREMENTS phrasing — strict `>` (`match_count > P`). `final_threshold_gate` implements `>=` (inclusive). Inherited inconsistency из Phase 2/3. На границе (count==threshold) gate says pass, requirement says fail. Non-blocking (precedent existed); optional boundary test для strict alignment.

## Что НЕ делаем

- ❌ Auto-tune `sanity_gate_p` — навсегда отвергнуто
- ❌ Dynamic formula (e.g. percentile-based) — простоты median достаточно
- ❌ Per-brand gate — out of scope v1
- ❌ Pre-flight coverage gate — false-positive abort'ы первые недели; пост-фактум gate надёжнее
- ❌ Auto-PR через GitHub Actions — operator принимает решение

## Связанные

- [[Sanity-gate M=1000 static с auto-suggest, не auto-tune]] — Phase 3 D-308/D-310 первоисточник
- [[Match-rate — KPI с первой недели]] — gate trips on KPI denominator failure
- [[Run-level sanity-gate перед доставкой]] — общий принцип
- [[.planning/phases/04-matcher-match-rate-kpi/04-CONTEXT|04-CONTEXT.md]] §D-406..D-409
- `src/ga_crawler/runner/gates.py` — `final_threshold_gate` + `auto_suggest_threshold`
