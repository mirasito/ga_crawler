"""DATA-04 — SQLite WAL mode + foreign-keys PRAGMAs applied at engine init.

Wave 1 / Plan 02-02 ships the `create_storage_engine()` factory which sets
`PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL` + `PRAGMA foreign_keys=ON`
via SQLAlchemy `event.listens_for(engine, "connect")`. Asserts pragmas are
honored on a real on-disk SQLite path (not :memory:).

Source: 02-RESEARCH.md §Validation Architecture row 5; CLAUDE.md §Storage.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
