"""Quick probe: viled.kz brands listing for plan 01-05 brand-selection.

Plan 01-05 Task 1 (checkpoint:human-action) is normally a manual visual sample
of viled.kz top-10 brands. To honor the user's YOLO preference and avoid a
hard human-blocking checkpoint, this script attempts an autonomous probe of
the viled.kz brands page first. If successful, we use observed brands; if not,
we fall back to the default list documented in plan_context (justified mix of
luxury and mass-market international brands present in 2026 KZ market).

Honor committed rate-limit: viled.kz = 2s sequential.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_fetch_viled_brands.py
"""

import re
import time
from pathlib import Path

from curl_cffi import requests
from selectolax.parser import HTMLParser

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    "https://viled.kz/brands",
    "https://viled.kz/brand",
    "https://viled.kz/",
]

found_brands: list[str] = []

for url in CANDIDATES:
    print(f"Fetching {url} ...")
    try:
        r = requests.get(url, impersonate="chrome", timeout=30, allow_redirects=True)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        time.sleep(2)
        continue
    print(f"  HTTP {r.status_code}, {len(r.text)} bytes")
    if r.status_code != 200 or len(r.text) < 1000:
        time.sleep(2)
        continue

    # Save snapshot for audit
    safe_name = url.replace("https://", "").replace("/", "_").strip("_") or "root"
    snap_path = OUT / f"viled-{safe_name}.html"
    snap_path.write_text(r.text, encoding="utf-8")
    print(f"  Saved {snap_path}")

    # Look for __NEXT_DATA__ block (viled is Next.js)
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r.text,
        re.DOTALL,
    )
    if m:
        next_data = m.group(1)
        # Brand names usually appear in JSON props; harvest unique-looking strings
        # that look like brand names (Capitalized or all-caps tokens, length >=3).
        brand_candidates = re.findall(
            r'"name"\s*:\s*"([A-Z][A-Za-zА-Яа-яЁё0-9\'\-\. &]{2,50})"',
            next_data,
        )
        # de-dup, preserve order
        seen = set()
        brand_candidates = [
            b for b in brand_candidates if not (b in seen or seen.add(b))
        ]
        print(f"  Brand-name candidates from __NEXT_DATA__: {len(brand_candidates)}")
        for i, b in enumerate(brand_candidates[:30], 1):
            print(f"    {i:>2}. {b}")
        found_brands.extend(brand_candidates)

    # Also try DOM extraction — links typically /brand/<slug> on Magento/Next sites
    tree = HTMLParser(r.text)
    href_brands = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href", "")
        if "/brand/" in href or "/brands/" in href:
            text = (a.text() or "").strip()
            if text and len(text) >= 2 and len(text) < 60:
                href_brands.append(text)
    seen2 = set()
    href_brands = [b for b in href_brands if not (b in seen2 or seen2.add(b))]
    if href_brands:
        print(f"  Brand-link anchors (text): {len(href_brands)}")
        for i, b in enumerate(href_brands[:30], 1):
            print(f"    {i:>2}. {b}")
        found_brands.extend(href_brands)

    time.sleep(2)

# De-dup final list
seen3 = set()
unique = [b for b in found_brands if not (b in seen3 or seen3.add(b))]
print()
print(f"=== Aggregate unique brand candidates: {len(unique)} ===")
for i, b in enumerate(unique[:50], 1):
    print(f"  {i:>2}. {b}")
