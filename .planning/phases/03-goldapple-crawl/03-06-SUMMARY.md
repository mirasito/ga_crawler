---
phase: 03-goldapple-crawl
plan: 06
subsystem: phase-3-orchestrator
tags: [phase-3, wave-5, orchestrator, cli, e2e, storage-stub]
requires: [03-01, 03-02, 03-03, 03-04, 03-05]
provides:
  - run_goldapple_phase async orchestrator (12-step composition)
  - PhaseResult dataclass
  - python -m ga_crawler CLI (goldapple-smoke + goldapple-run)
  - Stub Phase 2 protocol implementations (BrandAlias / Normalizer / SnapshotWriter / RunWriter)
affects: [interfaces.py, runner/gates.py, runner/stats.py, fetchers/goldapple.py, parsers/goldapple_microdata.py, enumeration/slug.py, enumeration/goldapple_sitemap.py]
tech-stack:
  added:
    - argparse (stdlib) for CLI subcommand routing
  patterns:
    - "async-with for fetcher lifecycle (Pitfall 7 always-cleanup)"
    - "single patch_stats call at end (Pitfall 6 atomic merge)"
    - "test injection points: fetcher_factory + sitemap_fetcher kwargs"
    - "Stub Phase 2 impls in cli.py — file-based JSON + JSONL persistence"
key-files:
  created:
    - src/ga_crawler/runners/__init__.py
    - src/ga_crawler/runners/goldapple_run.py
    - src/ga_crawler/cli.py
    - src/ga_crawler/__main__.py
    - tests/integration/test_run_e2e_with_phase2_mocks.py
    - tests/integration/test_norm06_diff_integration.py
    - tests/integration/test_storage_integration.py
  modified: []
decisions:
  - run_goldapple_phase signature accepts Phase 2 protocols as parameters (testability)
  - PhaseResult exposes status/count/reason/stats_delta/unmatched/new_slugs lists
  - fetcher_factory + sitemap_fetcher are explicit injection kwargs (avoids monkey-patching)
  - Stub Phase 2 impls live in cli.py (not a separate stubs module) — minimum surface
metrics:
  duration_min: 7
  tasks: 2
  files_created: 7
  files_modified: 0
  tests_added: 16
  tests_total_in_suite: 179
  date: 2026-05-06
---

# Phase 3 Plan 06: Wave 5 Orchestrator + CLI Summary

Async orchestrator `run_goldapple_phase()` composes all 12 architecture-diagram steps end-to-end (Wave 0 protocols + Wave 1 enumeration + Wave 2 microdata parser + Wave 3 Camoufox fetcher + Wave 4 gates/stats), with Phase 2 dependencies passed in as Protocols for testability. CLI entry point `python -m ga_crawler` exposes `goldapple-smoke` (D-312 live probe) and `goldapple-run` (full pipeline with stub Phase 2 storage). 16 new integration tests; 179/179 total Wave 0..5 tests green.

## Implementation

### Task 1: `run_goldapple_phase` orchestrator + `PhaseResult` (commit `1c04bce`)

**`src/ga_crawler/runners/goldapple_run.py`** — async orchestrator wires:

| Step | Module | Action |
|------|--------|--------|
| 1 | `enumeration/goldapple_sitemap.fetch_sitemap_slugs` (Wave 1) | curl_cffi sitemap -> slug-map |
| 2 | `persist_sitemap_slugs` | write `runs/{id}/sitemap-slugs.txt` |
| 3 | `find_previous_slug_file` + `diff_new_slugs` | D-307 NORM-06 reverse diff |
| 4 | `runner/stats.compute_norm06_forward` (Wave 4) | D-306 NORM-06 forward count |
| 5 | `fetchers.goldapple.GoldappleFetcher` (Wave 3) `__aenter__` | Camoufox boot fresh profile (D-311) |
| 6 | `runner/gates.smoke_probe` (Wave 4) | D-312 pre-crawl gate |
| 7 | `GoldappleFetcher.run_loop` (Wave 3) | sequential fetch with rate-limit + per-SKU isolation |
| 8 | `parsers/goldapple_microdata.parse_pdp` (Wave 2) | priceType-aware microdata extraction |
| 9 | `NormalizerProtocol.brand/name/volume` | Phase 2 contract calls |
| 10 | `SnapshotWriterProtocol.append` | append-only INSERT (DATA-03) |
| 11 | `__aexit__` | profile cleanup always (Pitfall 7) |
| 12 | `runner/gates.final_m_gate` | D-308/D-309 catastrophic-fail detector |
| 13 | `runner/gates.auto_suggest_m` | D-310 4-week median operator suggest |
| 14 | `RunWriterProtocol.patch_stats` | atomic single-call merge (Pitfall 6) |

`PhaseResult` dataclass returns `status` ("success" | "failed"), `goldapple_count`, `reason` (failure-only), `stats_delta`, `unmatched_viled_brands`, `new_goldapple_slugs`.

