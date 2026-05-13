---
tags: [priorities, v1-1-active, phase-8, plan-ready, execute-next]
date: 2026-05-13
status: phase-8-planned
current_phase: 8
next_command: /gsd-execute-phase 8
---

# Текущие приоритеты — Phase 8 planned, execute next

**Phase 8 planned 2026-05-13** через `/gsd-plan-phase 8` (YOLO autonomous). 5 plans в 4 waves, все доки committed.

## Что готово

- `08-RESEARCH.md` — selectolax 0.4 Lexbor recipes + viled JSON path empirically traced (`pp.attributes[0].attributes[]` — overrides STACK.md) + 10 pitfalls + Validation Architecture
- `08-VALIDATION.md` — Nyquist Dim 8 PASS; 14 per-task verification rows; sign-off approved
- `08-PATTERNS.md` — 22 файлов классифицированы, 19 с verbatim code excerpts + line ranges
- `08-01..05-PLAN.md` — 5 plans, 19 tasks total
- ROADMAP.md — wave dependencies аннотированы; cross-cutting constraints зафиксированы
- STATE.md — Current Position обновлён на "Ready to execute"

## Wave structure

| Wave | Plan | Trigger | Files |
|---|---|---|---|
| **0** | 08-01 (spike + fixtures + skill) | ❌ требует operator (30 URL curation + visual gate) | `.planning/spikes/v1.1-brand-name-shapes/*`, 3 fixtures, `tests/conftest.py`, skill |
| **1 ∥** | 08-02 (PARSE-FIX-01) ∥ 08-04 (PARSE-FIX-03) | ✅ autonomous after W0 | `goldapple_microdata.py` ∥ `viled_nextdata.py` (disjoint) |
| **2** | 08-03 (PARSE-FIX-02) | ✅ autonomous after 08-02 | `goldapple_microdata.py` (shared с 08-02) |
| **3** | 08-05 (PARSE-FIX-04 + 05 + doc cascade) | ✅ autonomous after W1+W2 | `gates.py`, `stats.py`, 3 tests, 4 doc files |

**Wave restructure note:** Планировщик автоматически restructured W1 потому что 08-02 и 08-03 оба модифицируют `src/ga_crawler/parsers/goldapple_microdata.py`. CONTEXT.md D-809 обещал 3-plan parallel — overridden, justified. Override закреплён в ROADMAP.md cross-cutting constraints.

## Next command

```
/gsd-execute-phase 8
```

**Wave 0 setup (operator):**
1. Курируй 30 goldapple.kz PDP URLs: 5 buckets × 6 PDPs each
   - lux (Tom Ford, Creed, Frederic Malle, etc.)
   - mass-market (L'Oréal, Maybelline, etc.)
   - niche (STEREOTYPE, Diptyque, etc.)
   - RU-brands (НАТУРА СИБИРИКА, etc. — Cyrillic uppercase test)
   - multi-word (Dolce & Gabbana, Yves Saint Laurent, etc.)
2. `uv run python .planning/spikes/v1.1-brand-name-shapes/capture.py` (~3 min Camoufox fetch)
3. Заполни `shape-table.md`: 30 PDP × {brand_raw, brand_displayed_in_h1, name_raw, volume_block_present?, volume_label_text, shape_bucket}
4. Identify SMOKE_URLs slots: ≥1 STEREOTYPE-style URL + ≥1 Armani-style URL (для PARSE-FIX-05 rotation)
5. Approve gate → Waves 1-3 запустятся автономно

**После Phase 8 ship — verification gate:**
1. Live dry-run yields `goldapple_comparable_count > 0` (was 0 in run #13)
2. `goldapple_volume_norm` non-null rate ≥90% на не-volumeless категориях
3. Invariant canary `brand.lower() not in name.lower()` holds
4. ~818-833 tests green (803 baseline + ~15-30 new)
5. Null-rate gate actively fails synthetic regression run (`parser_drift_null_volume_rate`)

## Что дальше после Phase 8

- **Phase 9** — Live-HTML Harness (TEST-HARNESS-01..06) — locks Phase 8 fix retroactively
- **Phase 10** — Audit Paperwork Carryover (AUDIT-DEBT-01..05) — parallel-safe с Phase 8/9
- **Phase 11** — Operator Deploy на Yandex Cloud kz1 (DEPLOY-01..08) — calendar-bound

## Related

- [[2026-05-13 — Phase 8 plan ready (5 plans, 4 waves) — wave restructure caught real file-overlap]] (текущая сессия)
- [[2026-05-13 — live-run 13 vskrыl 3 парсер-бага, v1.1 milestone открыт через gsd-new-milestone]]
- [[2026-05-13 — Phase 7 executed end-to-end + code review fixes, v1 milestone code-ship complete]]
- `.planning/phases/08-parser-bug-fixes/08-CONTEXT.md` — locked decisions D-801..D-819
- `.planning/phases/08-parser-bug-fixes/08-RESEARCH.md` — viled JSON path correction + selectolax 0.4 Lexbor recipes
- `.planning/ROADMAP.md` § Phase 8 — wave dependencies аннотированы

---

**Bottom line:** Phase 8 готов к execute. Один operator-step (W0 spike, ~60-90 min) разблокирует автономные waves 1-3 (~30 min). После ship — first matched-pair production run должен подтвердить SC#1 (`goldapple_comparable_count > 0`).
