---
tags: [decision, phase-3, sanity-gate, ops, anti-drift]
date: 2026-05-06
phase: 3
decisions: [D-308, D-309, D-310]
---

# Sanity-gate M=1000 static с auto-suggest, не auto-tune

CRAWL-05 sanity-gate `goldapple_count > M` использует **`M = 1000` static absolute** в config. После 4 недель history Phase 3 шлёт **auto-suggest** в ops-Telegram (`new M-rec: 0.7 × 4-week median = X`), но **никогда не auto-tune'ит** значение сам.

## Pipeline

1. Run фетчит ~3,450 URLs (D-302 full re-crawl, D-309 run-to-completion).
2. В конце run проверяет `goldapple_count > 1000`.
3. Pass → `runs.status='success'`, отчёт уходит в business-чат.
4. Fail → `runs.status='failed'`, business-чат **не получает ничего** (DELIVER-03 / spec-lock), ops-чат получает алерт.
5. На 5-й неделе и далее (если history достаточно) ops-Telegram также получает рекомендацию: `new M-rec = max(0.7 × 4-week median, 500)`. Operator решает PR-ом в config.

## Почему **не** auto-tune

Auto-tune обновлял бы M автоматически каждую неделю по формуле. Опасно: при постепенной anti-bot регрессии (gate-shell rate медленно растёт) M бесшумно ползёт вниз вместе с реальным count → sanity-gate **теряет смысл** как detector. Operator-in-loop нужен именно как human-judgement gate против silent drift.

## Почему **не** dynamic-median-only без floor

Bootstrap проблема: первые 4 недели нет history. Floor=500 защищает от ложных проходов в bootstrap-period. На v1 явный static лучше, чем формула с edge-cases.

## Почему **не** static relative-to-viled

`M = 0.3 × viled_count_in_matched_brands` связывает двух ритейлеров. Если viled сжимается → M падает → ложные проходы при сломанной goldapple-стороне. Не хотим этого coupling.

## Когда пересматривать

- После 8+ недель real history → operator может рассмотреть переход на dynamic-median (но только manual; auto-tune навсегда отвергнуто).
- При появлении production-инцидента где гейт не сработал — review threshold + circuit-breaker (D-309 mid-run circuit-breaker отвергнут на v1, но return на стол при evidence).

## Связанные

- [[Run-level sanity-gate перед доставкой]] — pattern parent
- [[Match-rate — KPI с первой недели]] — соседний invariant
- [[Канал доставки — Telegram + Excel вложение]] — что блокирует gate
- `.planning/phases/03-goldapple-crawl/03-CONTEXT.md` §Sanity-gate threshold M — D-308, D-309, D-310
- `.planning/REQUIREMENTS.md` CRAWL-05 — sanity-assertion gate
- `.planning/REQUIREMENTS.md` DELIVER-03 — pre-send gate в Phase 6
