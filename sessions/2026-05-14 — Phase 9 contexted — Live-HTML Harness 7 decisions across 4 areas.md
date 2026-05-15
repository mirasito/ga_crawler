---
tags: [session, v1-1-active, phase-9, contexted, plan-next]
date: 2026-05-14
status: phase-9-context-captured
current_phase: 9
next_command: /gsd-plan-phase 9
related_commits: ["2555847"]
---

# 2026-05-14 — Phase 9 contexted — Live-HTML Harness 7 decisions across 4 areas

Phase 9 (Live-HTML Harness, TEST-HARNESS-01..06) context zafiksirovan через `/gsd-discuss-phase 9`. Все 4 gray areas обсуждены, 7 решений локнуты, CONTEXT.md + DISCUSSION-LOG.md committed (2555847). Готов `/gsd-plan-phase 9`.

## Контекст входа

- Phase 8 закрыт 2026-05-13 (5/5 PARSE-FIX reqs Complete, run #13 parser bugs пофикшены)
- v1.1 milestone остался с 3 phases: Phase 9 (harness), Phase 10 (paperwork), Phase 11 (Yandex Cloud deploy)
- Phase 8 W0 spike оставил 3 живых fixture (`_live-2026-05-13-*.html`) которые Phase 9 ретроактивно подключает к syrupy harness'у
- syrupy 4.7 уже locked как dev-only dependency (per STATE.md locked decisions block)

## 4 обсуждённые области

### 1. Plan-wave structure + P2 bundling

- **D-901:** 3 plans — 09-01 (TH-01+02 syrupy infra), 09-02 parallel (TH-03 + TH-06), 09-03 conditional (P2 bundle ИЛИ defer doc cascade). Mirror Phase 8 W0/W1/W2 shape
- **D-902:** P2 GO/NO-GO criterion = **time-budget < 8h elapsed W0+W1** → GO. Измеряется через git commit timestamps. ≥8h → 09-03 пишет `defer-to-v1.2` doc cascade. User override allowed. См. [[P2 bundle gate — time-budget 8h elapsed W0+W1 для GO NO-GO checkpoint]]

### 2. Pydantic RawProduct write-boundary (TEST-HARNESS-06)

- **D-903:** Validation at `SqliteSnapshotWriter.persist` boundary, hard-raise per-SKU + run-fail на `rejected_rate > 5%` (reason `schema_validation_rejected_rate`). Cascade order: schema-rejected-rate gate ДО PARSE-FIX-04 null-rate gate. См. [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]]
- **D-904:** **Per-retailer schema split** — `GoldappleRawProduct` strict (brand+volume_raw+name+price все REQUIRED), `ViledRawProduct` relaxed (volume_raw `NonEmptyStr | None` для legitimate Frederic Malle Contre-Jour / Wild Vetiver Nones). См. [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]]

### 3. Live-drift test integration с cron (TEST-HARNESS-03)

- **D-905:** **Operator-only opt-in**, NO cron wiring. weekly-run.sh не меняется. README §8 «Live HTML harness» документирует когда запускать. Drift output → `.planning/research/parser-drift-YYYY-MM-DD.md`. См. [[pytest -m live — operator-only opt-in документируется в README §8]]
- **D-906:** **Two-mode drift test** — default cassette-replay против Phase 8 fixtures (быстрый деterministic unit-test); `--refresh-live` flag re-fetches через Camoufox + syrupy assert + sidecar update. Stale fixture (sidecar.date > 30 дней) = warning, не fail

### 4. PII canary + 50 MB size budget enforcement (TEST-HARNESS-02)

- **D-907:** Two enforcement points в **default pytest** (не -m live):
  - `tests/conftest.py` fixture loader wraps `_live-*.html` через `_assert_fixture_clean(path)` — грязный → `pytest.fail()` на load
  - Standalone `tests/test_live_fixtures_pii_canary.py` итерирует все fixtures, regex-scan'ит на `cf_clearance=` / `bot\d+:` / UUID hc-ping paths + size <50 MB per файл + aggregate <200 MB
  - Capture-fixtures CLI (TH-05 если P2 GO) scrub'ит ДО записи на disk (дублирующий barrier)

## Что зафиксировано в CONTEXT.md

