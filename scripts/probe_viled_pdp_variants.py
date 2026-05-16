"""Find viled PDP API that returns per-variant pricing for multi-size SKU."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from curl_cffi import requests as cffi_requests

OUT = Path("inbox/viled_pdp_335978")
OUT.mkdir(parents=True, exist_ok=True)
SKU = 335978

# Try several plausible endpoints based on viled site structure
candidates = [
    f"https://viled.kz/api/viled-catalog/v2/items/{SKU}",
    f"https://viled.kz/api/viled-catalog/items/{SKU}",
    f"https://viled.kz/api/viled-item/{SKU}",
    f"https://viled.kz/api/viled-catalog/v2/items/content/{SKU}",
    f"https://viled.kz/api/viled-catalog/v2/item/{SKU}",
    f"https://viled.kz/api/viled-product/v2/{SKU}",
    f"https://viled.kz/api/viled-catalog/v2/items/{SKU}/details",
    f"https://viled.kz/api/viled-catalog/v2/items/{SKU}/variants",
    f"https://viled.kz/api/viled-catalog/v2/items/{SKU}/sizes",
]

for url in candidates:
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=15)
    except Exception as e:
        print(f"{url}\n  ERROR: {e}\n")
        continue
    status = r.status_code
    size = len(r.content)
    body_preview = r.content[:200].decode("utf-8", errors="replace")
    print(f"{url}\n  status={status} size={size} preview={body_preview!r}\n")
    if status == 200 and size > 100:
        try:
            data = r.json()
            (OUT / f"{url.rsplit('/', 1)[-1]}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            (OUT / f"{url.rsplit('/', 1)[-1]}.bin").write_bytes(r.content)
    time.sleep(0.3)

# Also try fetching the PDP HTML page and look for backing data
pdp_url = f"https://viled.kz/item/{SKU}"
try:
    r = cffi_requests.get(pdp_url, impersonate="chrome", timeout=20)
    print(f"\nPDP HTML: status={r.status_code} size={len(r.content)}")
    if r.status_code == 200:
        (OUT / "pdp.html").write_text(r.text, encoding="utf-8")
        # Hunt for prices in the HTML
        import re
        # Look for any JSON-like structure with prices
        m = re.search(r'(\{[^}]{0,200}?"price"[^}]{0,500})', r.text)
        if m:
            print(f"price-mention: {m.group(1)[:400]}")
except Exception as e:
    print(f"PDP error: {e}")
