---
phase: 04-matcher-match-rate-kpi
verified: 2026-05-11T00:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 4: Matcher + Match-Rate KPI Verification Report

**Phase Goal:** Per-`run_id` strict-key matches between viled and goldapple are persisted with price deltas, match-rate is computed and logged as a tracked KPI from week 1, and a sanity-gate blocks delivery on low match counts.
**Verified:** 2026-05-11
**Status:** PASS
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (11 items)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MATCH-01 strict-key SQL JOIN — `build_matches_for_run` single-TX DELETE+INSERT, JOIN scoped to run_id | VERIFIED | `src/ga_crawler/matcher/strict_key.py` L148-163: `with engine.begin() as conn: conn.execute(DELETE_MATCHES_SQL, …); conn.execute(INSERT_MATCHES_SQL, …)`. INSERT JOINs on `v.brand_norm=g.brand_norm AND v.name_norm=g.name_norm AND v.volume_norm=g.volume_norm` (L84-86). DELETE is `DELETE FROM matches WHERE run_id = :rid` (L140) |
| 2 | MATCH-02 matches table — 13-column denormalized + composite PK | VERIFIED | `src/ga_crawler/storage/sqlite.py` L90-116: Match SQLModel with all 13 columns (run_id, viled_sku, goldapple_sku, brand_norm, name_norm, volume_norm, viled_price, goldapple_price, viled_was_price, goldapple_was_price, price_delta, price_delta_pct, matched_at). PK declared via `primary_key=True` on run_id+viled_sku+goldapple_sku (L100-102) |
| 3 | MATCH-03 match-rate KPI formula — symmetric filter, 10 stats keys, formula canary | VERIFIED | `compute_denominator` in `strict_key.py` L102-115: `multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED' AND brand_norm IN (DISTINCT goldapple brands)`. `matcher_run.py` L157-158: `rate = round(match_count * 100.0 / denominator, 2)`. `MatchStatsBuilder` keys include `match.rate`, `match.numerator`, `match.denominator`. Canary test `test_match_rate_formula_canary` at `tests/unit/test_matcher_strict_key.py:301` (6/5/3 → 60.0 + source-locked `ROUND(` substring) |
| 4 | MATCH-04 sanity-gate P + auto-suggest — default 20 from pyproject, gate called, auto-suggest log-only | VERIFIED | `MatchConfig.sanity_gate_p: int = 20` (`matcher/config.py` L26). `pyproject.toml` L91-96: `[tool.ga_crawler.match] sanity_gate_p=20` + p_auto_suggest_factor=0.7 + p_auto_suggest_after_runs=4. `matcher_run.py` L174 calls `final_threshold_gate(match_count, threshold_p)`. Auto-suggest at L183-195: `auto_suggest_threshold(...)` result logged via `log.info("match_auto_suggest_p", ...)` — NEVER set on builder. MATCH_STATS_KEYS has NO `auto_suggest_p` (`stats.py` L21-32) |
| 5 | Idempotency invariant — same run_id re-run produces identical matches + identical stats | VERIFIED | `build_matches_for_run` wraps DELETE+INSERT in one `engine.begin()` (L158). Deterministic SQL JOIN on immutable snapshots = same output. Integration test `tests/integration/test_matcher_run.py` (15 tests, all green) exercises idempotent re-run. Test count 465 passed confirms regression coverage |
| 6 | D-411 skip protocol — status read, skip if failed/running/None, matches NOT touched, single patch_stats | VERIFIED | `read_run_status` (`strict_key.py` L199-207). `matcher_run.py` L109-139: `if status in (None, "failed", "running"): … run_writer.patch_stats(run_id, dict(builder.delta)) … return MatcherPhaseResult(status="skipped", …)`. No call to `build_matches_for_run` on skip path. Builder sets skipped_reason ("failed_upstream" / "in_progress_upstream" / "missing_run_row") |
| 7 | D-409 P-gate semantics — matches stay in DB on gate-fail, run_writer.fail called, status='failed' | VERIFIED | `matcher_run.py` L202-219: order is `build_matches_for_run` (Step 3) → `final_threshold_gate` (Step 5) → on fail `run_writer.fail(run_id, reason)`. Matches rows inserted BEFORE gate evaluated → persist. Reason format: `f"match_count_below_threshold:{match_count}<{threshold_p}"` matches D-409 |
| 8 | D-412 CLI — matcher-run subcommand with type=int run_id; weekly-run --sanity-gate-p flag | VERIFIED | `cli.py` L232-259: `matcher = sub.add_parser("matcher-run", …)`; `matcher.add_argument("--run-id", type=int, required=True, …)`; `matcher.add_argument("--sanity-gate-p", type=int, …)`. `weekly.add_argument("--sanity-gate-p", type=int, default=None, …)` at L207-213. SQL injection blocked: argparse type=int + parameterized `text(...)` + bind params |
| 9 | Stats namespace — MATCH_STATS_KEYS exactly 10 keys; three-way disjoint with viled/goldapple | VERIFIED | `matcher/stats.py` L21-32: tuple has exactly 10 entries (count, rate, numerator, denominator, brand_overlap_count, viled_comparable_count, goldapple_comparable_count, skipped_reason, threshold_p, gate_passed). `tests/unit/test_matcher_stats.py:102` — `test_three_way_namespaces_disjoint`: asserts viled∩match=∅, goldapple∩match=∅, viled∩goldapple=∅ (passes in suite) |
| 10 | D-415 no alembic — matches table created via SQLModel.metadata.create_all | VERIFIED | `storage/sqlite.py` L141-159: `init_db` calls `SQLModel.metadata.create_all(engine)` + raw `CREATE VIEW IF NOT EXISTS` only. No `alembic/` directory at project root (verified `ls` returned "No such file or directory"). Match class registered in module-level SQLModel.metadata via `table=True` decoration |
| 11 | Test suite — 465+ tests pass | VERIFIED | `uv run pytest -q` output: `465 passed, 1 skipped, 37 warnings in 105.94s`. 53 test files total. No failures, no errors |

