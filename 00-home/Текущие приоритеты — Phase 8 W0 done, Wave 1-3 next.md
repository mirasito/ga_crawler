---
tags: [priorities, v1-1-active, phase-8, wave-0-done, execute-next]
date: 2026-05-14
status: phase-8-w0-done-w1-pending
current_phase: 8
next_command: /gsd-execute-phase 8 --wave 1
---

# Текущие приоритеты — Phase 8 W0 done, Wave 1-3 next

**Wave 0 spike committed 2026-05-14** (commit `9c70513`) — Plan 08-01 закрыт со стратегическим pivot'ом. Waves 1-3 готовы к autonomous execution.

## Что готово

- ✅ **W0 (Plan 08-01)** — 30-PDP shape-sampling spike + 3 fixtures + project-local skill (`spike-findings-v1.1-brand-name-shapes`)
- ✅ Pivot к h1 `.brand`/`.name` CSS-class spans (microdata premise of Plan 08-03 invalidated)
- ✅ SMOKE_URLs rotation slots finalized (stereotype-sago + armani-code + givenchy-irresistible retained)
- ✅ tests/conftest.py extended с 3 new session-scoped fixture loaders
- ✅ Test baseline confirmed: 801 passed / 1 skipped / 2 pre-existing failures (test_cli_deliver — unrelated)

## Что осталось (Waves 1-3, fully autonomous)

| Wave | Plan | Trigger | Files | Status |
|---|---|---|---|---|
| **1 ∥** | 08-02 (PARSE-FIX-01) ∥ 08-04 (PARSE-FIX-03) | ✅ autonomous via gsd-executor | `goldapple_microdata.py` (volume) ∥ `viled_nextdata.py` (volume) | 🟡 **mid-flight** — оба RED commits landed (`9df9c55` + `214e8ee`); 08-04 GREEN code unstaged + ready; 08-02 GREEN partial (selectolax pin bumped, helper not implemented) |
| **2** | 08-03 (PARSE-FIX-02) | ✅ autonomous after 08-02 | `goldapple_microdata.py` (brand+name; **h1-spans pivot**) | ⏸ ready (depends 08-02 GREEN) |
| **3** | 08-05 (PARSE-FIX-04 + 05 + doc cascade) | ✅ autonomous after W1+W2 | `gates.py`, `stats.py`, 3 tests, 4 doc files | ⏸ ready (depends all) |

## In-flight W1 state (uncommitted на момент save 2026-05-14)

Wave 1 subagents запустились параллельно перед user-interrupt и сделали partial work, который НЕ закоммичен:

**Plan 08-04 (PARSE-FIX-03 viled volume) — GREEN ready, just не committed:**
- `src/ga_crawler/parsers/viled_nextdata.py` — `_extract_volume_from_nextdata(a0: dict) -> Optional[str]` helper полностью реализован (читает `props.pageProps.attributes[0].attributes[]`, matches `("размер", "объем", "объём")`, isinstance guards per STRIDE T-08-13)
- `parse_pdp` callsite at line ~248: `raw_volume_text=_extract_volume_from_nextdata(a0) or name` (PARSE-FIX-03 wiring)
- `__all__` exports `_extract_volume_from_nextdata`
- `tests/unit/test_viled_nextdata_parser.py` D-812 flip done: `test_raw_volume_text_passthrough_is_name` renamed to `test_raw_volume_text_extraction_or_fallback`
- RED commit landed (`214e8ee`) с 11 helper unit tests + 4 round-trip fixture tests
- **Next session:** run `uv run pytest tests/parsers/test_viled_volume_from_nextdata.py tests/unit/test_viled_nextdata_parser.py -q` → if green, commit as `feat(08-04): GREEN — _extract_volume_from_nextdata...`

**Plan 08-02 (PARSE-FIX-01 goldapple volume) — GREEN partial:**
- `pyproject.toml` — selectolax pin bumped `>=0.3,<0.4` → `>=0.4.7,<0.5` ✅
- `uv.lock` regenerated ✅
- **STILL MISSING:** `_extract_volume_block(html: str) -> Optional[str]` helper в `src/ga_crawler/parsers/goldapple_microdata.py` с LOCAL Lexbor import
- **STILL MISSING:** parse_pdp callsite wiring at line 358-359 `raw_volume_text = _extract_volume_block(html) or name or None`
- RED commit landed (`9df9c55`) с 5 tests в test_goldapple_volume_block.py — they currently fail с ImportError
- **Next session:** implement helper (see SKILL.md for ОБЪЁМ/МЛ flex-box selector) → run tests → commit as `feat(08-02): GREEN — _extract_volume_block via selectolax 0.4 Lexbor...`

