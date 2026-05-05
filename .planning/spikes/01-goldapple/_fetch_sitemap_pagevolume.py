"""Plan 01-05 Task 2: fetch goldapple sitemap.xml + count product URLs per brand.

D-11 sitemap-first strategy. Per plan 01-04 finding: every HTML route is
JS-gated, but robots.txt is delivered plain. Sitemap.xml MAY also be plain
(it's served for crawlers; gating it would defeat its purpose).

Brands chosen autonomously from viled.kz homepage __NEXT_DATA__ probe
(_fetch_viled_brands.py). viled is luxury fashion + niche perfumery; the
beauty/perfumery section featured brands give us the most likely
viledINTERSECTgoldapple intersection (per D-12).

Selected brands (5):
  1. Jo Malone London  - niche perfumery
  2. Tom Ford          - luxury cosmetics + perfumery
  3. Creed             - niche perfumery
  4. Frederic Malle    - niche perfumery (Editions de Parfums)
  5. Givenchy          - luxury cosmetics + perfumery

Honor goldapple committed rate-limit: 3-5s random uniform between fetches.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_fetch_sitemap_pagevolume.py
"""

import json
import random
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from curl_cffi import requests

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
OUT.mkdir(parents=True, exist_ok=True)

SITEMAP_CANDIDATES = [
    "https://goldapple.kz/sitemap.xml",
    "https://goldapple.kz/sitemap_products.xml",
    "https://goldapple.kz/sitemap_index.xml",
]

# Brand selection: see module docstring (autonomous from viled probe).
SELECTED_BRANDS = {
    "Jo Malone London": ["jo-malone", "jomalone", "jo_malone", "malone-london"],
    "Tom Ford": ["tom-ford", "tomford", "tom_ford"],
    "Creed": ["creed"],
    "Frederic Malle": ["frederic-malle", "fredericmalle", "editions-de-parfums"],
    "Givenchy": ["givenchy"],
}


def goldapple_pause() -> None:
    """Honor committed rate-limit: 3-5s random uniform."""
    sleep_s = random.uniform(3.0, 5.0)
    print(f"  [pause {sleep_s:.2f}s - committed goldapple rate-limit]")
    time.sleep(sleep_s)


def fetch(url: str) -> requests.Response | None:
    print(f"Fetching {url} ...")
    try:
        r = requests.get(
            url, impersonate="chrome", timeout=60, allow_redirects=True
        )
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return None
    print(f"  HTTP {r.status_code}, {len(r.text)} bytes")
    return r


def is_xml_sitemap(text: str) -> bool:
    head = text[:500].lower()
    return "<urlset" in head or "<sitemapindex" in head or "<?xml" in head


