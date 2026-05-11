"""Plan 04-05 — CLI subcommand smoke tests for `matcher-run` (D-412).

End-to-end tests that invoke `python -m ga_crawler matcher-run ...` via
subprocess and assert exit codes + JSON output payload. Uses tmp_path SQLite
DBs planted with `init_db` + `SqliteSnapshotWriter` so the matcher SQL has
real rows to JOIN.

Also exercises the `weekly-run --sanity-gate-p` flag presence (Plan 04-05
amendment to existing subparser).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


# ---- Helpers ----


def _viled(sku_id: str, **overrides) -> dict:
    base = dict(
        sku_id=sku_id,
        url=f"https://viled.kz/{sku_id}",
        name="EDP 50ml",
        brand="Givenchy",
        brand_norm="givenchy",
        name_norm="eau de parfum",
        volume_norm="(50, ml, 1)",
        volume_raw="50 ml",
        multipack_flag=False,
        parse_error_flag=False,
        current_price=10000,
        was_price=None,
        currency="KZT",
        stock_state="IN_STOCK",
    )
    base.update(overrides)
    return base


def _goldapple(sku_id: str, **overrides) -> dict:
    base = _viled(sku_id)
    base["url"] = f"https://goldapple.kz/{sku_id}"
    base["current_price"] = 12000
    base.update(overrides)
    return base


@pytest.fixture
def planted_db(tmp_path):
    """tmp DB with 1 success-finalized run + 1 viled + 1 goldapple matched row."""
    db = tmp_path / "p.db"
    init_db(db)
    eng = make_engine(db)
    rw = SqliteRunWriter(eng)
    rid = rw.create()
    SqliteSnapshotWriter(eng).append(rid, "viled", [_viled("V1")])
    SqliteSnapshotWriter(eng).append(rid, "goldapple", [_goldapple("G1")])
    rw.finalize(rid, status="success")
    return db, rid


def _run_cli(*args, cwd=None):
    """Invoke `python -m ga_crawler ...` via subprocess. Returns CompletedProcess."""
    cmd = [sys.executable, "-m", "ga_crawler", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


# ---- Tests ----


def test_cli_help_lists_matcher_run():
    """Test 1: top-level --help mentions matcher-run subcommand."""
    r = _run_cli("--help")
    assert r.returncode == 0, r.stderr
    assert "matcher-run" in r.stdout


def test_cli_matcher_run_success(planted_db):
    """Test 2: matcher-run against planted snapshots succeeds (exit 0)."""
    db, rid = planted_db
    r = _run_cli(
        "matcher-run",
        "--run-id", str(rid),
        "--db-path", str(db),
        "--sanity-gate-p", "1",
    )
    assert r.returncode == 0, f"stderr={r.stderr}\nstdout={r.stdout}"
    assert '"match_count": 1' in r.stdout
    assert '"status": "success"' in r.stdout


def test_cli_matcher_run_gate_fail_exits_2(planted_db):
    """Test 3: matcher-run with high --sanity-gate-p fails the gate (exit 2)."""
    db, rid = planted_db
    r = _run_cli(
        "matcher-run",
        "--run-id", str(rid),
        "--db-path", str(db),
        "--sanity-gate-p", "99",
    )
    assert r.returncode == 2
    assert '"status": "failed"' in r.stdout
    assert "match_count_below_threshold" in r.stdout


def test_cli_matcher_run_skipped_when_upstream_failed(tmp_path):
    """Test 4: matcher-run on a failed-upstream run skips (exit 2)."""
    db = tmp_path / "p.db"
    init_db(db)
    eng = make_engine(db)
    rw = SqliteRunWriter(eng)
    rid = rw.create()
    rw.fail(rid, "viled crash")
    r = _run_cli(
        "matcher-run",
        "--run-id", str(rid),
        "--db-path", str(db),
        "--sanity-gate-p", "1",
    )
    assert r.returncode == 2
    assert '"status": "skipped"' in r.stdout
    assert "failed_upstream" in r.stdout


def test_cli_matcher_run_requires_run_id():
    """Test 5: argparse rejects missing --run-id (non-zero exit)."""
    r = _run_cli("matcher-run")
    assert r.returncode != 0
    # argparse error goes to stderr; tolerate either stream.
    combined = r.stderr + r.stdout
    assert "--run-id" in combined or "run_id" in combined


def test_cli_weekly_run_help_lists_sanity_gate_p():
    """Test 6: `weekly-run --help` advertises the new --sanity-gate-p flag."""
    r = _run_cli("weekly-run", "--help")
    assert r.returncode == 0, r.stderr
    assert "--sanity-gate-p" in r.stdout
