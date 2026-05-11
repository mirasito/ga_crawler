"""DATA-01, DATA-02 — SQLModel `Run` + `Snapshot` table definitions.

Wave 1 / Plan 02-02 implements `src/ga_crawler/storage/sqlite.py` with the two
SQLModel classes (Run with `run_id`, `started_at`, `status`, `stats: TEXT JSON`;
Snapshot with `run_id` FK + composite UNIQUE on (run_id, retailer, sku_id) per
DATA-03 append-only invariant). These tests assert table schema, column types,
and constraint declarations.

Phase 4 Plan 04-01 extends this file with `Match` SQLModel regression tests:
13 D-401 columns + composite PK `(run_id, viled_sku, goldapple_sku)` supporting
D-403 N→1 keep-all + idempotent `init_db()` table bootstrap (D-415: no alembic).

Source: 02-RESEARCH.md §Validation Architecture row 1; 02-CONTEXT.md D-214;
04-CONTEXT.md D-401..D-403, D-415.
"""
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from ga_crawler.storage.sqlite import Match, Run, Snapshot, init_db, make_engine


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return make_engine(db)


def test_snapshot_columns():
    cols = set(Snapshot.model_fields.keys())
    expected = {
        "id", "run_id", "retailer", "sku_id", "url", "name", "brand",
        "brand_norm", "name_norm", "volume_raw", "volume_norm",
        "multipack_flag", "parse_error_flag", "current_price", "was_price",
        "currency", "stock_state", "scraped_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_run_table():
    cols = set(Run.model_fields.keys())
    expected = {"run_id", "started_at", "finished_at", "status", "fail_reason", "stats"}
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_snapshot_unique_constraint(engine):
    with Session(engine) as s:
        s.add(Run(run_id=1, status="running"))
        s.commit()
        s.add(
            Snapshot(
                run_id=1, retailer="viled", sku_id="X1", url="u",
                name="n", brand="b", brand_norm="b", name_norm="n",
            )
        )
        s.commit()
        s.add(
            Snapshot(
                run_id=1, retailer="viled", sku_id="X1", url="u2",
                name="n2", brand="b", brand_norm="b", name_norm="n2",
            )
        )
        with pytest.raises(IntegrityError):
            s.commit()


# ---- Phase 4 / Plan 04-01: Match SQLModel regression tests (D-401..D-403, D-415) ----


def test_match_columns():
    """D-401: Match SQLModel must expose exactly the 13 denormalized columns
    so Phase 5 reporter can project directly without JOIN-back to snapshots."""
    cols = set(Match.model_fields.keys())
    expected = {
        "run_id", "viled_sku", "goldapple_sku",
        "brand_norm", "name_norm", "volume_norm",
        "viled_price", "goldapple_price",
        "viled_was_price", "goldapple_was_price",
        "price_delta", "price_delta_pct", "matched_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_match_composite_pk_allows_one_viled_to_many_goldapple(engine):
    """D-403 N→1 keep-all: PK is (run_id, viled_sku, goldapple_sku). Two rows
    with same (run_id, viled_sku) but different goldapple_sku INSERT cleanly —
    we never drop the "goldapple has multiple variants" commercial signal."""
    with Session(engine) as s:
        s.add(Run(run_id=1, status="running"))
        s.commit()
        s.add(Match(
            run_id=1, viled_sku="V1", goldapple_sku="G1",
            brand_norm="givenchy", name_norm="eau de parfum", volume_norm="(50, ml, 1)",
            viled_price=10000, goldapple_price=12000,
            price_delta=2000, price_delta_pct=20.00,
        ))
        s.add(Match(
            run_id=1, viled_sku="V1", goldapple_sku="G2",
            brand_norm="givenchy", name_norm="eau de parfum", volume_norm="(50, ml, 1)",
            viled_price=10000, goldapple_price=13000,
            price_delta=3000, price_delta_pct=30.00,
        ))
        s.add(Match(
            run_id=1, viled_sku="V1", goldapple_sku="G3",
            brand_norm="givenchy", name_norm="eau de parfum", volume_norm="(50, ml, 1)",
            viled_price=10000, goldapple_price=14000,
            price_delta=4000, price_delta_pct=40.00,
        ))
        s.commit()

    # Read back — multiset must match input (D-403 keep-all)
    with Session(engine) as s:
        rows = s.exec(  # type: ignore[call-overload]
            Match.__table__.select().where(Match.run_id == 1)
        ).all()
        retrieved_pairs = sorted((r.viled_sku, r.goldapple_sku) for r in rows)
        assert retrieved_pairs == [("V1", "G1"), ("V1", "G2"), ("V1", "G3")]


def test_match_composite_pk_rejects_exact_duplicate(engine):
    """D-401 composite PK uniqueness: same (run_id, viled_sku, goldapple_sku)
    twice → IntegrityError. Protects idempotency invariant (D-410 DELETE+INSERT
    transaction can never insert duplicates)."""
    with Session(engine) as s:
        s.add(Run(run_id=1, status="running"))
        s.commit()
        s.add(Match(
            run_id=1, viled_sku="V1", goldapple_sku="G1",
            brand_norm="b", name_norm="n", volume_norm="(50, ml, 1)",
            viled_price=10000, goldapple_price=12000,
            price_delta=2000, price_delta_pct=20.00,
        ))
        s.commit()
        s.add(Match(
            run_id=1, viled_sku="V1", goldapple_sku="G1",
            brand_norm="b", name_norm="n", volume_norm="(50, ml, 1)",
            viled_price=10000, goldapple_price=99999,
            price_delta=89999, price_delta_pct=899.99,
        ))
        with pytest.raises(IntegrityError):
            s.commit()


def test_init_db_creates_matches_table(tmp_path):
    """D-415: matches table is created idempotently via
    SQLModel.metadata.create_all (no alembic on day 1). Verify by querying
    sqlite_master after init_db()."""
    db = tmp_path / "init.db"
    init_db(db)
    engine = make_engine(db)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='matches'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "matches"
