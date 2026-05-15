"""Phase 4 matcher SQL primitives (v2: brand+volume JOIN + Python token filter).

v1 of this module used a pure SQL JOIN on ``brand_norm + name_norm + volume_norm``
that produced 0 matches against run-18 production data: viled and goldapple
emit structurally different ``name`` shapes (viled prepends a Russian product-
type prefix, goldapple emits only the English marketing tail). A pure string-
equality JOIN can never bridge that gap.

v2 splits the matcher into two layers:

  Layer 1 (SQL, ``SELECT_CANDIDATE_PAIRS_SQL``)
    Cartesian-style JOIN on ``brand_norm = brand_norm`` AND
    ``volume_norm = volume_norm`` (both NOT NULL) plus the original
    multipack/DELISTED/price filters. This is the fast pre-filter; ground-
    truth analysis on 228 manual pairs shows brand+volume is a tight enough
    gate that the candidate set per run is bounded (~1800 on run-18).

  Layer 2 (Python, ``ga_crawler.matcher.name_match.name_matches``)
    Token-overlap with stopword-aware discriminative-residual logic. See
    that module for the full rationale and ground-truth scoring.

The per-row INSERT SQL (``INSERT_MATCHES_SQL``) is kept as a single module
constant so the price-delta / price-delta-pct formula remains source-locked
by the regression canary; the orchestrator binds named params per accepted
pair instead of executing one bulk INSERT-SELECT.

Decisions:
  - D-401: matches schema — 13 denormalized columns (unchanged).
  - D-402: symmetric filters on numerator — ``multipack_flag=0 AND
    volume_norm IS NOT NULL AND stock_state != 'DELISTED'`` applied to BOTH
    retailers (unchanged, enforced at SQL pre-filter layer).
  - D-403: N→1 keep-all — multiple goldapple SKUs matching the same viled
    SKU each produce a match row (unchanged).
  - D-404: denominator = comparable viled SKUs whose ``brand_norm`` appears
    on goldapple side this run (unchanged).
  - D-405: KPI formula frozen — ``ROUND((g - v) * 100.0 / v, 2)``. Pinned by
    ``test_match_rate_formula_canary``.
  - D-410: ``build_matches_for_run`` = idempotent DELETE-then-INSERT inside
    ONE ``engine.begin()`` transaction.
  - D-411: ``read_run_status`` returns the literal ``status`` column value
    or ``None`` (unchanged).
  - D-420 (NEW, matcher-review-2026-05-15): name-side matching delegated to
    ``ga_crawler.matcher.name_match`` Python module; documented + unit-
    tested separately from the SQL primitives here.

Threats mitigated here:
  - T-04-03-01 (SQL injection): every SQL uses bind params (``:rid``,
    ``:v_sku``, etc.) — no f-string interpolation reaches the SQL layer.
  - T-04-03-02 (KPI formula silent drift): the per-row INSERT SQL is a
    module-level ``text(...)`` constant; canary test source-locks ``ROUND(``
    and the ``* 100.0 /`` numerator substring.
  - T-04-03-03 (partial INSERT on crash): ``build_matches_for_run`` wraps
    DELETE+all INSERTs in a single ``engine.begin()`` block.
"""

from __future__ import annotations

from typing import Iterable, Optional

import structlog
from sqlalchemy import text

from ga_crawler.matcher.name_match import name_matches

log = structlog.get_logger(__name__)


# ---- SQL constants (D-405: KPI formula frozen with week-1 baseline) ----

# Pre-filter brand+volume candidate pairs to send to the Python name filter.
# All D-402 numerator constraints are applied here (multipack=0, volume NOT
# NULL, stock != DELISTED, price NOT NULL) so the Python loop only sees
# eligible rows.
SELECT_CANDIDATE_PAIRS_SQL = text(
    """
    SELECT
      v.sku_id            AS v_sku,
      g.sku_id            AS g_sku,
      v.brand_norm        AS brand_norm,
      v.name_norm         AS v_name_norm,
      g.name_norm         AS g_name_norm,
      g.url               AS g_url,
      v.volume_norm       AS volume_norm,
      v.current_price     AS v_price,
      g.current_price     AS g_price,
      v.was_price         AS v_was,
      g.was_price         AS g_was
    FROM snapshots v
    JOIN snapshots g
      ON v.brand_norm = g.brand_norm
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

# Single-row INSERT, executed once per (viled, goldapple) pair the Python
# token filter accepts. The price-delta + price-delta-pct formula lives here
# and is source-locked by the regression canary.
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
    VALUES (
      :rid, :v_sku, :g_sku,
      :brand_norm, :name_norm, :volume_norm,
      :v_price, :g_price,
      :v_was, :g_was,
      (:g_price - :v_price),
      ROUND((:g_price - :v_price) * 100.0 / :v_price, 2),
      CURRENT_TIMESTAMP
    )
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


def _select_candidate_pairs(conn, run_id: int) -> Iterable:
    """Stream (viled, goldapple) candidate pairs after SQL brand+volume gate.

    Yields SQLAlchemy ``Row`` objects with columns matching
    ``SELECT_CANDIDATE_PAIRS_SQL``. The result set is bounded by the brand-
    overlap intersection on the run; on run-18 production data this is
    ~1800 rows.
    """
    return conn.execute(SELECT_CANDIDATE_PAIRS_SQL, {"rid": run_id})


def build_matches_for_run(engine, run_id: int) -> int:
    """D-410 idempotent DELETE-and-reinsert in a SINGLE transaction.

    Two-layer match: (1) SQL brand+volume pre-filter via
    ``SELECT_CANDIDATE_PAIRS_SQL``; (2) Python token-overlap filter via
    ``ga_crawler.matcher.name_match.name_matches``. Either all pre-existing
    matches for this run_id are deleted AND the new set is inserted, or
    neither change is applied. Returns the count of rows inserted.

    Re-running on the same run_id produces identical match rows because both
    the SQL pre-filter and the Python token filter are pure functions of the
    immutable snapshot rows.
    """
    inserted = 0
    with engine.begin() as conn:
        conn.execute(DELETE_MATCHES_SQL, {"rid": run_id})
        for cand in _select_candidate_pairs(conn, run_id):
            if not name_matches(
                viled_name_norm=cand.v_name_norm,
                goldapple_url=cand.g_url,
                goldapple_name_norm=cand.g_name_norm,
                brand_norm=cand.brand_norm,
            ):
                continue
            conn.execute(
                INSERT_MATCHES_SQL,
                {
                    "rid": run_id,
                    "v_sku": cand.v_sku,
                    "g_sku": cand.g_sku,
                    "brand_norm": cand.brand_norm,
                    # name_norm column is the viled side's normalized name
                    # (kept as the canonical "match key" for human review of
                    # the matches table).
                    "name_norm": cand.v_name_norm,
                    "volume_norm": cand.volume_norm,
                    "v_price": cand.v_price,
                    "g_price": cand.g_price,
                    "v_was": cand.v_was,
                    "g_was": cand.g_was,
                },
            )
            inserted += 1
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
    "SELECT_CANDIDATE_PAIRS_SQL",
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
