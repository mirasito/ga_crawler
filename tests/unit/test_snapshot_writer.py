"""DATA-03, DATA-04 verification. Source: 02-RESEARCH.md §Pattern 5 + Anti-Patterns."""
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ga_crawler.storage.sqlite import (
    Run,
    Snapshot,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


@pytest.fixture
def writer_setup(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    engine = make_engine(db)
    with Session(engine) as s:
        s.add(Run(run_id=1, status="running"))
        s.commit()
    return engine, SqliteSnapshotWriter(engine, batch_size=2)


def _record(sku_id: str, **overrides) -> dict:
    base = dict(
        sku_id=sku_id, url=f"https://x/{sku_id}", name="n", brand="B",
        brand_norm="b", name_norm="n", current_price=1000, was_price=None,
        currency="KZT", stock_state="IN_STOCK",
    )
    base.update(overrides)
    return base


def test_append_returns_count(writer_setup):
    _, writer = writer_setup
    n = writer.append(1, "viled", [_record("A"), _record("B"), _record("C")])
    assert n == 3


def test_append_only_no_update(writer_setup):
    engine, writer = writer_setup
    writer.append(1, "viled", [_record("X")])
    with pytest.raises(IntegrityError):
        writer.append(1, "viled", [_record("X", name="changed")])


def test_append_accepts_phase3_dict_shape(writer_setup):
    """Pitfall 7: Phase 3 goldapple_run.py:237-250 dict shape lacks multipack_flag /
    parse_error_flag / volume_raw — Phase 2 writer must accept gracefully via defaults.
    """
    _, writer = writer_setup
    p3_shape = {
        "sku_id": "P3", "url": "u", "name": "n", "brand": "b",
        "brand_norm": "b", "name_norm": "n",
        "current_price": 999, "was_price": None, "currency": "KZT",
        "stock_state": "IN_STOCK",
        "volume_norm": None, "raw_volume_text": None,
        # NOTE: no multipack_flag, parse_error_flag, volume_raw — must NOT crash
    }
    n = writer.append(1, "goldapple", [p3_shape])
    assert n == 1


def test_append_empty_returns_zero(writer_setup):
    _, writer = writer_setup
    assert writer.append(1, "viled", []) == 0


def test_per_batch_commit(writer_setup):
    """DATA-04: mid-run failure preserves prior batches. batch_size=2."""
    engine, writer = writer_setup
    good = [_record(f"K{i}") for i in range(4)]
    bad = _record("K0")  # duplicate of K0 — will trigger IntegrityError
    with pytest.raises(IntegrityError):
        writer.append(1, "viled", good + [bad])
    with Session(engine) as s:
        rows = s.exec(select(Snapshot).where(Snapshot.run_id == 1)).all()
        # First 2 batches (K0, K1, K2, K3) were committed at batch boundary;
        # the failing 5th row rolled back. Expected: 4 rows durable.
        assert len(rows) == 4