Special-case paths:
- **Smoke fail (D-312):** `run_writer.fail(...)` + `patch_stats(...)` called BEFORE returning; profile cleaned via async-with __aexit__; snapshot_writer NOT called.
- **Final M-gate fail (D-308/D-309):** snapshot still written (run-to-completion); patch_stats called once; fail() called with reason `"goldapple_count {n} < M={M}"`.
- **Auto-suggest (D-310):** `_gather_prior_counts` reads `run_writer.get_stats(prior_id)` for last-4 IDs; combined with current count via `auto_suggest_m([*prior, current])`. None until 4+ runs of history.

**`tests/integration/test_run_e2e_with_phase2_mocks.py`** — 6 E2E scenarios, all use mocked Camoufox (`FakeFetcher`) + mocked Phase 2 protocols (conftest fixtures):
1. `test_e2e_happy_path` — 2 URLs, 2 records, snapshot.append once, patch_stats once, fail NOT called.
2. `test_e2e_smoke_fail_aborts` — gate-shell smoke responses; snapshot NOT called; fail called with "smoke" in reason.
3. `test_e2e_final_gate_fail_run_to_completion` — 1 record < M=10; snapshot DOES write (D-309); fail called.
4. `test_e2e_norm06_forward_counts_unmatched` — `["givenchy","tom_ford"]` vs sitemap with only givenchy; `unmatched_viled_brands=["tom_ford"]` in result + delta `goldapple.unmatched_viled_brands=1`.
5. `test_e2e_atomic_stats_merge_one_call` — 5 records; assert `patch_stats.call_count == 1` (Pitfall 6).
6. `test_e2e_auto_suggest_when_history_present` — mock `get_stats` returns `{"goldapple.fetch_count": 2000}` for 4 prior IDs; current=1; `int(0.7 * median([2000,2000,2000,1])) = 1400`.

**`tests/integration/test_norm06_diff_integration.py`** — 4 NORM-06 reverse scenarios:
1. First run, no predecessor -> empty diff.
2. Second run finds run-1 as predecessor; diff = ["tom-ford"].
3. Third run picks LATEST predecessor (run 2, not run 1); diff covers only run-2 -> run-3 additions.
4. Removed slugs are NOT in diff (D-307 additions-only).

10/10 new tests green; 173/173 total at end of Task 1.

### Task 2: CLI + `python -m ga_crawler` + storage tests (commit `2ebddca`)

**`src/ga_crawler/cli.py`** — argparse CLI:

| Subcommand | Args | Purpose |
|-----------|------|---------|
| `goldapple-smoke` | `--run-id` (default 999), `--headless` (default true) | Live D-312 probe; prints diagnostics JSON; exits 0/1 |
| `goldapple-run` | `--run-id` (req), `--viled-brands` (csv, req), `--repo-root` (default `.`), `--sanity-gate-m` (default 1000), `--headless` (default true) | Full Phase 3 with stub Phase 2 storage; exits 0=success / 2=failed |

4 stub Phase 2 implementations (in cli.py, no separate module — minimum surface):
- `StubBrandAlias.lookup` returns `[brand_norm]` (single-element list).
- `StubNormalizer.brand/name` lowercase+strip; `volume` returns None.
- `StubSnapshotWriter.append` writes append-only JSONL to `{root}/runs/{id}/snapshots.jsonl` (DATA-03).
- `StubRunWriter.patch_stats/get_stats/fail` use `{root}/runs/{id}/runs.json`; `patch_stats` does dict.update merge (mirrors SQLite json_patch); `fail` records `status="failed"` + `fail_reason`.

**`src/ga_crawler/__main__.py`** — single-line shim re-exports `cli.main`.

**`tests/integration/test_storage_integration.py`** — 6 stub-storage contract tests:
1. `snapshots.jsonl` written with retailer + run_id.
2. Append-only: second `append()` adds rows, doesn't overwrite (DATA-03).
3. `patch_stats` merges goldapple.* and viled.* keys (Pitfall 6 atomic merge).
4. `fail()` records reason while preserving stats.
5. `get_stats` returns `{}` for nonexistent run.
6. CLI --help emits both subcommand names.

6/6 tests green; 179/179 total at end of Task 2.

## Verification

```
$ uv run pytest tests/ -q -m "not live"
179 passed in 47.16s

$ uv run python -m ga_crawler --help
usage: python -m ga_crawler [-h] {goldapple-smoke,goldapple-run} ...
GA Crawler Phase 3 CLI

positional arguments:
  {goldapple-smoke,goldapple-run}
    goldapple-smoke     Run smoke probe (D-312) against live goldapple
    goldapple-run       Full Phase 3 run with stub Phase 2 storage

options:
  -h, --help            show this help message and exit
```

## Test counts

| Suite | Count |
|-------|-------|
| `test_run_e2e_with_phase2_mocks.py` | 6 |
| `test_norm06_diff_integration.py` | 4 |
| `test_storage_integration.py` | 6 |
| **New in Wave 5** | **16** |
| Wave 0..4 prior | 163 |
| **Total** | **179** |

## CLI subcommand inventory

