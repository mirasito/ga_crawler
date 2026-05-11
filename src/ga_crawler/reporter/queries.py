"""Phase 5 reporter SQL primitives — read-only SELECTs over matches/snapshots/runs.

All SQL uses parameterized binds via SQLAlchemy ``text(":rid")`` to prevent
injection (T-04-03-01 inherited from Phase 4 matcher; reasserted as
T-05-sql-injection in 05-02-PLAN.md threat register).

Source:
  - 05-CONTEXT.md D-501..D-503 + Claude's Discretion (goldapple promos filter)
  - 05-RESEARCH.md Pattern 7 (ABS LIMIT) + Pitfalls 8 (NOT EXISTS), 9 (JOIN-back
    to snapshots for URLs because D-401 matches schema is denormalized 13-col
    without url columns), 10 (SQL-side discount math)
  - 05-PATTERNS.md "src/ga_crawler/reporter/queries.py" section
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


# ---------------------------------------------------------------------------
# SQL constants — module-level, source-locked. Operator changes via git PR.
# ---------------------------------------------------------------------------

# D-501 + Pitfall 9 (JOIN-back to snapshots for URLs).
# matches table has no url cols (D-401 13-col denormalized); URLs live in snapshots.
# Ordering: ABS(price_delta_pct) DESC so "biggest disagreement first" UX on the
# Per-SKU deltas sheet.
PER_SKU_DELTAS_SQL = text(
    """
    SELECT
      m.brand_norm, m.name_norm, m.volume_norm,
      m.viled_price, m.viled_was_price, vs.url AS viled_url,
      m.goldapple_price, m.goldapple_was_price, gs.url AS goldapple_url,
      m.price_delta, m.price_delta_pct
    FROM matches m
    JOIN snapshots vs
      ON vs.run_id = m.run_id AND vs.retailer = 'viled' AND vs.sku_id = m.viled_sku
    JOIN snapshots gs
      ON gs.run_id = m.run_id AND gs.retailer = 'goldapple' AND gs.sku_id = m.goldapple_sku
    WHERE m.run_id = :rid
    ORDER BY ABS(m.price_delta_pct) DESC
    """
)


# D-502 + Pitfall 8 (NOT EXISTS instead of NOT IN; symmetric D-402 filter).
# SKU-level gaps within brand-overlap (CRAWL-02 scope) — only goldapple SKUs
# that have no equivalent strict-key on viled side. NOT EXISTS lets SQLite's
# optimizer short-circuit on the correlated subquery.
ASSORTMENT_GAPS_SQL = text(
    """
    SELECT s.brand_norm, s.name_norm, s.volume_norm,
           s.current_price, s.was_price, s.url
    FROM snapshots s
    WHERE s.retailer = 'goldapple'
      AND s.run_id = :rid
      AND s.multipack_flag = 0
      AND s.volume_norm IS NOT NULL
      AND s.stock_state != 'DELISTED'
      AND NOT EXISTS (
          SELECT 1 FROM matches m
          WHERE m.run_id = :rid
            AND m.brand_norm = s.brand_norm
            AND m.name_norm = s.name_norm
            AND m.volume_norm = s.volume_norm
      )
    ORDER BY s.brand_norm, s.name_norm
    """
)


# Claude's Discretion (05-CONTEXT.md "Goldapple promos filter") + Pitfall 10
# (derive discount_amount + discount_pct in SQL so DataFrame consumer needs no
# pandas math). Sort by discount_pct DESC — most aggressive promo first.
GOLDAPPLE_PROMOS_SQL = text(
    """
    SELECT brand_norm, name_norm, volume_norm,
           current_price, was_price,
           (was_price - current_price) AS discount_amount,
           ROUND((was_price - current_price) * 100.0 / was_price, 2) AS discount_pct,
           url
    FROM snapshots
    WHERE retailer = 'goldapple'
      AND run_id = :rid
      AND was_price IS NOT NULL
      AND was_price > current_price
      AND multipack_flag = 0
      AND volume_norm IS NOT NULL
      AND stock_state != 'DELISTED'
    ORDER BY discount_pct DESC
    """
)


# D-504 top-3 deltas for summary text. Pattern 7 SQL ABS LIMIT — never
# materialize a 50k-row matches table into pandas just to pick 3.
TOP_N_DELTAS_SQL = text(
    """
    SELECT brand_norm, name_norm, volume_norm, price_delta_pct
    FROM matches
    WHERE run_id = :rid
    ORDER BY ABS(price_delta_pct) DESC
    LIMIT :n
    """
)


# D-512 ISO-week derivation input — read started_at column for the run.
RUN_STARTED_AT_SQL = text("SELECT started_at FROM runs WHERE run_id = :rid")


# ---------------------------------------------------------------------------
# Thin engine.connect() wrappers — pure read, no transactions needed.
# ---------------------------------------------------------------------------


def read_matches_for_run(engine: Engine, run_id: int) -> pd.DataFrame:
    """D-501 Per-SKU deltas. JOIN-back to snapshots for URLs (Pitfall 9).

    Returns a DataFrame with columns:
      brand_norm, name_norm, volume_norm,
      viled_price, viled_was_price, viled_url,
      goldapple_price, goldapple_was_price, goldapple_url,
      price_delta, price_delta_pct
    Sorted by ABS(price_delta_pct) DESC.
    """
    with engine.connect() as conn:
        return pd.read_sql(PER_SKU_DELTAS_SQL, conn, params={"rid": run_id})


def read_gaps_for_run(engine: Engine, run_id: int) -> pd.DataFrame:
    """D-502 Assortment gaps — SKU-level NOT EXISTS within brand-overlap.

    Returns DataFrame with columns:
      brand_norm, name_norm, volume_norm, current_price, was_price, url.
    """
    with engine.connect() as conn:
        return pd.read_sql(ASSORTMENT_GAPS_SQL, conn, params={"rid": run_id})


def read_promos_for_run(engine: Engine, run_id: int) -> pd.DataFrame:
    """Goldapple promos — discount derived in SQL (Pitfall 10).

    Returns DataFrame with columns:
      brand_norm, name_norm, volume_norm, current_price, was_price,
      discount_amount, discount_pct, url.
    Sorted by discount_pct DESC.
    """
    with engine.connect() as conn:
        return pd.read_sql(GOLDAPPLE_PROMOS_SQL, conn, params={"rid": run_id})


def read_top_n_deltas(engine: Engine, run_id: int, n: int = 3) -> list[dict]:
    """D-504 summary top-N. Returns list[dict] for direct template substitution
    in build_summary().
    """
    with engine.connect() as conn:
        rows = conn.execute(TOP_N_DELTAS_SQL, {"rid": run_id, "n": n}).fetchall()
    return [
        dict(
            brand_norm=r[0],
            name_norm=r[1],
            volume_norm=r[2],
            price_delta_pct=r[3],
        )
        for r in rows
    ]


def read_run_started_at(engine: Engine, run_id: int) -> Optional[datetime]:
    """D-512 input. Returns tz-aware datetime if present, None if run_id missing.

    Handles both datetime (SQLModel-managed row, production path) and ISO string
    (raw text() SELECT, test path) return types defensively. ISO strings without
    an explicit tz are treated as UTC (matches Run.started_at default factory).
    """
    with engine.connect() as conn:
        row = conn.execute(RUN_STARTED_AT_SQL, {"rid": run_id}).first()
    if row is None or row[0] is None:
        return None
    val = row[0]
    if isinstance(val, str):
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    # Already a datetime — guarantee tz-aware
    if val.tzinfo is None:
        val = val.replace(tzinfo=timezone.utc)
    return val


__all__ = [
    "PER_SKU_DELTAS_SQL",
    "ASSORTMENT_GAPS_SQL",
    "GOLDAPPLE_PROMOS_SQL",
    "TOP_N_DELTAS_SQL",
    "RUN_STARTED_AT_SQL",
    "read_matches_for_run",
    "read_gaps_for_run",
    "read_promos_for_run",
    "read_top_n_deltas",
    "read_run_started_at",
]
