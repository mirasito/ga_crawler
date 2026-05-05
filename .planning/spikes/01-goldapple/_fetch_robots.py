"""One-shot fetcher for robots.txt of viled.kz and goldapple.kz.

RECON-04 / plan 01-04, Task 1.

Uses curl_cffi with impersonate="chrome" (project standard per CLAUDE.md
Anti-Bot Strategy + PITFALLS.md Pitfall 1). Bare `requests` is forbidden —
goldapple.kz may block urllib3 TLS fingerprint even on robots.txt.

Conservative 5-second pause between fetches (Pitfall 13).

Saves snapshots to .planning/spikes/01-goldapple/sample-payloads/ for
audit-trail / drift detection.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_fetch_robots.py
"""

import time
from pathlib import Path

from curl_cffi import requests

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
OUT.mkdir(parents=True, exist_ok=True)

# (label, url) — label drives output filename.
# viled.kz: try www first (per plan note re www vs apex); save the one returning content.
TARGETS = [
    ("viled-kz", "https://viled.kz/robots.txt"),
    ("viled-kz-www", "https://www.viled.kz/robots.txt"),
    ("goldapple-kz", "https://goldapple.kz/robots.txt"),
]

for name, url in TARGETS:
    print(f"Fetching {url} ...")
    try:
        r = requests.get(url, impersonate="chrome", timeout=30, allow_redirects=True)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        time.sleep(5)
        continue

    print(
        f"  HTTP {r.status_code}, {len(r.content)} bytes, "
        f"content-type={r.headers.get('content-type', '?')}, "
        f"final_url={r.url}"
    )
    out_file = OUT / f"{name}-robots.txt"
    out_file.write_bytes(r.content)
    print(f"  Saved to {out_file}")

    time.sleep(5)

print("Done.")
