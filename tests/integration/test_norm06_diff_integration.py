"""End-to-end NORM-06 reverse direction (D-307): persist + diff across two runs.

Tests the persist_sitemap_slugs / find_previous_slug_file / diff_new_slugs
trio across multiple run-IDs, exercising:
  - first run has no predecessor (empty diff)
  - second run sees first run as predecessor
  - third run picks the LATEST predecessor (run 2, not run 1)
  - removed slugs are NOT surfaced (D-307: additions only)

Source plan: 03-06-PLAN.md Task 1 behavior (test_norm06_diff_integration.py).
"""

from __future__ import annotations

from pathlib import Path

from ga_crawler.enumeration.goldapple_sitemap import (
    diff_new_slugs,
    find_previous_slug_file,
    persist_sitemap_slugs,
)


def test_first_run_no_diff(tmp_path: Path) -> None:
    """Run 1: persist; no predecessor -> empty diff."""
    persist_sitemap_slugs({"givenchy", "tom-ford"}, run_id=1, root=tmp_path)
    prev = find_previous_slug_file(tmp_path, current_run_id=1)
    assert prev is None
    diff = diff_new_slugs({"givenchy", "tom-ford"}, prev)
    assert diff == []


def test_second_run_finds_new_slugs(tmp_path: Path) -> None:
    """Run 1 -> {givenchy}; run 2 -> {givenchy, tom-ford} -> diff = ['tom-ford']."""
    persist_sitemap_slugs({"givenchy"}, run_id=1, root=tmp_path)

    # Run 2 starts: find predecessor (run 1)
    prev = find_previous_slug_file(tmp_path, current_run_id=2)
    assert prev == tmp_path / "runs" / "1" / "sitemap-slugs.txt"

    new_in_run_2 = {"givenchy", "tom-ford"}
    diff = diff_new_slugs(new_in_run_2, prev)
    assert diff == ["tom-ford"]

    # Persist run 2
    persist_sitemap_slugs(new_in_run_2, run_id=2, root=tmp_path)


def test_third_run_only_new_in_diff(tmp_path: Path) -> None:
    """Run 3 finds run 2 as predecessor; new slugs since run 2 only."""
    persist_sitemap_slugs({"a"}, run_id=1, root=tmp_path)
    persist_sitemap_slugs({"a", "b"}, run_id=2, root=tmp_path)

    prev = find_previous_slug_file(tmp_path, current_run_id=3)
    assert prev == tmp_path / "runs" / "2" / "sitemap-slugs.txt"

    diff = diff_new_slugs({"a", "b", "c", "d"}, prev)
    assert diff == ["c", "d"]


def test_removed_slugs_not_in_diff(tmp_path: Path) -> None:
    """Slugs that disappeared between runs are NOT surfaced (D-307: additions only)."""
    persist_sitemap_slugs({"a", "b", "c"}, run_id=1, root=tmp_path)

    prev = find_previous_slug_file(tmp_path, current_run_id=2)
    diff = diff_new_slugs({"a"}, prev)  # b and c removed
    assert diff == []
