"""D-221 verification: v_current_snapshots returns latest successful run only."""
from sqlmodel import Session

from ga_crawler.storage.sqlite import Run, Snapshot, init_db, make_engine


def _add_run_with_snapshot(s, run_id: int, status: str, sku: str):
    s.add(Run(run_id=run_id, status=status))
    s.commit()
    s.add(
        Snapshot(
            run_id=run_id, retailer="viled", sku_id=sku, url="u", name="n",
            brand="b", brand_norm="b", name_norm="n",
        )
    )
    s.commit()


def test_view_returns_latest_success_run(tmp_path):
    db = tmp_path / "view.db"
    init_db(db)
    engine = make_engine(db)
    with Session(engine) as s:
        _add_run_with_snapshot(s, 1, "success", "RUN1")
        _add_run_with_snapshot(s, 2, "failed", "RUN2")
        _add_run_with_snapshot(s, 3, "success", "RUN3")
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT sku_id FROM v_current_snapshots").fetchall()
    assert {r[0] for r in rows} == {"RUN3"}


def test_view_empty_when_no_success_runs(tmp_path):
    db = tmp_path / "empty.db"
    init_db(db)
    engine = make_engine(db)
    with Session(engine) as s:
        _add_run_with_snapshot(s, 1, "failed", "X")
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT sku_id FROM v_current_snapshots").fetchall()
    # No successful run → MAX(run_id) is NULL → WHERE run_id = NULL → 0 rows
    assert rows == []
