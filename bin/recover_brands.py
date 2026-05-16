"""Targeted recovery for goldapple brands that hit the per-brand 403
budget mid-pagination. Re-enumerates ONLY the named brands with the
current (wider) hardening defaults, replaces their snapshots in-place
for the given run_id, then exits.

Usage:
    uv run python bin/recover_brands.py --run-id 19 \\
        --brand-norms zielinski_rozen,clarins,clinique

Requires data/ga_brand_slugs.yaml to already contain the brand_norm →
slug mapping (or default-kebab works).

Designed for the case where a full goldapple re-enum already produced
acceptable numbers for most brands but a few hit budget exhaustion on
later pages. Re-running the full phase costs ~90 minutes; recovering 3
brands takes ~10.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Iterable

import structlog
from dotenv import find_dotenv, load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.enumeration.goldapple_brand import enumerate_brand_hybrid
from ga_crawler.fetchers.goldapple import GoldappleFetcher
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.normalizers.volume import detect_multipack, serialize_volume_norm
from ga_crawler.runners.goldapple_brand_run import (
    _record_from_raw,
    load_slug_overrides,
    resolve_brand_slug,
)
from ga_crawler.storage.sqlite import (
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)

log = structlog.get_logger(__name__)


async def _recover_brands(
    *,
    run_id: int,
    brand_norms: list[str],
    db_path: Path,
    repo_root: Path,
    headless: bool,
) -> dict:
    # Bootstrap
    init_db(db_path)
    engine = make_engine(db_path)
    snapshot_writer = SqliteSnapshotWriter(engine)

    alias_path = repo_root / "config" / "brand-aliases.yaml"
    alias = YamlBrandAlias(alias_path)
    normalizer = Normalizer(alias)

    slug_overrides = load_slug_overrides(repo_root / "data" / "ga_brand_slugs.yaml")
    brand_to_slug = {
        bn: resolve_brand_slug(bn, slug_overrides) for bn in brand_norms
    }
    log.info("recover_targets", brand_to_slug=brand_to_slug)

    # Sanity-check the runs row exists.
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status FROM runs WHERE run_id = :rid"),
                          {"rid": run_id}).fetchone()
        if row is None:
            raise SystemExit(f"run_id={run_id} not found in runs table")
        log.info("recover_run_status", run_id=run_id, status=row[0])

    # Recover one brand at a time so partial progress is durable.
    results = []
    for bn, slug in brand_to_slug.items():
        log.info("recover_brand_start", brand_norm=bn, slug=slug)
        async with GoldappleFetcher(run_id=run_id, headless=headless) as fetcher:
            result = await enumerate_brand_hybrid(fetcher, slug)

        rp_count = len(result.raw_products)
        if rp_count == 0:
            log.warning("recover_brand_empty", brand_norm=bn, slug=slug,
                        error=result.error)
            results.append({"brand_norm": bn, "slug": slug,
                            "rp_count": 0, "error": result.error})
            continue

        # Convert to snapshot records, then DELETE existing rows for THIS
        # brand_norm (after normalization through aliases) and INSERT new ones.
        records = [_record_from_raw(rp, normalizer) for rp in result.raw_products]
        # Group by post-normalize brand_norm (since alias may merge multiple
        # raw brand strings to the same canonical key).
        post_norm_brand_norms = {r["brand_norm"] for r in records}

        with engine.begin() as conn:
            # Delete the OLD rows for whatever brand_norms this enumeration
            # touches. If alias maps GA's "Gucci" → "gucci-beauty", we delete
            # both "gucci" (stale) and "gucci-beauty" (current).
            del_targets = post_norm_brand_norms | {bn}
            for target in del_targets:
                conn.execute(
                    text("DELETE FROM snapshots WHERE run_id=:rid "
                         "AND retailer='goldapple' AND brand_norm=:bn"),
                    {"rid": run_id, "bn": target},
                )
        inserted = snapshot_writer.append(run_id, "goldapple", records)
        log.info("recover_brand_complete", brand_norm=bn, slug=slug,
                 raw_products=rp_count, inserted=inserted,
                 post_norm_brand_norms=sorted(post_norm_brand_norms),
                 cards_collected=result.cards_collected,
                 cards_list_calls=result.cards_list_calls,
                 badge=result.product_count_badge)
        results.append({
            "brand_norm": bn,
            "slug": slug,
            "rp_count": rp_count,
            "inserted": inserted,
            "post_norm_brand_norms": sorted(post_norm_brand_norms),
            "badge": result.product_count_badge,
        })

    return {"run_id": run_id, "recovered": results}


def main() -> int:
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    parser = argparse.ArgumentParser(description="Targeted goldapple brand recovery")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--brand-norms", required=True,
                        help="Comma-separated viled brand_norms to recover")
    parser.add_argument("--db-path", default="prices.db")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--headless", type=str, default="true")
    args = parser.parse_args()

    brand_norms = [b.strip() for b in args.brand_norms.split(",") if b.strip()]
    if not brand_norms:
        raise SystemExit("--brand-norms must be non-empty")

    result = asyncio.run(_recover_brands(
        run_id=args.run_id,
        brand_norms=brand_norms,
        db_path=Path(args.db_path),
        repo_root=Path(args.repo_root).resolve(),
        headless=args.headless.lower() in ("1", "true", "yes"),
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
