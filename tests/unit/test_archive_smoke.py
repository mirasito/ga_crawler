"""Minimal RED canary for Task 1 of plan 05-03 — module + symbol presence.

This file is the RED gate for `reporter/archive.py`. Once archive.py ships
with the 3 module-level callables, this collection succeeds and the smoke
assertions pass. Full year-boundary parametrize + atomic-write + size-guard
test coverage lives in `test_archive_iso_week.py`, `test_archive_atomic_write.py`,
and `tests/integration/test_archive_size_guard.py` per plan 05-03 Tasks 2/3.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def test_archive_module_imports():
    """ModuleNotFoundError on archive.py absence = RED gate."""
    from ga_crawler.reporter import archive  # noqa: F401


def test_archive_exposes_three_callables():
    """Plan 05-03 ships exactly these 3 module-level public functions."""
    from ga_crawler.reporter import archive

    assert callable(archive.derive_filename)
    assert callable(archive.write_atomic)
    assert callable(archive.check_size_guard)


def test_derive_filename_w19_smoke():
    """D-512 canary: 2026-05-10 14:00 UTC → Almaty 19:00 Sun → ISO 2026-W19."""
    from ga_crawler.reporter.archive import derive_filename

    out = derive_filename(datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc))
    assert out == "2026-W19.xlsx"


def test_write_atomic_round_trip_smoke(tmp_path):
    """D-510 smoke: bytes in → file with exact bytes out + final st_size returned."""
    from ga_crawler.reporter.archive import write_atomic

    target = tmp_path / "smoke.xlsx"
    n = write_atomic(b"hello world", target)
    assert target.exists()
    assert target.read_bytes() == b"hello world"
    assert n == 11


def test_check_size_guard_returns_tuple_smoke(tmp_path):
    """D-515 smoke: returns (passed, size_bytes) — never raises on oversize."""
    from ga_crawler.reporter.archive import check_size_guard

    p = tmp_path / "tiny.xlsx"
    p.write_bytes(b"x" * 100)
    passed, size = check_size_guard(p, limit_mb=1)
    assert passed is True
    assert size == 100
