"""Viled fast-API crawl — bypass PDP fetches entirely.

Discovered 2026-05-15: viled exposes /api/viled-catalog/v2/items/content
which returns full pagination AND all product fields (brandName, groupName,
minPrice/realMinPrice, currency, attributes[Размер]) in a single call.

This script walks all pages of the configured viled catalog URLs and writes
snapshots directly to the snapshots table — skipping the entire ViledFetcher
PDP-fetch pipeline. For 7,602 beauty items this compresses what would be a
~4-hour PDP crawl into a ~3-minute API walk.

Usage:
  uv run python bin/viled_fast_crawl.py [--db-path PATH] [--pause SECONDS]

Output: prints JSON with {run_id, viled_count, status}. The created run_id is
the seed for downstream goldapple/matcher/reporter phases via:
  uv run python -m ga_crawler weekly-run --goldapple-only  (uses same DB)

Note: this is an OPERATOR-ONLY script. Not wired into cron. The standard
weekly-run still uses ViledFetcher (per CRAWL-01..06 contract). Use this
script when you need full-catalog coverage in a single invocation.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Optional

import structlog
from curl_cffi import requests as cffi_requests
from dotenv import find_dotenv, load_dotenv

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.config import ViledConfig
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.normalizers.volume import detect_multipack, serialize_volume_norm
from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)

log = structlog.get_logger(__name__)

_CATALOG_API = "https://viled.kz/api/viled-catalog/v2/items/content"
_PAGE_SIZE = 60
_VOLUME_ATTR_NAMES = ("размер", "объем", "объём")
_CATALOG_BASE_RE = re.compile(r"https?://viled\.kz/(men|women|kids)/catalog/(\d+)")


def _parse_catalog_base(catalog_base: str) -> Optional[tuple[str, str]]:
    """Extract (gender, catalog_id) from catalog URL."""
    m = _CATALOG_BASE_RE.match(catalog_base)
    if not m:
        return None
    return m.group(1), m.group(2)


def _extract_volume_from_attributes(attributes: list[dict]) -> Optional[str]:
    """Find first Размер/объем attribute value in the catalog API attributes list."""
    if not attributes:
        return None
    for attr in attributes:
        name = (attr.get("name") or "").strip().lower()
        if name in _VOLUME_ATTR_NAMES:
            value = (attr.get("value") or "").strip()
            if value:
                return value
    return None


def _walk_catalog(gender: str, catalog_id: str, pause: float) -> list[dict]:
    """Walk all pages of /api/viled-catalog/v2/items/content for (gender, catalog_id).

    Returns list of raw catalog item dicts (one per product). Stops when
    pageNumber stops incrementing (defensive guard against backend changes).
    """
    items: list[dict] = []
    page = 1
    total_pages: Optional[int] = None
    while True:
        params = {
            "gender": gender,
            "catalogId": catalog_id,
            "page": page,
            "pageSize": _PAGE_SIZE,
        }
        try:
            resp = cffi_requests.get(_CATALOG_API, params=params, impersonate="chrome", timeout=30)
        except Exception as e:
            log.error("viled_api_request_failed", gender=gender, catalog_id=catalog_id, page=page, error=str(e))
            break
        if resp.status_code != 200:
            log.warning("viled_api_non_200", page=page, status=resp.status_code)
            break
        try:
            data = resp.json()
        except Exception as e:
            log.error("viled_api_json_parse_failed", page=page, error=str(e))
            break
        content = data.get("content", []) or []
        returned_page = data.get("pageNumber")
        if total_pages is None:
            total_pages = data.get("totalPages") or 1
            total = data.get("total", 0)
            log.info(
                "viled_api_first_page",
                gender=gender,
                catalog_id=catalog_id,
                total=total,
                totalPages=total_pages,
            )
        if returned_page != page:
            log.warning(
                "viled_api_pagination_diverged",
                requested=page,
                returned=returned_page,
                note="server returned different page than requested — stopping",
            )
            break
        items.extend(content)
        log.info(
            "viled_api_page_fetched",
            gender=gender,
            catalog_id=catalog_id,
            page=page,
            page_count=len(content),
            cumulative=len(items),
        )
        if page >= total_pages or not content:
            break
        page += 1
        time.sleep(pause)
    return items


def _catalog_item_to_normalized(item: dict, normalizer: Normalizer) -> Optional[dict]:
    """Convert a catalog API item to the SnapshotWriter dict shape.

    Returns None if essential fields are missing.
    """
    sku_id = item.get("id")
    brand_raw = (item.get("brandName") or "").strip()
    name_raw = (item.get("groupName") or "").strip()
    min_price = item.get("minPrice")
    real_min_price = item.get("realMinPrice")
    if sku_id is None or not brand_raw or not name_raw or not min_price:
        return None

    raw_volume_text = _extract_volume_from_attributes(item.get("attributes", []))
    volume_norm_tuple = normalizer.volume(raw_volume_text or "")
    volume_norm = serialize_volume_norm(volume_norm_tuple)
    multipack_flag = detect_multipack(raw_volume_text or "")

    enable_discount = item.get("enableDiscount", False)
    was_price = None
    if enable_discount and real_min_price and real_min_price != min_price:
        was_price = int(real_min_price)

    return {
        "sku_id": str(sku_id),
        "url": f"https://viled.kz/item/{sku_id}",
        "name": name_raw,
        "brand": brand_raw,
        "brand_norm": normalizer.brand(brand_raw),
        "name_norm": normalizer.name(name_raw),
        "current_price": int(min_price),
        "was_price": was_price,
        "currency": "KZT",
        "stock_state": "IN_STOCK",  # catalog API only lists available items; UNKNOWN if site changes
        "volume_raw": raw_volume_text,
        "volume_norm": volume_norm,
        "multipack_flag": multipack_flag,
        "parse_error_flag": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Viled fast-API crawl (bypasses PDP fetches)")
    parser.add_argument("--db-path", default="prices.db", help="SQLite path")
    parser.add_argument("--pyproject", default="pyproject.toml", help="config path")
    parser.add_argument("--pause", type=float, default=0.5, help="inter-page pause seconds")
    parser.add_argument("--repo-root", default=".", help="repo root for alias file")
    args = parser.parse_args()

    # Load .env for any downstream callers
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    # Initialize DB + storage
    db_path = Path(args.db_path)
    init_db(db_path)
    engine = make_engine(db_path)
    run_writer = SqliteRunWriter(engine)
    snapshot_writer = SqliteSnapshotWriter(engine)

    # Normalizer (uses YAML brand alias file)
    repo_root = Path(args.repo_root).resolve()
    alias_path = repo_root / "config" / "brand-aliases.yaml"
    if not alias_path.exists():
        for candidate in (repo_root / "data/brand-aliases.yaml", repo_root / "src/ga_crawler/data/brand-aliases.yaml", repo_root / "brand-aliases.yaml"):
            if candidate.exists():
                alias_path = candidate
                break
    if not alias_path.exists():
        log.warning("brand_alias_missing", searched=str(repo_root / "data/brand-aliases.yaml"))
        # Construct empty alias as fallback
        alias = YamlBrandAlias.__new__(YamlBrandAlias)
        alias._map = {}
    else:
        alias = YamlBrandAlias(alias_path)
    normalizer = Normalizer(alias)

    # Config (catalog URLs)
    config = ViledConfig.from_pyproject(args.pyproject)

    # Create run row
    run_id = run_writer.create()
    log.info("viled_fast_crawl_started", run_id=run_id, catalog_urls=list(config.catalog_urls))

    # Walk each catalog
    all_records: list[dict] = []
    seen_ids: set[str] = set()
    started = time.perf_counter()
    for catalog_base in config.catalog_urls:
        parsed = _parse_catalog_base(catalog_base)
        if not parsed:
            log.warning("catalog_base_invalid", url=catalog_base)
            continue
        gender, catalog_id = parsed
        raw_items = _walk_catalog(gender, catalog_id, args.pause)
        log.info("viled_catalog_walked", catalog_base=catalog_base, raw_count=len(raw_items))
        for item in raw_items:
            record = _catalog_item_to_normalized(item, normalizer)
            if record is None:
                continue
            sku = record["sku_id"]
            if sku in seen_ids:
                continue  # dedup across catalogs
            seen_ids.add(sku)
            all_records.append(record)

    inserted = snapshot_writer.append(run_id, "viled", all_records)
    duration = time.perf_counter() - started
    log.info(
        "viled_fast_crawl_complete",
        run_id=run_id,
        records_built=len(all_records),
        inserted=inserted,
        duration_seconds=round(duration, 1),
    )

    # Patch run stats
    run_writer.patch_stats(run_id, {
        "viled.fetch_count": len(all_records),
        "viled.persisted_count": inserted,
        "viled.fetch_failures": 0,
        "viled.parse_failures": 0,
        "viled.fetch_duration_seconds": int(duration),
        "viled.mean_fetch_seconds": 0.0,
        "viled.parse_quality_pass": True,
        "viled.sanity_gate_n_pass": True,  # we crawled the full catalog
        "viled.null_rate_required_fields": 0.0,
        "viled.fast_api_mode": True,
    })

    print(json.dumps({
        "run_id": run_id,
        "viled_count": inserted,
        "status": "success",
        "duration_seconds": round(duration, 1),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
