"""End-to-end MVP test for the brand-page enumerator.

Pipeline:
  1. Read viled.brand_norm + COUNT(sku) from prices.db run 18 (top 18 brands).
  2. Resolve each viled brand_norm → GA brand slug via data/ga_brand_slugs.yaml
     overrides + default kebab rule.
  3. Boot ONE Camoufox session and enumerate each brand via the SPA-scroll
     + cards-list XHR-capture flow (ga_crawler.enumeration.goldapple_brand).
  4. CLONE viled snapshots from run 18 → new run 19 (so we test against the
     same viled inventory).
  5. INSERT all enumerated goldapple snapshots under run 19 (via
     SqliteSnapshotWriter and the existing Normalizer to compute brand_norm
     etc.).
  6. Run the v2 matcher on run 19.
  7. Print before/after comparison (run 18 = sitemap-based, run 19 = brand-based).

This is a one-shot validation script — does NOT modify weekly-run pipelines.
After we're happy with the results, integration goes into runners/goldapple_run.py
in a follow-up change.

Usage:
    uv run python scripts/test_brand_enumerator.py
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import yaml
from sqlalchemy import text
from sqlmodel import Session

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.enumeration.goldapple_brand import enumerate_brands
from ga_crawler.fetchers.goldapple import GoldappleFetcher
from ga_crawler.matcher.strict_key import (
    build_matches_for_run,
    compute_brand_overlap,
    compute_comparable_counts,
    compute_denominator,
)
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.normalizers.volume import detect_multipack, serialize_volume_norm
from ga_crawler.storage.sqlite import (
    Run,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)

DB_PATH = Path("prices.db")
BRAND_SLUG_YAML = Path("data/ga_brand_slugs.yaml")
SOURCE_RUN_ID = 18  # viled snapshots cloned from here
TEST_RUN_ID = 19    # new run we'll create + populate


def default_slug(brand_norm: str) -> str:
    """Default brand-norm → GA slug rule."""
    return re.sub(r"[_\s]+", "-", brand_norm.lower()).strip("-")


def load_slug_map() -> dict[str, str]:
    if not BRAND_SLUG_YAML.exists():
        return {}
    data = yaml.safe_load(BRAND_SLUG_YAML.read_text(encoding="utf-8")) or {}
    return dict(data.get("overrides") or {})


def get_target_brand_norms(engine, run_id: int, top_n: int = 30) -> list[tuple[str, int]]:
    """Top-N viled brand_norms from a given run, by SKU count."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT brand_norm, COUNT(*) AS n FROM snapshots "
                "WHERE retailer='viled' AND run_id=:rid "
                "GROUP BY brand_norm ORDER BY n DESC LIMIT :n"
            ),
            {"rid": run_id, "n": top_n},
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def clone_viled_snapshots(engine, source_run_id: int, target_run_id: int) -> int:
    """INSERT a viled-only copy of snapshots from source_run_id under target_run_id."""
    with engine.begin() as conn:
        # Snapshot table has integer PK; we must omit id to allow autoincrement.
        copied = conn.execute(
            text(
                "INSERT INTO snapshots "
                "(run_id, retailer, sku_id, url, name, brand, brand_norm, name_norm, "
                " volume_raw, volume_norm, multipack_flag, parse_error_flag, "
                " current_price, was_price, currency, stock_state, scraped_at) "
                "SELECT :tgt, retailer, sku_id, url, name, brand, brand_norm, name_norm, "
                "       volume_raw, volume_norm, multipack_flag, parse_error_flag, "
                "       current_price, was_price, currency, stock_state, scraped_at "
                "FROM snapshots WHERE run_id=:src AND retailer='viled'"
            ),
            {"src": source_run_id, "tgt": target_run_id},
        )
        return copied.rowcount or 0


