"""DATA-06 — `bin/backup.sh` produces atomic SQLite snapshot under backups/.

Wave 5 / Plan 02-06 ships `bin/backup.sh` per D-219:
    sqlite3 prices.db ".backup backups/$(date +%Y-%m-%d).db"
    ls -t backups/*.db | tail -n +5 | xargs -r rm -f   # retention=4

Asserts:
  - script invocation produces a new backups/{YYYY-MM-DD}.db file
  - backup file is a valid SQLite database with the expected tables
  - retention rotation keeps exactly 4 newest backup files
  - missing source DB exits non-zero
  - target directory is created if absent

Source: 02-RESEARCH.md §Pitfall 3 (WAL-safe atomic backup);
        02-CONTEXT.md D-219 (online .backup + 4-rotate retention).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import time
from datetime import date
from pathlib import Path

import pytest

from ga_crawler.storage.sqlite import init_db

BACKUP_SCRIPT = Path("bin/backup.sh").resolve()


def _resolve_bash() -> str | None:
    """Resolve a POSIX-compatible bash interpreter.

    On Windows, Microsoft ships `System32\\bash.exe` aliased to WSL. If WSL is
    not installed, it errors out with a Cyrillic "WSL not installed" message
    even when invoked from a non-WSL context. We therefore prefer Git Bash
    (`C:\\Program Files\\Git\\usr\\bin\\bash.exe`) and fall back to whatever
    `shutil.which("bash")` returns first — `shutil.which` follows the user's
    full PATH including Program Files entries that subprocess.run skips.
    """
    candidates = [
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return shutil.which("bash")


_BASH = _resolve_bash()


pytestmark = pytest.mark.skipif(
    _BASH is None or not BACKUP_SCRIPT.exists(),
    reason="bin/backup.sh requires bash on PATH (Git Bash on Windows OK)",
)


def _run_backup(db_path: Path, backup_dir: Path) -> subprocess.CompletedProcess:
    """Invoke bin/backup.sh with explicit DB and target-dir arguments."""
    return subprocess.run(
        [_BASH, str(BACKUP_SCRIPT), str(db_path), str(backup_dir)],
        capture_output=True,
        text=True,
    )


def test_backup_creates_valid_sqlite(tmp_path: Path) -> None:
    """Backup script writes a readable SQLite file at backups/YYYY-MM-DD.db."""
    db = tmp_path / "src.db"
    init_db(db)
    bdir = tmp_path / "backups"
    proc = _run_backup(db, bdir)
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    today = date.today().isoformat()
    backup_path = bdir / f"{today}.db"
    assert backup_path.exists(), f"backup file missing: {backup_path}"
    # Verify the backup is a valid SQLite database with our schema
    conn = sqlite3.connect(str(backup_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert "runs" in names, f"runs table missing in backup; saw {names}"
        assert "snapshots" in names, f"snapshots table missing in backup; saw {names}"
    finally:
        conn.close()


def test_backup_4_rotation_retention(tmp_path: Path) -> None:
    """`ls -t | tail -n +5 | xargs rm -f` keeps the 4 most recent .db files."""
    db = tmp_path / "src.db"
    init_db(db)
    bdir = tmp_path / "backups"
    bdir.mkdir()
    # Pre-populate 6 stale .db files with descending mtimes (i=0 newest of stale,
    # i=5 oldest). The new backup written by the script will be NEWER than all 6.
    now = time.time()
    for i in range(6):
        p = bdir / f"2025-01-{i + 10:02d}.db"
        p.write_bytes(b"SQLite format 3\x00")  # minimal valid header
        # Older index = farther in past
        os.utime(p, (now - (i + 1) * 86400, now - (i + 1) * 86400))
    proc = _run_backup(db, bdir)
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    remaining = sorted(bdir.glob("*.db"))
    # 6 stale + 1 new = 7 total; rotation keeps 4 most recent → 3 deleted.
    assert len(remaining) == 4, (
        f"expected 4 remaining, got {len(remaining)}: {[p.name for p in remaining]}"
    )


def test_backup_fails_on_missing_source(tmp_path: Path) -> None:
    """Non-existent source DB → exit code != 0 (documented exit 1)."""
    bdir = tmp_path / "backups"
    proc = _run_backup(tmp_path / "nonexistent.db", bdir)
    assert proc.returncode != 0
    assert "ERROR" in proc.stderr or proc.returncode == 1


def test_backup_creates_dir_if_missing(tmp_path: Path) -> None:
    """Target directory is created via `mkdir -p` if absent before run."""
    db = tmp_path / "src.db"
    init_db(db)
    bdir = tmp_path / "fresh_backups"  # does NOT exist yet
    assert not bdir.exists()
    proc = _run_backup(db, bdir)
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    assert bdir.exists(), "backup script did not create target dir"
    today = date.today().isoformat()
    assert (bdir / f"{today}.db").exists()
