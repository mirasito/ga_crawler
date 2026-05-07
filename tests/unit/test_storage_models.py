"""DATA-01, DATA-02 — SQLModel `Run` + `Snapshot` table definitions.

Wave 1 / Plan 02-02 implements `src/ga_crawler/storage/sqlite.py` with the two
SQLModel classes (Run with `run_id`, `started_at`, `status`, `stats: TEXT JSON`;
Snapshot with `run_id` FK + composite UNIQUE on (run_id, retailer, sku_id) per
DATA-03 append-only invariant). These tests assert table schema, column types,
and constraint declarations.

Source: 02-RESEARCH.md §Validation Architecture row 1; 02-CONTEXT.md D-214.
"""
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from ga_crawler.storage.sqlite import Run, Snapshot, init_db, make_engine


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
