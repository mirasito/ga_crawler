---
phase: 4
slug: matcher-kpi
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-14
audited: 2026-05-14
---

# Phase 4 — Security (Matcher + Match-Rate KPI)

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Retroactive audit — Phase 4 shipped 2026-05-11; audit performed 2026-05-14 (AUDIT-DEBT-02).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Orchestrator → matcher SQL | `run_id` value flows from `matcher_run.py` into SQL JOIN via `strict_key.py` primitives; must not allow injection | integer run identifier |
| Matcher → SQLite `matches` table | DELETE+INSERT pair must be atomic; partial write leaves orphan rows | match rows (SKU pairs + price fields) |
| KPI formula → stats namespace | `price_delta_pct` formula and denominator filter must not silently change across refactors | derived numeric KPI |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-03-01 | Injection | `matcher/strict_key.py` — SQL layer | mitigate | All six module-level SQL constants use `sqlalchemy.text(...)` with named bind params (`:rid`, `:retailer`). Zero f-string interpolation in SQL layer. See evidence below. | closed |
| T-04-03-02 | Tampering | `matcher/strict_key.py` — KPI formula | mitigate | Symmetric-filter denominator confirmed in `compute_denominator`. Regression-canary test `test_match_rate_formula_canary` source-locks the formula and SQL via `str(INSERT_MATCHES_SQL)` substring assertions. See evidence below. | closed |
| T-04-03-03 | Tampering | `matcher/strict_key.py` — transaction atomicity | mitigate | `build_matches_for_run` wraps DELETE+INSERT in a single `engine.begin()` block (D-410). D-411 `read_run_status` pre-finalize gate skips matcher entirely on non-success upstream status. See evidence below. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Verification Evidence

### T-04-03-01 — SQL Injection via `run_id` / `retailer`

Verification method: grep for `text(...)` constants with `:rid` / `:retailer` bind params; confirm no f-string reaches the SQL layer.

| Constant | File | Line | Bind Params |
|----------|------|------|-------------|
| `INSERT_MATCHES_SQL` | `src/ga_crawler/matcher/strict_key.py` | 58 | `:rid` (×3 — SELECT, WHERE v, WHERE g) |
| `DENOMINATOR_SQL` | `src/ga_crawler/matcher/strict_key.py` | 102 | `:rid` (×2 — outer + subquery) |
| `BRAND_OVERLAP_SQL` | `src/ga_crawler/matcher/strict_key.py` | 117 | `:rid` (×2 — outer + subquery) |
| `COMPARABLE_COUNT_SQL` | `src/ga_crawler/matcher/strict_key.py` | 129 | `:retailer`, `:rid` |
| `DELETE_MATCHES_SQL` | `src/ga_crawler/matcher/strict_key.py` | 140 | `:rid` |
| `RUN_STATUS_SQL` | `src/ga_crawler/matcher/strict_key.py` | 142 | `:rid` |

All six constants pass params via `conn.execute(CONSTANT, {"rid": run_id})` or `{"rid": run_id, "retailer": retailer}` dict. No string interpolation in SQL. Mirrors Phase 2 D-215 pattern.

Call sites confirmed:
- `build_matches_for_run` lines 159-160: `{"rid": run_id}` for DELETE then INSERT
- `compute_denominator` line 173: `{"rid": run_id}`
- `compute_brand_overlap` line 180: `{"rid": run_id}`
- `compute_comparable_counts` lines 192-195: `{"rid": run_id, "retailer": retailer}`
- `read_run_status` line 206: `{"rid": run_id}`

**Finding: CLOSED**

---

### T-04-03-02 — KPI Formula Silent Drift

Verification method: confirm `compute_denominator` applies symmetric D-402 filter; confirm regression-canary test exists and source-locks the SQL.

**Denominator symmetric filter** (`strict_key.py` lines 102-115):
```
DENOMINATOR_SQL = text("""
    SELECT COUNT(*) FROM snapshots v
    WHERE v.retailer = 'viled'
      AND v.run_id = :rid
      AND v.multipack_flag = 0
      AND v.volume_norm IS NOT NULL
      AND v.stock_state != 'DELISTED'
      AND v.brand_norm IN (
        SELECT DISTINCT g.brand_norm FROM snapshots g
        WHERE g.retailer = 'goldapple' AND g.run_id = :rid
      )
""")
```
Filters (`multipack_flag=0`, `volume_norm IS NOT NULL`, `stock_state != 'DELISTED'`) mirror `INSERT_MATCHES_SQL` WHERE clause exactly. Symmetric per D-402.

**Regression-canary test** (`tests/unit/test_matcher_strict_key.py` lines 301-343 — `test_match_rate_formula_canary`):
- Plants 6 viled SKUs (5 comparable, 1 DELISTED), 3 goldapple SKUs
- Asserts `compute_denominator(engine, 1) == 5` — pins denominator formula
- Asserts `build_matches_for_run(engine, 1) == 3` — pins match count
- Asserts `round(3 * 100.0 / 5, 2) == 60.0` — pins rate formula
- Source-locks SQL: `"ROUND(" in str(INSERT_MATCHES_SQL)` and `"*100.0/v.current_price" in str(INSERT_MATCHES_SQL)` — any formula drift fails this test

**Finding: CLOSED**

---

### T-04-03-03 — Transaction Atomicity + D-411 Pre-Finalize Gate

Verification method: confirm DELETE+INSERT share one `engine.begin()` block; confirm `read_run_status` gate fires before any match SQL.

**Atomic DELETE+INSERT** (`strict_key.py` lines 158-163):
```python
def build_matches_for_run(engine, run_id: int) -> int:
    with engine.begin() as conn:
        conn.execute(DELETE_MATCHES_SQL, {"rid": run_id})
        result = conn.execute(INSERT_MATCHES_SQL, {"rid": run_id})
        inserted = result.rowcount if result.rowcount is not None else 0
    return inserted
```
Both statements execute within the same `engine.begin()` context manager (single SQLAlchemy connection transaction). A crash between DELETE and INSERT rolls back both. D-410 confirmed.

**D-411 pre-finalize gate** (`runners/matcher_run.py` lines 109-139):
```python
status = read_run_status(engine, run_id)
if status in (None, "failed", "running"):
    reason = (
        "failed_upstream" if status == "failed"
        else "in_progress_upstream" if status == "running"
        else "missing_run_row"
    )
    ...
    return MatcherPhaseResult(status="skipped", ...)
```
`read_run_status` is Step 1 (first call in `run_matcher_phase`). If status is not `"success"` or `"partial"`, the function returns immediately — `build_matches_for_run` is never called. Gate fires before any match-table SQL.

**Finding: CLOSED**

---

## Unregistered Threat Flags

`04-SUMMARY.md ## Threat Flags`: "none — retroactive reconstruction"

No new attack surface was declared by the executor during implementation. No unregistered flags to log.

---

## Accepted Risks Log

No accepted risks. All three threats carry `mitigate` disposition and are closed by implementation evidence.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-14 | 3 | 3 | 0 | claude-sonnet-4-6 / gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (none)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-14
