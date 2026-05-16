"""Probe viled catalog API for SKU 335978 to inspect multi-variant shape."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from curl_cffi import requests as cffi_requests

OUT = Path("inbox/viled_335978.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

# Walk all women pages catalog 1310 page 1-100 hunting for the SKU
import time

found_item = None
for page in range(1, 100):
    r = cffi_requests.get(
        f"https://viled.kz/api/viled-catalog/v2/items/content?gender=women&catalogId=1310&page={page}&pageSize=60",
        impersonate="chrome", timeout=20,
    )
    if r.status_code != 200:
        time.sleep(0.5)
        continue
    try:
        data = r.json()
    except Exception:
        continue
    items = data.get("content", []) or []
    for item in items:
        if item.get("id") == 335978:
            found_item = item
            print(f"FOUND on page {page}")
            break
    if found_item:
        break
    time.sleep(0.2)

if found_item:
    OUT.write_text(json.dumps(found_item, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written to {OUT}")
    print(f"Top keys: {sorted(found_item.keys())}")
    # Print attribute structure
    attrs = found_item.get("attributes", [])
    print(f"\nattributes ({len(attrs)} items):")
    for a in attrs[:8]:
        print(f"  {a}")
    # Print price fields
    print(f"\nminPrice={found_item.get('minPrice')}, realMinPrice={found_item.get('realMinPrice')}")
    print(f"enableDiscount={found_item.get('enableDiscount')}")
else:
    print("NOT FOUND in any page")
