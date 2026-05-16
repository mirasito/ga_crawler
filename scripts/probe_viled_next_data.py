"""Extract __NEXT_DATA__ from viled PDP — full structured product data
including per-variant pricing."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

html = Path("inbox/viled_pdp_335978/pdp.html").read_text(encoding="utf-8")
m = re.search(
    r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>',
    html, re.DOTALL,
)
if not m:
    print("FAIL: __NEXT_DATA__ not found")
    sys.exit(1)

data = json.loads(m.group(1))
item = data.get("props", {}).get("pageProps", {}).get("item", {})
Path("inbox/viled_335978_next_data.json").write_text(
    json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
)

# Inspect for variant pricing
print("top keys:", sorted(item.keys()))
print()
for k in ["itemPrices", "itemPriceList", "prices", "variants", "sizes", "items", "skus"]:
    if k in item:
        v = item[k]
        print(f"{k}: type={type(v).__name__}, len={len(v) if hasattr(v, '__len__') else '?'}")
        if isinstance(v, list) and v:
            print(f"  sample[0]: {json.dumps(v[0], ensure_ascii=False)[:600]}")
            print()
