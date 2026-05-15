"""Run goldapple + matcher + report against an existing run_id.

Companion to bin/viled_fast_crawl.py — assumes viled phase already
populated the snapshots table for the given run_id.

Usage:
  uv run python bin/run_goldapple_for_existing_run.py --run-id N [--sanity-gate-m 50]

This calls run_goldapple_phase directly (skipping main_run.run_weekly's
new-run-id creation) so the goldapple brand-filter sees the viled snapshots
that were already persisted under this run_id.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import structlog
from dotenv import find_dotenv, load_dotenv

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.config import GoldappleConfig, MatchConfig
from ga_crawler.matcher.strict_key import build_matches_for_run, read_run_status
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.parsers.dispatcher import ParseDispatcher
from ga_crawler.reporter.xlsx_builder import build_xlsx_report
from ga_crawler.runner.gates import auto_suggest_threshold, final_threshold_gate
from ga_crawler.runners.goldapple_run import run_goldapple_phase
from ga_crawler.runners.main_run import _derive_viled_brands_from_snapshots
from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)

log = structlog.get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Continue weekly pipeline from existing viled run_id")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--db-path", default="prices.db")
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--sanity-gate-m", type=int, default=50)
    parser.add_argument("--sanity-gate-p", type=int, default=0)
    parser.add_argument("--headless", type=str, default="true")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    db_path = Path(args.db_path)
    init_db(db_path)
    engine = make_engine(db_path)
    run_writer = SqliteRunWriter(engine)
    snapshot_writer = SqliteSnapshotWriter(engine)

    repo_root = Path(args.repo_root).resolve()
    alias_path = repo_root / "config" / "brand-aliases.yaml"
    alias = YamlBrandAlias(alias_path) if alias_path.exists() else YamlBrandAlias.__new__(YamlBrandAlias)
    if not alias_path.exists():
        alias._map = {}
    normalizer = Normalizer(alias)
    dispatcher = ParseDispatcher()

    # Read viled brands from existing run snapshots
    viled_brands = _derive_viled_brands_from_snapshots(engine, args.run_id)
    log.info("derived_viled_brands", run_id=args.run_id, count=len(viled_brands))
    if not viled_brands:
        print(json.dumps({"status": "no_viled_brands", "run_id": args.run_id}))
        return 1

    # Goldapple phase
    config = GoldappleConfig.from_pyproject(args.pyproject)
    if args.sanity_gate_m is not None:
        import dataclasses
        config = dataclasses.replace(config, sanity_gate_m=args.sanity_gate_m)
    log.info("goldapple_phase_start", run_id=args.run_id, sanity_gate_m=config.sanity_gate_m)
    ga_result = run_goldapple_phase(
        run_id=args.run_id,
        config=config,
        viled_brands=viled_brands,
        brand_alias=alias,
        normalizer=normalizer,
        snapshot_writer=snapshot_writer,
        run_writer=run_writer,
        dispatcher=dispatcher,
    )
    log.info(
        "goldapple_phase_complete",
        run_id=args.run_id,
        status=ga_result.status,
        goldapple_count=getattr(ga_result, "goldapple_count", "?"),
        reason=getattr(ga_result, "reason", None),
    )

    if ga_result.status != "success":
        print(json.dumps({
            "status": ga_result.status,
            "run_id": args.run_id,
            "reason": getattr(ga_result, "reason", None),
        }, indent=2))
        return 1

    # Matcher
    match_config = MatchConfig.from_pyproject(args.pyproject)
    if args.sanity_gate_p is not None:
        import dataclasses
        match_config = dataclasses.replace(match_config, sanity_gate_p=args.sanity_gate_p)

    log.info("matcher_phase_start", run_id=args.run_id)
    if read_run_status(engine, args.run_id) != "success":
        # Manually mark success before matcher gate (run hasn't called run_writer.success yet)
        run_writer.success(args.run_id)
    started_match = time.perf_counter()
    inserted = build_matches_for_run(engine, args.run_id)
    duration_match = time.perf_counter() - started_match
    log.info("matcher_phase_complete", run_id=args.run_id, match_count=inserted, duration=duration_match)

    # Reporter
    log.info("reporter_phase_start", run_id=args.run_id)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = reports_dir / f"2026-W20-full-{args.run_id}.xlsx"
    started_report = time.perf_counter()
    sheet_counts = build_xlsx_report(engine, args.run_id, xlsx_path)
    duration_report = time.perf_counter() - started_report
    log.info(
        "reporter_phase_complete",
        run_id=args.run_id,
        xlsx_path=str(xlsx_path),
        size_bytes=xlsx_path.stat().st_size,
        sheets=sheet_counts,
        duration=duration_report,
    )

    print(json.dumps({
        "status": "success",
        "run_id": args.run_id,
        "viled_brands": len(viled_brands),
        "goldapple_count": getattr(ga_result, "goldapple_count", "?"),
        "match_count": inserted,
        "xlsx_path": str(xlsx_path),
        "xlsx_size_bytes": xlsx_path.stat().st_size,
        "sheets": sheet_counts,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
