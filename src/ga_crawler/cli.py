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

  python -m ga_crawler deliver-run --run-id N [--force] [--dry-run] [--db-path PATH] [--pyproject PATH] [--repo-root PATH]
      D-608 standalone Telegram delivery recovery tool. Sends business
      caption + xlsx (or ops alert) to Telegram per run_id. Idempotent —
      re-running on `delivered_business` is a no-op (`--force` overrides).
      On Telegram unreachable, the xlsx stays on disk and
      `runs.stats.deliver.delivery_status='undelivered_telegram_unreachable'`.
      Exit codes: 0 delivered/skipped-idempotent, 2 undelivered (retryable),
      3 missing TG_BOT_TOKEN (config error).

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

Plan 06-04 additions:
  - ADDED: `deliver-run` subcommand + `_cmd_deliver` handler (D-608).
  - `_cmd_deliver` is the ONLY place in the project that calls
    `dotenv.load_dotenv()` — keeps test runs from picking up a real
    on-disk `.env` (RESEARCH caveat #4). Structural canary
    `test_load_dotenv_only_in_cli` enforces this invariant.

Phase 9 Plan 03 additions:
  - ADDED: `capture-fixtures` subcommand + `_cmd_capture_fixtures` async handler (TH-05, D-907).
  - ADDED: `_scrub_html_for_fixture` scrub-on-write helper (D-907 belt-and-suspenders).
  - ADDED: `_camoufox_version_runtime` helper.
  - Operator-only; NOT in cron. See README §8 «Live HTML harness» for runbook.
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


def _cmd_deliver(args) -> int:
    """ADDED Plan 06-04 (D-608): standalone deliver-run for recovery.

    Idempotency dispatch (D-606 enum):
      pending                           -> run full delivery
      delivered_business                -> no-op (--force overrides)
      delivered_ops_only                -> re-attempt (rare; fixed-via-recovery)
      undelivered_telegram_unreachable  -> re-attempt full
      skipped_no_credentials            -> re-validate ENV
      skipped_already_delivered         -> no-op (idempotency response)

    Exit codes (D-608):
      0 -> delivered_business OR delivered_ops_only OR skipped_already_delivered
      2 -> undelivered_telegram_unreachable (retryable)
      3 -> skipped_no_credentials (config error -- TG_BOT_TOKEN missing)
    """
    from dotenv import find_dotenv, load_dotenv

    from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
    from ga_crawler.runners.delivery_run import run_delivery_phase
    from ga_crawler.storage.sqlite import (
        SqliteRunWriter,
        init_db,
        make_engine,
    )

    # RESEARCH caveat #4: load_dotenv() lives ONLY here, never in
    # DeliverEnvConfig.from_env() -- keeps the unit-test path clean
    # (tests bypass via monkeypatch.setenv) and lets the operator opt
    # into .env loading at the CLI boundary.
    #
    # quick-task 20260514-cli-dotenv-leak: `find_dotenv(usecwd=True)` is
    # LOAD-BEARING. Default `find_dotenv()` walks up from this module's
    # __file__, which always finds the project's .env regardless of where
    # the CLI was invoked from. That made subprocess tests with stripped
    # TG_* env vars silently re-read real credentials and deliver
    # fake-xlsx fixtures to the operator's real Telegram chat. Anchoring
    # the search at os.getcwd() keeps prod behavior (operator runs
    # `cd /opt/ga_crawler && python -m ga_crawler ...`) while making
    # tmp-cwd subprocess tests credential-free.
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    init_db(args.db_path)
    engine = make_engine(args.db_path)
    run_writer = SqliteRunWriter(engine)
    repo_root = Path(args.repo_root).resolve()

    cfg = DeliverConfig.from_pyproject(args.pyproject)
    env = DeliverEnvConfig.from_env()

    result = run_delivery_phase(
        run_id=args.run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=cfg,
        env=env,
        force=args.force,
        dry_run=args.dry_run,
    )

    payload = json.dumps(
        {
            "delivery_status": result.delivery_status,
            "route": result.route,
            "run_id": args.run_id,
            "business_caption_message_id": result.business_caption_message_id,
            "business_document_message_id": result.business_document_message_id,
            "ops_message_id": result.ops_message_id,
            "attempt_count": result.attempt_count,
            "last_error": result.last_error,
            "delivered_at": result.delivered_at,
            "stats_delta_keys": sorted(result.stats_delta.keys()),
        },
        ensure_ascii=False,
        indent=2,
    )
    # Plan 05-05 Unicode-stdout pattern -- emoji + Cyrillic safe on Windows.
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()

    # D-608 exit code mapping.
    if result.delivery_status in (
        "delivered_business",
        "delivered_ops_only",
        "skipped_already_delivered",
    ):
        return 0
    if result.delivery_status == "skipped_no_credentials":
        return 3
    if result.delivery_status == "pending" and args.dry_run:
        # --dry-run preview success: orchestrator returns pending without I/O.
        return 0
    return 2  # undelivered_*


async def _cmd_capture_fixtures(args) -> int:
    """TH-05 (D-907 belt-and-suspenders): capture live HTML into tests/fixtures/<retailer>/
    as _live-YYYY-MM-DD-<slug>.html with sidecar JSON. Scrub before write.

    Phase 9 Plan 03 (Variant A only). See README §8 «Live HTML harness» for runbook.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    try:
        from tests._fixture_metadata import FixtureMetadata, write_sidecar
    except ImportError as e:
        log.error("test fixture helpers unavailable", error=str(e))
        return 3

    retailer = args.retailer
    url = args.url
    slug = args.slug
    if retailer not in ("goldapple", "viled"):
        log.error("invalid retailer", retailer=retailer, allowed=["goldapple", "viled"])
        return 2

    # --- Fetch ---
    if retailer == "goldapple":
        async with GoldappleFetcher(run_id=-1, headless=args.headless) as fetcher:
            rec = await fetcher.fetch_one(fetcher._page, url)
        if "html" not in rec or rec.get("block"):
            log.error(
                "capture_fixtures_fetch_blocked",
                url=url,
                block_reason=rec.get("block_reason"),
                error=rec.get("error"),
            )
            return 1
        title = rec.get("title", "") or ""
        status = int(rec.get("status", 0) or 0)
        html = rec["html"]
    else:  # viled
        from ga_crawler.fetchers.viled import ViledFetcher
        rec = ViledFetcher(run_id=-1).fetch_one(url)
        title = ""  # viled fetch_one does not return title
        status = int(rec.get("status", 0) or 0)
        html = rec["html"]

    # --- Scrub (D-907 belt-and-suspenders; mirrors _PII_PATTERNS from conftest) ---
    html = _scrub_html_for_fixture(html)

    # --- Dry-run gate ---
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.dry_run:
        fixture_name = f"_live-{today}-{slug}.html"
        print(
            f"[dry-run] would write tests/fixtures/{retailer}/{fixture_name} "
            f"({len(html)} bytes)"
        )
        return 0

    # --- Write fixture + sidecar ---
    fixtures_dir = Path("tests") / "fixtures" / retailer
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixtures_dir / f"_live-{today}-{slug}.html"
    fixture_path.write_text(html, encoding="utf-8")

    meta = FixtureMetadata(
        date=datetime.now(timezone.utc).isoformat(),
        url=url,
        status=status,
        html_size=len(html.encode("utf-8")),
        title=title,
        camoufox_version=_camoufox_version_runtime(),
    )
    sidecar = write_sidecar(fixture_path, meta)
    print(f"[capture-fixtures] wrote {fixture_path} + {sidecar}")
    return 0


def _scrub_html_for_fixture(html: str) -> str:
    """D-907 scrub-on-write: drop cf_clearance, Telegram bot tokens, UUID v4,
    hc-ping paths from HTML before commit. Mirrors conftest._PII_PATTERNS.

    Note: UUID v4 standalone pattern is NOT applied here (see 09-01-SUMMARY.md
    deviation #2 — goldapple HTML legitimately contains UUID-format buildIds).
    The hc-ping-specific pattern covers the actual operator healthcheck token threat.
    """
    import re

    patterns = [
        (re.compile(r"cf_clearance\s*=[^;\"\s]*", re.IGNORECASE), "cf_clearance=SCRUBBED"),
        (re.compile(r"\bbot\d{9,10}:[A-Za-z0-9_\-]{30,}\b"), "botSCRUBBED:SCRUBBED"),
        (re.compile(r"\bAuthorization:\s*Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), "Authorization: Bearer SCRUBBED"),
        (re.compile(r"hc-ping\.com/[0-9a-f\-]{32,36}", re.IGNORECASE), "hc-ping.com/SCRUBBED"),
    ]
    for pat, repl in patterns:
        html = pat.sub(repl, html)
    return html


def _camoufox_version_runtime() -> str:
    """Return the installed camoufox version string, or 'unknown' if unavailable."""
    try:
        from importlib.metadata import version
        return version("camoufox")
    except Exception:
        return "unknown"


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

    # ADDED Plan 06-04 (D-608) — deliver-run standalone recovery tool.
    deliver = sub.add_parser(
        "deliver-run",
        help="Send Telegram delivery against an existing run_id "
             "(idempotent per D-606 enum, D-608)",
    )
    deliver.add_argument(
        "--run-id",
        type=int,
        required=True,
        help="runs.run_id of an existing run to deliver report for",
    )
    deliver.add_argument(
        "--db-path",
        default="prices.db",
        help="SQLite database file path",
    )
    deliver.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml for [tool.ga_crawler.deliver] config",
    )
    deliver.add_argument(
        "--repo-root",
        default=".",
        help="Repo root for resolving xlsx_path + Pitfall C containment check",
    )
    deliver.add_argument(
        "--force",
        action="store_true",
        help="Override idempotency for delivered_business state (D-608)",
    )
    deliver.add_argument(
        "--dry-run",
        action="store_true",
        help="Build gate decision + messages, print JSON preview to stdout, "
             "skip Telegram API + skip patch_stats (D-608 read-only mode)",
    )

    # ADDED Phase 9 Plan 03 (D-907 TH-05) — capture-fixtures standalone operator tool.
    capture = sub.add_parser(
        "capture-fixtures",
        help="Capture a live HTML PDP into tests/fixtures/<retailer>/_live-DATE-<slug>.html "
             "with sidecar JSON (TH-05; D-907 scrub-on-write). Operator-only — not in cron.",
    )
    capture.add_argument(
        "--retailer",
        required=True,
        choices=["goldapple", "viled"],
        help="Retailer to fetch from",
    )
    capture.add_argument(
        "--url",
        required=True,
        help="Full PDP URL to capture",
    )
    capture.add_argument(
        "--slug",
        required=True,
        help="Short kebab-case slug for the fixture filename (e.g. 'stereotype-sago')",
    )
    capture.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect URL + compute scrubbed size but write no files",
    )
    capture.add_argument(
        "--headless",
        type=_parse_bool,
        default=True,
        help="Camoufox headless flag for goldapple fetch (default: True)",
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
    if args.cmd == "deliver-run":
        return _cmd_deliver(args)
    if args.cmd == "capture-fixtures":
        return asyncio.run(_cmd_capture_fixtures(args))
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