- 7 решений D-901..D-907 + Claude's Discretion items
- Полный canonical_refs список (PROJECT/REQUIREMENTS/ROADMAP/STATE + research SUMMARY/STACK/ARCHITECTURE/PITFALLS + Phase 8 CONTEXT + spike skill + 3 live fixtures + production code paths)
- code_context: reusable assets, established patterns, integration points
- Deferred ideas → v1.2: auto-scheduled cron, GitHub Action CI, flake-decorator ban canary, parser-drift auto-classifier

## Plan-shape для downstream

```
09-01 (W0 sequential, must-have)
  TH-01: syrupy 4.7 + HTMLSnapshotExtension
  TH-02: fixture path convention + sidecar JSON + PII canary + size guard
09-02 (W1 parallel, 2 plans на разные файлы)
  TH-03: tests/live/test_parser_drift.py (cassette + --refresh-live)
  TH-06: storage/schemas.py + SqliteSnapshotWriter.persist injection + 5% gate
09-03 (W2 sequential, conditional)
  IF elapsed < 8h: TH-04 brand-coverage canary + TH-05 capture-fixtures CLI
  ELSE: defer-to-v1.2 doc cascade
```

## Что отложено в Claude's Discretion

- Точное имя файла для `HTMLSnapshotExtension` — `tests/conftest.py` если <30 LOC, иначе `tests/_snapshot_extension.py`
- Точное имя для Pydantic schemas — `src/ga_crawler/storage/schemas.py` (новый) или extend `storage/types.py` (planner inspects)
- Sidecar JSON helper — отдельный модуль или inline в conftest
- UUID hc-ping regex — стандартная UUID v4
- `parser-drift-YYYY-MM-DD.md` template shape — следует Phase 1 spike memo convention

## Next command

```
/gsd-plan-phase 9
```

Это запустит researcher (если нужен — но research v1.1 уже сделан) → planner → plan-checker → produce 3 PLAN.md в `.planning/phases/09-live-html-harness/`.

После plan ready → `/gsd-execute-phase 9` запустит W0/W1/W2 с GO/NO-GO checkpoint в 8h budget gate.

## Verification gate после Phase 9 ship

1. `pytest -m live` (cassette mode) проходит на всех 3 Phase 8 fixtures
2. `pytest -m live --refresh-live` syrupy-asserts'ит против Camoufox-fetched HTML (operator-runs only)
3. PII canary + size guard test проходит в default `pytest` (catches before merge)
4. Pydantic `RawProduct` validation injected at `SqliteSnapshotWriter.persist` — synthetic test инжектит invalid SKU batch → assert `runs.stats.schema_rejected_rate > 0.05` → assert run failed reason `schema_validation_rejected_rate`
5. Tests green ≥845 (current ~830 после Phase 8; +~15 от Phase 9 must-have; +~10 если P2 GO)
6. P2 GO/NO-GO решён через time-budget gate; cascade doc если NO-GO

## Related

- [[Текущие приоритеты — Phase 9 contexted, plan next]] — что делать прямо сейчас
- ~~[[Текущие приоритеты — Phase 8 W1 done, W2 next]]~~ — superseded (Phase 8 закрыт 2026-05-13, Phase 9 contexted 2026-05-14)
- [[2026-05-14 — Phase 8 W1 GREEN shipped + cli.py dotenv-leak hotfix closes data egress]] — Phase 8 finish trail (предыдущая сессия)
- [[Pydantic RawProduct validation at SqliteSnapshotWriter — 5 percent reject-rate gate orthogonal to PARSE-FIX-04]] (D-903/D-904)
- [[pytest -m live — operator-only opt-in документируется в README §8]] (D-905)
- [[P2 bundle gate — time-budget 8h elapsed W0+W1 для GO NO-GO checkpoint]] (D-902)
- [[Per-retailer Pydantic schema split — goldapple strict viled relaxed для legitimate Nones]] (D-904)
- `.planning/phases/09-live-html-harness/09-CONTEXT.md` — load-bearing artefact (committed 2555847)
- `.planning/phases/09-live-html-harness/09-DISCUSSION-LOG.md` — audit trail с альтернативами для каждого вопроса

---

**Bottom line:** Phase 9 contexted end-to-end через `/gsd-discuss-phase 9` — все 4 user-selected gray areas closed (wave structure, Pydantic boundary, live-drift cron integration, PII canary enforcement). 3-plan wave shape decided; P2 gated на 8h time-budget. Next: `/gsd-plan-phase 9` → planner expands CONTEXT.md в 3 executable PLAN.md.
