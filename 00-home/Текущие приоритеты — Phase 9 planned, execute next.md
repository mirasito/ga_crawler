---
tags: [priorities, v1-1-active, phase-9, planned, execute-next]
date: 2026-05-14
status: phase-9-planned-execute-pending
current_phase: 9
next_command: /gsd-execute-phase 9
---

# Текущие приоритеты — Phase 9 planned, execute next

Phase 9 (Live-HTML Harness) полностью спланирован 2026-05-14 evening через `/gsd-plan-phase 9` end-to-end. 4 PLAN.md across 3 waves committed (`68b3ed7`), plan-checker PASS 8/8 dimensions. Готов `/gsd-execute-phase 9`.

## Что готово

- ✅ **Phase 8 closed 2026-05-13** — 5/5 PARSE-FIX reqs Complete, parser bugs fixed
- ✅ **Phase 9 contexted 2026-05-14 morning** — CONTEXT.md + DISCUSSION-LOG.md committed (`2555847`), 7 decisions D-901..D-907 across 4 gray areas
- ✅ **Phase 9 researched 2026-05-14 evening** — 09-RESEARCH.md committed (`3f6bd2a`); syrupy 4.9.x + Pydantic 2.10 patterns Context7-verified; 7 paste-ready code skeletons; 7 landmines; **2 critical CONTEXT corrections** surfaced
- ✅ **Phase 9 validation strategy** — 09-VALIDATION.md committed (`78c44d9`); 13 Wave 0 test-file stubs + 6 T-09-* threat refs + Per-Task Verification Map
- ✅ **Phase 9 patterns mapped** — 09-PATTERNS.md committed (`7adbca0`); 14/18 new files have concrete analog line-ranges; 4 greenfield identified
- ✅ **Phase 9 planned end-to-end** — 4 PLAN.md committed (`68b3ed7`); plan-checker PASS across all 8 dimensions

## Critical CONTEXT corrections caught by research

1. **`SqliteSnapshotWriter.persist` → `.append`** — D-903 ссылался на `persist` (conceptual name); actual method `def append(run_id, retailer, products) -> int` at `src/ga_crawler/storage/sqlite.py:177`. Planner использует `append` verbatim во всех `<action>` полях 09-02b, cross-references D-903 в plan SUMMARY.
2. **`storage/types.py` не существует** — D-904 «extend существующий types.py если он есть» fallback inapplicable; `storage/schemas.py` — greenfield path (only choice).

## 4 plans across 3 waves

| Wave | Plan | Requirements | Files highlights | Autonomous |
|---|---|---|---|---|
| **W0** | `09-01-PLAN.md` | TH-01, TH-02 | syrupy 4.9.x install, `HTMLSnapshotExtension` (≤7 LOC), `_assert_fixture_clean` PII canary, sidecar JSON helper, `_html_normalize.py` (cf_clearance + buildId + CSS-hash strip) | ✓ |
| **W1** | `09-02a-PLAN.md` | TH-03 | `tests/live/test_parser_drift.py` (3 Phase 8 fixtures retroactive), `tests/test_snapshot_soundness.py` (missing-snapshot negative test) | ✓ |
| **W1** | `09-02b-PLAN.md` | TH-06 | `storage/schemas.py` (per-retailer Pydantic), `storage/sqlite.py` (append wire-in), `runner/gates.py` (`schema_rejected_rate_gate(rate=0.05)`), `runner/stats.py` (SCHEMA_STATS_KEYS), 3 test files | ✓ (parallel — disjoint files from 09-02a) |
| **W2** | `09-03-PLAN.md` | TH-04, TH-05 | Variant A (P2 GO): brand-coverage canary + capture-fixtures CLI / Variant B (P2 NO-GO): doc cascade / Always: README §8 «Live HTML harness» | ✗ (user GO/NO-GO checkpoint per D-902) |

## Locked decisions (см. 09-CONTEXT.md)

- **D-901**: 3-plan wave structure (W0 → W1 parallel → W2 conditional)
- **D-902**: P2 gate = `elapsed_W0_W1 < 8h` → GO (git commit timestamps). См. [[P2 bundle gate — time-budget 8h elapsed W0+W1 для GO NO-GO checkpoint]]
- **D-903**: Pydantic validation в `SqliteSnapshotWriter.append` boundary, hard-raise per-SKU, run-fail на `rejected_rate > 5%` (reason `schema_validation_rejected_rate`). Cascade: schema gate ДО PARSE-FIX-04 null-rate gate. См. [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]]
- **D-904**: Per-retailer schema — `GoldappleRawProduct` strict, `ViledRawProduct.volume_raw: NonEmptyStr | None`. См. [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]]
- **D-905**: `pytest -m live` — operator-only opt-in, README §8 mandatory, no cron wiring. См. [[pytest -m live — operator-only opt-in документируется в README §8]]
- **D-906**: Two-mode (cassette-replay default + `--refresh-live` flag); stale fixture >30d = warning
- **D-907**: PII canary + size budget в default pytest (two enforcement points: conftest loader + standalone canary test)

