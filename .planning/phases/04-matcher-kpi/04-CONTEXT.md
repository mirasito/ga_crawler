---
phase: 4
slug: matcher-match-rate-kpi
status: archived
reconstructed: 2026-05-14
reconstructed_from: ".planning/milestones/v1.0-REQUIREMENTS.md + src/ga_crawler/matcher/strict_key.py docstrings"
note: "Retroactive stub for Phase 10 AUDIT-DEBT-01..04 skill State-B precondition. v1.0 milestone closed 2026-05-13; original CONTEXT artifacts were not archived per-phase, only milestone-level."
---

# Phase 4 Context — Matcher + Match-Rate KPI

**Phase boundary:** Ships the strict-key matcher (`brand_norm + name_norm + volume_norm` SQL JOIN) against Phase 2+3 snapshots, computes match-rate KPI, writes results to the `matches` table, and gates the run if match count falls below threshold P.

## Implementation Decisions (from v1.0-REQUIREMENTS.md evidence trail)

- **D-401** — `matches` table schema: 13 denormalized columns including composite PK `(run_id, viled_sku, goldapple_sku)`. Ships in Plan 04-01 as `Match` SQLModel.
- **D-402** — Symmetric filter on numerator: `multipack_flag=0 AND volume_norm IS NOT NULL AND stock_state != 'DELISTED'` applied to BOTH retailers in `INSERT_MATCHES_SQL`.
- **D-403** — N→1 keep-all: multiple goldapple SKUs sharing the same key can map to one viled SKU; composite PK allows duplicate rows.
- **D-404** — Denominator = comparable viled SKUs whose `brand_norm` appears on goldapple side this run. `compute_denominator(engine, run_id)` ships in Plan 04-03.
- **D-405** — KPI formula frozen with week-1 baseline: `price_delta_pct = ROUND((g.current_price − v.current_price) × 100.0 / v.current_price, 2)`. Source-locked by `test_match_rate_formula_canary`.
- **D-407** — Auto-suggest P threshold after 4+ runs: `match_auto_suggest_p` structured-log event. NEVER auto-tunes — operator PR only.
- **D-408** — Seed `[tool.ga_crawler.match] sanity_gate_p = 20` in `pyproject.toml`. Loaded via `MatchConfig.from_pyproject`.
- **D-409** — Audit-trail invariant: match rows already inserted persist on gate trip (mirrors D-218 gate-fail-but-snapshot-persists).
- **D-410** — `build_matches_for_run` = idempotent DELETE+INSERT inside ONE `engine.begin()` transaction.
- **D-411** — `read_run_status` returns literal `status` column value or `None`. Reused by Phase 6 gate (`evaluate_gate` D-604).

## Phase Outcomes

4 MATCH requirements closed (MATCH-01..04). 465+ tests covering matcher SQL JOIN logic, KPI math, sanity-gate behavior, and standalone CLI subcommand.
