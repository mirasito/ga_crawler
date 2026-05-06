"""Stub storage contract tests — append-only, JSON state, fail() idempotence.

Verifies the StubSnapshotWriter and StubRunWriter (cli.py) satisfy the
SnapshotWriterProtocol and RunWriterProtocol contracts and behave
correctly under append-only / atomic-merge / fail-record semantics.

Source plan: 03-06-PLAN.md Task 2 (test_storage_integration.py).
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from ga_crawler.cli import StubRunWriter, StubSnapshotWriter, main


def test_snapshot_writer_appends_jsonl(tmp_path: Path) -> None:
    writer = StubSnapshotWriter(tmp_path)
    products = [
        {"sku_id": "100", "name": "A", "current_price": 1000, "currency": "KZT"},
        {"sku_id": "200", "name": "B", "current_price": 2000, "currency": "KZT"},
    ]
    n = writer.append(run_id=1, retailer="goldapple", products=products)
    assert n == 2
    out = tmp_path / "runs" / "1" / "snapshots.jsonl"
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert rows[0]["sku_id"] == "100"
    assert rows[0]["retailer"] == "goldapple"
    assert rows[0]["run_id"] == 1


def test_snapshot_writer_append_only_no_overwrite(tmp_path: Path) -> None:
    """DATA-03 immutable: second .append() appends, does NOT overwrite."""
    writer = StubSnapshotWriter(tmp_path)
    writer.append(run_id=1, retailer="goldapple", products=[{"sku_id": "100"}])
    writer.append(run_id=1, retailer="goldapple", products=[{"sku_id": "200"}])
    out = tmp_path / "runs" / "1" / "snapshots.jsonl"
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_run_writer_patch_stats_merges(tmp_path: Path) -> None:
    rw = StubRunWriter(tmp_path)
    rw.patch_stats(run_id=1, delta={"goldapple.fetch_count": 100, "viled.fetch_count": 200})
    rw.patch_stats(run_id=1, delta={"goldapple.gate_shell_count": 0})
    stats = rw.get_stats(run_id=1)
    assert stats == {
        "goldapple.fetch_count": 100,
        "goldapple.gate_shell_count": 0,
        "viled.fetch_count": 200,
    }


def test_run_writer_fail_records_reason(tmp_path: Path) -> None:
    rw = StubRunWriter(tmp_path)
    rw.patch_stats(run_id=1, delta={"goldapple.fetch_count": 50})
    rw.fail(run_id=1, reason="goldapple_count 50 < M=1000")
    p = tmp_path / "runs" / "1" / "runs.json"
    state = json.loads(p.read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["fail_reason"] == "goldapple_count 50 < M=1000"
    assert state["stats"]["goldapple.fetch_count"] == 50


def test_run_writer_get_stats_empty_when_no_run(tmp_path: Path) -> None:
    rw = StubRunWriter(tmp_path)
    assert rw.get_stats(run_id=99) == {}


def test_cli_main_smoke_command_exists() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(["--help"])
        except SystemExit:
            pass
    out = buf.getvalue()
    assert "goldapple-smoke" in out
    assert "goldapple-run" in out
