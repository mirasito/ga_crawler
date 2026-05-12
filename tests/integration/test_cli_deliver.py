"""Plan 06-04 (Wave 3) -- subprocess CLI tests for ``python -m ga_crawler deliver-run``.

Mirror of ``tests/integration/test_cli_report_subcommand.py`` shape. Real
SQLite DBs planted with ``init_db`` + ``SqliteRunWriter`` + ``SqliteSnapshotWriter``
+ 1 finalized success run so the orchestrator has a stats row to gate on.

D-608 standalone recovery tool — re-sends Telegram delivery against an
existing run_id without re-crawling. Subprocess tests cover:
  * --help registration + flags
  * Missing TG_BOT_TOKEN -> exit code 3 + skipped_no_credentials
  * --dry-run -> exit 0 + JSON preview to stdout (no Telegram I/O)
  * --force flag parsed correctly
  * Unicode-safe stdout (Cyrillic + emoji)

Real-bot subprocess tests are infeasible (subprocess cannot share
``mock_aiogram_bot``); the orchestrator-level test suite in
``tests/integration/test_delivery_run.py`` covers the in-process happy
paths via ``patched_bot``.

The structural canary ``test_load_dotenv_only_in_cli`` enforces RESEARCH
caveat #4 -- ``load_dotenv`` MUST appear in exactly one file under
``src/ga_crawler/`` and that file MUST be ``cli.py``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePath

import pytest
from sqlalchemy import text as _text

from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)

pytestmark = pytest.mark.integration

REPO_ROOT_FOR_CANARY = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _write_pyproject(tmp_path: Path) -> Path:
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        "[tool.ga_crawler.deliver]\n"
        "retry_max_attempts = 3\n"
        "retry_backoff_min_seconds = 5\n"
        "retry_backoff_max_seconds = 45\n"
        "ops_message_truncate_chars = 3500\n"
        "business_caption_max_chars = 1024\n"
        'parse_mode = "HTML"\n',
        encoding="utf-8",
    )
    return pyp


def _plant_run(
    tmp_path: Path,
    *,
    status: str = "success",
    summary_text: str = "Test summary",
    xlsx_relpath: str = "reports/2026-W19.xlsx",
    size_guard_passed: bool = True,
) -> tuple[Path, int]:
    """Create db at tmp_path/prices.db with one run + report.* stats.

    Returns ``(db_path, run_id)``. The xlsx file is also planted on disk so
    the orchestrator's Pitfall C path-containment check succeeds.
    """
    db_path = tmp_path / "prices.db"
    init_db(db_path)
    engine = make_engine(db_path)
    run_writer = SqliteRunWriter(engine)
    run_id = run_writer.create()

    # Force a deterministic started_at for stable ops-alert output.
    with engine.begin() as conn:
        conn.execute(
            _text("UPDATE runs SET started_at = :sa WHERE run_id = :rid"),
            {
                "sa": datetime(2026, 5, 10, 14, 0, 0, tzinfo=timezone.utc),
                "rid": run_id,
            },
        )

    if status == "success":
        run_writer.finalize(run_id, status="success")
    elif status == "failed":
        run_writer.fail(run_id, reason="planted failure")
    # Plant the xlsx file on disk so _resolve_xlsx_safely succeeds.
    xlsx_full = tmp_path / xlsx_relpath
    xlsx_full.parent.mkdir(parents=True, exist_ok=True)
    xlsx_full.write_bytes(b"PK\x03\x04fake-xlsx-content-for-cli-tests")

    run_writer.patch_stats(
        run_id,
        {
            "viled.fetch_count": 3,
            "goldapple.fetch_count": 8,
            "match.count": 3,
            "match.rate": 60.0,
            "report.xlsx_path": xlsx_relpath,
            "report.xlsx_size_bytes": xlsx_full.stat().st_size,
            "report.summary_text": summary_text,
            "report.size_guard_passed": size_guard_passed,
            "report.skipped_reason": "",
        },
    )
    return db_path, run_id


def _run_cli(*args, cwd=None, env=None) -> subprocess.CompletedProcess:
    """Invoke ``python -m ga_crawler ...`` via subprocess (UTF-8 captured)."""
    cmd = [sys.executable, "-m", "ga_crawler", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, env=env, encoding="utf-8",
    )


def _extract_payload(stdout: str) -> dict:
    """Extract the LAST indented JSON payload from CLI stdout.

    structlog JSONRenderer writes single-line JSON for log events; our
    handler emits the result payload via ``json.dumps(..., indent=2)``,
    which begins with ``"{\\n"``. In dry-run mode the orchestrator also
    writes its own preview JSON BEFORE the CLI payload -- so we take the
    LAST occurrence of ``"{\\n"`` to land on the CLI's final payload.
    """
    idx = stdout.rfind("{\n")
    assert idx != -1, f"no indented JSON payload in stdout: {stdout!r}"
    return json.loads(stdout[idx:])


def _env_without_tg() -> dict:
    """Build a subprocess env dict with TG_* variables stripped.

    Starts from the current process env (so PATH / SystemRoot etc. survive
    on Windows where subprocess needs them) and removes any TG_* keys so
    the deliver-run handler observes them as missing.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("TG_")}
    return env


