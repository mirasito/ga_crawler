"""DATA-06 — `bin/backup.sh` produces atomic SQLite snapshot under backups/.

Wave 5 / Plan 02-06 ships `bin/backup.sh` per D-219:
    sqlite3 prices.db ".backup backups/$(date +%Y-%m-%d).db"
    ls -t backups/*.db | tail -n +5 | xargs rm -f   # retention=4

Asserts:
  - script invocation produces a new backups/{YYYY-MM-DD}.db file
  - backup file is a valid SQLite database with the same row counts as source
  - retention rotation keeps exactly 4 newest backup files

Source: 02-RESEARCH.md §Validation Architecture row 24; 02-CONTEXT.md D-219.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 5 not implemented yet — Plan 02-06")


def test_placeholder():
    """Placeholder. Plan 02-06 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-06"
