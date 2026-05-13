# Phase 8: Parser Bug Fixes — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 8-parser-bug-fixes
**Areas discussed:** Pre-spike protocol (30 PDP), selectolax 0.4 migration scope, Plan-wave order + TDD discipline, PARSE-FIX-04 null-rate gate scope

---

## Pre-spike (30 PDP shape-sampling)

| Option | Description | Selected |
|--------|-------------|----------|
| 30 PDP, 5 strata, shape-table.md + wrap-up skill | Camoufox fetch 30 живых goldapple PDP в 5 стратах по 6 (lux/mass-market/niche/RU-brands/multi-word). Output: `.planning/spikes/v1.1-brand-name-shapes/shape-table.md` + raw HTML. Wrap-up в project skill `spike-findings-v1.1-brand-name-shapes/SKILL.md` чтобы downstream agents видели выводы. | ✓ |
| Lightweight: 10 PDP, ad-hoc table inline в RESEARCH.md | 10 PDP по 2 в каждой из 5 страт. Объекты в spike dir но без skill wrap-up — shape-категории в `08-RESEARCH.md` под разделом `Shape Bucket Table`. | |
| Heavy: 50 PDP + viled 20 PDP (cross-retailer) | 50 goldapple + 20 viled = 70 живых PDP. Для viled — потому что `attributes[].name=="Размер"` может быть null. Output: 2 shape-table.md (одна на retailer). | |

**User's choice:** 30 PDP, 5 strata, shape-table.md + wrap-up skill
**Notes:** Mandatory pre-code блокировка W0 — никаких правок в parsers/* до завершения spike.

---

## selectolax 0.3 → 0.4 migration scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: Lexbor только в новых helpers | `pyproject.toml`: selectolax `>=0.4.7,<0.5`. Локальный import `from selectolax.lexbor import LexborHTMLParser` внутри `_extract_volume_block(tree)`. Существующие 60+ тестов и viled parser не трогаем. Blast radius: 1 функция. | ✓ |
| Wholesale: все parsers на LexborHTMLParser | Переводим оба парсера. Простота: один backend. Risk: 60+ тестов могут сломаться на edge-case CSS-селекторах. Doп regression work. | |
| Lexbor по всему goldapple_microdata.py | Только goldapple parser на Lexbor (он выигрывает от `:lexbor-contains`, viled нет). viled_nextdata.py не трогаем. Middle ground. | |

**User's choice:** Minimal: Lexbor только в новых helpers
**Notes:** Modest остаётся default backend; Lexbor opt-in только где `:lexbor-contains` нужен.

---

## Plan-wave order + TDD discipline

| Option | Description | Selected |
|--------|-------------|----------|
| W0 spike → W1 fixes (3 бага) → W2 gate+rotation, строгий TDD | W0 (mandatory blocking): 30-PDP spike + skill + 3 fixtures. W1 parallel (разные файлы): goldapple-volume, goldapple-brand/name, viled-volume — каждый с RED test на живой fixture ПЕРЕД кодом. W2 sequential: PARSE-FIX-04 gate, PARSE-FIX-05 SMOKE rotation, doc cascade. ~3 волны, 5-7 планов. | ✓ |
| Linear 5-plan: spike → fix1 → fix2 → fix3 → gate+rotation+docs | Простое последовательное качение планов, нет parallel waves. Быстрее планировать, но дольше wall-clock. | |
| Big-bang: spike + все фиксы в одном плане | 1 spike-plan + 1 mega-plan с 3 фиксами + gate + rotation. Один коммит трогает оба парсера + gate — тяжёлый review/rollback. | |

**User's choice:** W0 spike → W1 fixes (3 бага) → W2 gate+rotation, строгий TDD
**Notes:** RED test против `_live-2026-05-13-*.html` fixture ОБЯЗАТЕЛЬНО до touching production code. Атомарные RED + GREEN pairs per plan.

---

## PARSE-FIX-04 null-rate gate scope

| Option | Description | Selected |
|--------|-------------|----------|
| 50% absolute, goldapple-only, volume_norm + brand | Gate срабатывает если `null_rate(goldapple.volume_norm) > 0.5` ИЛИ `null_rate(goldapple.brand) > 0.5`. Абсолютный порог 50%. Viled не включаем (legitimate Nones у Contre-Jour). | ✓ |
| 50% absolute, goldapple volume_norm only | Строго по тексту реквайремента. Brand/name полагаемся на invariant canary. Risk: brand-only-null регрессия выживёт. | |
| Rolling baseline (last 4 weeks median + 30% jitter) | Адаптивный к categorical noise. Risk: в v1.1 нет 4 свежих ранов с fixed parser — bootstrap-period первые 4 недели. Сложнее в D-411 skip-protocol. | |

**User's choice:** 50% absolute, goldapple-only, volume_norm + brand
**Notes:** Brand-canary `assert brand.lower() not in name.lower()` остаётся ОТДЕЛЬНЫМ per-SKU invariant — не заменяется gate'ом. Cascade: gate ловит "all SKUs broken", invariant ловит per-SKU regression.

---

## Claude's Discretion

- Внутренняя структура `_extract_volume_block(tree)` helper — точный CSS-селектор после Lexbor `:lexbor-contains("ОБЪЁМ" i)` определяется на основе live HTML spike output
- Brand-prefix fallback `_strip_brand_prefix(name, brand)` — включаем или нет решается по shape-table data в Plan 08-03
- Точный JSON path для viled `attributes[].name == "Размер"` — подтверждается Wave-0 mini-probe против beauty PDP в Plan 08-01
- Final SMOKE_URL slot selection (STEREOTYPE + Armani конкретные URL) — deferred to Plan 08-05 после W0 spike output

## Deferred Ideas

- Backfill runs 1-13 — out (forward-only, one-line MILESTONES.md annotation)
- scripts/capture_fixtures.py CLI subcommand — Phase 9 TEST-HARNESS-05
- syrupy HTML snapshot harness — Phase 9 TEST-HARNESS-01..03
- Pydantic write-boundary validation — Phase 9 TEST-HARNESS-06
- Brand-coverage quota canary — Phase 9 P2 cheap-bundle TEST-HARNESS-04
- Match-rate floor alert — не в v1.1 reqs roster; v2 backlog if operator пожалуется post-deploy
- viled volume null-rate gate — Phase 8 сознательно gold-only; v1.2 candidate если evidence покажет нужду
