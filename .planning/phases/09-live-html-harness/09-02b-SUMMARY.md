---
phase: "09-live-html-harness"
plan: "02b"
subsystem: "storage/validation + runner/gates"
tags:
  - pydantic
  - validation
  - schema
  - gate
  - tdd
  - storage
  - python
dependency_graph:
  requires:
    - "09-01"
  provides:
    - "GoldappleRawProduct (strict) + ViledRawProduct (relaxed) Pydantic schemas"
    - "SqliteSnapshotWriter.append write-boundary validation (per-row model_validate)"
    - "schema_rejected_rate_gate(threshold=0.05) frozen-dataclass gate"
    - "SCHEMA_STATS_KEYS namespace for orchestrator wire-up"
  affects:
    - "src/ga_crawler/storage/sqlite.py (append loop modified)"
    - "src/ga_crawler/runner/gates.py (schema gate added)"
    - "src/ga_crawler/runner/stats.py (SCHEMA_STATS_KEYS added)"
tech_stack:
  added:
    - "Pydantic 2.10 StringConstraints + Annotated NonEmptyStr pattern"
    - "ConfigDict(extra='ignore') + model_validate per-row injection"
  patterns:
    - "Frozen dataclass gate result (mirrors Phase 8 ParserDriftGateResult)"
    - "Dispatcher table _SCHEMA_BY_RETAILER for retailer-agnostic validation"
    - "Error projection {loc, type} only — T-09-PII guard"
key_files:
  created:
    - "src/ga_crawler/storage/schemas.py"
    - "tests/storage/__init__.py"
    - "tests/storage/test_schemas.py"
    - "tests/integration/test_writer_schema_gate.py"
    - "tests/runner/test_schema_rejected_gate.py"
  modified:
    - "src/ga_crawler/storage/sqlite.py"
    - "src/ga_crawler/runner/gates.py"
    - "src/ga_crawler/runner/stats.py"
    - "tests/integration/test_storage_integration.py"
    - "tests/integration/test_phase8_synthetic_regression.py"
    - "tests/unit/test_snapshot_writer.py"
decisions:
  - "D-904 per-retailer split confirmed: GoldappleRawProduct (strict volume_raw=NonEmptyStr) + ViledRawProduct (relaxed volume_raw=Optional[NonEmptyStr]=None)"
  - "Writer method is append() per RESEARCH §9 Q1 — CONTEXT.md D-903 'persist' is conceptual name only"
  - "SCHEMA_STATS_KEYS is run-level (not retailer-scoped) per RESEARCH §9 Q3 — no SchemaStatsBuilder class"
  - "Rule 1 fix: 3 pre-existing tests updated to include volume_raw for goldapple rows (schema enforcement is intentional behavior change)"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-14"
  tasks_completed: 3
  tests_added: 27
  files_created: 5
  files_modified: 6
---

# Phase 09 Plan 02b: Pydantic Per-Retailer Schemas + Write-Boundary Gate Summary

Pydantic 2.10 per-retailer raw-product schemas wired at `SqliteSnapshotWriter.append` write-boundary (D-903), with strict goldapple / relaxed viled split (D-904) and `schema_rejected_rate_gate(threshold=0.05)` mirroring Phase 8 D-815 pattern.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | TH-06a/b schema test stubs | 23580cc | tests/storage/__init__.py, tests/storage/test_schemas.py |
| 1 GREEN | Per-retailer Pydantic schemas | 680739e | src/ga_crawler/storage/schemas.py |
| 2 RED | TH-06c writer integration stubs | 7f6c25e | tests/integration/test_writer_schema_gate.py |
| 2 GREEN | Wire model_validate at append | aafedc1 | src/ga_crawler/storage/sqlite.py + 3 regression fixes |
| 3 RED | TH-06d gate + stats stubs | 0ee3abe | tests/runner/test_schema_rejected_gate.py |
| 3 GREEN | schema_rejected_rate_gate + SCHEMA_STATS_KEYS | 32c6093 | src/ga_crawler/runner/gates.py, src/ga_crawler/runner/stats.py |

