"""Phase 4 strict-key matcher SQL primitives.

Pure SQL JOIN builder + denominator query + comparable counts + run status
read. The orchestrator in ``runners/matcher_run.py`` (Plan 04-04) calls these
primitives sequentially within a single phase invocation; this module owns
NO state and NO orchestration — only deterministic SQL against a passed-in
SQLAlchemy engine.

Decisions:
  - D-401: matches schema — 13 denormalized columns (Plan 04-01 ships the table).
  - D-402: symmetric filters on numerator — ``multipack_flag=0 AND
    volume_norm IS NOT NULL AND stock_state != 'DELISTED'`` applied to BOTH
    retailers.
  - D-403: N→1 keep-all — duplicates by ``(brand_norm, name_norm, volume_norm)``
    on goldapple side produce multiple match rows; PK is composite to allow.
  - D-404: denominator = comparable viled SKUs whose ``brand_norm`` appears on
    goldapple side this run (symmetric with D-402 filter).
  - D-405: KPI formula frozen with week-1 baseline; INSERT_MATCHES_SQL and
    DENOMINATOR_SQL are module-level constants pinned by regression-canary.
  - D-410: ``build_matches_for_run`` = idempotent DELETE+INSERT inside ONE
    ``engine.begin()`` transaction. Re-running on the same run_id produces the
    same rows (deterministic SQL JOIN on immutable snapshots).
  - D-411: ``read_run_status`` returns the literal ``status`` column value or
    ``None``.

Threats mitigated here:
  - T-04-03-01 (SQL injection via run_id): every SQL uses ``text("... :rid ...")``
    + ``params={"rid": run_id}`` — no f-string interpolation reaches the SQL
    layer. ``compute_comparable_counts`` likewise passes ``retailer`` via bind
    param. Mirrors Phase 2 D-215.
  - T-04-03-02 (KPI formula silent drift): the INSERT and DENOMINATOR SQL live
    as module-level ``text(...)`` constants so the regression-canary test
    (``test_match_rate_formula_canary``) can source-lock them via ``str(...)``
    substring asserts.
  - T-04-03-03 (partial INSERT on crash): ``build_matches_for_run`` wraps
    DELETE+INSERT in a single ``engine.begin()`` block — atomic per D-410.
"""

from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import text

log = structlog.get_logger(__name__)


# ---- SQL constants (D-405: frozen with week-1 KPI baseline) ----

# NOTE on the additional ``current_price IS NOT NULL`` clause: it is implicit
# in the JOIN-result-is-meaningful invariant but D-402 does not explicitly list
# it. Included here as a NOT-NULL-guard because (a) the Match table requires
# ``viled_price INTEGER NOT NULL`` and ``goldapple_price INTEGER NOT NULL`` per
# D-401, and (b) without it a snapshot with ``current_price=NULL`` would raise
# IntegrityError on INSERT. This is the only added clause beyond D-402 — it is
# a NOT-NULL-guard for the Match schema, not a scope reduction.
INSERT_MATCHES_SQL = text(
    """
    INSERT INTO matches (
      run_id, viled_sku, goldapple_sku,
      brand_norm, name_norm, volume_norm,
      viled_price, goldapple_price,
      viled_was_price, goldapple_was_price,
      price_delta, price_delta_pct,
      matched_at
    )
    SELECT
      :rid,
      v.sku_id,
      g.sku_id,
      v.brand_norm,
      v.name_norm,
      v.volume_norm,
      v.current_price,
      g.current_price,
      v.was_price,
      g.was_price,
      (g.current_price - v.current_price),
      ROUND((g.current_price - v.current_price) * 100.0 / v.current_price, 2),
      CURRENT_TIMESTAMP
    FROM snapshots v
    JOIN snapshots g
      ON v.brand_norm = g.brand_norm
     AND v.name_norm  = g.name_norm
     AND v.volume_norm = g.volume_norm
    WHERE v.retailer = 'viled'
      AND v.run_id = :rid
      AND v.multipack_flag = 0
      AND v.volume_norm IS NOT NULL
      AND v.stock_state != 'DELISTED'
      AND v.current_price IS NOT NULL
      AND g.retailer = 'goldapple'
      AND g.run_id = :rid
      AND g.multipack_flag = 0
      AND g.volume_norm IS NOT NULL
      AND g.stock_state != 'DELISTED'
      AND g.current_price IS NOT NULL
    """
)

