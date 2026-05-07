"""DATA-05 lifecycle integration: create → patch_stats(viled+goldapple) → finalize.

Source: 02-RESEARCH.md §System Architecture Diagram steps 1+2e+4+6.
"""
from sqlmodel import Session

from ga_crawler.storage.sqlite import (
    Run,
    SqliteRunWriter,
    init_db,
    make_engine,
)


def test_full_run_cycle(tmp_path):
    db = tmp_path / "lifecycle.db"
    init_db(db)
    engine = make_engine(db)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    rw.patch_stats(rid, {"viled.fetch_count": 500, "viled.sanity_gate_n_pass": 1})
    rw.patch_stats(
        rid, {"goldapple.fetch_count": 3000, "goldapple.sanity_gate_m_pass": 1}
    )
    rw.finalize(rid, "success")
    with Session(engine) as s:
        row = s.get(Run, rid)
        assert row.status == "success"
        assert row.finished_at is not None
    stats = rw.get_stats(rid)
    assert "viled.fetch_count" in stats
    assert "goldapple.fetch_count" in stats
    assert stats["viled.fetch_count"] == 500
    assert stats["goldapple.fetch_count"] == 3000
