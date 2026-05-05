"""Side-deliverable: inspect viled product __NEXT_DATA__ shape for Phase 2 hot-start.

Plan 01-07 RECON-02 + CONTEXT.md "Не обсуждали явно" specifies that we
opportunistically capture JSON-LD/__NEXT_DATA__ schema for Phase 2 PARSE-02.

This script:
  1. Fetches ONE viled product page (the first URL from viled-product-urls.txt).
  2. Extracts the __NEXT_DATA__ JSON blob.
  3. Walks the structure and reports which keys hold price/title/brand/volume —
     the canonical fields needed by Phase 2 PARSE-02.
  4. Saves a redacted (compact) extract sample for the MEMO appendix.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_inspect_viled_nextdata.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from curl_cffi import requests

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
URLS_FILE = OUT / "viled-product-urls.txt"

PRICE_KEY_PATTERNS = re.compile(r"price|cost|amount", re.IGNORECASE)
BRAND_KEY_PATTERNS = re.compile(r"brand", re.IGNORECASE)
TITLE_KEY_PATTERNS = re.compile(r"^(name|title|productName|itemName)$", re.IGNORECASE)
VOLUME_KEY_PATTERNS = re.compile(r"volume|size|capacity", re.IGNORECASE)
CURRENCY_KEY_PATTERNS = re.compile(r"currency", re.IGNORECASE)


def walk(obj, path: str, hits: dict[str, list[tuple[str, object]]]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else k
            if PRICE_KEY_PATTERNS.search(k):
                hits["price"].append((sub, v))
            if BRAND_KEY_PATTERNS.search(k):
                hits["brand"].append((sub, v))
            if TITLE_KEY_PATTERNS.match(k):
                hits["title"].append((sub, v))
            if VOLUME_KEY_PATTERNS.search(k):
                hits["volume"].append((sub, v))
            if CURRENCY_KEY_PATTERNS.search(k):
                hits["currency"].append((sub, v))
            walk(v, sub, hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]", hits)


def main() -> int:
    urls = [u.strip() for u in URLS_FILE.read_text(encoding="utf-8").splitlines() if u.strip()]
    if not urls:
        print("ERROR: no URLs available; run _fetch_viled_urls.py first.")
        return 1
    target = urls[0]
    print(f"Fetching {target} for __NEXT_DATA__ inspection ...")
    r = requests.get(target, impersonate="chrome", timeout=30)
    print(f"  HTTP {r.status_code}, {len(r.content)} bytes")
    if r.status_code != 200:
        print("  non-200, abort")
        return 2

    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r.text,
        re.DOTALL,
    )
    if not m:
        print("  __NEXT_DATA__ not found")
        return 3
    raw = m.group(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  __NEXT_DATA__ JSON parse error: {e}")
        return 4

    print(f"  __NEXT_DATA__ parsed: top-level keys = {list(data.keys())}")
    if "props" in data:
        print(f"  data['props'] keys: {list(data['props'].keys())}")
        if "pageProps" in data["props"]:
            print(f"  data['props']['pageProps'] keys: {list(data['props']['pageProps'].keys())[:30]}")

    hits: dict[str, list] = {
        "price": [], "brand": [], "title": [], "volume": [], "currency": [],
    }
    walk(data, "", hits)

    # Print first 5 examples per category
    print()
    for cat, items in hits.items():
        print(f"=== {cat} hits: {len(items)} ===")
        for path, value in items[:5]:
            v_repr = json.dumps(value, ensure_ascii=False) if not isinstance(value, (dict, list)) else f"<{type(value).__name__} keys/len={len(value)}>"
            if len(v_repr) > 120:
                v_repr = v_repr[:117] + "..."
            print(f"  {path}: {v_repr}")
        print()

    # Save compact sample of pageProps for MEMO appendix
    sample: dict = {"url": target, "next_data_top_keys": list(data.keys())}
    if "props" in data and "pageProps" in data["props"]:
        page_props = data["props"]["pageProps"]
        # Save a slim version: top-level keys + a compact preview
        slim = {}
        for k, v in page_props.items():
            if isinstance(v, dict):
                slim[k] = {"_type": "dict", "keys": list(v.keys())[:20]}
            elif isinstance(v, list):
                slim[k] = {"_type": "list", "len": len(v),
                           "sample_first": v[0] if v and not isinstance(v[0], (dict, list)) else
                           (list(v[0].keys())[:20] if v and isinstance(v[0], dict) else None)}
            else:
                v_str = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                slim[k] = v_str[:200] if isinstance(v_str, str) else v_str
        sample["pageProps_shape"] = slim

    # Also extract the price field paths and example values
    sample["price_field_paths"] = [
        {"path": p, "value": (v if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>")}
        for p, v in hits["price"][:20]
    ]
    sample["brand_field_paths"] = [
        {"path": p, "value": (v if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>")}
        for p, v in hits["brand"][:10]
    ]
    sample["title_field_paths"] = [
        {"path": p, "value": (v if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>")}
        for p, v in hits["title"][:10]
    ]
    sample["currency_field_paths"] = [
        {"path": p, "value": (v if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>")}
        for p, v in hits["currency"][:10]
    ]

    out_path = OUT / "viled-nextdata-shape.json"
    out_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Saved shape extract to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
