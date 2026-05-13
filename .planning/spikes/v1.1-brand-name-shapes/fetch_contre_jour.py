"""Fetch viled Frederic Malle / Contre-Jour PDP for Bug #3 fixture.

Item id 408872 located via existing viled-catalog-women-1310-page1.html fixture.
URL guessing: viled.kz/women/item/<id>/<slug>  (mirror of existing
viled-pdp-407682.html which encodes id 407682 of women/item URL).
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from curl_cffi import requests

CANDIDATES = [
    "https://viled.kz/women/item/408872",
    "https://viled.kz/women/item/408872/",
    "https://viled.kz/zhenshchinam/item/408872",
    "https://viled.kz/perfumery/item/408872",
]

for url in CANDIDATES:
    try:
        r = requests.get(url, impersonate="chrome", timeout=30, allow_redirects=True)
        print(f"  {r.status_code:>3}  len={len(r.text):>7}  final={r.url}", file=sys.stderr)
        if r.status_code == 200 and len(r.text) > 50_000 and "Contre" in r.text:
            out = Path(__file__).resolve().parent / "viled-contre-jour-408872.html"
            out.write_text(r.text, encoding="utf-8")
            print(f"  WROTE {out}", file=sys.stderr)
            sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {url}: {exc}", file=sys.stderr)

print("FAIL — no candidate URL worked", file=sys.stderr)
sys.exit(1)
