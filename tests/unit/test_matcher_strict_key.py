"""Phase 4 matcher SQL primitives — unit tests with synthetic in-memory snapshots.

Pins every D-decision behavior from 04-CONTEXT.md:
  - D-402 symmetric numerator filter (multipack / volume / DELISTED)
  - D-403 N→1 keep-all
  - D-404 denominator confined to brand-overlap
  - D-405 KPI formula frozen (regression-canary)
  - D-410 idempotent DELETE+INSERT in one TX
  - D-411 read_run_status return shape
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from ga_crawler.matcher.strict_key import (
    INSERT_MATCHES_SQL,
    build_matches_for_run,
    compute_brand_overlap,
    compute_comparable_counts,
    compute_denominator,
    read_run_status,
)
from ga_crawler.storage.sqlite import (
    Run,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


# ---- Fixtures ----


@pytest.fixture
def engine(tmp_path):
    """On-disk SQLite engine with real WAL + matches table. Returns engine."""
    db = tmp_path / "matcher.db"
    init_db(db)
    eng = make_engine(db)
    # Plant a runs row (FK constraint on matches.run_id and snapshots.run_id).
    with Session(eng) as s:
        s.add(Run(run_id=1, status="running"))
        s.commit()
    return eng


def _viled_payload(sku_id: str, **overrides) -> dict:
    base = dict(
        sku_id=sku_id,
        url=f"https://viled.kz/{sku_id}",
        name="Eau de Parfum 50ml",
        brand="Givenchy",
        brand_norm="givenchy",
        name_norm="eau de parfum",
        volume_norm="(50, ml, 1)",
        volume_raw="50 мл",
        multipack_flag=False,
        parse_error_flag=False,
        current_price=10000,
        was_price=None,
        currency="KZT",
        stock_state="IN_STOCK",
    )
    base.update(overrides)
    return base


def _goldapple_payload(sku_id: str, **overrides) -> dict:
    base = _viled_payload(sku_id)
    base["url"] = f"https://goldapple.kz/{sku_id}"
    base["current_price"] = 12000
    base.update(overrides)
    return base


def _plant(engine, run_id: int, viled_rows: list[dict], goldapple_rows: list[dict]) -> None:
    """Insert paired viled+goldapple snapshots via SqliteSnapshotWriter."""
    writer = SqliteSnapshotWriter(engine, batch_size=10)
    if viled_rows:
        writer.append(run_id, "viled", viled_rows)
    if goldapple_rows:
        writer.append(run_id, "goldapple", goldapple_rows)


def _count_matches(engine, run_id: int) -> int:
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            f"SELECT COUNT(*) FROM matches WHERE run_id={int(run_id)}"
        ).first()
    return row[0] if row else 0


# ---- Tests ----


def test_strict_key_match_happy_path(engine):
    _plant(engine, 1, [_viled_payload("V1")], [_goldapple_payload("G1")])
    inserted = build_matches_for_run(engine, 1)
    assert inserted == 1
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT viled_sku, goldapple_sku, brand_norm, name_norm, volume_norm, "
            "viled_price, goldapple_price, price_delta, price_delta_pct "
            "FROM matches WHERE run_id=1"
        ).fetchall()
    assert len(rows) == 1
    r = rows[0]
    assert r[0] == "V1"
    assert r[1] == "G1"
    assert r[2] == "givenchy"
    assert r[3] == "eau de parfum"
    assert r[4] == "(50, ml, 1)"
    assert r[5] == 10000
    assert r[6] == 12000
    assert r[7] == 2000  # goldapple - viled
    assert r[8] == pytest.approx(20.0)  # 2000 / 10000 * 100


def test_idempotent_rerun(engine):
    """D-410: same run_id → same matches set; counts stable."""
    _plant(engine, 1, [_viled_payload("V1")], [_goldapple_payload("G1")])
    n1 = build_matches_for_run(engine, 1)
    n2 = build_matches_for_run(engine, 1)
    n3 = build_matches_for_run(engine, 1)
    assert n1 == n2 == n3 == 1
    assert _count_matches(engine, 1) == 1


def test_multipack_excluded_from_numerator(engine):
    """D-402: multipack_flag=1 → not matched."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", multipack_flag=True)],
        [_goldapple_payload("G1", multipack_flag=True)],
    )
    assert build_matches_for_run(engine, 1) == 0


