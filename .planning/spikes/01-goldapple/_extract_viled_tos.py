"""Extract viled.kz Privacy Policy content from __NEXT_DATA__ blob.

RECON-04 / plan 01-04, Task 2.

viled.kz is a Next.js SPA. The /privacy page returns 216 KB HTML with the
real text content embedded in a <script id="__NEXT_DATA__"> JSON blob.
This script extracts that blob, decodes the HTML content, and saves it
as plain text for reading + audit-trail.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_extract_viled_tos.py
"""

import json
import re
from html import unescape
from pathlib import Path

SAMPLES = Path(".planning/spikes/01-goldapple/sample-payloads")
SRC = SAMPLES / "viled-privacy.html"
OUT_TXT = SAMPLES / "viled-privacy.txt"
OUT_JSON = SAMPLES / "viled-privacy-nextdata.json"

raw = SRC.read_bytes().decode("utf-8")

m = re.search(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    raw,
    re.DOTALL,
)
if not m:
    raise SystemExit("__NEXT_DATA__ block not found")

data = json.loads(m.group(1))
OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved __NEXT_DATA__ JSON -> {OUT_JSON} ({OUT_JSON.stat().st_size} bytes)")

# Extract the privacy-policy content
pp = data["props"]["pageProps"]
print(f"page type: {pp.get('type')}")

content = pp["content"]
title = content.get("title", "")
html_body = content.get("content", "")

# Strip HTML tags from the body to get plain text
plain = re.sub(r"<[^>]+>", "\n", html_body)
plain = unescape(plain)
plain = re.sub(r"\n{3,}", "\n\n", plain).strip()

OUT_TXT.write_text(f"# {title}\n\n{plain}\n", encoding="utf-8")
print(f"Saved plain-text privacy policy -> {OUT_TXT} ({OUT_TXT.stat().st_size} bytes)")
print(f"\nTitle: {title}")
print(f"Plain-text length: {len(plain)} chars")
print(f"\n--- First 600 chars ---\n{plain[:600]}\n")

# Search for anti-scraping / automated-access / IP-related keywords
keywords = [
    "автоматизирован", "автоматическ", "парсин", "парс",
    "робот", "бот", "ботов", "scraping", "scrap", "crawl",
    "конкурент", "сравнение цен", "сравнен",
    "интеллектуальн", "авторск",
    "запрещ", "не допуск",
    "третьи лиц", "третьим лиц",
    "agent", "user-agent",
    "права", "лицензи",
]
print("\n--- Keyword scan ---")
for kw in keywords:
    idx = plain.lower().find(kw.lower())
    if idx >= 0:
        ctx = plain[max(0, idx - 100) : idx + 300]
        ctx = re.sub(r"\s+", " ", ctx).strip()
        print(f"\nHIT [{kw}]:\n  ...{ctx}...")