## Plan-checker verdict — PASS 8/8

| D# | Dimension | Status |
|---|---|---|
| D1 | Goal-Backward Coverage (5 SCs mapped) | PASS |
| D2 | Requirement Coverage (6 TH-XX в exactly one plan) | PASS |
| D3 | CONTEXT Decision Fidelity (D-901..D-907 encoded; `append` correction carried through) | PASS |
| D4 | Anti-Shallow Execution (`<read_first>` + concrete `<action>` + literals like `0.05`) | PASS |
| D5 | Wave Dependencies (zero file overlap 09-02a vs 09-02b, verified disjoint) | PASS |
| D6 | Security Threat Model (all 6 T-09-* in `<threat_model>` blocks) | PASS |
| D7 | Conditional 09-03 Encoding (both variants + decision-gate + `autonomous: false`) | PASS |
| D8 | Nyquist Validation (every impl task `<automated>` pytest-x verifiable) | PASS |

2 non-blocking warnings оставлены as-is (cosmetic — RESEARCH §9 heading; structural TDD nit on 09-02a Task 1).

## Что осталось

```
/clear  ← fresh context window
/gsd-execute-phase 9
```

Executor запустит:
1. **Wave 0 sequentially**: `09-01` ships syrupy + harness infrastructure
2. **Wave 1 parallel**: `09-02a` (live drift test) ∥ `09-02b` (Pydantic write-boundary + gate + stats) — disjoint `files_modified` verified
3. **Wave 2 user-gated**: `09-03` Task 1 measures `git log` elapsed → halts для P2 GO/NO-GO decision → executes Variant A (TH-04+TH-05 ship) или Variant B (defer doc cascade); README §8 в обеих variants

## Verification gate после Phase 9 ship

1. `pytest -m live` (cassette mode) — 3 Phase 8 fixtures pass invariants
2. `pytest tests/test_snapshot_soundness.py` — missing-snapshot negative test ловит soundness regression
3. Default `pytest` — PII canary + size guard pass на `_live-2026-05-13-*.html`
4. `pytest tests/integration/test_writer_schema_gate.py` — Pydantic injection ловит synthetic >5% reject-rate → run-fail
5. Tests green ≥845 (current ~830 после Phase 8; W0 adds ~15 new test files)
6. P2 GO/NO-GO решение committed либо как code либо как doc cascade

## Что дальше после Phase 9

- **Phase 10** — Audit Paperwork Carryover (AUDIT-DEBT-01..05) — parallel-safe с Phase 9; pure documentation
- **Phase 11** — Operator Deploy на Yandex Cloud kz1 (DEPLOY-01..08) — calendar-bound; depends Phase 8+9 ship

## Related

- [[2026-05-14 — Phase 9 planned end-to-end — 4 plans, 3 waves, plan-checker PASS 8 of 8]] (текущая сессия — planning)
- [[2026-05-14 — Phase 9 contexted — Live-HTML Harness 7 decisions across 4 areas]] (утренняя сессия — contexting)
- ~~[[Текущие приоритеты — Phase 9 contexted, plan next]]~~ — superseded 2026-05-14 evening (plans ready)
- [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]] (D-903)
- [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]] (D-904)
- [[pytest -m live — operator-only opt-in документируется в README §8]] (D-905)
- [[P2 bundle gate — time-budget 8h elapsed W0+W1 для GO NO-GO checkpoint]] (D-902)
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` (committed 2555847)
- `.planning/phases/09-live-html-harness/09-RESEARCH.md` (committed 3f6bd2a)
- `.planning/phases/09-live-html-harness/09-VALIDATION.md` (committed 78c44d9)
- `.planning/phases/09-live-html-harness/09-PATTERNS.md` (committed 7adbca0)
- 4 PLAN.md files (committed 68b3ed7)

---

**Bottom line:** Phase 9 готов к execute. 4 plans, plan-checker PASS 8/8, P2 conditional decision-gate encoded в 09-03. Run `/gsd-execute-phase 9` после `/clear`.
