"""Phase 5 reporter SQL primitives — unit tests against synthetic_report_run.

Source-locks SQL constants via str(...) substring assertions (mirror of
Phase 4 D-405 KPI-formula-canary pattern in tests/unit/test_matcher_strict_key.py).

Behavior tests run the 5 readers against the `synthetic_report_run` fixture
from conftest.py (in-memory SQLite + 1 success run + 3 viled + 8 goldapple
snapshots + 3 matches with deterministic price_delta_pct values).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from ga_crawler.reporter.queries import (
    ASSORTMENT_GAPS_SQL,
    GOLDAPPLE_PROMOS_SQL,
    PER_SKU_DELTAS_SQL,
    RUN_STARTED_AT_SQL,
    TOP_N_DELTAS_SQL,
    read_gaps_for_run,
    read_matches_for_run,
    read_promos_for_run,
    read_run_started_at,
    read_top_n_deltas,
)


# ---------- SQL source-lock canaries ----------


def test_per_sku_deltas_sql_uses_join_back_to_snapshots_for_urls():
    """Pitfall 9: matches table has NO url columns; JOIN both retailer-side
    snapshots for `URL viled` and `URL goldapple` at presentation time.
    """
    sql = str(PER_SKU_DELTAS_SQL)
    assert "FROM matches" in sql
    assert "JOIN snapshots vs" in sql or "JOIN snapshots" in sql
    assert "vs.url" in sql
    assert "gs.url" in sql


def test_per_sku_deltas_sql_orders_by_abs_delta_pct_desc():
    """D-501: Per-SKU deltas sheet sorted by ABS(price_delta_pct) DESC."""
    sql = str(PER_SKU_DELTAS_SQL)
    assert "ORDER BY ABS(m.price_delta_pct) DESC" in sql or "ORDER BY ABS" in sql


def test_assortment_gaps_sql_uses_not_exists():
    """Pitfall 8: prefer NOT EXISTS over NOT IN; SQLite optimizer prefers it."""
    sql = str(ASSORTMENT_GAPS_SQL)
    assert "NOT EXISTS" in sql
    assert "NOT IN" not in sql


def test_assortment_gaps_sql_applies_d402_symmetric_filter():
    """D-502 + D-402: gaps filter must include multipack=0, volume_norm IS NOT NULL,
    stock_state != 'DELISTED' on the goldapple side.
    """
    sql = str(ASSORTMENT_GAPS_SQL)
    assert "multipack_flag = 0" in sql
    assert "volume_norm IS NOT NULL" in sql
    assert "DELISTED" in sql
    assert "retailer = 'goldapple'" in sql


def test_goldapple_promos_sql_derives_discount_in_sql():
    """Pitfall 10: derive discount_amount + discount_pct in SQL; pandas consumer
    does no math.
    """
    sql = str(GOLDAPPLE_PROMOS_SQL)
    assert "was_price > current_price" in sql
    assert "discount_amount" in sql
    assert "discount_pct" in sql
    assert "ORDER BY discount_pct DESC" in sql


def test_top_n_deltas_sql_uses_abs_limit():
    """D-504: SQL ABS LIMIT — don't materialize 50k rows to pick 3."""
    sql = str(TOP_N_DELTAS_SQL)
    assert "ABS(price_delta_pct)" in sql
    assert "LIMIT :n" in sql


def test_all_sql_constants_use_parameterized_rid_binds():
    """T-05-sql-injection: every SQL uses :rid binds (no f-string interpolation)."""
    for s in (
        PER_SKU_DELTAS_SQL,
        ASSORTMENT_GAPS_SQL,
        GOLDAPPLE_PROMOS_SQL,
        TOP_N_DELTAS_SQL,
        RUN_STARTED_AT_SQL,
    ):
        assert ":rid" in str(s), f"missing :rid bind in {s}"


# ---------- Behavioral tests against synthetic_report_run fixture ----------