**Score:** 11/11 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ga_crawler/storage/sqlite.py` | Match SQLModel + init_db addition | VERIFIED | 13 fields + composite PK + matched_at default + ix_match_run_brand index |
| `src/ga_crawler/matcher/__init__.py` | Package marker | VERIFIED | 1-line docstring (intentional — no re-exports needed) |
| `src/ga_crawler/matcher/config.py` | MatchConfig + from_pyproject | VERIFIED | frozen dataclass, defaults 20/0.7/4, tomllib loader with fallback to defaults |
| `src/ga_crawler/matcher/stats.py` | MATCH_STATS_KEYS + MatchStatsBuilder | VERIFIED | 10 keys tuple, reuses StatsNamespaceError, mirror of ViledStatsBuilder |
| `src/ga_crawler/matcher/strict_key.py` | 6 SQL constants + 5 public functions | VERIFIED | INSERT_MATCHES_SQL, DENOMINATOR_SQL, BRAND_OVERLAP_SQL, COMPARABLE_COUNT_SQL, DELETE_MATCHES_SQL, RUN_STATUS_SQL + build_matches_for_run, compute_denominator, compute_brand_overlap, compute_comparable_counts, read_run_status |
| `src/ga_crawler/runners/matcher_run.py` | run_matcher_phase + MatcherPhaseResult | VERIFIED | 7-step orchestrator, MatcherPhaseResult dataclass with status/match_count/match_rate/reason/stats_delta |
| `src/ga_crawler/runners/main_run.py` | matcher composition after goldapple | VERIFIED | L244-302: pre-finalize → run_matcher_phase → handle success/failed/skipped. MainRunResult gains match_count/match_rate fields (L65-66) |
| `src/ga_crawler/cli.py` | matcher-run subcommand + weekly-run --sanity-gate-p | VERIFIED | `_cmd_matcher` handler + arg-parser block; --sanity-gate-p on weekly-run |
| `pyproject.toml` | [tool.ga_crawler.match] block | VERIFIED | L91-96: 3 keys (sanity_gate_p=20, p_auto_suggest_factor=0.7, p_auto_suggest_after_runs=4) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `matcher_run.run_matcher_phase` | `strict_key.build_matches_for_run` | import + call Step 3 | WIRED | L31-37 imports, L152 invocation |
| `matcher_run.run_matcher_phase` | `strict_key.compute_denominator` + comparable_counts + brand_overlap + read_run_status | imports + Step 1-2 calls | WIRED | L142-149 |
| `matcher_run.run_matcher_phase` | `runner.gates.final_threshold_gate` + `auto_suggest_threshold` | import + Step 5 | WIRED | L38, L174, L183 |
| `main_run.run_weekly` | `matcher_run.run_matcher_phase` | import + call after goldapple | WIRED | L44 import, L262 invocation |
| `cli._cmd_matcher` | `matcher_run.run_matcher_phase` | lazy import in handler | WIRED | L109, L124 invocation |
| `MatchConfig.from_pyproject` | `[tool.ga_crawler.match]` toml block | tomllib.load + nested .get | WIRED | config.py L37-54 |
| `Match` model | `init_db` (SQLModel.metadata.create_all) | table=True registration | WIRED | sqlite.py L90 + L148 |
| `main_run` | `MatchConfig.from_pyproject` for default P | call at L256 | WIRED | After CLI override fallback |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `Match` table rows | INSERT … SELECT from snapshots | snapshots table (Phase 2/3 writes) | Yes — real JOIN against persisted snapshots | FLOWING |
| `runs.stats.match.*` keys | builder.delta → patch_stats | computed counts + match_count + rate | Yes — values derived from live SQL | FLOWING |
| `MatcherPhaseResult.match_rate` | round(count * 100 / denom, 2) | actual queries against engine | Yes — zero-denom guard sets 0.0 + log | FLOWING |
| Auto-suggest log line | `_gather_prior_match_counts` reads prior `runs.stats.match.count` | get_stats(prior) for lookback window | Yes — reads back from db; logged only (per D-407 invariant) | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `uv run pytest -q` | `465 passed, 1 skipped, 37 warnings in 105.94s` | PASS |
| Three-way namespace disjointness | grep test_three_way_namespaces_disjoint | found at tests/unit/test_matcher_stats.py:102 (asserts ∩ = ∅ three ways) | PASS |
| Formula canary test exists | grep test_match_rate_formula_canary | found at tests/unit/test_matcher_strict_key.py:301 (6/5/3→60.0 + ROUND substring lock) | PASS |
| CLI matcher-run subcommand parses | argparse declaration | --run-id type=int required + --sanity-gate-p type=int + --db-path + --pyproject | PASS |
| pyproject [tool.ga_crawler.match] readable | tomllib via MatchConfig.from_pyproject | 3 keys present with seed values 20/0.7/4 | PASS |
| No alembic dir at project root | `ls alembic/` | "No such file or directory" — confirms D-415 | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MATCH-01 | Plan 04-03 | Strict-key SQL JOIN on (brand_norm, name_norm, volume_norm) for current run_id | SATISFIED | INSERT_MATCHES_SQL + build_matches_for_run + D-402 symmetric filter present |
| MATCH-02 | Plan 04-01, 04-03 | Denormalized 13-column matches table + DELETE+INSERT single TX | SATISFIED | Match SQLModel matches schema verbatim; single-TX confirmed |
| MATCH-03 | Plan 04-03, 04-04 | Match-rate KPI formula + symmetric denominator + computed/logged | SATISFIED | compute_denominator D-404 + orchestrator round formula + zero-denom guard + canary test |
| MATCH-04 | Plan 04-01, 04-04 | Sanity-gate P configurable, gate-fail flips run.status='failed', auto-suggest log-only | SATISFIED | pyproject namespace + final_threshold_gate + run_writer.fail + auto_suggest_threshold log-only |

No orphaned requirements detected (REQUIREMENTS.md Phase 4 mapping = MATCH-01..04 exactly, all closed).

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | No TODO/FIXME/placeholder/stub patterns detected in Phase 4 source files |

The matcher source files (`matcher/`, `runners/matcher_run.py`, modified `runners/main_run.py`, modified `cli.py`, modified `storage/sqlite.py`) contain only intentional NOTE comments documenting design decisions (D-411 mapping, D-409 audit invariant, D-407 log-only). No placeholder code paths.

---

## Human Verification Required

None. All 11 must-haves are programmatically verifiable through codebase inspection + the regression test suite (which exercises end-to-end orchestrator integration via `tests/integration/test_matcher_run.py` and `tests/integration/test_main_run_e2e.py`).

The phase is complete and ready for Phase 5 (Reporter).

---

## Gaps Summary

No gaps. All 11 must-haves verified against code (not just SUMMARY.md claims):

1. SQL JOIN — present, parameterized, single-TX
2. 13-column denormalized table — schema matches D-401 verbatim
3. KPI formula — symmetric filters, formula canary test pinned (6/5/3 → 60.0), source-locked SQL substring
4. Sanity-gate P + auto-suggest — gate wired, auto-suggest log-only (not in stats namespace)
5. Idempotency — DELETE-then-INSERT in one transaction, integration tests cover re-run
6. D-411 skip — status read first, matches NOT touched on skip, single patch_stats
7. D-409 audit invariant — INSERT before gate, rows persist on fail-flip
8. CLI — type-safe matcher-run + weekly-run --sanity-gate-p
9. Stats namespace — 10 keys, three-way disjoint test confirms no key collision
10. No alembic — confirmed missing dir + SQLModel.metadata.create_all bootstrap
11. Full test suite 465 passed (1 skipped) — no regressions, all green

---

_Verified: 2026-05-11_
_Verifier: Claude (gsd-verifier)_
