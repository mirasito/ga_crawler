"""DATA-04 verification. Source: 02-RESEARCH.md §Initializing the WAL session."""
from ga_crawler.storage.sqlite import init_db, make_engine


def test_wal_pragma_active(tmp_path):
    db = tmp_path / "wal.db"
    init_db(db)
    engine = make_engine(db)
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"


def test_synchronous_normal(tmp_path):
    db = tmp_path / "sync.db"
    init_db(db)
    engine = make_engine(db)
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA synchronous").fetchone()
        # NORMAL = 1
        assert result[0] == 1


def test_foreign_keys_on(tmp_path):
    db = tmp_path / "fk.db"
    init_db(db)
    engine = make_engine(db)
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
