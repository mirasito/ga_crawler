"""GA Crawler CLI — Phase 2 production cutover (Plan 02-05 / D-212).

Four subcommands (Plan 05-05 adds the fourth):

  python -m ga_crawler goldapple-smoke
      One-off smoke probe against live goldapple. Prints diagnostics. No DB writes.
      KEPT verbatim from Phase 3 (Plan 03-06).

  python -m ga_crawler weekly-run [--db-path ...] [--sanity-gate-n ...] [--sanity-gate-p ...] ...
      Full weekly run (viled + goldapple + matcher + reporter) writing to real SQLite +
      Norm06 ledger + reports/YYYY-WNN.xlsx. Plan 04-05 adds --sanity-gate-p override.

  python -m ga_crawler matcher-run --run-id N [--sanity-gate-p P] [--db-path ...]
      D-412 standalone matcher recovery tool. Re-runs strict-key matcher against
      an EXISTING runs row (idempotent — Plan 04-03 DELETE+INSERT in one TX).
      Use case: matcher bug found, fix code, re-match without 4h crawl re-run.

  python -m ga_crawler report-run --run-id N [--output-dir DIR] [--db-path PATH] [--pyproject PATH]
      D-509 standalone reporter recovery tool. Builds xlsx + text summary against
      an EXISTING successful runs row. Idempotent — re-running overwrites
      reports/YYYY-WNN.xlsx without backup (DB is source-of-truth per DATA-03).
      Use case: reporter bug found, fix code, regenerate xlsx without 4h re-crawl.

D-212 cutover (Plan 02-05):
  - DELETED: 4 Stub classes (StubBrandAlias, StubNormalizer, StubSnapshotWriter,
    StubRunWriter). Phase 3 tests now use mocks from tests/conftest.py.
  - DELETED: `goldapple-run` subcommand + `_cmd_run` handler.
  - ADDED: `weekly-run` subcommand backed by `runners/main_run.py::run_weekly`.
  - KEPT: `goldapple-smoke` subcommand + `_cmd_smoke` handler (unchanged).

Plan 04-05 additions:
  - ADDED: `matcher-run` subcommand + `_cmd_matcher` handler (D-412).
  - AMENDED: `weekly-run` gains `--sanity-gate-p N` flag (mirrors --sanity-gate-m).

Plan 05-05 additions:
  - ADDED: `report-run` subcommand + `_cmd_report` handler (D-509).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import structlog

from ga_crawler.fetchers.goldapple import GoldappleFetcher
from ga_crawler.runner.gates import smoke_probe

log = structlog.get_logger(__name__)


# ---- CLI command handlers ----


async def _cmd_smoke(args) -> int:
    """KEPT verbatim from Phase 3 Plan 03-06. Smoke probe against live goldapple."""
    async with GoldappleFetcher(run_id=args.run_id, headless=args.headless) as fetcher:
        result = await smoke_probe(fetcher)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


def _cmd_weekly(args) -> int:
    """ADDED Plan 02-05. Full weekly run via runners/main_run.run_weekly.

    Plan 04-05: pass through --sanity-gate-p to override matcher P-threshold.
    """
    from ga_crawler.runners.main_run import run_weekly

    repo_root = Path(args.repo_root).resolve()
    result = run_weekly(
        repo_root=repo_root,
        db_path=args.db_path,
        headless=args.headless,
        viled_only=args.viled_only,
        goldapple_only=args.goldapple_only,
        sanity_gate_n=args.sanity_gate_n,
        sanity_gate_m=args.sanity_gate_m,
        sanity_gate_p=args.sanity_gate_p,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": result.run_id,
                "viled_count": result.viled_count,
                "goldapple_count": result.goldapple_count,
                "match_count": result.match_count,
                "match_rate": result.match_rate,
                "reason": result.reason,
                "norm06_path": str(result.norm06_path) if result.norm06_path else None,
                "stats_delta_keys": sorted(result.stats_delta.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "success" else 2


def _cmd_matcher(args) -> int:
    """ADDED Plan 04-05 (D-412): standalone matcher re-run for recovery.

    Idempotent — calling against the same run_id twice produces the same
    matches rows (Plan 04-03 DELETE+INSERT in single TX). No re-crawl;
    matcher reads existing snapshots and computes match.* stats + matches table.

    Exit codes:
      0  -> matcher status='success'
      2  -> matcher status='failed' (P-gate trip) OR status='skipped'
            (upstream not in 'success'/'partial' state — D-411)
    """
    from ga_crawler.matcher.config import MatchConfig
    from ga_crawler.runners.matcher_run import run_matcher_phase
    from ga_crawler.storage.sqlite import (
        SqliteRunWriter,
        init_db,
        make_engine,
    )

    init_db(args.db_path)
    engine = make_engine(args.db_path)
    run_writer = SqliteRunWriter(engine)
    cfg = MatchConfig.from_pyproject(args.pyproject)
    effective_p = (
        args.sanity_gate_p if args.sanity_gate_p is not None else cfg.sanity_gate_p
    )

    result = run_matcher_phase(
        run_id=args.run_id,
        engine=engine,
        run_writer=run_writer,
        threshold_p=effective_p,
        p_auto_suggest_factor=cfg.p_auto_suggest_factor,
        p_auto_suggest_after_runs=cfg.p_auto_suggest_after_runs,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": args.run_id,
                "match_count": result.match_count,
                "match_rate": result.match_rate,
                "reason": result.reason,
                "threshold_p": effective_p,
                "stats_delta_keys": sorted(result.stats_delta.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "success" else 2


def _cmd_report(args) -> int:
    """ADDED Plan 05-05 (D-509): standalone reporter re-run for recovery.

    Idempotent — calling against the same run_id twice produces the same
    xlsx (modulo zip timestamps) at the same path. No re-crawl; reporter
    reads existing matches/snapshots and rebuilds the xlsx + patches
    runs.stats.report.* in a single atomic call.

    Exit codes:
      0  -> reporter status='success'
      2  -> reporter status='skipped' (upstream not success, or run missing)
    """
    import dataclasses

    from ga_crawler.reporter.config import ReportConfig
    from ga_crawler.runners.reporter_run import run_reporter_phase
    from ga_crawler.storage.sqlite import (
        SqliteRunWriter,
        init_db,
        make_engine,
    )

    init_db(args.db_path)
    engine = make_engine(args.db_path)
    run_writer = SqliteRunWriter(engine)
    repo_root = Path(args.repo_root).resolve()

    cfg = ReportConfig.from_pyproject(args.pyproject)
    if args.output_dir is not None:
        # Frozen-safe override via dataclasses.replace (mirror Plan 02-05
        # _config_with_overrides pattern for ViledConfig).
        cfg = dataclasses.replace(cfg, output_dir=args.output_dir)

    result = run_reporter_phase(
        run_id=args.run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=cfg,
    )
    payload = json.dumps(
        {
            "status": result.status,
            "run_id": args.run_id,
            "xlsx_path": result.xlsx_path,
            "xlsx_size_bytes": result.xlsx_size_bytes,
            "summary_text": result.summary_text,
            "size_guard_passed": result.size_guard_passed,
            "reason": result.reason,
            "stats_delta_keys": sorted(result.stats_delta.keys()),
        },
        ensure_ascii=False,
        indent=2,
    )
    # Plan 05-05 Rule 1 deviation: summary_text contains Cyrillic + emoji
    # (📊 from D-504 template). On Windows the default stdout encoding is
    # cp1252 which cannot encode \U0001f4ca → UnicodeEncodeError. Write the
    # UTF-8 bytes directly to sys.stdout.buffer to bypass the locale codec.
    # `print()` works fine on Linux/macOS where stdout is UTF-8 by default;
    # writing bytes is portable.
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
    return 0 if result.status == "success" else 2


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def _parse_bool(v: str) -> bool:
    return str(v).strip().lower() not in ("false", "0", "no", "off")


def main(argv: Optional[list[str]] = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(
        prog="python -m ga_crawler",
        description="GA Crawler - Phase 2 (production weekly run)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # KEPT — goldapple-smoke (Phase 3 Plan 03-06).
    smoke = sub.add_parser(
        "goldapple-smoke",
        help="Run smoke probe (D-312) against live goldapple",
    )
    smoke.add_argument("--run-id", type=int, default=999)
    smoke.add_argument("--headless", type=_parse_bool, default=True)

    # ADDED — weekly-run (Plan 02-05 D-212).
    weekly = sub.add_parser(
        "weekly-run",
        help="Full weekly run (viled + goldapple -> SQLite + Norm06 ledger)",
    )
    weekly.add_argument(
        "--repo-root",
        default=".",
        help="Project root for Norm06 ledger and week-over-week artifacts",
    )
    weekly.add_argument(
        "--db-path",
        default="prices.db",
        help="SQLite database file path (auto-created)",
    )
    weekly.add_argument(
        "--sanity-gate-n",
        type=int,
        default=None,
        help="Override viled sanity-N threshold (default: pyproject.toml value)",
    )
    weekly.add_argument(
        "--sanity-gate-m",
        type=int,
        default=None,
        help="Override goldapple sanity-M threshold (default: pyproject.toml value)",
    )
    weekly.add_argument(
        "--sanity-gate-p",
        type=int,
        default=None,
        help="Plan 04-05: Override matcher sanity-P threshold "
             "(default: pyproject.toml [tool.ga_crawler.match].sanity_gate_p)",
    )
    weekly.add_argument(
        "--headless",
        type=_parse_bool,
        default=True,
        help="Camoufox headless flag for goldapple phase",
    )
    weekly.add_argument(
        "--viled-only",
        action="store_true",
        help="Run only the viled phase (skip goldapple)",
    )
    weekly.add_argument(
        "--goldapple-only",
        action="store_true",
        help="Run only the goldapple phase (skip viled)",
    )

    # ADDED Plan 04-05 (D-412) — matcher-run standalone recovery tool.
    matcher = sub.add_parser(
        "matcher-run",
        help="Run strict-key matcher on existing snapshots for a given run_id "
             "(idempotent, D-412)",
    )
    matcher.add_argument(
        "--run-id",
        type=int,
        required=True,
        help="runs.run_id of an existing run to (re-)match",
    )
    matcher.add_argument(
        "--db-path",
        default="prices.db",
        help="SQLite database file path",
    )
    matcher.add_argument(
        "--sanity-gate-p",
        type=int,
        default=None,
        help="Override match-count sanity threshold P "
             "(default: pyproject.toml [tool.ga_crawler.match].sanity_gate_p = 20)",
    )
    matcher.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml for [tool.ga_crawler.match] config",
    )

    # ADDED Plan 05-05 (D-509) — report-run standalone recovery tool.
    report = sub.add_parser(
        "report-run",
        help="Build xlsx report + text summary against an existing successful "
             "run_id (idempotent, D-509)",
    )
    report.add_argument(
        "--run-id",
        type=int,
        required=True,
        help="runs.run_id of an existing successful run to (re-)build report for",
    )
    report.add_argument(
        "--output-dir",
        default=None,
        help="Override [tool.ga_crawler.report].output_dir (default: 'reports' per pyproject)",
    )
    report.add_argument(
        "--db-path",
        default="prices.db",
        help="SQLite database file path",
    )
    report.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml for [tool.ga_crawler.report] config",
    )
    report.add_argument(
        "--repo-root",
        default=".",
        help="Repo root for resolving output_dir + path containment check",
    )

    args = parser.parse_args(argv)
    if args.cmd == "goldapple-smoke":
        return asyncio.run(_cmd_smoke(args))
    if args.cmd == "weekly-run":
        return _cmd_weekly(args)
    if args.cmd == "matcher-run":
        return _cmd_matcher(args)
    if args.cmd == "report-run":
        return _cmd_report(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
