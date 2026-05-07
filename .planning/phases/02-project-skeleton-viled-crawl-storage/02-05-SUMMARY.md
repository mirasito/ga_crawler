---
phase: 02
plan: 05
subsystem: orchestrator-keystone
tags: [orchestrator, gates, stats, cli-cutover, d-212, d-218, d-221, pitfall-6, data-05]
requires:
  - 02-02-SUMMARY (storage layer — SqliteRunWriter, SqliteSnapshotWriter, init_db, make_engine, Norm06Writer)
  - 02-03-SUMMARY (normalizers — Normalizer facade, YamlBrandAlias, detect_multipack)
  - 02-04-SUMMARY (parsers/fetcher — ParseDispatcher, ViledFetcher, fetch_catalog_urls, ViledConfig)
provides:
  - "Retailer-agnostic gates: auto_suggest_threshold, final_threshold_gate, parse_quality_gate (D-203, D-218)"
  - "ViledStatsBuilder mirror of GoldappleStatsBuilder (Open Q7)"
  - "run_viled_phase 8-step pipeline with sequential parse-quality + sanity-N gates"
  - "run_weekly composition orchestrator with DATA-05 try/except lifecycle"
  - "weekly-run CLI subcommand backed by run_weekly"
affects:
  - "src/ga_crawler/cli.py — 4 Stub classes deleted (D-212), goldapple-run subcommand removed"
  - "tests/integration/test_storage_integration.py — rewritten against production storage layer"
tech-stack:
  added: []
  patterns: ["runner.gates retailer-agnostic refactor", "ViledStatsBuilder additive namespace mirror", "run_viled_phase 8-step pipeline", "main_run try/except DATA-05 lifecycle", "Norm06 ledger D-211 ownership", "v_current_snapshots brand-pool D-221 (table read mid-run)"]
key-files:
  created:
    - src/ga_crawler/runners/viled_run.py (328 LOC — orchestrator)
    - src/ga_crawler/runners/main_run.py (294 LOC — composition)
    - tests/unit/test_auto_suggest_threshold.py (73 LOC, 8 tests)
    - tests/unit/test_viled_stats_builder.py (125 LOC, 16 tests)
  modified:
    - src/ga_crawler/runner/gates.py (139 -> 239 LOC; +D-203 + D-218 helpers + 3 backward-compat shims)
    - src/ga_crawler/runner/stats.py (146 -> 219 LOC; +VILED_STATS_KEYS + ViledStatsBuilder)
    - src/ga_crawler/cli.py (218 -> 165 LOC; -53 LOC after D-212 stub deletion)
    - tests/unit/test_sanity_n_gate.py (skip-stub -> 57 LOC, 12 tests)
    - tests/unit/test_parse_quality_gate.py (skip-stub -> 56 LOC, 7 tests)
    - tests/integration/test_viled_run_e2e_with_real_storage.py (skip-stub -> 324 LOC, 5 tests, 1 skip)
    - tests/integration/test_main_run_e2e.py (skip-stub -> 310 LOC, 5 tests)
    - tests/integration/test_storage_integration.py (rewritten — production storage; 176 LOC, 8 tests)
decisions:
  - id: D-203
    decision: "auto_suggest_threshold(history, factor, min_runs) is the canonical retailer-agnostic helper; auto_suggest_m kept as backward-compat shim forwarding to (history, 0.7, 4)"
    rationale: "Phase 3 callers (runners/goldapple_run.py imports auto_suggest_m, final_m_gate) must stay green; refactor adds new generic helpers + shims so no Phase 3 file is touched. Verified by `git diff src/ga_crawler/runners/goldapple_run.py` empty after Plan 02-05."
  - id: D-218
    decision: "Sequential gates in viled_run.py: parse_quality_gate FIRST (>5% null required-field rate fails), sanity_gate_n SECOND (count < N fails). Either failing → run_writer.fail(reason); snapshot rows still persist (audit trail invariant)."
    rationale: "Parse-quality is a content-quality signal; sanity-N is a count signal. Running parse-quality first means a 'parsed garbage' run fails for the right reason rather than masquerading as a low-count run. Audit-trail invariant preserved: failure to gate does NOT delete persisted rows; snapshots are immutable per DATA-03."
  - id: D-221 (mid-run brand-pool read)
    decision: "main_run.py reads viled brand list from `snapshots WHERE retailer='viled' AND run_id=:rid` directly (NOT v_current_snapshots) because the run is still 'running' when the goldapple phase starts."
    rationale: "v_current_snapshots filters on `runs.status='success'`. At the point we need the brand list (between viled and goldapple phases), the run is in 'running' state; v_current_snapshots returns 0 rows. Querying the snapshots table directly with run_id=current is functionally equivalent and unblocks the brand-intersect step."
  - id: Pitfall 6
    decision: "viled_run.py calls run_writer.patch_stats EXACTLY ONCE on the success path (and exactly once on each failure path before returning). Verified by spy in test_atomic_stats_merge_pitfall_6."
    rationale: "Per-fetch UPDATE causes contention with goldapple_run on the same runs.stats column. Single end-of-phase patch_stats relies on SQLite json_patch atomicity; viled.* and goldapple.* namespaces are disjoint by construction (test_namespaces_disjoint)."
  - id: D-212 stub deletion (cascade)
    decision: "tests/integration/test_storage_integration.py rewritten to exercise the production SqliteSnapshotWriter / SqliteRunWriter (instead of the deleted Stub* classes). Plan-foretold cascading fix."
    rationale: "Phase 3 plan-03-06 wrote stubs in cli.py for parallel-development isolation. Phase 2 ships the real storage layer (Plan 02-02), so the stubs are obsolete. This file's tests still cover the same contracts (append-only, atomic merge, idempotent fail) — now against production code paths."