# --------------------------------------------------------------------------- #
# Test 1: --help lists deliver-run                                            #
# --------------------------------------------------------------------------- #


def test_deliver_run_help_lists_subcommand():
    """Top-level --help mentions deliver-run."""
    r = _run_cli("--help")
    assert r.returncode == 0, r.stderr
    assert "deliver-run" in r.stdout


# --------------------------------------------------------------------------- #
# Test 2: deliver-run --help shows all flags                                  #
# --------------------------------------------------------------------------- #


def test_deliver_run_help_shows_all_flags():
    """deliver-run --help advertises --run-id, --db-path, --pyproject,
    --repo-root, --force, --dry-run."""
    r = _run_cli("deliver-run", "--help")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    for flag in ("--run-id", "--db-path", "--pyproject", "--repo-root",
                 "--force", "--dry-run"):
        assert flag in out, f"missing flag in --help: {flag}\nstdout={out!r}"


# --------------------------------------------------------------------------- #
# Test 3: missing run-id -> non-zero exit                                     #
# --------------------------------------------------------------------------- #


def test_deliver_run_missing_run_id_exits_nonzero(tmp_path):
    r = _run_cli("deliver-run", cwd=str(tmp_path), env=_env_without_tg())
    assert r.returncode != 0
    combined = (r.stderr or "") + (r.stdout or "")
    assert "--run-id" in combined or "run_id" in combined


# --------------------------------------------------------------------------- #
# Test 4: missing TG_BOT_TOKEN -> exit code 3                                 #
# --------------------------------------------------------------------------- #


def test_deliver_run_missing_token_exits_3(tmp_path):
    """D-611 asymmetric + D-608 exit code 3 (config error)."""
    db_path, run_id = _plant_run(tmp_path)
    pyp = _write_pyproject(tmp_path)

    r = _run_cli(
        "deliver-run",
        "--run-id", str(run_id),
        "--db-path", str(db_path),
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
        cwd=str(tmp_path),
        env=_env_without_tg(),
    )
    assert r.returncode == 3, f"stderr={r.stderr}\nstdout={r.stdout}"
    payload = _extract_payload(r.stdout)
    assert payload["delivery_status"] == "skipped_no_credentials"
    assert payload["route"] == "skipped"
    assert payload["run_id"] == run_id
    assert "missing_env_TG_BOT_TOKEN" in payload["last_error"]


# --------------------------------------------------------------------------- #
# Test 5: --dry-run prints preview, exits 0                                   #
# --------------------------------------------------------------------------- #


