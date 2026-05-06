"""Unit tests for week-over-week NEW slug diff (D-307 NORM-06 reverse direction)."""

from __future__ import annotations

from pathlib import Path

from ga_crawler.enumeration.goldapple_sitemap import (
    diff_new_slugs,
    find_previous_slug_file,
    persist_sitemap_slugs,
)


def test_persist_creates_parent_and_writes_sorted(tmp_path: Path) -> None:
    out = persist_sitemap_slugs({"banana", "apple", "cherry"}, run_id=7, root=tmp_path)
    assert out == tmp_path / "runs/7/sitemap-slugs.txt"
    assert out.exists()
    content = out.read_text(encoding="utf-8").splitlines()
    assert content == ["apple", "banana", "cherry"]


def test_find_previous_no_runs_dir(tmp_path: Path) -> None:
    assert find_previous_slug_file(tmp_path, current_run_id=42) is None


def test_find_previous_returns_latest_predecessor(tmp_path: Path) -> None:
    persist_sitemap_slugs({"a"}, run_id=30, root=tmp_path)
    persist_sitemap_slugs({"b"}, run_id=40, root=tmp_path)
    persist_sitemap_slugs({"c"}, run_id=20, root=tmp_path)
    prev = find_previous_slug_file(tmp_path, current_run_id=42)
    assert prev == tmp_path / "runs/40/sitemap-slugs.txt"


def test_find_previous_skips_future_runs(tmp_path: Path) -> None:
    """Run 45 > current 42; must be ignored even though file exists."""
    persist_sitemap_slugs({"x"}, run_id=45, root=tmp_path)
    assert find_previous_slug_file(tmp_path, current_run_id=42) is None


def test_find_previous_skips_non_numeric_dirs(tmp_path: Path) -> None:
    """A dir named 'meta' or other non-int name is ignored cleanly."""
    (tmp_path / "runs" / "meta").mkdir(parents=True)
    (tmp_path / "runs" / "meta" / "sitemap-slugs.txt").write_text("x", encoding="utf-8")
    persist_sitemap_slugs({"y"}, run_id=10, root=tmp_path)
    prev = find_previous_slug_file(tmp_path, current_run_id=20)
    assert prev == tmp_path / "runs/10/sitemap-slugs.txt"


def test_diff_first_run_empty(tmp_path: Path) -> None:
    """Pitfall 8 doc: first run returns empty diff (previous_path=None)."""
    assert diff_new_slugs({"a", "b", "c"}, previous_path=None) == []


def test_diff_additions_returned_sorted(tmp_path: Path) -> None:
    prev = tmp_path / "prev.txt"
    prev.write_text("apple\n", encoding="utf-8")
    diff = diff_new_slugs({"apple", "banana", "cherry"}, previous_path=prev)
    assert diff == ["banana", "cherry"]


def test_diff_removals_ignored(tmp_path: Path) -> None:
    """D-307: tracks ADDITIONS only. Removals are silently dropped."""
    prev = tmp_path / "prev.txt"
    prev.write_text("apple\nbanana\ncherry\n", encoding="utf-8")
    diff = diff_new_slugs({"apple"}, previous_path=prev)
    assert diff == []


def test_diff_handles_blank_lines_in_previous(tmp_path: Path) -> None:
    prev = tmp_path / "prev.txt"
    prev.write_text("apple\n\nbanana\n   \n", encoding="utf-8")
    diff = diff_new_slugs({"apple", "banana", "cherry"}, previous_path=prev)
    assert diff == ["cherry"]
