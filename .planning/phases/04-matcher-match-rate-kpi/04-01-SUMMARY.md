---
phase: 04-matcher-match-rate-kpi
plan: 01
subsystem: matcher
tags: [storage, sqlmodel, config, pyproject, tdd, wave-1]
dependency_graph:
  requires:
    - storage/sqlite.py (Run + Snapshot tables, init_db, make_engine)
    - config.py (ViledConfig.from_pyproject mirror)
  provides:
    - storage/sqlite.py::Match (denormalized 13-column SQLModel, composite PK)
    - matcher/__init__.py (package marker)
    - matcher/config.py::MatchConfig (frozen dataclass + from_pyproject loader)
    - pyproject.toml::[tool.ga_crawler.match] (3 operator-tunable constants)
  affects:
    - tests/unit/test_storage_models.py (extended +4 tests)
    - tests/unit/test_match_config.py (new, 5 tests)
tech_stack:
  added:
    - none (reuses existing tomllib, SQLModel, sqlalchemy)
  patterns:
    - SQLModel composite-PK declaration (3 primary_key=True fields, no auto-id)
    - pyproject namespace mirror (ViledConfig → MatchConfig, exact pattern reuse)
    - idempotent CREATE TABLE IF NOT EXISTS via SQLModel.metadata.create_all (D-415, no alembic)
key_files:
  created:
    - src/ga_crawler/matcher/__init__.py
    - src/ga_crawler/matcher/config.py
    - tests/unit/test_match_config.py
  modified:
    - src/ga_crawler/storage/sqlite.py (added Match class + __all__ export)
    - pyproject.toml (appended [tool.ga_crawler.match] block)
    - tests/unit/test_storage_models.py (added 4 Match regression tests + import)
decisions_honored:
  - D-401 (13-column denormalized matches schema with composite PK)
  - D-403 (N→1 keep-all: composite PK supports many goldapple_sku per viled_sku)
  - D-406 (seed sanity_gate_p = 20)
  - D-407 (p_auto_suggest_factor=0.7, p_auto_suggest_after_runs=4)
  - D-408 (TOML namespace [tool.ga_crawler.match])
  - D-413 (matcher/ package layout)
  - D-415 (no alembic, idempotent CREATE TABLE IF NOT EXISTS)
metrics:
  duration_seconds: ~450
  tasks_completed: 2
  files_created: 3
  files_modified: 3
  tests_added: 9
  tests_passing_before: 392
  tests_passing_after: 401
  completed_date: 2026-05-11
---

# Phase 4 Plan 04-01: Matcher Storage + Config Foundation Summary

**One-liner:** Wave 1 foundation — Match SQLModel table (13 D-401 columns, composite PK supporting D-403 N→1) + matcher/ package skeleton + MatchConfig pyproject loader (D-408 namespace) lay the substrate every downstream Phase 4 plan depends on, with 9 new regression tests pinning schema and config contracts.

## What Shipped

### Storage foundation (Task 1)
- **`Match` SQLModel** in `src/ga_crawler/storage/sqlite.py` with exact D-401 schema:
  - 3-field composite PK `(run_id, viled_sku, goldapple_sku)` — supports D-403 N→1 keep-all
  - 10 denormalized data columns: `brand_norm`, `name_norm`, `volume_norm`, `viled_price`, `goldapple_price`, `viled_was_price` (nullable), `goldapple_was_price` (nullable), `price_delta` (signed), `price_delta_pct` (REAL), `matched_at` (DEFAULT CURRENT_TIMESTAMP via `default_factory`)
  - `ix_match_run_brand` index for Phase 5 reporter per-brand aggregation queries
  - FK on `run_id` → `runs.run_id` (cascade matches the existing Snapshot pattern)
- **`__all__`** in `storage/sqlite.py` extended with `"Match"` between `"Snapshot"` and `"SqliteSnapshotWriter"`
- **`init_db()` unchanged** — `SQLModel.metadata.create_all(engine)` auto-discovers the new Match class (D-415: no alembic). Verified by `test_init_db_creates_matches_table` querying sqlite_master.

### Matcher package + config loader (Task 2)
- **`src/ga_crawler/matcher/__init__.py`** — single-line docstring per D-413 module layout: `"""Strict-key matcher (Phase 4): SQL JOIN builder, denominator query, stats namespace."""`
- **`src/ga_crawler/matcher/config.py`** — `MatchConfig` frozen dataclass + `from_pyproject` classmethod. Exact mirror of `src/ga_crawler/config.py::ViledConfig.from_pyproject`:
  - `sanity_gate_p: int = 20` (D-406/D-408 seed)
  - `p_auto_suggest_factor: float = 0.7` (D-407)
  - `p_auto_suggest_after_runs: int = 4` (D-407)
  - Missing file → defaults; per-key fallback for partial namespace.
- **`pyproject.toml`** — appended `[tool.ga_crawler.match]` block immediately after `[tool.ga_crawler.crawl.viled]` (matching the existing namespace placement convention).

### Regression coverage (9 new tests, 0 regressions)
- **`tests/unit/test_storage_models.py`** (+4 tests):
  - `test_match_columns` — pins 13-column D-401 schema
  - `test_match_composite_pk_allows_one_viled_to_many_goldapple` — D-403 invariant (3 rows with same viled_sku, distinct goldapple_sku all INSERT)
  - `test_match_composite_pk_rejects_exact_duplicate` — idempotency invariant (duplicate triple → IntegrityError)
  - `test_init_db_creates_matches_table` — D-415 bootstrap via sqlite_master probe
