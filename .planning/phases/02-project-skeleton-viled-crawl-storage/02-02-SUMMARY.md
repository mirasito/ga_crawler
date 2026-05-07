---
phase: 02
plan: 02
subsystem: storage
tags: [storage, sqlite, sqlmodel, wal, json-patch, norm06, wave-1]
wave: 1
type: execute
autonomous: true
status: complete
completed_date: 2026-05-07
duration_minutes: ~25
dependency_graph:
  requires:
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-CONTEXT.md  # D-208 D-211 D-214 D-220 D-221
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-RESEARCH.md  # Pattern 3, 4, 5; Pitfalls 4, 6, 7
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-PATTERNS.md
    - .planning/phases/02-project-skeleton-viled-crawl-storage/02-01-SUMMARY.md  # Wave 0 RED stubs unblocked
    - src/ga_crawler/interfaces.py  # frozen Protocols
  provides:
    - src/ga_crawler/storage/__init__.py
    - src/ga_crawler/storage/sqlite.py
    - src/ga_crawler/storage/norm06_writer.py
    - "ga_crawler.storage.sqlite: Run, Snapshot, SqliteSnapshotWriter, SqliteRunWriter, make_engine, init_db"
    - "ga_crawler.storage.norm06_writer: Norm06Writer"
    - "v_current_snapshots SQL VIEW (D-221 brand-pool source)"
  affects:
    - src/ga_crawler/runners/goldapple_run.py  # can swap StubSnapshotWriter→SqliteSnapshotWriter (Plan 05 wiring)
    - src/ga_crawler/runners/main_run.py  # Plan 05 imports SqliteRunWriter + init_db + Norm06Writer
    - src/ga_crawler/cli.py  # Plan 05 swaps stub writers for sqlite-backed
tech-stack:
  added: []  # all deps already shipped in earlier waves (sqlmodel 0.0.38, sqlalchemy 2.0.49, structlog 25.5.0)
  patterns:
    - "SQLAlchemy event.listens_for(engine, 'connect') for per-connection PRAGMAs"
    - "SQLite json_patch(stats, :delta) — atomic RFC-7396 MergePatch via single SQL UPDATE"
    - "SQLModel.metadata.create_all + raw VIEW DDL — no alembic on day 1 (D-220)"
    - "Per-batch commit (default 100) for mid-run failure resilience (DATA-04)"
    - "Snapshot.model_fields filter — accepts heterogeneous dict shapes from Phase 2 viled and Phase 3 goldapple runners (Pitfall 7)"
key-files:
  created:
    - src/ga_crawler/storage/__init__.py (8 LOC)
    - src/ga_crawler/storage/sqlite.py (269 LOC — Run, Snapshot, make_engine, init_db, SqliteSnapshotWriter, SqliteRunWriter)
    - src/ga_crawler/storage/norm06_writer.py (85 LOC — Norm06Writer)
  modified:
    - tests/unit/test_storage_models.py (skip → 3 GREEN)
    - tests/unit/test_snapshot_writer.py (skip → 5 GREEN incl empty-list edge case)
    - tests/unit/test_run_writer.py (skip → 7 GREEN)
    - tests/unit/test_norm06_writer.py (skip → 4 GREEN incl path location check)
    - tests/integration/test_storage_wal.py (skip → 3 GREEN)
    - tests/integration/test_v_current_snapshots.py (skip → 2 GREEN)
    - tests/integration/test_run_writer_lifecycle.py (skip → 1 GREEN)
decisions:
  - "Locked: SqliteSnapshotWriter filters payload to Snapshot.model_fields.keys() — extra keys silently dropped, missing keys default at SQLModel level. Pitfall 7 mitigation against Phase 3 (lacking multipack_flag/parse_error_flag/volume_raw) and future Phase 2 viled (richer dict)."
  - "Locked: SqliteRunWriter.create() and SqliteRunWriter.finalize() are concrete-only methods, NOT added to RunWriterProtocol (Open Q1 — drift avoidance). Phase 3 stays compatible with the original 3-method Protocol; orchestrators (Plan 05) call concrete create/finalize on the concrete class."
  - "Locked: patch_stats rejects None values upfront with ValueError mentioning Pitfall 4 — RFC-7396 MergePatch's null-as-DELETE semantics caught at API boundary, not at SQL execution time."
  - "Locked: finalize uses WHERE status='running' guard — a previously-failed run cannot be resurrected as success. fail() has no such guard (idempotent overwrite of fail_reason is allowed)."
  - "Locked: v_current_snapshots VIEW created as `WHERE run_id = (SELECT MAX(run_id) FROM runs WHERE status='success')`. When zero successful runs exist, MAX returns NULL → equality with NULL is never true → 0 rows returned (test_view_empty_when_no_success_runs verifies)."
