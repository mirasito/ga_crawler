"""Plan 05-05 — CLI subcommand smoke tests for `report-run` (D-509).

End-to-end tests that invoke `python -m ga_crawler report-run ...` via
subprocess and assert exit codes + JSON output payload. Uses tmp_path SQLite
DBs planted with `init_db` + `SqliteSnapshotWriter` + 1 finalized success run
so reporter has matches/snapshots to read.

Mirror of tests/integration/test_cli_matcher_subcommand.py shape.

D-509 standalone recovery tool — re-runs reporter against an existing
successful run_id without re-crawling (idempotent: overwrites
reports/YYYY-WNN.xlsx).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text as _text

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
        name="Givenchy EDP 50ml",
        brand="Givenchy",
        brand_norm="givenchy",
        name_norm="eau de parfum",
        volume_norm="(50, ml, 1)",
        volume_raw="50 ml",
        multipack_flag=False,
        parse_error_flag=False,
        current_price=50000,
        was_price=None,
        currency="KZT",
        stock_state="IN_STOCK",
    )
    base.update(overrides)
    return base


def _goldapple(sku_id: str, **overrides) -> dict:
    base = _viled(sku_id)
    base["url"] = f"https://goldapple.kz/{sku_id}"
    base["current_price"] = 55000
    base.update(overrides)
    return base


def _write_pyproject(tmp_path: Path) -> Path:
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        "[tool.ga_crawler.report]\n"
        'output_dir = "reports"\n'
        "size_limit_mb = 45\n"
        "top_n_deltas = 3\n"
        'timezone = "Asia/Almaty"\n',
        encoding="utf-8",
    )
    return pyp


@pytest.fixture
def planted_db(tmp_path):
    """tmp DB with 1 success-finalized run + 1 viled + 1 goldapple matched row
    + 1 match + pre-populated upstream stats so reporter D-507 passes."""
    db = tmp_path / "p.db"
    init_db(db)
    eng = make_engine(db)
    rw = SqliteRunWriter(eng)
    rid = rw.create()

    # Force started_at to a deterministic value → ISO 2026-W19 in Asia/Almaty
    with eng.begin() as conn:
        conn.execute(
            _text("UPDATE runs SET started_at = :sa WHERE run_id = :rid"),
            {"sa": datetime(2026, 5, 10, 14, 0, 0, tzinfo=timezone.utc), "rid": rid},
        )

    SqliteSnapshotWriter(eng).append(rid, "viled", [_viled("V1")])
    SqliteSnapshotWriter(eng).append(rid, "goldapple", [_goldapple("G1")])

    # Plant one match row (denormalized 13-col)
    with eng.begin() as conn:
        conn.execute(
            _text(
                "INSERT INTO matches (run_id, viled_sku, goldapple_sku, brand_norm, "
                "name_norm, volume_norm, viled_price, goldapple_price, viled_was_price, "
                "goldapple_was_price, price_delta, price_delta_pct, matched_at) "
                "VALUES (:rid, 'V1', 'G1', 'givenchy', 'eau de parfum', "
                "'(50, ml, 1)', 50000, 55000, NULL, NULL, 5000, 10.0, "
                "'2026-05-10T14:20:00Z')"
            ),
            {"rid": rid},
        )

    # Pre-populate upstream namespaces (Pitfall 6 flat dotted keys)
    rw.patch_stats(rid, {
        "viled.fetch_count": 1,
        "goldapple.fetch_count": 1,
        "match.count": 1,
        "match.rate": 100.0,
        "match.denominator": 1,
    })
    rw.finalize(rid, status="success")
    return db, rid


def _run_cli(*args, cwd=None):
    """Invoke `python -m ga_crawler ...` via subprocess. Returns CompletedProcess."""
    cmd = [sys.executable, "-m", "ga_crawler", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, encoding="utf-8"
    )


def _extract_payload(stdout: str) -> dict:
    """Extract the indented JSON payload from stdout.

    structlog JSONRenderer emits single-line JSON to stdout for log events
    (without indent), then our CLI handler emits the result payload via
    `json.dumps(..., indent=2)`. The payload always starts with a `{\\n` (open
    brace followed by newline) — single-line log events use `{"...}\\n` with
    content on the same line. Split on `{\n` to find the payload start.
    """
    # The payload starts with literal "{\n" — log events are single-line.
    idx = stdout.find("{\n")
    assert idx != -1, f"no indented JSON payload found in stdout: {stdout!r}"
    return json.loads(stdout[idx:])


# ---- Tests ----


def test_cli_help_lists_report_run():
    """Plan 05-05 Test 1: top-level --help mentions report-run subcommand."""
    r = _run_cli("--help")
    assert r.returncode == 0, r.stderr
    assert "report-run" in r.stdout


def test_report_run_help_lists_required_flags(tmp_path):
    """Plan 05-05 Test 2: report-run --help advertises required + optional flags."""
    r = _run_cli("report-run", "--help")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "--run-id" in out
    assert "--output-dir" in out
    assert "--db-path" in out
    assert "--pyproject" in out


def test_report_run_missing_run_id_exits_2(tmp_path):
    """Plan 05-05 Test 3: argparse rejects missing --run-id (non-zero exit)."""
    r = _run_cli("report-run", cwd=str(tmp_path))
    assert r.returncode != 0
    combined = (r.stderr or "") + (r.stdout or "")
    assert "--run-id" in combined or "run_id" in combined


def test_report_run_non_int_run_id_rejected(tmp_path):
    """Plan 05-05 Test 4 (T-05-sql-injection canary): argparse type=int rejects
    non-integer values at the CLI boundary before any SQL is touched."""
    r = _run_cli("report-run", "--run-id", "abc", cwd=str(tmp_path))
    assert r.returncode != 0
    combined = (r.stderr or "") + (r.stdout or "")
    assert "invalid" in combined.lower() or "int" in combined.lower()


def test_report_run_nonexistent_run_exits_2(tmp_path):
    """Plan 05-05 Test 5: non-existent run_id → reporter skips with
    reason='missing_run_row'; exit code 2 (skipped is failed-equivalent for ops monitoring)."""
    db_path = tmp_path / "empty.db"
    init_db(db_path)
    pyp = _write_pyproject(tmp_path)

    r = _run_cli(
        "report-run",
        "--run-id", "99999",
        "--db-path", str(db_path),
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
        cwd=str(tmp_path),
    )
    assert r.returncode == 2, f"stderr={r.stderr}\nstdout={r.stdout}"
    payload = _extract_payload(r.stdout)
    assert payload["status"] == "skipped"
    assert payload["reason"] == "missing_run_row"


def test_report_run_success_writes_xlsx_and_exits_0(planted_db, tmp_path):
    """Plan 05-05 Test 6: success path → exit 0; JSON payload has xlsx_path +
    xlsx_size_bytes + summary_text + size_guard_passed; xlsx exists on disk."""
    db, rid = planted_db
    pyp = _write_pyproject(tmp_path)

    r = _run_cli(
        "report-run",
        "--run-id", str(rid),
        "--db-path", str(db),
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
        cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"stderr={r.stderr}\nstdout={r.stdout}"
    payload = _extract_payload(r.stdout)
    assert payload["status"] == "success"
    assert payload["run_id"] == rid
    assert payload["xlsx_path"].endswith(".xlsx")
    assert payload["xlsx_size_bytes"] > 0
    assert payload["size_guard_passed"] is True
    assert isinstance(payload["summary_text"], str)
    assert payload["summary_text"] != ""
    assert payload["reason"] is None
    # All 7 D-514 keys + 'threshold_p' surrogate would not be here; just stats_delta_keys.
    assert "stats_delta_keys" in payload
    assert isinstance(payload["stats_delta_keys"], list)
    assert any(k.startswith("report.") for k in payload["stats_delta_keys"]), (
        f"report.* keys missing from stats_delta_keys: {payload['stats_delta_keys']}"
    )

    # File exists on disk under tmp_path
    xlsx_abs = tmp_path / payload["xlsx_path"]
    assert xlsx_abs.exists(), f"xlsx missing at {xlsx_abs}"
    assert xlsx_abs.stat().st_size == payload["xlsx_size_bytes"]


def test_report_run_output_dir_override(planted_db, tmp_path):
    """Plan 05-05 Test 7: --output-dir custom_reports overrides ReportConfig.output_dir
    via dataclasses.replace (frozen-safe)."""
    db, rid = planted_db
    pyp = _write_pyproject(tmp_path)

    r = _run_cli(
        "report-run",
        "--run-id", str(rid),
        "--db-path", str(db),
        "--output-dir", "custom_reports",
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
        cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"stderr={r.stderr}\nstdout={r.stdout}"
    payload = _extract_payload(r.stdout)
    assert payload["xlsx_path"].startswith("custom_reports/"), payload["xlsx_path"]
    assert (tmp_path / payload["xlsx_path"]).exists()


def test_report_run_idempotent_re_invocation(planted_db, tmp_path):
    """Plan 05-05 Test 8 (D-510 idempotency): two consecutive subprocess invocations
    both exit 0; xlsx path identical; xlsx overwritten without backup."""
    db, rid = planted_db
    pyp = _write_pyproject(tmp_path)
    args = (
        "report-run",
        "--run-id", str(rid),
        "--db-path", str(db),
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
    )
    r1 = _run_cli(*args, cwd=str(tmp_path))
    assert r1.returncode == 0, f"first run: stderr={r1.stderr}\nstdout={r1.stdout}"
    r2 = _run_cli(*args, cwd=str(tmp_path))
    assert r2.returncode == 0, f"second run: stderr={r2.stderr}\nstdout={r2.stdout}"

    p1 = _extract_payload(r1.stdout)
    p2 = _extract_payload(r2.stdout)
    assert p1["xlsx_path"] == p2["xlsx_path"]
    assert p1["status"] == p2["status"] == "success"