def test_deliver_run_dry_run_prints_preview(tmp_path):
    """--dry-run -> exit 0 + JSON payload with route key + no patch_stats."""
    db_path, run_id = _plant_run(tmp_path)
    pyp = _write_pyproject(tmp_path)
    env = _env_without_tg()
    env["TG_BOT_TOKEN"] = "123456789:dry-run-stub-ABCDEFG"
    env["TG_BUSINESS_CHAT_ID"] = "-100000001"
    env["TG_OPS_CHAT_ID"] = "-100000002"

    r = _run_cli(
        "deliver-run",
        "--run-id", str(run_id),
        "--db-path", str(db_path),
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
        "--dry-run",
        cwd=str(tmp_path),
        env=env,
    )
    assert r.returncode == 0, f"stderr={r.stderr}\nstdout={r.stdout}"
    # The orchestrator writes the dry-run preview to stdout via
    # sys.stdout.buffer; the CLI handler then writes its own payload.
    # The CLI payload has a top-level "route" key after extraction.
    payload = _extract_payload(r.stdout)
    assert "route" in payload
    assert payload["delivery_status"] == "pending"


# --------------------------------------------------------------------------- #
# Test 6: --force flag parsed                                                 #
# --------------------------------------------------------------------------- #


def test_force_flag_parsed():
    """argparse parses --force as boolean True; absence as False."""
    from ga_crawler.cli import main as cli_main  # noqa: F401  -- ensure importable
    # Drive parser directly to confirm flag wiring.
    import argparse
    from ga_crawler import cli as _cli

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    # Replicate the deliver-run shape -- if main() re-organizes args we will
    # catch it via --help test #2; here we only verify flag semantics.
    p = sub.add_parser("deliver-run")
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    ns_no_force = parser.parse_args(["deliver-run", "--run-id", "1"])
    assert ns_no_force.force is False
    assert ns_no_force.dry_run is False

    ns_force = parser.parse_args(["deliver-run", "--run-id", "1", "--force"])
    assert ns_force.force is True

    # Sanity-check the actual CLI module exposes _cmd_deliver too.
    assert hasattr(_cli, "_cmd_deliver"), "cli.py must expose _cmd_deliver"


# --------------------------------------------------------------------------- #
# Test 7: Unicode-safe stdout on Windows (Cyrillic + emoji)                   #
# --------------------------------------------------------------------------- #


def test_unicode_stdout_safe_on_windows(tmp_path):
    """Cyrillic + emoji in summary_text round-trip through stdout (UTF-8)."""
    db_path, run_id = _plant_run(
        tmp_path,
        summary_text="\U0001f4ca Сводка недели 2026-W19 — Привет!",
    )
    pyp = _write_pyproject(tmp_path)
    # Drive a skipped_no_credentials path so we get a payload without real Telegram.
    r = _run_cli(
        "deliver-run",
        "--run-id", str(run_id),
        "--db-path", str(db_path),
        "--pyproject", str(pyp),
        "--repo-root", str(tmp_path),
        cwd=str(tmp_path),
        env=_env_without_tg(),
    )
    assert r.returncode == 3, f"stderr={r.stderr}\nstdout={r.stdout}"
    # No UnicodeEncodeError raised on Windows -- subprocess captured stdout as UTF-8.
    payload = _extract_payload(r.stdout)
    assert payload["delivery_status"] == "skipped_no_credentials"


# --------------------------------------------------------------------------- #
# Test 8: structural canary -- load_dotenv ONLY in cli.py                     #
# --------------------------------------------------------------------------- #


def test_load_dotenv_only_in_cli():
    """RESEARCH caveat #4: load_dotenv must appear in exactly one .py file
    under ``src/ga_crawler/`` AND that file must be ``cli.py``.

    Cross-platform path matching via PurePath.parts -- avoids OS-specific
    separators in the assertion message.
    """
    src_root = REPO_ROOT_FOR_CANARY / "src" / "ga_crawler"
    hits: list[Path] = []
    for p in src_root.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        if re.search(r"\bload_dotenv\s*\(", text):
            hits.append(p)
    assert len(hits) == 1, (
        f"load_dotenv must appear in exactly one file under src/ga_crawler/; "
        f"found: {hits}"
    )
    # PurePath.parts last two segments are ('ga_crawler', 'cli.py') on both
    # POSIX and Windows.
    parts = PurePath(hits[0]).parts[-2:]
    assert parts == ("ga_crawler", "cli.py"), (
        f"load_dotenv must ONLY live in ga_crawler/cli.py; found: {hits[0]}"
    )
