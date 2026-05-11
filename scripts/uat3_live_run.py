"""UAT Phase 3, Test 6 — bounded live goldapple run.

Faithful to the original Test 6 intent (pre-D-212 CLI cutover):
  goldapple-run --run-id 44 --viled-brands givenchy,jo_malone_london --sanity-gate-m 10

The `goldapple-run` subcommand was deleted in Plan 02-05 (D-212 cutover) in favor
of `weekly-run`, which derives viled_brands from the current run's viled snapshot.
This driver replicates the bounded test by calling `run_goldapple_phase` directly
with the same 2 brands, M=10, against a fresh prices.db.

Includes a one-shot smoke-probe retry with 75-sec cooldown to absorb the anti-bot
transient documented in 03-07-SUMMARY Operational Findings #1 and #2.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import structlog

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.runners.goldapple_run import run_goldapple_phase
from ga_crawler.storage.norm06_writer import Norm06Writer
from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


async def _run_with_smoke_retry(
    *,
    run_id: int,
    viled_brands: list[str],
    repo_root: Path,
    brand_alias,
    normalizer,
    snapshot_writer,
    run_writer,
    headless: bool,
    M: int,
    cooldown_seconds: int = 75,
):
    """Call run_goldapple_phase, retry once with cooldown on smoke_probe_failed."""
    result = await run_goldapple_phase(
        run_id=run_id,
        viled_brands=viled_brands,
        repo_root=repo_root,
        brand_alias=brand_alias,
        normalizer=normalizer,
        snapshot_writer=snapshot_writer,
        run_writer=run_writer,
        headless=headless,
        M=M,
    )
    if result.status == "failed" and result.reason == "smoke_probe_failed":
        print(
            f"[uat3] smoke_probe_failed on first attempt — "
            f"sleeping {cooldown_seconds}s then retrying once",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(cooldown_seconds)
        # The previous run_writer.fail() call already marked the row failed;
        # a retry needs a NEW run row to keep DATA-05 lifecycle clean.
        new_run_id = run_writer.create()
        print(f"[uat3] retry with new run_id={new_run_id}", file=sys.stderr, flush=True)
        result = await run_goldapple_phase(
            run_id=new_run_id,
            viled_brands=viled_brands,
            repo_root=repo_root,
            brand_alias=brand_alias,
            normalizer=normalizer,
            snapshot_writer=snapshot_writer,
            run_writer=run_writer,
            headless=headless,
            M=M,
        )
        # Update run_id so caller sees the actual completed one.
        result_dict = {
            "status": result.status,
            "goldapple_count": result.goldapple_count,
            "reason": result.reason,
            "stats_delta_keys": sorted(result.stats_delta.keys()),
            "unmatched_viled_brands": result.unmatched_viled_brands,
            "new_goldapple_slug_count": len(result.new_goldapple_slugs),
            "effective_run_id": new_run_id,
            "smoke_retry_used": True,
        }
        return new_run_id, result, result_dict
    return run_id, result, {
        "status": result.status,
        "goldapple_count": result.goldapple_count,
        "reason": result.reason,
        "stats_delta_keys": sorted(result.stats_delta.keys()),
        "unmatched_viled_brands": result.unmatched_viled_brands,
        "new_goldapple_slug_count": len(result.new_goldapple_slugs),
        "effective_run_id": run_id,
        "smoke_retry_used": False,
    }


def main() -> int:
    _configure_logging()
    repo_root = Path(".").resolve()
    db_path = repo_root / "prices.db"
    aliases_path = repo_root / "config" / "brand-aliases.yaml"

    init_db(db_path)
    engine = make_engine(db_path)

    run_writer = SqliteRunWriter(engine)
    snapshot_writer = SqliteSnapshotWriter(engine)
    brand_alias = YamlBrandAlias(aliases_path)
    normalizer = Normalizer(brand_alias)

    viled_brands = ["givenchy", "jo_malone_london"]
    M = 10

    run_id = run_writer.create()
    print(
        f"[uat3] starting run_id={run_id} viled_brands={viled_brands} M={M} "
        f"db_path={db_path}",
        file=sys.stderr,
        flush=True,
    )

    started = time.time()
    effective_run_id, result, summary = asyncio.run(
        _run_with_smoke_retry(
            run_id=run_id,
            viled_brands=viled_brands,
            repo_root=repo_root,
            brand_alias=brand_alias,
            normalizer=normalizer,
            snapshot_writer=snapshot_writer,
            run_writer=run_writer,
            headless=False,
            M=M,
        )
    )
    duration = time.time() - started

    # Persist Norm06 ledger + finalize success row if not already failed.
    norm06_path = Norm06Writer(repo_root).persist(
        effective_run_id,
        result.unmatched_viled_brands,
        result.new_goldapple_slugs,
    )
    if result.status == "success":
        run_writer.finalize(effective_run_id, status="success")
    summary["norm06_path"] = str(norm06_path)
    summary["duration_seconds"] = round(duration, 1)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.status == "success" else 2


if __name__ == "__main__":
    sys.exit(main())