def test_read_matches_returns_three_rows_sorted_by_abs_delta_desc(synthetic_report_run):
    """Per-SKU deltas: 3 matched rows ordered creed (-22.30) > givenchy (+15.50)
    > dior (+5.00) by ABS(price_delta_pct) DESC.
    """
    engine, _writer, run_id, _root = synthetic_report_run
    df = read_matches_for_run(engine, run_id)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    # Order check
    assert df.iloc[0]["brand_norm"] == "creed"
    assert df.iloc[1]["brand_norm"] == "givenchy"
    assert df.iloc[2]["brand_norm"] == "dior"
    # ABS order: 22.30 > 15.50 > 5.00
    abs_deltas = df["price_delta_pct"].abs().tolist()
    assert abs_deltas == sorted(abs_deltas, reverse=True)
    # JOIN-back to snapshots produced URL columns (Pitfall 9)
    assert "viled_url" in df.columns
    assert "goldapple_url" in df.columns
    assert df.iloc[0]["viled_url"].startswith("https://viled.kz/")
    assert df.iloc[0]["goldapple_url"].startswith("https://goldapple.kz/")


def test_read_gaps_returns_five_rows(synthetic_report_run):
    """5 goldapple SKUs without viled-counterpart: chanel + armani + ysl
    + tom-ford-noir + givenchy-irresistible (the 2 promo rows are also gaps).
    """
    engine, _writer, run_id, _root = synthetic_report_run
    df = read_gaps_for_run(engine, run_id)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 5
    brands = set(df["brand_norm"].tolist())
    assert brands == {"chanel", "armani", "ysl", "tom ford", "givenchy"}


def test_read_promos_returns_two_rows_sorted_by_discount_pct_desc(synthetic_report_run):
    """2 goldapple rows with was_price > current_price; sorted by discount_pct DESC
    (Tom Ford -20% noir > Givenchy -16.67% irresistible).
    """
    engine, _writer, run_id, _root = synthetic_report_run
    df = read_promos_for_run(engine, run_id)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0]["brand_norm"] == "tom ford"
    assert df.iloc[1]["brand_norm"] == "givenchy"
    # Sorted DESC by discount_pct
    pcts = df["discount_pct"].tolist()
    assert pcts == sorted(pcts, reverse=True)
    # SQL-derived columns are present
    assert "discount_amount" in df.columns
    assert "discount_pct" in df.columns
    # Sanity: 20% on the Tom Ford row, ~16.67% on Givenchy
    assert df.iloc[0]["discount_pct"] == 20.0
    # Givenchy irresistible: (30000-25000)/30000 *100 = 16.67
    assert abs(df.iloc[1]["discount_pct"] - 16.67) < 0.01


def test_read_top_n_deltas_returns_list_of_dicts(synthetic_report_run):
    """D-504: top-3 ordered creed > givenchy > dior; list[dict] return shape."""
    engine, _writer, run_id, _root = synthetic_report_run
    top3 = read_top_n_deltas(engine, run_id, n=3)
    assert isinstance(top3, list)
    assert len(top3) == 3
    assert all(isinstance(r, dict) for r in top3)
    assert top3[0]["brand_norm"] == "creed"
    assert top3[1]["brand_norm"] == "givenchy"
    assert top3[2]["brand_norm"] == "dior"
    # Required keys per build_summary contract
    for r in top3:
        assert set(r.keys()) >= {"brand_norm", "name_norm", "volume_norm", "price_delta_pct"}


def test_read_top_n_deltas_respects_n_limit(synthetic_report_run):
    """LIMIT :n bound enforced; n=1 returns only the largest-abs row."""
    engine, _writer, run_id, _root = synthetic_report_run
    top1 = read_top_n_deltas(engine, run_id, n=1)
    assert len(top1) == 1
    assert top1[0]["brand_norm"] == "creed"


def test_read_run_started_at_returns_tz_aware_datetime(synthetic_report_run):
    """D-512 input: started_at must be tz-aware datetime (or parsed string)."""
    engine, _writer, run_id, _root = synthetic_report_run
    started = read_run_started_at(engine, run_id)
    assert started is not None
    assert isinstance(started, datetime)
    assert started.tzinfo is not None


def test_read_run_started_at_missing_run_returns_none(synthetic_report_run):
    """Defensive: nonexistent run_id → None (no exception)."""
    engine, _writer, _run_id, _root = synthetic_report_run
    assert read_run_started_at(engine, 99999) is None
