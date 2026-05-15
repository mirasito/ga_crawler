---
tags: [priorities, v1-1-active, phase-9, contexted, plan-next]
date: 2026-05-14
status: phase-9-contexted-plan-pending
current_phase: 9
next_command: /gsd-plan-phase 9
---

# Текущие приоритеты — Phase 9 contexted, plan next

Phase 9 (Live-HTML Harness) контекст зафиксирован 2026-05-14 через `/gsd-discuss-phase 9`. 7 решений (D-901..D-907) committed (2555847). Готов `/gsd-plan-phase 9`.

## Что готово

- ✅ **Phase 8 closed 2026-05-13** — 5/5 PARSE-FIX reqs Complete, parser bugs fixed, 3 live fixtures committed (`_live-2026-05-13-stereotype.html` / `_live-2026-05-13-armani-code.html` / `tests/fixtures/viled/_live-2026-05-13-contre-jour.html`)
- ✅ **Phase 9 contexted 2026-05-14** — CONTEXT.md + DISCUSSION-LOG.md committed; 4 gray areas обсуждены через `AskUserQuestion`; 3-plan wave shape decided; P2 GO/NO-GO criterion locked
- ✅ Research v1.1 уже сделан в `.planning/research/` (STACK §B syrupy verbatim, ARCHITECTURE §B harness placement) — `/gsd-plan-phase` может пройти с `--skip-research`

## Что осталось

| Wave | Plan | Files (предполагаемо — planner уточнит) | Status |
|---|---|---|---|
| **0** | 09-01 (TH-01 + TH-02) | `pyproject.toml` (syrupy dev-dep), `tests/conftest.py` (HTMLSnapshotExtension + `_assert_fixture_clean`), `tests/_fixture_metadata.py` (sidecar JSON helper), `tests/test_live_fixtures_pii_canary.py` | ⏸ ready для plan |
| **1** | 09-02 (TH-03 + TH-06, parallel) | `tests/live/test_parser_drift.py`, `src/ga_crawler/storage/schemas.py`, `runner/gates.py` (schema-rejected-rate gate), `runner/stats.py` (new keys), `README.md` §8 | ⏸ ready для plan |
| **2** | 09-03 (TH-04 + TH-05 conditional) | IF elapsed <8h: `src/ga_crawler/cli.py` (capture-fixtures subcommand), brand-coverage canary tests. ELSE: doc cascade only (REQUIREMENTS/STATE/ROADMAP). | ⏸ conditional |

## Locked decisions (см. CONTEXT.md полностью)

- **D-901**: 3 plans, P2 GO/NO-GO checkpoint after W1
- **D-902**: P2 gate = `elapsed_W0_W1 < 8h` → GO (git commit timestamp arithmetic). См. [[P2 bundle gate — time-budget 8h elapsed W0+W1 для GO NO-GO checkpoint]]
- **D-903**: Pydantic validation в `SqliteSnapshotWriter.persist`, hard-raise per-SKU, run-fail на `rejected_rate > 5%` (reason `schema_validation_rejected_rate`). Cascade: schema-rejected-rate ДО PARSE-FIX-04 null-rate. См. [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]]
- **D-904**: Per-retailer schema — goldapple strict (volume_raw REQUIRED), viled relaxed (volume_raw `NonEmptyStr | None`). См. [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]]
- **D-905**: `pytest -m live` — operator-only opt-in, README §8, no cron wiring. См. [[pytest -m live — operator-only opt-in документируется в README §8]]
- **D-906**: Two-mode (cassette-replay default + `--refresh-live` flag); stale fixture >30d = warning
- **D-907**: PII canary + size budget в default pytest (conftest loader + standalone test); capture-fixtures CLI scrub'ит ДО записи

## Critical handoff для planner

Planner должен (per CONTEXT.md `<canonical_refs>`):

1. Прочитать `.planning/research/STACK.md` §B (lines 85-119) — syrupy code pattern verbatim
2. Прочитать `.planning/research/ARCHITECTURE.md` §B (lines 80-117) — file placement, sidecar JSON shape, drift test responsibilities
3. Inspect `src/ga_crawler/storage/` — определить точное имя класса/метода `SqliteSnapshotWriter.persist` boundary point для D-903 injection
4. Inspect `src/ga_crawler/runner/gates.py` D-203 pattern (`auto_suggest_threshold`, `final_threshold_gate`, `parse_quality_gate`) для shape нового `schema_rejected_rate_gate`
5. Inspect `tests/conftest.py:23-37` для extending `goldapple_pdp_html` / `viled_pdp_html` fixture loaders через `_assert_fixture_clean(path)` (D-907)
6. **Skip-research**: `/gsd-plan-phase 9 --skip-research` уместен потому что v1.1 research уже cover'ит Phase 9 dimensions

## Next command

```
/gsd-plan-phase 9
```

или с явным `--skip-research`:

```
/gsd-plan-phase 9 --skip-research
```

После plan ready → `/gsd-execute-phase 9` запустит W0 (09-01) sequentially → W1 (09-02) parallel → measure elapsed at W1 closeout → branch к W2 (09-03) GO или defer doc cascade.

## Verification gate после Phase 9 ship

1. `pytest -m live` (cassette mode) — все 3 Phase 8 fixtures pass invariants
2. `pytest -m live --refresh-live` (operator path) — syrupy assert против Camoufox-fetched live HTML; missing-snapshot soundness rule fails если new shape variant
3. Default `pytest` запускает PII canary + size guard test — passes (no leaked credentials в `_live-*.html` fixtures)
4. Pydantic `RawProduct` validation injected — synthetic invalid-SKU batch test ловит >5% reject-rate → run failed `schema_validation_rejected_rate`
5. Tests green ≥845 (current ~830 после Phase 8)
6. P2 GO/NO-GO решение committed либо как code (TH-04+05 shipped) либо как doc cascade (REQUIREMENTS/STATE/ROADMAP с `Deferred to v1.2`)

## Что дальше после Phase 9

- **Phase 10** — Audit Paperwork Carryover (AUDIT-DEBT-01..05) — parallel-safe с Phase 9; pure documentation
- **Phase 11** — Operator Deploy на Yandex Cloud kz1 (DEPLOY-01..08) — calendar-bound; depends Phase 8+9 ship

## Related

- [[2026-05-14 — Phase 9 contexted — Live-HTML Harness 7 decisions across 4 areas]] (текущая сессия)
- ~~[[Текущие приоритеты — Phase 8 W1 done, W2 next]]~~ — superseded 2026-05-14 (Phase 8 закрыт через Plans 08-03/08-05 doc cascade 2026-05-13; Phase 9 contexted сейчас)
- [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]] (D-903)
- [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]] (D-904)
- [[pytest -m live — operator-only opt-in документируется в README §8]] (D-905)
- [[P2 bundle gate — time-budget 8h elapsed W0+W1 для GO NO-GO checkpoint]] (D-902)
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` — load-bearing artefact (committed 2555847)
- `.planning/phases/09-live-html-harness/09-DISCUSSION-LOG.md` — discussion audit trail
- `.planning/research/STACK.md` §B + ARCHITECTURE.md §B — research load-bearing для plan

---

**Bottom line:** Phase 9 готов к planning. 7 решений локнуты CONTEXT.md, 3-plan wave shape decided, P2 conditional на 8h time-budget gate. Run `/gsd-plan-phase 9` либо `/gsd-plan-phase 9 --skip-research` (research v1.1 already covers Phase 9 dimensions).