metrics:
  duration: "~16 minutes"
  date: "2026-05-07"
  commits:
    - hash: ab8e44f
      type: feat
      msg: "refactor gates retailer-agnostic + ViledStatsBuilder mirror"
    - hash: 890f050
      type: feat
      msg: "viled_run orchestrator + main_run composition + integration tests"
    - hash: 737b1b0
      type: refactor
      msg: "cli.py D-212 cutover - delete stubs, add weekly-run"
---

# Phase 2 Plan 5: Gates + Orchestrator + CLI Cutover Summary

## One-liner

Shipped the keystone wave of Phase 2: retailer-agnostic gates (D-203) with parse-quality + sanity-N sequential checks (D-218), `ViledStatsBuilder` namespace mirror, `run_viled_phase` 8-step orchestrator, `run_weekly` composition with DATA-05 try/except lifecycle, and the D-212 CLI cutover that deletes 4 Phase 3 stubs and replaces `goldapple-run` with `weekly-run` — all 381/381 non-live tests pass and Phase 3 frozen modules are untouched.

## Test Count Delta

- Before this plan: 321 passed / 5 skipped (370/3 after some upstream test fills landed)
- After this plan: **381 passed / 2 skipped** (12 warnings, all pre-existing datetime-adapter deprecation)
- New tests this plan: 49 unit + 9 integration + 3 CLI-help = **61 new green tests**
- 1 deliberate skip: `test_parse_quality_gate_fails_with_corrupt_pdp` in viled_run e2e — gate semantics covered exhaustively in `tests/unit/test_parse_quality_gate.py`; reaching null required-fields from a successful parse requires post-parse mutation that bypasses the orchestrator contract.
- 1 carryover skip from earlier wave (test_run_e2e_with_phase2_mocks.py "Wave 5 not implemented yet — Plan 02-06").

## Modules Shipped

| File | LOC | Role |
|---|---|---|
| `src/ga_crawler/runner/gates.py` (modified) | +100 LOC | D-203 retailer-agnostic helpers + D-218 parse-quality gate + 3 backward-compat shims |
| `src/ga_crawler/runner/stats.py` (modified) | +73 LOC | VILED_STATS_KEYS (9-tuple) + ViledStatsBuilder mirror |
| `src/ga_crawler/runners/viled_run.py` (NEW) | 328 LOC | 8-step pipeline: catalog enum → fetch → parse → normalize → persist → parse-quality gate → sanity-N gate → atomic stats merge |
| `src/ga_crawler/runners/main_run.py` (NEW) | 294 LOC | run_weekly composition with try/except DATA-05 lifecycle |
| `src/ga_crawler/cli.py` (modified) | -53 LOC | 4 Stub classes deleted, goldapple-run deleted, weekly-run added |

## Stubs Deleted (D-212)

The original `cli.py` contained 4 Phase 3 Stub classes intended for parallel development before Phase 2 storage existed:

- `StubBrandAlias` — `lookup` returns `[brand_norm]`
- `StubNormalizer` — lowercase brand/name; `volume` returns `None`
- `StubSnapshotWriter` — append-only JSONL writer to `runs/{N}/snapshots.jsonl`
- `StubRunWriter` — JSON file writer with manual `dict.update`-based stats merge

All 4 are now deleted. The mock fixtures in `tests/conftest.py` (`mock_brand_alias`, `mock_normalizer`, `mock_snapshot_writer`, `mock_run_writer`) take over the testability role — Phase 3 unit and mocked-integration tests use these MagicMock-based fixtures, not the deleted concrete stubs.

LOC reduction: 218 → 165 (= -53 LOC, mostly from the 4 stub bodies + the `_cmd_run` handler).

## Cascading Fix

`tests/integration/test_storage_integration.py` was the only file outside `cli.py` importing the deleted stubs. It has been **rewritten** to exercise the production `SqliteSnapshotWriter` / `SqliteRunWriter` from `ga_crawler.storage.sqlite`. The narrative is preserved (append-only, atomic merge, fail-record semantics) and 3 new CLI-help output checks were added that verify D-212 cutover at runtime: `goldapple-smoke` listed, `weekly-run` listed, `goldapple-run` NOT listed.

## CLI Output Confirmation

