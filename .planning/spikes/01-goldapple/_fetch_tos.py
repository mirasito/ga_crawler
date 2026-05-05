"""Fetch ToS pages for viled.kz and goldapple.kz to find anti-scraping clauses.

RECON-04 / plan 01-04, Task 2.

Strategy:
1. Try a list of common ToS slugs for each site.
2. For successful fetches, save snapshot to sample-payloads/.
3. Print a short search for relevant terms (scraping, automated, robot, etc.).
4. If a candidate URL returns 403/empty/Cloudflare-shell — log it; document
   the gap in tos-audit.md (per plan 01-04 guidance, do NOT escalate to
   Patchright for ToS — that's overkill).

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_fetch_tos.py
"""

import re
import time
from pathlib import Path

from curl_cffi import requests

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
OUT.mkdir(parents=True, exist_ok=True)

# Common ToS / Terms / Условия использования slugs.
CANDIDATES: list[tuple[str, str]] = [
    # viled.kz (likely Magento-based with Russian slugs)
    ("viled-terms", "https://viled.kz/terms"),
    ("viled-usloviya", "https://viled.kz/usloviya"),
    ("viled-soglashenie", "https://viled.kz/soglashenie"),
    ("viled-polzovatelskoe-soglashenie", "https://viled.kz/polzovatelskoe-soglashenie"),
    ("viled-publichnaya-oferta", "https://viled.kz/publichnaya-oferta"),
    ("viled-oferta", "https://viled.kz/oferta"),
    ("viled-privacy", "https://viled.kz/privacy"),
    ("viled-privacy-policy", "https://viled.kz/privacy-policy"),
    # goldapple.kz
    ("goldapple-rules", "https://goldapple.kz/rules"),
    ("goldapple-terms", "https://goldapple.kz/terms"),
    ("goldapple-usloviya", "https://goldapple.kz/usloviya"),
    ("goldapple-oferta", "https://goldapple.kz/oferta"),
    ("goldapple-publichnaya-oferta", "https://goldapple.kz/publichnaya-oferta"),
    ("goldapple-polzovatelskoe-soglashenie", "https://goldapple.kz/polzovatelskoe-soglashenie"),
    ("goldapple-privacy", "https://goldapple.kz/privacy"),
    ("goldapple-privacy-policy", "https://goldapple.kz/privacy-policy"),
    ("goldapple-confidentiality", "https://goldapple.kz/confidentiality"),
    ("goldapple-soglashenie", "https://goldapple.kz/soglashenie"),
]

# Keywords (RU + EN) we care about for anti-scraping clauses.
KEYWORDS = [
    "scrap", "crawl", "robot", "автоматизирован", "автоматическ", "парсин",
    "ботов", "бота", "bots", "agent", "конкурентн", "сравнени",
    "competitive", "third-party", "third party", "third-parties",
    "запрещ", "prohibited", "интеллектуальн", "intellectual",
    "agree", "согласи", "лицензи", "license",
]

results: list[dict] = []

for label, url in CANDIDATES:
    try:
        r = requests.get(url, impersonate="chrome", timeout=30, allow_redirects=True)
    except Exception as e:
        print(f"[ERR ] {url}: {type(e).__name__}: {e}")
        time.sleep(3)
        continue

    status = r.status_code
    body = r.content
    final = r.url
    text_len = len(body)
    ct = r.headers.get("content-type", "?")

    # Save HTML if status==200 AND not tiny (CF challenge pages are usually <2KB).
    if status == 200 and text_len > 1500:
        out_file = OUT / f"{label}.html"
        out_file.write_bytes(body)
        # Extract visible text via crude tag-strip for keyword scan
        text_lower = re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace")).lower()
        hits = sorted({k for k in KEYWORDS if k in text_lower})
        print(f"[ OK ] {url} -> HTTP {status}, {text_len}B, ct={ct}, final={final}")
        print(f"        saved {out_file.name}, keyword hits: {hits}")
        results.append({
            "label": label,
            "url": url,
            "final_url": final,
            "status": status,
            "size": text_len,
            "file": out_file.name,
            "keyword_hits": hits,
        })
    else:
        print(f"[SKIP] {url} -> HTTP {status}, {text_len}B (not saved)")

    time.sleep(3)

print("\n=== Summary of saved ToS-candidate pages ===")
for r in results:
    print(
        f"  {r['label']:50s} status={r['status']} size={r['size']:>6d} "
        f"hits={r['keyword_hits']}"
    )

print(f"\nTotal saved: {len(results)}")
