"""Unit tests for archive.write_atomic — D-510 atomic write + Pitfall 5 crash safety.

Verified: tmp+rename + parent mkdir + overwrite + no orphan tmp on success.
Plus repo-level structural canaries: reports/.gitkeep tracked, .gitignore excludes xlsx.
"""

from __future__ import annotations

from pathlib import Path

from ga_crawler.reporter.archive import write_atomic


def test_write_atomic_creates_complete_file(tmp_path):
    target = tmp_path / "out.xlsx"
    payload = b"hello world\n" * 100
    n = write_atomic(payload, target)
    assert target.exists()
    assert target.read_bytes() == payload
    assert n == len(payload)


def test_write_atomic_returns_st_size(tmp_path):
    target = tmp_path / "out.xlsx"
    payload = b"x" * 1234
    n = write_atomic(payload, target)
    assert n == target.stat().st_size == 1234


def test_write_atomic_creates_parent_directory(tmp_path):
    """target in nested non-existent dir → parents created."""
    nested = tmp_path / "deep" / "nest" / "ed"
    assert not nested.exists()
    target = nested / "out.xlsx"
    write_atomic(b"data", target)
    assert nested.exists() and nested.is_dir()
    assert target.exists()


def test_write_atomic_overwrites_existing(tmp_path):
    """Pre-existing target → replaced with new content, no raise."""
    target = tmp_path / "out.xlsx"
    target.write_bytes(b"old content goes here")
    write_atomic(b"new content", target)
    assert target.read_bytes() == b"new content"


def test_write_atomic_no_orphan_tmp_on_success(tmp_path):
    """After successful write, the *.xlsx.tmp file MUST be gone (renamed)."""
    target = tmp_path / "out.xlsx"
    tmp_sibling = target.with_suffix(target.suffix + ".tmp")
    write_atomic(b"complete data", target)
    assert target.exists()
    assert not tmp_sibling.exists(), "orphan *.xlsx.tmp remained after successful write"


def test_write_atomic_zero_bytes_handled(tmp_path):
    """Empty payload still produces a 0-byte file (not an error)."""
    target = tmp_path / "out.xlsx"
    n = write_atomic(b"", target)
    assert target.exists()
    assert n == 0


def test_write_atomic_idempotent_repeat(tmp_path):
    """Same target written twice with same payload → same final state, no orphans."""
    target = tmp_path / "out.xlsx"
    write_atomic(b"payload v1", target)
    write_atomic(b"payload v1", target)
    assert target.read_bytes() == b"payload v1"
    tmp_sibling = target.with_suffix(target.suffix + ".tmp")
    assert not tmp_sibling.exists()


def test_write_atomic_second_write_replaces_first(tmp_path):
    """D-510 overwrite policy: second call with different payload replaces first."""
    target = tmp_path / "out.xlsx"
    write_atomic(b"first version", target)
    write_atomic(b"second version different length", target)
    assert target.read_bytes() == b"second version different length"


def test_write_atomic_uses_xlsx_tmp_suffix_sibling(tmp_path):
    """Crash-window proof: tmp lives in the same parent dir (same FS for atomic rename).

    Inspect the source to verify the .xlsx.tmp sibling pattern — the rename
    only is atomic on the same filesystem, so a cross-mount tempfile would
    silently break crash safety.
    """
    import inspect

    from ga_crawler.reporter import archive

    src = inspect.getsource(archive.write_atomic)
    assert "xlsx.tmp" in src or ".tmp" in src
    assert "with_suffix" in src
    assert "os.replace" in src


def test_reports_dir_gitkeep_tracked():
    """`reports/.gitkeep` MUST exist (Phase 2 D-219 mirror pattern)."""
    assert Path("reports/.gitkeep").exists(), (
        "reports/.gitkeep is the directory-tracking sentinel — must be present "
        "on every clone so reporter writes never silently fail on missing parent dir"
    )


def test_gitignore_excludes_xlsx():
    """`.gitignore` MUST exclude `reports/*.xlsx` artifact rule."""
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "reports/*.xlsx" in gitignore


def test_gitignore_excludes_xlsx_tmp():
    """`.gitignore` MUST exclude `reports/*.xlsx.tmp` orphan rule."""
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "reports/*.xlsx.tmp" in gitignore