- **`tests/unit/test_match_config.py`** (5 new):
  - `test_match_config_defaults`
  - `test_from_pyproject_reads_match_namespace`
  - `test_from_pyproject_missing_file_returns_defaults`
  - `test_from_pyproject_partial_namespace_uses_defaults`
  - `test_pyproject_has_match_namespace` (production TOML regression canary)

## Verification

```
$ uv run pytest tests/unit/test_storage_models.py tests/unit/test_match_config.py -q
............                                                                  [100%]
12 passed in 0.32s

$ uv run pytest -q
401 passed, 1 skipped, 12 warnings in 104.37s
# Was 392 passed before plan; +9 new tests, 0 regressions

$ uv run python -c "from ga_crawler.storage.sqlite import Match; from ga_crawler.matcher.config import MatchConfig; print(Match.__tablename__, MatchConfig().sanity_gate_p)"
matches 20
```

## Decisions Honored

| Decision | How Applied |
|----------|-------------|
| D-401 (13-col denormalized schema + composite PK) | Match SQLModel declares exact column list verbatim from CONTEXT; composite PK via three `primary_key=True` fields (no auto-id) |
| D-403 (N→1 keep-all) | Composite PK includes both `viled_sku` and `goldapple_sku` — test `test_match_composite_pk_allows_one_viled_to_many_goldapple` proves multi-INSERT semantics |
| D-406 (seed P=20) | `MatchConfig.sanity_gate_p` default = 20; pyproject seed = 20 |
| D-407 (factor=0.7, after_runs=4) | Both defaults set in dataclass + TOML; matches D-203/D-310 cross-retailer pattern |
| D-408 (TOML namespace) | `[tool.ga_crawler.match]` appended to pyproject.toml; `from_pyproject` reads `data['tool']['ga_crawler']['match']` |
| D-413 (matcher/ package) | Created `src/ga_crawler/matcher/__init__.py` + `config.py`; package is now importable for Wave 2 plans to extend with `strict_key.py`, `stats.py` |
| D-415 (no alembic) | `init_db()` left unchanged — SQLModel.metadata.create_all picks up Match automatically; idempotent on re-deploy against existing DBs |

## Deviations from Plan

**None — plan executed exactly as written.**

All acceptance criteria met:
- `class Match(SQLModel, table=True)` count: 1
- `"Match",` in `__all__`: 1
- `ix_match_run_brand` index declared: 1
- `price_delta_pct: float` typed correctly: 1
- `[tool.ga_crawler.match]` in pyproject: 1
- Three constants present with documented values
- `src/ga_crawler/matcher/__init__.py` exists with non-empty content
- `class MatchConfig` + `from_pyproject` both present

No deviations from plan; no Rule 1/2/3 auto-fixes triggered; no checkpoints hit (plan is fully autonomous). No CLAUDE.md directives required adjustment.

## TDD Gate Compliance

Both tasks executed strict RED → GREEN cycle:
- **Task 1 RED**: `tests/unit/test_storage_models.py` extended with `Match` import → collection ImportError verified.
- **Task 1 GREEN**: Match class added → 7/7 tests pass.
- **Task 2 RED**: `tests/unit/test_match_config.py` created → ModuleNotFoundError on `ga_crawler.matcher.config` verified.
- **Task 2 GREEN**: matcher package + config + TOML block → 5/5 tests pass.

Per-task commits document both phases in git history (test additions and source additions co-committed within each task's single commit, as both phases happen within one auto-task in the plan). Commit messages reference D-numbers + test names explicitly.

## Open Questions / Wave 2 Handoff

Nothing blocking. Wave 2 (Plans 04-02..04-05) consumes this foundation:
- **`matcher/strict_key.py`** (Plan 04-02 or 04-03): will INSERT into the Match table via raw SQL (`text()` JOIN); the table now exists.
- **`matcher/stats.py`** (Plan 04-03 or 04-04): will build MatchStatsBuilder with the 10 D-414 keys; `MatchConfig` is now available for `threshold_p` plumbing.
- **`runners/matcher_run.py`** (Plan 04-04 or 04-05): will call `MatchConfig.from_pyproject()` for runtime constants.
- **`cli.py::_cmd_matcher`** (Plan 04-05): will plumb `--sanity-gate-p` override through `MatchConfig`.

No threat flags introduced: Match table holds public price/SKU data only (T-04-01-02 disposition: accept); `init_db` DDL is idempotent (T-04-01-03 mitigation applied); MatchConfig `int()/float()` wrappers raise TypeError on non-numeric TOML (T-04-01-04 mitigation applied via dataclass type-coercion).

## Self-Check: PASSED

Verified post-write:
- `src/ga_crawler/matcher/__init__.py` — FOUND
- `src/ga_crawler/matcher/config.py` — FOUND
- `tests/unit/test_match_config.py` — FOUND
- Commit `ab32b1e` (Task 1) — FOUND
- Commit `63eca48` (Task 2) — FOUND
- Full pytest 401 passed — VERIFIED
- Smoke `Match.__tablename__='matches'`, `MatchConfig().sanity_gate_p=20` — VERIFIED
