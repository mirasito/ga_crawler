---
phase: 2
slug: project-skeleton-viled-crawl-storage
status: archived
reconstructed: 2026-05-14
reconstructed_from: ".planning/milestones/v1.0-REQUIREMENTS.md + src/ga_crawler/storage/sqlite.py docstring"
note: "Retroactive stub for Phase 10 AUDIT-DEBT-01..04 skill State-B precondition. v1.0 milestone closed 2026-05-13; original CONTEXT artifacts were not archived per-phase, only milestone-level."
---

# Phase 2 Context — Project Skeleton: Viled Crawl + Storage

**Phase boundary:** Scaffolds the full project skeleton and ships the viled.kz crawl + storage pipeline (end-to-end for one retailer). Phase 3 reuses the same skeleton for goldapple.

## Implementation Decisions (from v1.0-REQUIREMENTS.md evidence trail)

- **D-203** — Retailer-agnostic sanity gate `final_threshold_gate(count, threshold)` shipped in `runner/gates.py`. Viled threshold = `sanity_gate_n` from `[tool.ga_crawler.crawl.viled]` in `pyproject.toml`. The gate is reused by Phase 3 via backward-compat shims `final_m_gate` / `final_n_gate`.
- **D-207** — Brand-alias table read-once per process (`YamlBrandAlias` loader); lookup + `canonical_for` reverse helper ship in Phase 2-03.
- **D-214** — Single-module storage (`sqlite.py` + `norm06_writer.py`). No `data/`, `models/`, `repositories/` split on day 1.
- **D-218** — Parse quality gate runs FIRST in `viled_run.py` (before sanity-N gate). Threshold ≤ 5% null-required-field rate; >5% → `run_writer.fail(run_id, ...)`. Audit-trail invariant: snapshot rows persist regardless of gate outcome.
- **D-219** — Database backup via `bin/backup.sh`: online `sqlite3 .backup` + 4-file retention per RESEARCH Pitfall 3 (atomic + WAL-safe).
- **D-221** — `v_current_snapshots` VIEW is the single source of truth for "latest successful run"; Phase 3 brand-pool reads `DISTINCT brand_norm WHERE retailer='viled'`.
- **D-225** — `pause_seconds` default 2.0 for viled rate-limit; loaded from `[tool.ga_crawler.crawl.viled]` namespace.

## Phase Outcomes

22 v1 requirements closed (DATA-01..06 + CRAWL-01/03/04/05/06 + PARSE-01..06 + NORM-01..06). Full viled catalog enumeration (page-1 limitation accepted for v1), parse pipeline, normalizers, DB writer, backup shell script shipped. Phase 3 builds goldapple side on top of this skeleton.