def parse_sitemap_urls(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (sub_sitemap_urls, page_urls).

    If text is a sitemapindex, returns sub-sitemap URLs and empty pages.
    If urlset, returns empty subs and page URLs.
    """
    # Strip BOM (U+FEFF) and leading whitespace
    xml_text = xml_text.lstrip(chr(0xFEFF)).lstrip()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  Parse error: {e}")
        return [], []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tag = root.tag.split("}", 1)[-1] if "}" in root.tag else root.tag

    locs = [
        loc.text
        for loc in root.findall(".//sm:loc", ns)
        if loc.text
    ]
    if tag == "sitemapindex":
        print(f"  -> sitemapindex with {len(locs)} child sitemaps")
        return locs, []
    elif tag == "urlset":
        print(f"  -> urlset with {len(locs)} URLs")
        return [], locs
    else:
        print(f"  Unknown root tag: {tag}")
        return [], []


def main() -> None:
    # ----- Step 1: try sitemap candidates -----
    primary_xml: str | None = None
    primary_url: str | None = None
    fetch_count = 0

    for url in SITEMAP_CANDIDATES:
        if fetch_count > 0:
            goldapple_pause()
        fetch_count += 1
        r = fetch(url)
        if r is None:
            continue
        if r.status_code == 200 and is_xml_sitemap(r.text):
            primary_xml = r.text
            primary_url = url
            print(f"  [OK] Got sitemap from {url}")
            break

    if primary_xml is None:
        print("\n=== ALL sitemap candidates failed (gated or 404) ===")
        # Document gap & exit with structured fallback
        gap_record = {
            brand: {
                "url_count": 0,
                "source": "deferred",
                "notes": (
                    "sitemap.xml not reachable via curl_cffi; HTML brand pages "
                    "are JS-gated (per 01-04). Defer page-volume to plan 01-08 "
                    "warm-Patchright session."
                ),
            }
            for brand in SELECTED_BRANDS
        }
        out_json = OUT / "page-volume-raw.json"
        out_json.write_text(
            json.dumps(gap_record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  Saved gap record to {out_json}")
        return

    # Save primary (decode-stable: write bytes directly to preserve XML decl)
    primary_path = OUT / "goldapple-sitemap.xml"
    primary_path.write_text(primary_xml, encoding="utf-8")
    print(f"  Saved primary sitemap to {primary_path} ({len(primary_xml)} bytes)")

    # ----- Step 2: gather all URLs (recursively follow sitemapindex) -----
    sub_sitemaps, page_urls = parse_sitemap_urls(primary_xml)
    all_urls: list[str] = list(page_urls)

    if sub_sitemaps:
        # Heuristic: pick sub-sitemaps likely to contain product pages.
        # Save list of all sub-sitemaps; fetch product-related ones.
        product_subs = [
            s
            for s in sub_sitemaps
            if any(
                kw in s.lower()
                for kw in ("product", "catalog", "item", "goods")
            )
        ]
        if not product_subs:
            # No obvious product subs - fetch all (capped to avoid abuse)
            product_subs = sub_sitemaps[:5]

        print(
            f"\n  Fetching {len(product_subs)} sub-sitemap(s) "
            f"(out of {len(sub_sitemaps)} total)..."
        )
        for i, sub in enumerate(product_subs):
            goldapple_pause()
            r = fetch(sub)
            if r is None or r.status_code != 200 or not is_xml_sitemap(r.text):
                print(f"  (skipping {sub} - bad response)")
                continue
            # Save first sub for evidence; concat URLs for analysis
            if i == 0:
                sub_path = OUT / "goldapple-sitemap-products.xml"
                sub_path.write_text(r.text, encoding="utf-8")
                print(f"  Saved first sub-sitemap to {sub_path}")
            _, sub_urls = parse_sitemap_urls(r.text)
            all_urls.extend(sub_urls)

    print(f"\n=== Total page URLs gathered: {len(all_urls)} ===")
    if not all_urls:
        print("  No URLs extracted - sitemap may have unusual structure.")

    # Show sample for diagnostics
    print("Sample URLs:")
    for u in all_urls[:5]:
        print(f"  {u}")

    # ----- Step 3: per-brand counts (substring match on URL) -----
    per_brand: dict[str, dict] = {}
    for brand, slugs in SELECTED_BRANDS.items():
        matched: list[str] = []
        used_slug: str | None = None
        for slug in slugs:
            hits = [u for u in all_urls if slug.lower() in u.lower()]
            if hits and (not matched or len(hits) > len(matched)):
                matched = hits
                used_slug = slug
        per_brand[brand] = {
            "url_count": len(matched),
            "source": "sitemap" if matched else "sitemap-no-match",
            "matched_slug": used_slug,
            "tried_slugs": slugs,
            "sample_urls": matched[:3],
            "notes": (
                "no URLs matched any candidate slug - manual goldapple-slug "
                "verification needed during Phase 3"
                if not matched
                else "matched on substring of sitemap URL"
            ),
        }
        print(
            f"  {brand}: {len(matched)} URLs "
            f"(slug={used_slug!r})"
        )

    # ----- Step 4: save -----
    out_json = OUT / "page-volume-raw.json"
    payload = {
        "_meta": {
            "primary_sitemap_url": primary_url,
            "total_urls_in_sitemap": len(all_urls),
            "method": "sitemap.xml + substring slug match",
            "fetched_at": "2026-05-05",
            "rate_limit_honored": "3-5s random uniform between fetches",
        },
        **per_brand,
    }
    out_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  Saved {out_json}")
    print("DONE.")


if __name__ == "__main__":
    main()