def test_volume_norm_null_excluded(engine):
    """D-402: NULL volume_norm on either side → not matched."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", volume_norm=None)],
        [_goldapple_payload("G1")],
    )
    assert build_matches_for_run(engine, 1) == 0

    # Reverse case — new run to keep the test isolated.
    with Session(engine) as s:
        s.add(Run(run_id=2, status="running"))
        s.commit()
    _plant(
        engine,
        2,
        [_viled_payload("V2")],
        [_goldapple_payload("G2", volume_norm=None)],
    )
    assert build_matches_for_run(engine, 2) == 0


def test_delisted_excluded(engine):
    """D-402: stock_state='DELISTED' → not matched on either side."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", stock_state="DELISTED")],
        [_goldapple_payload("G1")],
    )
    assert build_matches_for_run(engine, 1) == 0


def test_other_stock_states_kept(engine):
    """OUT_OF_STOCK / UNAVAILABLE / UNKNOWN → KEPT (only DELISTED excluded)."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", stock_state="IN_STOCK")],
        [_goldapple_payload("G1", stock_state="OUT_OF_STOCK")],
    )
    assert build_matches_for_run(engine, 1) == 1


def test_n_to_1_keep_all(engine):
    """D-403: 2 goldapple with same key as 1 viled → both pairs persisted."""
    _plant(
        engine,
        1,
        [_viled_payload("V1")],
        [
            _goldapple_payload("G1", current_price=12000),
            _goldapple_payload("G2", current_price=13000),
        ],
    )
    assert build_matches_for_run(engine, 1) == 2
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT goldapple_sku, goldapple_price FROM matches "
            "WHERE run_id=1 ORDER BY goldapple_sku"
        ).fetchall()
    assert [r[0] for r in rows] == ["G1", "G2"]


def test_denominator_only_in_brand_overlap(engine):
    """D-404: viled SKUs in brand NOT present on goldapple → not in denominator."""
    _plant(
        engine,
        1,
        [
            _viled_payload("V1", brand_norm="givenchy"),
            _viled_payload("V2", brand_norm="givenchy", name_norm="b"),
            _viled_payload("V3", brand_norm="givenchy", name_norm="c"),
            _viled_payload("V4", brand_norm="chanel"),  # chanel not on goldapple
            _viled_payload("V5", brand_norm="chanel", name_norm="b"),
        ],
        [_goldapple_payload("G1", brand_norm="givenchy")],
    )
    assert compute_denominator(engine, 1) == 3


def test_denominator_zero_when_no_brand_overlap(engine):
    """No shared brands → denominator=0; build_matches returns 0; no error."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", brand_norm="chanel")],
        [_goldapple_payload("G1", brand_norm="givenchy")],
    )
    assert compute_denominator(engine, 1) == 0
    assert build_matches_for_run(engine, 1) == 0


def test_brand_overlap_count(engine):
    """compute_brand_overlap returns COUNT(DISTINCT brand_norm) of intersection."""
    _plant(
        engine,
        1,
        [
            _viled_payload("V1", brand_norm="givenchy"),
            _viled_payload("V2", brand_norm="chanel"),
            _viled_payload("V3", brand_norm="dior"),  # not on goldapple
        ],
        [
            _goldapple_payload("G1", brand_norm="givenchy"),
            _goldapple_payload("G2", brand_norm="chanel"),
        ],
    )
    assert compute_brand_overlap(engine, 1) == 2


def test_comparable_counts_per_retailer(engine):
    """compute_comparable_counts: filters multipack / volume / DELISTED for given retailer."""
    _plant(
        engine,
        1,
        [
            _viled_payload("V1"),  # comparable
            _viled_payload("V2", name_norm="b"),  # comparable
            _viled_payload("V3", name_norm="c"),  # comparable
            _viled_payload("V4", multipack_flag=True),  # excluded
            _viled_payload("V5", stock_state="DELISTED", name_norm="d"),  # excluded
        ],
        [
            _goldapple_payload("G1"),  # comparable
            _goldapple_payload("G2", volume_norm=None, name_norm="b"),  # excluded
        ],
    )
    assert compute_comparable_counts(engine, 1, "viled") == 3
    assert compute_comparable_counts(engine, 1, "goldapple") == 1


def test_read_run_status_running_vs_success_vs_missing(engine):
    """D-411: returns 'running' / 'success' / None depending on row state."""
    assert read_run_status(engine, 1) == "running"  # fixture-planted
    with Session(engine) as s:
        s.add(Run(run_id=2, status="success"))
        s.commit()
    assert read_run_status(engine, 2) == "success"
    assert read_run_status(engine, 9999) is None