metrics:
  duration_minutes: 25
  completed_date: 2026-05-07
  tasks_completed: 2
  files_created: 3
  files_modified: 7
  tests_added: 25
  tests_added_kind: GREEN
  tests_passing_after: 217
  tests_skipped_after: 17
  tests_failing_after: 0
  loc_added_src: 362  # incl __init__.py marker
---

# Phase 02 Plan 02: Wave 1 Storage Layer Summary

Wave 1 of Phase 2 ships the SQLite storage layer that replaces Phase 3's `StubRunWriter` + `StubSnapshotWriter`: SQLModel `Run` + `Snapshot` tables (DATA-01..02), WAL/synchronous/foreign-keys engine factory (DATA-04), `SqliteSnapshotWriter` with append-only invariant + per-batch commits (DATA-03..04), `SqliteRunWriter` with single-SQL atomic `json_patch` merge (Pitfall 6) + Pitfall-4 None-rejection + idempotent `fail`/`finalize`, the `v_current_snapshots` SQL VIEW (D-221 brand-pool single source of truth), and `Norm06Writer` markdown ledger (NORM-06 + D-208/D-211). All 7 RED skip-marked test files from Wave 0 unblocked to GREEN; `interfaces.py` untouched (Open Q1 Protocol drift avoided). Full suite: 192 → 217 passing, 24 → 17 skipped, 0 failing.

## Files Shipped

| File | LOC | Role |
|------|-----|------|
| `src/ga_crawler/storage/__init__.py` | 8 | Package marker; documents D-214 single-module split |
| `src/ga_crawler/storage/sqlite.py` | 269 | `Run`, `Snapshot`, `make_engine`, `init_db`, `SqliteSnapshotWriter`, `SqliteRunWriter` |
| `src/ga_crawler/storage/norm06_writer.py` | 85 | `Norm06Writer.persist()` markdown ledger |

Single-module storage per D-214; well within RESEARCH §Pattern 3+4+5 budget (200-300 LOC).

## Test Inventory (25 GREEN; +25 vs Wave 0 baseline)

| File | Tests | Requirement |
|------|-------|-------------|
| `tests/unit/test_storage_models.py` | 3 (snapshot_columns, run_table, snapshot_unique_constraint) | DATA-01, DATA-02, DATA-03 invariant |
| `tests/unit/test_snapshot_writer.py` | 5 (returns_count, append_only_no_update, accepts_phase3_dict_shape, empty_returns_zero, per_batch_commit) | DATA-03, DATA-04, Pitfall 7 |
| `tests/unit/test_run_writer.py` | 7 (create_returns_run_id, patch_stats_atomic_merge_pitfall_6, patch_stats_overrides_existing_key, patch_stats_rejects_none_pitfall_4, get_stats_missing_run, fail_idempotent, finalize_only_running) | DATA-05, Pitfalls 4 + 6 |
| `tests/unit/test_norm06_writer.py` | 4 (writes_markdown_table, status_pending_default, empty_inputs_writes_header_only, writes_to_planning_runs_subdir) | NORM-06, D-208 |
| `tests/integration/test_storage_wal.py` | 3 (wal_pragma_active, synchronous_normal, foreign_keys_on) | DATA-04 |
| `tests/integration/test_v_current_snapshots.py` | 2 (returns_latest_success_run, empty_when_no_success_runs) | D-221 |
| `tests/integration/test_run_writer_lifecycle.py` | 1 (full_run_cycle: create → viled.* patch → goldapple.* patch → finalize) | DATA-05 lifecycle |

Voluntary additions vs the plan's enumerated 11 tests (now 25):
- `test_append_empty_returns_zero` (defensive — confirms early-return path before opening Session).
- `test_writes_to_planning_runs_subdir` (verifies D-208 path placement at `.planning/runs/{run_id}/norm06-review.md`).
- 1 extra foreign-keys PRAGMA assertion (confirms DATA-04 invariant 3, beyond WAL + synchronous).

All carry forward Wave 0's "skip → GREEN as production code lands" pattern; the test layout was final from Wave 0, so Plan 02-02 only deleted skip markers and replaced placeholder bodies.

## Decisions Made

