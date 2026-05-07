"""DATA-05 + Pitfall 4 + Pitfall 6 verification. Source: 02-RESEARCH.md §Pattern 4."""
import pytest
from sqlmodel import Session

from ga_crawler.storage.sqlite import (
    Run,
    SqliteRunWriter,
    init_db,
    make_engine,
)


@pytest.fixture
def writer(tmp_path):
    db = tmp_path / "rw.db"
    init_db(db)
    engine = make_engine(db)
    return SqliteRunWriter(engine), engine


def test_create_returns_run_id(writer):
    rw, _ = writer
    rid1 = rw.create()
    rid2 = rw.create()
    assert isinstance(rid1, int) and isinstance(rid2, int)
    assert rid1 != rid2


def test_patch_stats_atomic_merge_pitfall_6(writer):
    """Pitfall 6: viled.* and goldapple.* keys merge cleanly via json_patch."""
    rw, _engine = writer
    rid = rw.create()
    rw.patch_stats(rid, {"viled.fetch_count": 100, "viled.parse_failures": 2})
    rw.patch_stats(rid, {"goldapple.fetch_count": 1000, "goldapple.fetch_failures": 5})
    stats = rw.get_stats(rid)
    assert stats["viled.fetch_count"] == 100
    assert stats["viled.parse_failures"] == 2
    assert stats["goldapple.fetch_count"] == 1000
    assert stats["goldapple.fetch_failures"] == 5


def test_patch_stats_overrides_existing_key(writer):
    rw, _ = writer
    rid = rw.create()
    rw.patch_stats(rid, {"k": 1})
    rw.patch_stats(rid, {"k": 2})
    assert rw.get_stats(rid)["k"] == 2


def test_patch_stats_rejects_none_pitfall_4(writer):
    """Pitfall 4: RFC-7396 treats null as DELETE; we reject upstream."""
    rw, _ = writer
    rid = rw.create()
    with pytest.raises(ValueError, match="Pitfall 4"):
        rw.patch_stats(rid, {"viled.foo": None})


def test_get_stats_missing_run(writer):
    rw, _ = writer
    assert rw.get_stats(9999) == {}


def test_fail_idempotent(writer):
    rw, engine = writer
    rid = rw.create()
    rw.fail(rid, "first reason")
    rw.fail(rid, "second reason")  # must not raise
    with Session(engine) as s:
        row = s.get(Run, rid)
        assert row.status == "failed"
        assert row.fail_reason == "second reason"


def test_finalize_only_running(writer):
    """finalize() WHERE status='running' guard: cannot un-fail a failed run."""
    rw, engine = writer
    rid = rw.create()
    rw.fail(rid, "boom")
    rw.finalize(rid, "success")  # must NOT change status
    with Session(engine) as s:
        row = s.get(Run, rid)
        assert row.status == "failed"