```
$ python -m ga_crawler --help
usage: python -m ga_crawler [-h] {goldapple-smoke,weekly-run} ...

GA Crawler - Phase 2 (production weekly run)

positional arguments:
  {goldapple-smoke,weekly-run}
    goldapple-smoke     Run smoke probe (D-312) against live goldapple
    weekly-run          Full weekly run (viled + goldapple -> SQLite + Norm06 ledger)

$ python -m ga_crawler weekly-run --help
usage: python -m ga_crawler weekly-run [-h] [--repo-root REPO_ROOT]
                                       [--db-path DB_PATH]
                                       [--sanity-gate-n SANITY_GATE_N]
                                       [--sanity-gate-m SANITY_GATE_M]
                                       [--headless HEADLESS] [--viled-only]
                                       [--goldapple-only]
```

`goldapple-run` is gone. Both kept (`goldapple-smoke`) and added (`weekly-run`) subcommands are visible. All 7 weekly-run flags advertised: `--repo-root`, `--db-path`, `--sanity-gate-n`, `--sanity-gate-m`, `--headless`, `--viled-only`, `--goldapple-only`.

## Pitfall 6 Verification

`tests/integration/test_viled_run_e2e_with_real_storage.py::test_atomic_stats_merge_pitfall_6` wraps `run_writer.patch_stats` with a spy and asserts `len(spy_calls) == 1` on the success path. The single delta contains all 9 viled.* keys (fetch_count, fetch_failures, parse_failures, fetch_duration_seconds, mean_fetch_seconds, sanity_gate_n_pass, parse_quality_pass, null_rate_required_fields, plus auto_suggest_n when 4+ runs of history are available). On failure paths, patch_stats is also called exactly once before `return ViledPhaseResult(status='failed', ...)`.

## DATA-05 Verification

`tests/integration/test_main_run_e2e.py::test_data05_uncaught_exception_finalizes` patches `SqliteSnapshotWriter.append` to raise `RuntimeError`, runs `run_weekly()`, and asserts:

1. The `MainRunResult.status` is `"failed"` with the exception type embedded in `reason`.
2. The `runs` row in the DB is closed: `status='failed'`, `finished_at IS NOT NULL`, `fail_reason` non-null and contains the stack-trace marker.

The `try/except` in `run_weekly` ALSO catches the case where the viled phase's own `run_writer.fail` was called first; the second `fail()` from the outer except block is idempotent (verified separately in unit tests of `SqliteRunWriter`).

## Threat Flags

None. The module's network surface is limited to viled curl_cffi and goldapple Camoufox (Phase 3 frozen). The new files are pure orchestration code: no new endpoints, no new auth surface, no new file-write paths beyond `Norm06Writer` (already in the threat register).

## Cascading Constraint for Plan 02-06

Plan 02-06 is the closeout plan. It needs to:

1. **Seed `config/brand-aliases.yaml`** with the production list of viled brands (the brand-alias YAML was previously a fixture in `tests/fixtures/viled/`; production needs a real list seeded from the historical viled catalog dump).
2. **Ship a backup script** (`scripts/backup-prices-db.sh` or equivalent) — D-220 says no DB-table backup on v1, but `cp prices.db prices.db.bak` cron entry should land for the operator playbook.
3. **Final E2E verification** against a real viled fetch — this Plan 02-05 only verifies with mocked HTTP. Plan 02-06 should run `python -m ga_crawler weekly-run --viled-only --sanity-gate-n=10 --db-path=/tmp/e2e-test.db` against live viled.kz once and assert the DB has rows + Norm06 ledger writes.
4. **Catalog pagination follow-up note** — the v1 page-1-only limitation (Plan 02-04 cascade flag, ~120 SKUs total) is enough to seed the D-201 sanity_gate_n=100 detector. Plan 02-06 should land a tracking ticket in the Phase 7 backlog for reverse-engineering the XHR pagination.

## Self-Check: PASSED

Verified each created/modified file exists and each commit is in `git log --all`:

- `src/ga_crawler/runners/viled_run.py` — FOUND
- `src/ga_crawler/runners/main_run.py` — FOUND
- `tests/unit/test_auto_suggest_threshold.py` — FOUND
- `tests/unit/test_viled_stats_builder.py` — FOUND
- `tests/unit/test_sanity_n_gate.py` — FOUND (rewritten from skip-stub)
- `tests/unit/test_parse_quality_gate.py` — FOUND (rewritten from skip-stub)
- `tests/integration/test_viled_run_e2e_with_real_storage.py` — FOUND (rewritten from skip-stub)
- `tests/integration/test_main_run_e2e.py` — FOUND (rewritten from skip-stub)
- `tests/integration/test_storage_integration.py` — FOUND (rewritten for D-212 cascade)
- Commits ab8e44f, 890f050, 737b1b0 — all in git log
- All success_criteria assertions in plan front-matter validated:
  - 4 unit test files GREEN (49 tests pass)
  - 2 integration test files GREEN (9 tests pass + 1 deliberate skip)
  - `grep -c "class Stub" src/ga_crawler/cli.py` → 0
  - `python -m ga_crawler --help` shows weekly-run + goldapple-smoke
  - `git diff src/ga_crawler/runners/goldapple_run.py` empty
  - `pytest -m "not live"` exits 0 (381 passed / 2 skipped)