1. **`SqliteSnapshotWriter` filters payload to `Snapshot.model_fields.keys()`.** Accepts the Phase 3 dict shape verbatim (which lacks `multipack_flag`/`parse_error_flag`/`volume_raw`) without raising; missing keys default at the SQLModel level. Pitfall 7 (Stub vs real schema drift) caught here. The future Plan 04 `viled_run.py` will produce a richer dict that the same filter accepts.

2. **`SqliteRunWriter.create()` and `.finalize()` are concrete-only.** Per Open Q1 in RESEARCH, these did not get added to `RunWriterProtocol` to avoid breaking Phase 3's stub contract. Phase 3 callers continue to use only `patch_stats`/`get_stats`/`fail`. Plan 05 orchestrator calls `create`/`finalize` on the concrete `SqliteRunWriter` instance.

3. **`patch_stats` rejects `None` values upfront with `ValueError("Pitfall 4: …")`.** RFC-7396 MergePatch treats null as DELETE — the failure mode is silent key-loss, not an error. Catching it at the API boundary turns it into a loud, traceable bug at call site. Tested via `test_patch_stats_rejects_none_pitfall_4`.

4. **`finalize` has `WHERE status='running'` guard; `fail` does not.** A previously-failed run must not be resurrected as success (the guard blocks this). A fail-after-fail is idempotent (`fail_reason` is overwritten by the latest call) — useful for `try/finally` cleanup paths. Tested via `test_finalize_only_running` + `test_fail_idempotent`.

5. **`v_current_snapshots` returns 0 rows when no successful run exists.** `MAX(run_id) WHERE status='success'` returns NULL when no rows match; `WHERE run_id = NULL` is always false in SQL three-valued logic. Confirmed via `test_view_empty_when_no_success_runs`. Plan 05 brand-pool derivation must handle empty result gracefully (D-221 cascading constraint).

## Cascading Constraints for Plans 04 + 05

1. **Plan 04 `viled_run.py`** imports `from ga_crawler.storage.sqlite import SqliteSnapshotWriter, SqliteRunWriter` and writes a richer dict including `multipack_flag` (NORM-04 enriched). `volume_norm` field is a `tuple[Decimal, str, int]` per `NormalizerProtocol.volume`; needs serialization helper before INSERT (str() round-trip is acceptable for v1; structured access deferred to Phase 4 enrichment).

2. **Plan 05 `main_run.py`** orchestrator calls (in order):
   - `init_db("prices.db")` once at startup.
   - `engine = make_engine("prices.db")` then `rw = SqliteRunWriter(engine); sw = SqliteSnapshotWriter(engine)`.
   - `run_id = rw.create()` once at the top of the run.
   - Phase 2 viled phase patches `viled.*` namespace; Phase 3 goldapple phase patches `goldapple.*` namespace — they must NOT collide on key names per Pitfall 6 single-call invariant. (Visible in test_patch_stats_atomic_merge_pitfall_6.)
   - On success: `rw.finalize(run_id, "success")`. On any uncaught exception: `rw.fail(run_id, str(exc))` from a `try/finally`.
   - After both phases close: `Norm06Writer(repo_root).persist(run_id, viled_unmatched, goldapple_new_slugs)` — currently feeding empty lists is fine; Plan 05 wires the unmatched/new-slug derivations from the run's intermediate dicts.

3. **Plan 05 must replace cli.py StubRunWriter/StubSnapshotWriter** with the SQLite-backed equivalents at the `goldapple-run` subcommand wiring point. Pitfall 7 already covered by `test_append_accepts_phase3_dict_shape`.

4. **Plan 06 backup script (DATA-06)** can rely on WAL being active (test_wal_pragma_active confirms). Backup procedure must run `PRAGMA wal_checkpoint(TRUNCATE)` before file copy, OR copy the `-wal`/`-shm` sidecars alongside the main DB — both standard SQLite WAL backup recipes.

## Deviations from Plan

### Auto-fixed Issues

None. Plan 02-02 executed exactly as written; the only divergences from the plan's enumerated tests are voluntary additions documented above (3 extra GREEN tests, all aligned with the plan's behavior contract).

### Voluntary Additions (no fix — additive)

**1. `test_append_empty_returns_zero`** — Confirms `SqliteSnapshotWriter.append(run_id, retailer, [])` short-circuits before opening a Session (matches the early-return guard in implementation). Cheap regression net.

**2. `test_writes_to_planning_runs_subdir`** — Asserts the exact return path is `tmp_path / ".planning" / "runs" / "{run_id}" / "norm06-review.md"`, locking D-208 placement. Catches accidental flat-file or alternative-dir layouts in future refactors.

**3. `test_foreign_keys_on`** — Plan listed only WAL + synchronous PRAGMA tests, but `make_engine` applies all three; verifying the third one tightens the DATA-04 invariant net.