**Recovery option:** `/gsd-execute-phase 8 --wave 1` re-spawns both agents — they'll see existing RED commits + partial GREEN code, and complete the work atomically. OR manual finish: implement `_extract_volume_block` (see W0 SKILL.md), commit GREEN, then resume W2+W3 via `/gsd-execute-phase 8 --wave 2`.

**Critical handoff:** Plan 08-03 executor MUST read `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` перед coding — Plan PLAN.md still говорит о `<meta itemprop="name">` walking, но SKILL.md документирует pivot к h1-spans (30/30 100% coverage). CONTEXT.md "Claude's Discretion" блок explicitly allows downstream adaptation на основе W0 evidence.

## Next command

```
/gsd-execute-phase 8 --wave 1
```

Это запустит W1 (08-02 + 08-04 параллельно), automatically продолжит к W2 (08-03 после 08-02 merge) → W3 (08-05) → phase verification + STATE.md close.

**Ожидаемое wall-clock:** ~25-35 min total для всех 3 waves (W1 ~10 min parallel; W2 ~10 min sequential after W1; W3 ~10 min doc cascade + 2 testfiles).

## Verification gate после Phase 8 ship

1. Live dry-run yields `goldapple_comparable_count > 0` (was 0 in run #13)
2. `goldapple_volume_norm` non-null rate ≥90% на не-volumeless категориях (25/30 PDPs в W0 spike имели volume block — predicts 83% baseline, должно держаться)
3. Invariant canary `brand.lower() not in name.lower()` — log-warn (NOT fail-hard) per W0 finding D-816 softening
4. ~818-833 tests green (801 baseline + ~15-30 new W1+W2+W3)
5. Null-rate gate (`parser_drift_null_volume_rate`) actively fails synthetic regression run per Plan 08-05 Success Criteria #5

## Что дальше после Phase 8

- **Phase 9** — Live-HTML Harness (TEST-HARNESS-01..06) — locks Phase 8 fix retroactively, formalizes spike-capture как `python -m ga_crawler capture-fixtures`
- **Phase 10** — Audit Paperwork Carryover (AUDIT-DEBT-01..05) — parallel-safe с Phase 8/9
- **Phase 11** — Operator Deploy на Yandex Cloud kz1 (DEPLOY-01..08) — calendar-bound

## Open follow-ups (для W1+ executor agents)

- Plan 08-03 executor должен **NOT** implement `<meta itemprop="name">` walk — SKILL.md pivot к h1 spans
- Plan 08-03 executor должен **NOT** implement `_strip_brand_prefix` fallback — W0 evidence 28/30 clean
- Plan 08-03 executor должен **SOFTEN** D-816 invariant canary к log-warn (NOT fail-hard) — 2/30 PDPs legitimately fail на upstream data redundancy
- Plan 08-05 executor должен использовать finalized SMOKE_URLs из SKILL.md (stereotype-sago + armani-code + givenchy-irresistible)

## Related

- [[2026-05-14 — Phase 8 W0 spike done, microdata премиса invalidated — pivot к h1-spans extraction]] (текущая сессия)
- [[2026-05-13 — Phase 8 plan ready (5 plans, 4 waves) — wave restructure caught real file-overlap]] (previous session, Phase 8 planned)
- [[Goldapple brand+name extraction — h1 spans CSS class substring, не itemprop microdata]] (new decision born из W0 spike)
- [[Goldapple PDP renders volume в structured flexbox blok, не в microdata]] (Plan 08-02 strategy — selectolax 0.4 Lexbor)
- [[viled Размер JSON path — nested attributes 0 attributes, не item attributes]] (Plan 08-04 strategy)
- `.claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md` — system-discoverable spike output
- `.planning/spikes/v1.1-brand-name-shapes/MEMO.md` — full decision memo
- `.planning/phases/08-parser-bug-fixes/08-01-SUMMARY.md` — Plan 08-01 closure

---

**Bottom line:** W0 spike поймал load-bearing premise error в Plan 08-03 (microdata absent on goldapple PDPs) — pivot к h1-spans strategy committed в SKILL.md. Waves 1-3 autonomous, ~25-35 min wall-clock через `gsd-executor` subagents. После ship — first matched-pair production run должен подтвердить SC#1 (`goldapple_comparable_count > 0`).