## What Was Built

### src/ga_crawler/storage/schemas.py (greenfield)
- `NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]`
- `RawProductBase`: sku_id, url, name, brand (all NonEmptyStr) + current_price (Field gt=0)
- `GoldappleRawProduct(RawProductBase)`: STRICT — volume_raw: NonEmptyStr required; justified by 83% PDP shape-table coverage (spike-findings SKILL.md L39)
- `ViledRawProduct(RawProductBase)`: RELAXED — volume_raw: Optional[NonEmptyStr] = None; justified by Contre-Jour / Wild Vetiver legitimate-None cases (08-01-SUMMARY Bug #3)
- `ConfigDict(extra='ignore')` on both — writer's valid_fields pre-filter already strips unknowns

### src/ga_crawler/storage/sqlite.py (modified)
- Added `from pydantic import ValidationError` + `from ga_crawler.storage.schemas import ...`
- Module-level `_SCHEMA_BY_RETAILER = {"goldapple": GoldappleRawProduct, "viled": ViledRawProduct}`
- `_REJECTED_REASONS_CAP = 50` — memory bound per RESEARCH §4.2
- `SqliteSnapshotWriter.__init__`: added `self._last_rejected_reasons: list[dict] = []`
- `SqliteSnapshotWriter.append`: per-row `schema_cls.model_validate(payload)` inside loop; ValidationError -> `continue` (skip INSERT) + append to `rejected_reasons` (capped at 50); error projection `{loc, type}` only (T-09-PII guard per RESEARCH §7.2); `self._last_rejected_reasons = rejected_reasons` after loop

### src/ga_crawler/runner/gates.py (modified)
- `SchemaRejectedGateResult`: frozen dataclass with `passed, rejected_rate, rejected_count, total_attempted, failure_reason`
- `schema_rejected_rate_gate(rejected_count, total_attempted, *, threshold=0.05)`: STRICT `>` semantics (exactly 0.05 passes; 0.0501 fails) — mirrors Phase 8 D-815 convention
- `failure_reason = "schema_validation_rejected_rate"` when failed
- Both added to `__all__`

### src/ga_crawler/runner/stats.py (modified)
- `SCHEMA_STATS_KEYS: tuple[str, ...] = ("schema.rejected_count", "schema.rejected_rate", "schema.rejected_reasons")` — run-level, NOT retailer-scoped
- Added to `__all__`

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/storage/test_schemas.py | 12 | GREEN |
| tests/integration/test_writer_schema_gate.py | 6 | GREEN |
| tests/runner/test_schema_rejected_gate.py | 9 | GREEN |
| Full suite (not live) | 875 | GREEN (up from 860 baseline) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing brand_norm/name_norm in test_writer_schema_gate._row helper**
- **Found during:** Task 2 RED → GREEN transition
- **Issue:** `_row()` helper in new integration test lacked `brand_norm`/`name_norm` which are NOT NULL columns in Snapshot; INSERT raised IntegrityError
- **Fix:** Added `brand_norm`, `name_norm`, `currency`, `stock_state` to `_row()` helper
- **Files modified:** tests/integration/test_writer_schema_gate.py
- **Commit:** aafedc1

**2. [Rule 1 - Bug] test_storage_integration._row missing volume_raw (regression caused by our schema enforcement)**
- **Found during:** Task 2 GREEN full-suite run
- **Issue:** Existing Phase 2 integration test used `retailer="goldapple"` rows without `volume_raw`; now schema-rejected, assert n==2 failed
- **Fix:** Added `volume_raw="50 мл"` to `_row()` in test_storage_integration.py with explanatory comment
- **Files modified:** tests/integration/test_storage_integration.py
- **Commit:** aafedc1

**3. [Rule 1 - Bug] test_phase8_synthetic_regression._gold_snap set volume_raw=None for null-volume regression rows**
- **Found during:** Task 2 GREEN full-suite run
- **Issue:** Phase 8 test simulated content drift by setting `volume_raw=None` when `volume_norm=None`; goldapple strict schema rejected those rows, so SQL null-rate query returned 0.0 instead of 0.6, test assertion failed
- **Fix:** Set `volume_raw="50 мл"` unconditionally (scraping OK; normalization may fail = content drift independent of structural presence). Added comment explaining the schema/content drift distinction.
- **Files modified:** tests/integration/test_phase8_synthetic_regression.py
- **Commit:** aafedc1

**4. [Rule 1 - Bug] test_snapshot_writer.test_append_accepts_phase3_dict_shape expected n==1 but now gets n==0**
- **Found during:** Task 2 GREEN full-suite run
- **Issue:** Phase 2 "Pitfall 7" compatibility test verified goldapple rows without volume_raw don't crash; Phase 9 intentionally schema-rejects them silently
- **Fix:** Updated assertion to `n == 0` + `len(writer._last_rejected_reasons) == 1`; added comment documenting the behavior change and that "no crash" contract still holds
- **Files modified:** tests/unit/test_snapshot_writer.py
- **Commit:** aafedc1

## Boundary Language Note

CONTEXT.md D-903 uses the conceptual name "persist" for the write-boundary. The ACTUAL method on `SqliteSnapshotWriter` is `append(run_id, retailer, products) -> int` (confirmed by reading sqlite.py pre-modification; RESEARCH §9 Q1 was correct). All implementation uses `append` verbatim. Future readers: `persist` in design docs = `append` in code.

## Architecture Note

**Cascade position:** Schema gate (structural drift) runs BEFORE Phase 8 `parser_drift_null_rate_gate` (content drift). The two gates are complementary:
- Schema gate: "did the parser emit the RIGHT SHAPE?" (volume_raw present and non-empty)
- PARSE-FIX-04 gate: "is the parsed/normalized content reasonable?" (volume_norm not overwhelmingly null)

## Orchestrator Wire-Up Scope

This plan ships the gate function + writer integration. Full orchestrator call-site change (`patch_stats(run_id, {schema.rejected_count: ...})` + gate result → `run_writer.fail(...)`) in `runners/main_run.py` is documented in the writer integration test (proves end-to-end contract) but implementation in the orchestrator is a follow-on task OR handled by a future plan.

## Known Stubs

None. All code paths are live with real behavior.

## Threat Flags

None. All mitigations from plan's threat model are implemented:
- T-09-SCHEMA: per-row model_validate + schema-reject + rate-gate implemented
- T-09-GATE: 0.05 threshold, STRICT `>`, kw-only arg for revisitability
- T-09-PII: error projection to `{loc, type}` only; verified by test_writer_no_input_key_in_rejected_reasons

## Self-Check: PASSED

- src/ga_crawler/storage/schemas.py: FOUND
- src/ga_crawler/storage/sqlite.py: FOUND (model_validate at L212, _SCHEMA_BY_RETAILER at L49, _last_rejected_reasons at L190)
- src/ga_crawler/runner/gates.py: FOUND (schema_rejected_rate_gate at L370, in __all__ at L456)
- src/ga_crawler/runner/stats.py: FOUND (SCHEMA_STATS_KEYS at L166, in __all__ at L234)
- tests/storage/__init__.py: FOUND
- tests/storage/test_schemas.py: FOUND
- tests/integration/test_writer_schema_gate.py: FOUND
- tests/runner/test_schema_rejected_gate.py: FOUND
- Commits: 23580cc, 680739e, 7f6c25e, aafedc1, 0ee3abe, 32c6093 — all exist
- Full suite: 875 passed, 1 skipped — GREEN
