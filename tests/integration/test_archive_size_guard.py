"""Integration tests for archive.check_size_guard — D-515 / REPORT-06.

Marked as integration because we materialize 45+ MB files on disk. Uses
pytest tmp_path to keep artifacts isolated and auto-cleaned.

Invariants:
  - check_size_guard NEVER raises (D-515 — flag-only)
  - xlsx persists on disk regardless of size (manual recovery / Phase 6 split)
  - Inclusive boundary on the limit (<=)
  - Phase 5 reporter is independent of delivery (ARCHITECTURE.md)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ga_crawler.reporter.archive import check_size_guard, write_atomic


pytestmark = pytest.mark.integration


def _make_file(path: Path, size_bytes: int) -> None:
    """Write a file of exactly ``size_bytes`` bytes (efficient via os.truncate).

    Uses ``f.truncate(size_bytes)`` which is O(1) and creates a sparse file
    on most filesystems. ``check_size_guard`` reads ``stat().st_size`` which
    returns the logical size, so this is byte-exact and fast even for 1 GB.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.truncate(size_bytes)


def test_size_guard_under_limit(tmp_path):
    target = tmp_path / "small.xlsx"
    _make_file(target, 1024)  # 1 KB
    passed, size = check_size_guard(target, limit_mb=1)
    assert passed is True
    assert size == 1024


def test_size_guard_at_exact_limit_passes_inclusive(tmp_path):
    """Boundary: file size == limit → passed=True (inclusive <=)."""
    target = tmp_path / "exact.xlsx"
    limit_bytes = 1 * 1024 * 1024  # 1 MB exact
    _make_file(target, limit_bytes)
    passed, size = check_size_guard(target, limit_mb=1)
    assert passed is True
    assert size == limit_bytes


def test_size_guard_one_byte_over_limit_fails(tmp_path):
    """limit+1 byte → passed=False."""
    target = tmp_path / "over.xlsx"
    limit_bytes = 1 * 1024 * 1024  # 1 MB
    _make_file(target, limit_bytes + 1)
    passed, size = check_size_guard(target, limit_mb=1)
    assert passed is False
    assert size == limit_bytes + 1


def test_size_guard_45mb_threshold_matches_d516_default(tmp_path):
    """Plan 05-04 orchestrator will call check_size_guard with limit_mb=45 (D-516 seed).

    A 45 MB + 1 byte file is the canonical D-515 trip case — proves a
    ReportConfig.size_limit_mb default of 45 trips at the next byte.
    """
    target = tmp_path / "near-telegram.xlsx"
    _make_file(target, 45 * 1024 * 1024 + 1)  # 45 MB + 1 byte
    passed, size = check_size_guard(target, limit_mb=45)
    assert passed is False
    assert size > 45 * 1024 * 1024


def test_size_guard_file_persists_after_check(tmp_path):
    """D-515 invariant: check_size_guard is read-only; xlsx must remain on disk.

    ARCHITECTURE.md "reporter independent of delivery" — even when oversize,
    the artifact is kept for manual recovery / Phase 6 split-and-send-later.
    """
    target = tmp_path / "persists.xlsx"
    _make_file(target, 46 * 1024 * 1024)  # over 45 MB limit
    passed, size = check_size_guard(target, limit_mb=45)
    assert passed is False
    # File still exists with same size after check
    assert target.exists()
    assert target.stat().st_size == size


def test_size_guard_never_raises_on_oversize(tmp_path):
    """D-515 mandates flag-only behavior — even 1 GB-sized file does not raise."""
    target = tmp_path / "huge.xlsx"
    _make_file(target, 1024 * 1024 * 1024)  # 1 GB (sparse, O(1))
    # Must not raise
    passed, size = check_size_guard(target, limit_mb=45)
    assert passed is False
    assert size == 1024 * 1024 * 1024


def test_size_guard_combined_with_write_atomic(tmp_path):
    """Smoke combo: write_atomic produces file; size guard reads back size correctly.

    Exercises the Plan 05-04 orchestrator's expected call sequence:
    excel_builder.build_workbook() → write_atomic() → check_size_guard().
    """
    target = tmp_path / "subdir" / "report.xlsx"
    payload = b"x" * (2 * 1024 * 1024 + 500)  # 2 MB + 500 bytes
    n = write_atomic(payload, target)
    assert n == len(payload)
    passed, size = check_size_guard(target, limit_mb=2)
    assert passed is False  # 2.0005 MB > 2 MB limit
    assert size == len(payload)
    passed2, _ = check_size_guard(target, limit_mb=3)
    assert passed2 is True  # 2.0005 MB <= 3 MB limit


def test_size_guard_zero_byte_file(tmp_path):
    """Empty file (0 bytes) passes any positive limit; size_bytes == 0."""
    target = tmp_path / "empty.xlsx"
    _make_file(target, 0)
    passed, size = check_size_guard(target, limit_mb=45)
    assert passed is True
    assert size == 0