def test_cross_run_isolation(engine):
    """run_id scoping: build_matches_for_run(1) does NOT touch run_id=2 matches."""
    with Session(engine) as s:
        s.add(Run(run_id=2, status="running"))
        s.commit()
    _plant(engine, 1, [_viled_payload("V1")], [_goldapple_payload("G1")])
    _plant(engine, 2, [_viled_payload("V2")], [_goldapple_payload("G2")])
    build_matches_for_run(engine, 1)
    build_matches_for_run(engine, 2)
    assert _count_matches(engine, 1) == 1
    assert _count_matches(engine, 2) == 1
    # Rebuilding run_id=1 must not touch run_id=2.
    build_matches_for_run(engine, 1)
    assert _count_matches(engine, 2) == 1


def test_match_rate_formula_canary(engine):
    """D-405 KPI formula frozen with week-1 baseline.

    Synthetic 6-viled / 5-comparable / 3-matched fixture pins:
      - compute_denominator == 5
      - build_matches_for_run returns 3
      - round(3 * 100.0 / 5, 2) == 60.0 (formula derived by orchestrator)

    SQL source also locked: INSERT_MATCHES_SQL must contain ROUND and the
    ``* 100.0 /`` numerator. v2 of the matcher (matcher-review-2026-05-15)
    moves from a JOIN-bound formula referencing ``v.current_price`` to a
    per-row INSERT bound to ``:v_price``; the formula's intent is identical
    and the canary now pins the new shape. Any future change to the formula
    must (a) update this canary, (b) update STATE.md accumulated decisions.
    """
    _plant(
        engine,
        1,
        [
            _viled_payload("V1", brand_norm="givenchy", name_norm="a", volume_norm="(50, ml, 1)"),
            _viled_payload("V2", brand_norm="givenchy", name_norm="b", volume_norm="(50, ml, 1)"),
            _viled_payload("V3", brand_norm="givenchy", name_norm="c", volume_norm="(50, ml, 1)"),
            _viled_payload("V4", brand_norm="givenchy", name_norm="d", volume_norm="(50, ml, 1)"),
            _viled_payload("V5", brand_norm="givenchy", name_norm="e", volume_norm="(50, ml, 1)"),
            _viled_payload(
                "V6",
                brand_norm="givenchy",
                name_norm="f",
                volume_norm="(50, ml, 1)",
                stock_state="DELISTED",
            ),  # NOT comparable
        ],
        [
            _goldapple_payload("G1", brand_norm="givenchy", name_norm="a", volume_norm="(50, ml, 1)"),
            _goldapple_payload("G2", brand_norm="givenchy", name_norm="b", volume_norm="(50, ml, 1)"),
            _goldapple_payload("G3", brand_norm="givenchy", name_norm="c", volume_norm="(50, ml, 1)"),
        ],
    )
    assert compute_denominator(engine, 1) == 5
    assert build_matches_for_run(engine, 1) == 3
    rate = round(3 * 100.0 / 5, 2)
    assert rate == 60.0
    # Source-lock the SQL formula (post-v2 shape: per-row INSERT with bind
    # params; substring assertion locks ROUND + the *100.0/ numerator).
    sql_text = str(INSERT_MATCHES_SQL).replace(" ", "").replace("\n", "")
    assert "ROUND(" in sql_text
    assert "*100.0/:v_price" in sql_text


def test_price_delta_sign(engine):
    """D-401: price_delta = goldapple_price - viled_price (signed)."""
    _plant(
        engine,
        1,
        [
            _viled_payload("V1", current_price=10000, name_norm="a"),
            _viled_payload("V2", current_price=15000, name_norm="b"),
        ],
        [
            _goldapple_payload("G1", current_price=12000, name_norm="a"),
            _goldapple_payload("G2", current_price=10000, name_norm="b"),
        ],
    )
    build_matches_for_run(engine, 1)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT viled_sku, price_delta FROM matches WHERE run_id=1 ORDER BY viled_sku"
        ).fetchall()
    deltas = {r[0]: r[1] for r in rows}
    assert deltas["V1"] == 2000  # 12000 - 10000
    assert deltas["V2"] == -5000  # 10000 - 15000


def test_was_price_passthrough(engine):
    """was_price NULL on goldapple side preserved as NULL in match row."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", was_price=20000)],
        [_goldapple_payload("G1", was_price=None)],
    )
    build_matches_for_run(engine, 1)
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT viled_was_price, goldapple_was_price FROM matches WHERE run_id=1"
        ).first()
    assert row[0] == 20000
    assert row[1] is None


def test_join_skips_partial_key_mismatch(engine):
    """Strict-key requires brand_norm + name_norm + volume_norm ALL equal."""
    _plant(
        engine,
        1,
        [_viled_payload("V1", brand_norm="givenchy", name_norm="x", volume_norm="(50, ml, 1)")],
        [_goldapple_payload("G1", brand_norm="givenchy", name_norm="x", volume_norm="(100, ml, 1)")],
    )
    assert build_matches_for_run(engine, 1) == 0