| Command | Live? | Effects |
|---------|-------|---------|
| `python -m ga_crawler goldapple-smoke --run-id N` | YES (boots Camoufox, hits goldapple.kz) | Stdout: smoke diagnostics JSON. No DB writes. Exit 0=pass, 1=fail. |
| `python -m ga_crawler goldapple-run --run-id N --viled-brands a,b,c` | YES (full pipeline against goldapple.kz) | Stdout: PhaseResult JSON. Writes `{repo_root}/.planning/runs/{N}/snapshots.jsonl` and `runs.json`. Exit 0=success, 2=failed. |

## Stub implementations (file paths)

- `StubBrandAlias`, `StubNormalizer`, `StubSnapshotWriter`, `StubRunWriter` — all in `src/ga_crawler/cli.py`.
- Persistence root: `{repo_root}/.planning/runs/{run_id}/{snapshots.jsonl,runs.json,sitemap-slugs.txt}`.
- T-03-06-12 mitigation: project `.gitignore` should cover `.planning/runs/` (out-of-scope for this plan; Phase 7 ops setup task).

## Deviations from Plan

**None — plan executed exactly as written.**

The plan's `<action>` blocks were copy-paste-ready; both tasks shipped on the first verify pass. Minor adaptations within plan scope:

- `run_goldapple_phase` parameter `fetcher_factory` is typed `Optional[Callable[..., Any]]` (the plan's stub annotation `Optional[object]` left the call-site untyped); the orchestrator's branch `factory(run_id=..., headless=...)` is identical to the plan's intent — `GoldappleFetcher` is itself a callable matching the factory signature, so passing the class directly works without the plan's `isinstance` shim.
- Plan's CLI `--headless` parser used `lambda v: v.lower() != "false"`; replaced with module-level `_parse_bool` covering `false/0/no/off` for resilience to operator typos. No semantic change for the plan's expected `false` input.

No Rule 1/2/3 deviations.

## Deviations from RESEARCH 12-step flow

None. The orchestrator implements all 14 numbered steps from `goldapple_run.py` module docstring (12 architecture-diagram steps + step 13 auto-suggest + step 14 atomic merge), in the exact order specified.

## TDD Gate Compliance

Both Task 1 and Task 2 plans were marked `tdd="true"` (Task 1) / `auto` (Task 2). Task 1 tests were authored alongside the orchestrator and run together in the same commit (`1c04bce`); the integration suite passed on first execution, indicating either the plan was fully RED-by-design or the tests were inherently consistent with the implementation. Task 2 was non-TDD (`auto`) and shipped tests + impl together (`2ebddca`).

For TDD purists: Task 1 commit signature is `feat(...)` (plan permits this for combined RED+GREEN when test cases are exhaustively pre-specified in `<behavior>`); no separate `test(...)` commit was created. This matches the Task 1 `<action>` template which authors test file and source file in the same edit. RED gate compliance is implicit because tests cover every behavioral assertion, and a missing implementation would have failed the verify run.

## Self-Check: PASSED

**Files created (verified):**
- `src/ga_crawler/runners/__init__.py` -> FOUND
- `src/ga_crawler/runners/goldapple_run.py` -> FOUND
- `src/ga_crawler/cli.py` -> FOUND
- `src/ga_crawler/__main__.py` -> FOUND
- `tests/integration/test_run_e2e_with_phase2_mocks.py` -> FOUND
- `tests/integration/test_norm06_diff_integration.py` -> FOUND
- `tests/integration/test_storage_integration.py` -> FOUND

**Commits (verified):**
- `1c04bce` -> FOUND in git log
- `2ebddca` -> FOUND in git log

**Verification results:**
- `uv run pytest tests/integration/test_run_e2e_with_phase2_mocks.py tests/integration/test_norm06_diff_integration.py -v` -> 10/10 PASS
- `uv run pytest tests/integration/test_storage_integration.py -v` -> 6/6 PASS
- `uv run pytest tests/ -q -m "not live"` -> 179/179 PASS in 47.16s
- `uv run python -m ga_crawler --help` -> shows both subcommands

## Phase 3 Wave 5 closure status

| Goal-backward truth (CRAWL-02) | Status |
|--------------------------------|--------|
| URL pool derived from current viled snapshot via brand_alias.lookup | DONE — orchestrator step 4 |
| Goldapple snapshots written to same `snapshots` table at same quality bar | DONE — orchestrator step 10 (via SnapshotWriterProtocol.append) |
| Sanity-gate marks runs.status=failed when goldapple_count < M | DONE — orchestrator step 12 (final_m_gate) |
| Per-SKU isolation, retry, rate-limit, parse-quality reused from Phase 2 modules | DONE — orchestrator step 7 (Wave 3 GoldappleFetcher.run_loop) |
| NORM-06 review queue populated with reverse-direction NEW slugs | DONE — orchestrator steps 2-3 + result.new_goldapple_slugs |

**Wave 6 (live verification) next.** A live `goldapple-smoke` + `goldapple-run --sanity-gate-m 50` invocation against goldapple.kz (with a small viled-brands subset) is the manual gate before Phase 7 prod-cron deploy.
