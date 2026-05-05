"""Compute final page-volume estimate from saved sitemap corpus.

Reads goldapple-all-urls.txt (already saved), classifies URLs, and produces
a corrected page-volume-raw.json with:

- Catalog-wide numeric-product URL count (real SKU pages)
- Brand-page facet counts per selected brand (sub-categories within /brands/<slug>)
- Average products-per-brand catalog-wide (key Phase 3 anchor)

Per CLAUDE.md: no production code, no bare `requests` (we use saved data only).

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_compute_pagevolume.py
"""

import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
ALL_URLS_FILE = OUT / "goldapple-all-urls.txt"

SELECTED_BRANDS = {
    "Jo Malone London": "jo-malone-london",
    "Tom Ford": "tom-ford",
    "Creed": "creed",
    "Frederic Malle": "frederic-malle",
    "Givenchy": "givenchy",
}


def classify_url(url: str) -> str:
    p = url.replace("https://goldapple.kz/", "").rstrip("/")
    if not p:
        return "root"
    seg0 = p.split("/")[0]
    if re.match(r"^\d{7,}-", seg0):
        return "product-numeric"  # actual SKU page
    if seg0 == "brands":
        return "brand-page" if "/" in p[7:] else "brand-root"
    if seg0 == "s":
        return "short-slug"
    if seg0 == "f":
        return "facet-snapshot"
    return f"category:{seg0}"


def main() -> None:
    if not ALL_URLS_FILE.exists():
        print(f"FATAL: {ALL_URLS_FILE} not found. Run _fetch_sitemap_pagevolume.py first.")
        return

    all_urls = ALL_URLS_FILE.read_text(encoding="utf-8").splitlines()
    print(f"Total URLs: {len(all_urls)}")

    classes = Counter(classify_url(u) for u in all_urls)
    print("\nURL class distribution:")
    for cls, c in classes.most_common():
        pct = 100 * c / len(all_urls)
        print(f"  {c:>6}  ({pct:5.1f}%)  {cls}")

    product_urls = [u for u in all_urls if classify_url(u) == "product-numeric"]

    # Distinct brand slugs in /brands/* universe
    brand_slug_counts: Counter = Counter()
    for u in all_urls:
        m = re.match(r"^https://goldapple\.kz/brands/([^/?#]+)(/.*)?$", u)
        if m:
            brand_slug_counts[m.group(1)] += 1

    distinct_brands = len(brand_slug_counts)
    print(f"\nDistinct brand slugs in /brands/*: {distinct_brands}")

    # Per-brand facet counts (sitemap entries under /brands/<slug>)
    per_brand: dict[str, dict] = {}
    for brand, slug in SELECTED_BRANDS.items():
        re_brand = re.compile(rf"^https://goldapple\.kz/brands/{re.escape(slug)}(/|\?|$)")
        facet_urls = [u for u in all_urls if re_brand.match(u)]

        # Count product URLs that contain the slug-keyword (heuristic, not exact)
        slug_kw = slug.split("-")[0] if "-" in slug else slug
        # Use first two segments for tighter match (e.g., 'tom-ford' not 'tom')
        kw_match = slug if "-" in slug else slug
        product_keyword_hits = [u for u in product_urls if kw_match in u.lower()]

        per_brand[brand] = {
            "slug": slug,
            "url_count": len(facet_urls),
            "source": "sitemap",
            "method": "/brands/<slug>* facet count from sitemap-1/2/3.xml",
            "product_keyword_hits": len(product_keyword_hits),
            "notes": (
                "Facet count = brand sub-category pages indexed in sitemap "
                "(not SKU count). Real SKU count per brand requires fetching "
                "brand listing page (JS-gated; deferred to 01-08 warm-Patchright)."
                if len(facet_urls) > 1
                else "Brand has minimal sitemap presence — likely most products "
                "indexed under category routes rather than /brands/<slug>. "
                "Refer to product_keyword_hits as backup signal."
            ),
            "facet_url_sample": facet_urls[:3],
        }

    # Aggregates
    facet_counts = [v["url_count"] for v in per_brand.values()]
    facet_counts_sorted = sorted(facet_counts)
    n = len(facet_counts_sorted)
    median = (
        facet_counts_sorted[n // 2]
        if n % 2 == 1
        else (facet_counts_sorted[n // 2 - 1] + facet_counts_sorted[n // 2]) / 2
    )

    aggregates = {
        "total_urls_in_sitemap": len(all_urls),
        "product_numeric_urls_total": len(product_urls),
        "distinct_brand_slugs_in_sitemap": distinct_brands,
        "catalog_wide_avg_products_per_brand": round(
            len(product_urls) / distinct_brands, 1
        ),
        "selected_brands_count": len(per_brand),
        "selected_brands_facet_total": sum(facet_counts),
        "selected_brands_facet_avg": round(sum(facet_counts) / n, 1),
        "selected_brands_facet_min": min(facet_counts),
        "selected_brands_facet_median": median,
        "selected_brands_facet_max": max(facet_counts),
    }

    payload = {
        "_meta": {
            "primary_sitemap_url": "https://goldapple.kz/sitemap.xml",
            "sub_sitemaps": [
                "https://goldapple.kz/sitemap-1.xml",
                "https://goldapple.kz/sitemap-2.xml",
                "https://goldapple.kz/sitemap-3.xml",
            ],
            "method_primary": "sitemap.xml + classify by URL pattern",
            "method_secondary": "n/a (sitemap reachable plain)",
            "fetched_at": "2026-05-05",
            "rate_limit_honored": "3-5s random uniform between fetches",
            "key_finding": (
                "goldapple.kz sitemap.xml IS reachable plain via curl_cffi "
                "impersonate=chrome (HTTP 200, no JS-challenge). This is "
                "significantly different from HTML routes (per 01-04). "
                "Total catalog ~100,779 numeric-id product URLs across 1,461 "
                "brand slugs."
            ),
            "important_caveat": (
                "Per-brand facet count (the 'url_count' field) reflects "
                "/brands/<slug>* sitemap entries (catalog sub-views), NOT SKU "
                "count. Actual SKU count per brand requires rendering brand "
                "listing pages, which are JS-gated. Defer real SKU counts to "
                "plan 01-08 warm-Patchright session."
            ),
        },
        "aggregates": aggregates,
        "per_brand": per_brand,
    }

    out_json = OUT / "page-volume-raw.json"
    out_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved {out_json}")

    print("\n=== SUMMARY ===")
    print(f"Total URLs in sitemap: {aggregates['total_urls_in_sitemap']:,}")
    print(f"Numeric-id product URLs: {aggregates['product_numeric_urls_total']:,}")
    print(f"Distinct brand slugs: {aggregates['distinct_brand_slugs_in_sitemap']:,}")
    print(
        f"Catalog-wide average products/brand: "
        f"{aggregates['catalog_wide_avg_products_per_brand']}"
    )
    print()
    print("Selected brands (facet counts from sitemap /brands/<slug>*):")
    for brand, v in per_brand.items():
        print(
            f"  {brand} ({v['slug']}): {v['url_count']} facets, "
            f"{v['product_keyword_hits']} product-numeric URLs containing slug"
        )


if __name__ == "__main__":
    main()
