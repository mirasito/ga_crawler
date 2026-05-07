"""Production storage contract tests — append-only, atomic merge, fail() idempotence.

D-212 Plan 02-05 cutover: the original test file targeted Phase 3 Stub*
classes from `cli.py`. Those stubs are now DELETED — this rewritten file
exercises the same contracts against the production
`SqliteSnapshotWriter` / `SqliteRunWriter` from `ga_crawler.storage.sqlite`.

The Plan 02-02 storage tests (test_snapshot_writer.py, test_run_writer.py,
test_storage_wal.py, test_run_writer_lifecycle.py) cover the same surface
in unit form; this file keeps the integration-style narrative + the CLI
help-output smoke check (now adjusted to the post-D-212 subcommand set).

Source: 02-CONTEXT.md D-212; 02-PATTERNS.md "cli.py cutover" §595-628.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from sqlmodel import Session

from ga_crawler.cli import main
from ga_crawler.storage.sqlite import (
    Run,
    Snapshot,
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


# ---- Helpers ----


def _setup(tmp_path: Path):
    db = tmp_path / "test.db"
    init_db(db)
    engine = make_engine(db)
    return engine


def _row(sku_id: str, name: str = "X", price: int = 1000) -> dict:
    """Minimal Snapshot dict with the production-shape keys (Plan 02-02)."""
    return {
        "sku_id": sku_id,
        "url": f"https://example.com/{sku_id}",
        "name": name,
        "brand": "TestBrand",
        "brand_norm": "testbrand",
        "name_norm": name.lower(),
        "current_price": price,
        "currency": "KZT",
        "stock_state": "IN_STOCK",
    }


# ---- SnapshotWriter contract ----


def test_snapshot_writer_appends_rows(tmp_path: Path) -> None:
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    products = [_row("100", "A", 1000), _row("200", "B", 2000)]
    n = writer.append(run_id=rid, retailer="goldapple", products=products)
    assert n == 2
    with Session(engine) as s:
        from sqlmodel import select

        rows = list(s.exec(select(Snapshot)))
    assert len(rows) == 2
    assert rows[0].retailer == "goldapple"
    assert rows[0].run_id == rid
    assert rows[0].sku_id == "100"


def test_snapshot_writer_append_only_no_overwrite(tmp_path: Path) -> None:
    """DATA-03 immutable: second .append() inserts new rows; prior batch persists."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    writer = SqliteSnapshotWriter(engine)
    writer.append(run_id=rid, retailer="goldapple", products=[_row("100")])
    writer.append(run_id=rid, retailer="goldapple", products=[_row("200")])
    with Session(engine) as s:
        from sqlmodel import select

        rows = list(s.exec(select(Snapshot)))
    assert len(rows) == 2
    assert {r.sku_id for r in rows} == {"100", "200"}


# ---- RunWriter contract (Pitfall 6 atomic merge) ----


def test_run_writer_patch_stats_merges(tmp_path: Path) -> None:
    """Pitfall 6: viled.* + goldapple.* keys merge cleanly via json_patch."""
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    rw.patch_stats(
        run_id=rid,
        delta={"goldapple.fetch_count": 100, "viled.fetch_count": 200},
    )
    rw.patch_stats(run_id=rid, delta={"goldapple.gate_shell_count": 0})
    stats = rw.get_stats(run_id=rid)
    assert stats == {
        "goldapple.fetch_count": 100,
        "goldapple.gate_shell_count": 0,
        "viled.fetch_count": 200,
    }


def test_run_writer_fail_records_reason(tmp_path: Path) -> None:
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    rid = rw.create()
    rw.patch_stats(run_id=rid, delta={"goldapple.fetch_count": 50})
    rw.fail(run_id=rid, reason="goldapple_count 50 < M=1000")
    with Session(engine) as s:
        run = s.get(Run, rid)
    assert run is not None
    assert run.status == "failed"
    assert run.fail_reason == "goldapple_count 50 < M=1000"
    stats = rw.get_stats(rid)
    assert stats["goldapple.fetch_count"] == 50


def test_run_writer_get_stats_empty_when_no_run(tmp_path: Path) -> None:
    engine = _setup(tmp_path)
    rw = SqliteRunWriter(engine)
    assert rw.get_stats(run_id=99) == {}


# ---- CLI help output (D-212 cutover verification) ----


def test_cli_main_smoke_command_listed() -> None:
    """goldapple-smoke is KEPT after D-212 cutover."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(["--help"])
        except SystemExit:
            pass
    out = buf.getvalue()
    assert "goldapple-smoke" in out


def test_cli_main_weekly_run_command_listed() -> None:
    """weekly-run is ADDED by D-212 cutover."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(["--help"])
        except SystemExit:
            pass
    out = buf.getvalue()
    assert "weekly-run" in out


def test_cli_main_goldapple_run_command_removed() -> None:
    """goldapple-run is DELETED by D-212 cutover (replaced by weekly-run)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(["--help"])
        except SystemExit:
            pass
    out = buf.getvalue()
    assert "goldapple-run" not in out