DENOMINATOR_SQL = text(
    """
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
    """
)

BRAND_OVERLAP_SQL = text(
    """
    SELECT COUNT(DISTINCT v.brand_norm) FROM snapshots v
    WHERE v.retailer = 'viled'
      AND v.run_id = :rid
      AND v.brand_norm IN (
        SELECT DISTINCT g.brand_norm FROM snapshots g
        WHERE g.retailer = 'goldapple' AND g.run_id = :rid
      )
    """
)

COMPARABLE_COUNT_SQL = text(
    """
    SELECT COUNT(*) FROM snapshots
    WHERE retailer = :retailer
      AND run_id = :rid
      AND multipack_flag = 0
      AND volume_norm IS NOT NULL
      AND stock_state != 'DELISTED'
    """
)

DELETE_MATCHES_SQL = text("DELETE FROM matches WHERE run_id = :rid")

RUN_STATUS_SQL = text("SELECT status FROM runs WHERE run_id = :rid")


# ---- Public API ----


def build_matches_for_run(engine, run_id: int) -> int:
    """D-410 idempotent DELETE-and-reinsert in a SINGLE transaction.

    Either all pre-existing matches for this run_id are deleted AND the new
    set is inserted, or neither change is applied. Returns the count of rows
    inserted in this call.

    Re-running on the same run_id produces identical match rows because the
    underlying JOIN is deterministic on immutable snapshot rows.
    """
    with engine.begin() as conn:
        conn.execute(DELETE_MATCHES_SQL, {"rid": run_id})
        result = conn.execute(INSERT_MATCHES_SQL, {"rid": run_id})
        inserted = result.rowcount if result.rowcount is not None else 0
    log.info("matches_built", run_id=run_id, inserted=inserted)
    return inserted


def compute_denominator(engine, run_id: int) -> int:
    """D-404 denominator: comparable viled SKUs in brand-overlap with goldapple.

    Symmetric filter with the numerator (D-402): ``multipack_flag=0``,
    ``volume_norm IS NOT NULL``, ``stock_state != 'DELISTED'``.
    """
    with engine.connect() as conn:
        row = conn.execute(DENOMINATOR_SQL, {"rid": run_id}).first()
    return int(row[0]) if row else 0


def compute_brand_overlap(engine, run_id: int) -> int:
    """COUNT(DISTINCT brand_norm) of the viled∩goldapple intersection."""
    with engine.connect() as conn:
        row = conn.execute(BRAND_OVERLAP_SQL, {"rid": run_id}).first()
    return int(row[0]) if row else 0


def compute_comparable_counts(engine, run_id: int, retailer: str) -> int:
    """COUNT of snapshots after comparable filter (D-402) for the given retailer.

    Args:
      retailer: 'viled' or 'goldapple' (string passed via bind param — no
        f-string interpolation; T-04-03-05 mitigation).
    """
    with engine.connect() as conn:
        row = conn.execute(
            COMPARABLE_COUNT_SQL,
            {"rid": run_id, "retailer": retailer},
        ).first()
    return int(row[0]) if row else 0


def read_run_status(engine, run_id: int) -> Optional[str]:
    """D-411 input: returns the literal status column value or ``None``.

    Caller (matcher_run orchestrator) interprets None / 'running' / 'failed'
    as skip-conditions; only 'success' OR 'partial' allow matching to proceed.
    """
    with engine.connect() as conn:
        row = conn.execute(RUN_STATUS_SQL, {"rid": run_id}).first()
    return row[0] if row else None


__all__ = [
    "INSERT_MATCHES_SQL",
    "DENOMINATOR_SQL",
    "BRAND_OVERLAP_SQL",
    "COMPARABLE_COUNT_SQL",
    "DELETE_MATCHES_SQL",
    "RUN_STATUS_SQL",
    "build_matches_for_run",
    "compute_denominator",
    "compute_brand_overlap",
    "compute_comparable_counts",
    "read_run_status",
]
