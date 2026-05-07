"""DATA-01, DATA-02 — SQLModel `Run` + `Snapshot` table definitions.

Wave 1 / Plan 02-02 implements `src/ga_crawler/storage/sqlite.py` with the two
SQLModel classes (Run with `run_id`, `started_at`, `status`, `stats: TEXT JSON`;
Snapshot with `run_id` FK + composite UNIQUE on (run_id, retailer, sku_id) per
DATA-03 append-only invariant). These tests assert table schema, column types,
and constraint declarations.

Source: 02-RESEARCH.md §Validation Architecture row 1; 02-CONTEXT.md D-214.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