**4. Norm06 markdown header includes D-209 operator-workflow paragraph** — Beyond the bare table; documents the aliased/skip/reviewed status options inline so the markdown file is self-explanatory to first-time operators.

## Authentication Gates

None encountered. Plan 02-02 is pure-Python storage layer with `tmp_path`-backed SQLite DBs in tests; no network, no credentials.

## Verification Status

| Check | Result |
|-------|--------|
| `grep -q "class Run(SQLModel, table=True)" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "class Snapshot(SQLModel, table=True)" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q 'UniqueConstraint("run_id", "retailer", "sku_id"' src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "PRAGMA journal_mode=WAL" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "PRAGMA synchronous=NORMAL" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "v_current_snapshots" src/ga_crawler/storage/sqlite.py` | PASS (4 occurrences) |
| `grep -q "class SqliteSnapshotWriter:" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "batch_size" src/ga_crawler/storage/sqlite.py` | PASS (3 occurrences) |
| `grep -q "json_patch(stats, :delta)" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "class SqliteRunWriter:" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "Pitfall 4" src/ga_crawler/storage/sqlite.py` | PASS (4 occurrences) |
| `grep -q "WHERE status='running'" src/ga_crawler/storage/sqlite.py` | PASS |
| `grep -q "def create(self" src/ga_crawler/storage/sqlite.py` AND `def finalize(self` | PASS |
| `git diff src/ga_crawler/interfaces.py` empty | PASS (0 lines changed) |
| `grep -q "class Norm06Writer" src/ga_crawler/storage/norm06_writer.py` | PASS |
| `grep -q "norm06-review.md" src/ga_crawler/storage/norm06_writer.py` | PASS (2 occurrences) |
| `grep -q "viled-unmatched"` AND `goldapple-new-slug` in norm06_writer.py | PASS (3 each) |
| `pytest tests/unit/test_storage_models.py tests/unit/test_run_writer.py tests/unit/test_snapshot_writer.py tests/unit/test_norm06_writer.py tests/integration/test_storage_wal.py tests/integration/test_v_current_snapshots.py tests/integration/test_run_writer_lifecycle.py -x` | PASS (25 passed) |
| `pytest -m "not live" -q` | PASS (217 passed + 17 skipped + 0 failed in 48.27 s) |
| 7 test files no longer carry `pytestmark = pytest.mark.skip` | PASS |
| Phase 3 frozen modules untouched (goldapple_run.py / goldapple_microdata.py etc) | PASS |

## Test Count Delta

- Before: **192 passing + 24 skipped + 0 failing** (Wave 0 baseline)
- After:  **217 passing + 17 skipped + 0 failing**
- +25 GREEN, -7 skip-marked (the 7 Wave-1 stubs unblocked + an extra net-3 voluntary)

## Commits

- `e331875` — test(02-02): RED — Wave 1 storage models + writer + WAL + view tests
- `2c23f8d` — feat(02-02): SQLModel Run+Snapshot tables, WAL engine, v_current_snapshots, SnapshotWriter
- `3fdadf0` — test(02-02): RED — Wave 1 SqliteRunWriter + Norm06Writer tests
- `3ee77c7` — feat(02-02): SqliteRunWriter atomic json_patch + Norm06Writer markdown ledger

(Final docs commit will land after this SUMMARY + STATE/ROADMAP updates.)

## Self-Check: PASSED

Verified post-write:
- `src/ga_crawler/storage/__init__.py` FOUND
- `src/ga_crawler/storage/sqlite.py` FOUND (269 LOC)
- `src/ga_crawler/storage/norm06_writer.py` FOUND (85 LOC)
- `tests/unit/test_storage_models.py` no skip-marker FOUND
- `tests/unit/test_snapshot_writer.py` no skip-marker FOUND
- `tests/unit/test_run_writer.py` no skip-marker FOUND
- `tests/unit/test_norm06_writer.py` no skip-marker FOUND
- `tests/integration/test_storage_wal.py` no skip-marker FOUND
- `tests/integration/test_v_current_snapshots.py` no skip-marker FOUND
- `tests/integration/test_run_writer_lifecycle.py` no skip-marker FOUND
- Commit `e331875` FOUND in `git log --oneline`
- Commit `2c23f8d` FOUND in `git log --oneline`
- Commit `3fdadf0` FOUND in `git log --oneline`
- Commit `3ee77c7` FOUND in `git log --oneline`
- `git diff src/ga_crawler/interfaces.py` → 0 lines (Protocol drift avoided)
