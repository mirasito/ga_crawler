"""GA Crawler CLI — Phase 2 production cutover (Plan 02-05 / D-212).

Two subcommands:

  python -m ga_crawler goldapple-smoke
      One-off smoke probe against live goldapple. Prints diagnostics. No DB writes.
      KEPT verbatim from Phase 3 (Plan 03-06).

  python -m ga_crawler weekly-run [--db-path ...] [--sanity-gate-n ...] ...
      Full weekly run (viled + goldapple) writing to real SQLite + Norm06 ledger.
      Replaces the deleted `goldapple-run` Phase 3 stub-bound subcommand.

D-212 cutover (Plan 02-05):
  - DELETED: 4 Stub classes (StubBrandAlias, StubNormalizer, StubSnapshotWriter,
    StubRunWriter). Phase 3 tests now use mocks from tests/conftest.py.
  - DELETED: `goldapple-run` subcommand + `_cmd_run` handler.
  - ADDED: `weekly-run` subcommand backed by `runners/main_run.py::run_weekly`.
  - KEPT: `goldapple-smoke` subcommand + `_cmd_smoke` handler (unchanged).
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
    """ADDED Plan 02-05. Full weekly run via runners/main_run.run_weekly."""
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
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "run_id": result.run_id,
                "viled_count": result.viled_count,
                "goldapple_count": result.goldapple_count,
                "reason": result.reason,
                "norm06_path": str(result.norm06_path) if result.norm06_path else None,
                "stats_delta_keys": sorted(result.stats_delta.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
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

    args = parser.parse_args(argv)
    if args.cmd == "goldapple-smoke":
        return asyncio.run(_cmd_smoke(args))
    if args.cmd == "weekly-run":
        return _cmd_weekly(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