async def main() -> None:
    print(f"=== Init engine on {DB_PATH} ===")
    init_db(DB_PATH)
    engine = make_engine(DB_PATH)

    # ---- Step 1: target brand norms (top 18 viled brands) ----
    targets = get_target_brand_norms(engine, run_id=SOURCE_RUN_ID, top_n=30)
    print(f"\n=== Step 1: viled top-{len(targets)} brand_norms (run {SOURCE_RUN_ID}) ===")
    slug_map = load_slug_map()
    target_slugs: list[tuple[str, str, int]] = []
    for brand_norm, n in targets:
        slug = slug_map.get(brand_norm) or default_slug(brand_norm)
        target_slugs.append((brand_norm, slug, n))
        print(f"  {brand_norm:30}  ({n:>4} viled SKU)  → /brands/{slug}")

    # ---- Step 2: ensure target run row exists ----
    print(f"\n=== Step 2: prepare run {TEST_RUN_ID} ===")
    with Session(engine) as s:
        existing = s.get(Run, TEST_RUN_ID)
        if existing is None:
            s.add(Run(
                run_id=TEST_RUN_ID,
                started_at=datetime.now(timezone.utc),
                status="running",
                stats="{}",
            ))
            s.commit()
            print(f"  created Run row run_id={TEST_RUN_ID}")
        else:
            print(f"  Run row run_id={TEST_RUN_ID} already exists — will rebuild")

    # Wipe any prior snapshots for run 19 (rerunnable).
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM matches WHERE run_id=:rid"), {"rid": TEST_RUN_ID})
        conn.execute(text("DELETE FROM snapshots WHERE run_id=:rid"), {"rid": TEST_RUN_ID})

    # ---- Step 3: clone viled snapshots from source run ----
    n_viled = clone_viled_snapshots(engine, SOURCE_RUN_ID, TEST_RUN_ID)
    print(f"  cloned {n_viled} viled snapshots from run {SOURCE_RUN_ID}")

    # ---- Step 4: brand enumeration via Camoufox ----
    print(f"\n=== Step 3: enumerate {len(target_slugs)} brands via /brands/<slug> ===")
    t0 = time.time()
    async with GoldappleFetcher(run_id=TEST_RUN_ID, headless=True) as fetcher:
        slugs_only = [slug for (_, slug, _) in target_slugs]
        results = await enumerate_brands(fetcher, slugs_only, inter_brand_pause_seconds=2.0)

    total_raw = 0
    for (bn, slug, viled_count), res in zip(target_slugs, results):
        total_raw += len(res.raw_products)
        flag = "✓" if res.raw_products else "✗"
        print(
            f"  {flag} {bn:25} slug={slug:35} "
            f"badge={res.product_count_badge!s:>4} "
            f"cards={res.cards_collected:>4} dedup={len(res.raw_products):>4} "
            f"xhr={res.cards_list_calls:>2}"
            + (f"  ERR={res.error}" if res.error else "")
        )
    elapsed_s = time.time() - t0
    print(f"\n  Total raw products enumerated: {total_raw}  in {elapsed_s:.1f}s")

    # Persist raw cards to disk BEFORE normalize/insert — if persistence
    # fails downstream we don't have to re-crawl.
    dump_dir = Path("inbox/ga_brand_dump")
    dump_dir.mkdir(parents=True, exist_ok=True)
    for (bn, slug, _), res in zip(target_slugs, results):
        if not res.raw_products:
            continue
        (dump_dir / f"{slug}.json").write_text(
            json.dumps(
                [{"sku_id": r.sku_id, "url": r.url, "name": r.name,
                  "brand_raw": r.brand_raw, "current_price": r.current_price,
                  "was_price": r.was_price, "currency": r.currency,
                  "availability": r.availability,
                  "raw_volume_text": r.raw_volume_text} for r in res.raw_products],
                ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"  raw products dumped to {dump_dir}/")

    # ---- Step 5: normalize + insert into run 19 ----
    print(f"\n=== Step 4: normalize + insert {total_raw} GA snapshots into run {TEST_RUN_ID} ===")
    alias_path = Path("config/brand-aliases.yaml")
    alias_loader = YamlBrandAlias(alias_path)  # empty self-seeded dict if absent
    normalizer = Normalizer(alias_loader)
    writer = SqliteSnapshotWriter(engine, batch_size=200)

    payloads: list[dict] = []
    now = datetime.now(timezone.utc)  # SQLite adapter wants datetime, not isoformat str
    for (bn, slug, _), res in zip(target_slugs, results):
        for rp in res.raw_products:
            brand_norm = normalizer.brand(rp.brand_raw)
            name_norm = normalizer.name(rp.name)
            volume_norm = serialize_volume_norm(
                normalizer.volume(rp.raw_volume_text or rp.name)
            )

            stock_state = "IN_STOCK" if rp.availability == "InStock" else "OUT_OF_STOCK"
            multipack_flag = detect_multipack(rp.name)
            payloads.append(dict(
                sku_id=rp.sku_id,
                url=rp.url,
                name=rp.name,
                brand=rp.brand_raw,
                brand_norm=brand_norm,
                name_norm=name_norm,
                volume_raw=rp.raw_volume_text,
                volume_norm=volume_norm,
                multipack_flag=multipack_flag,
                parse_error_flag=False,
                current_price=rp.current_price,
                was_price=rp.was_price,
                currency=rp.currency,
                stock_state=stock_state,
                scraped_at=now,
            ))

    if payloads:
        writer.append(TEST_RUN_ID, "goldapple", payloads)
    print(f"  inserted {len(payloads)} goldapple snapshots")

    # ---- Step 6: run matcher v2 ----
    print(f"\n=== Step 5: run v2 matcher on run {TEST_RUN_ID} ===")
    v_comp = compute_comparable_counts(engine, TEST_RUN_ID, "viled")
    g_comp = compute_comparable_counts(engine, TEST_RUN_ID, "goldapple")
    overlap = compute_brand_overlap(engine, TEST_RUN_ID)
    denom = compute_denominator(engine, TEST_RUN_ID)
    print(f"  comparable viled       : {v_comp}")
    print(f"  comparable goldapple   : {g_comp}")
    print(f"  brand_overlap          : {overlap}")
    print(f"  denominator            : {denom}")

    n_matches = build_matches_for_run(engine, TEST_RUN_ID)
    print(f"  matches inserted       : {n_matches}")
    if denom > 0:
        print(f"  match rate             : {round(n_matches*100.0/denom, 2)}%")

    # ---- Step 7: comparison with run 18 ----
    print(f"\n=== Comparison: run {SOURCE_RUN_ID} vs run {TEST_RUN_ID} ===")
    with engine.connect() as conn:
        for rid in (SOURCE_RUN_ID, TEST_RUN_ID):
            v = conn.execute(text(
                "SELECT COUNT(*) FROM snapshots WHERE run_id=:r AND retailer='viled'"
            ), {"r": rid}).fetchone()[0]
            g = conn.execute(text(
                "SELECT COUNT(*) FROM snapshots WHERE run_id=:r AND retailer='goldapple'"
            ), {"r": rid}).fetchone()[0]
            m = conn.execute(text(
                "SELECT COUNT(*) FROM matches WHERE run_id=:r"
            ), {"r": rid}).fetchone()[0]
            print(f"  run {rid}: viled={v}  goldapple={g}  matches={m}")

    # Mark run as success
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE runs SET finished_at=:f, status='success' "
                "WHERE run_id=:r"
            ),
            {"f": datetime.now(timezone.utc), "r": TEST_RUN_ID},
        )

    print(f"\nDone. New snapshots + matches persisted under run {TEST_RUN_ID}.")


if __name__ == "__main__":
    asyncio.run(main())
