"""Scan saved ToS-candidate HTML files for anti-scraping clauses.

RECON-04 / plan 01-04, Task 2.

Reads HTML files saved by _fetch_tos.py, extracts visible text, searches
for relevant keywords (RU + EN), prints contextual snippets.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_scan_tos.py
"""

import re
from pathlib import Path

SAMPLES = Path(".planning/spikes/01-goldapple/sample-payloads")

KEYWORDS = [
    # English
    "scrap", "crawl", "crawler", "robot", "bots", "automated", "automation",
    "third-party", "third party", "competitive", "intellectual property",
    "prohibit", "agree",
    # Russian (cosmetics/legal terms)
    "автоматиз", "парсин", "ботов", "бота", "робот",
    "конкурент", "сравнен", "интеллектуальн",
    "запрещ", "не допуск",
    "оферт", "политик", "согласи", "пользователь",
    "персональн", "конфиденц",
    "третьим лицам", "третьи лиц",
]


def scan(path: Path) -> None:
    raw = path.read_bytes()
    print(f"\n=== {path.name} ({len(raw)} bytes) ===")

    # Charset
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    declared = m.group(1).decode() if m else "none"
    print(f"declared charset: {declared}")

    text = raw.decode("utf-8", errors="replace")

    # Title
    mt = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    title = mt.group(1).strip() if mt else "(none)"
    print(f"title: {title[:200]}")

    # Strip <script>, <style>, then tags
    clean = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style[^>]*>.*?</style>", " ", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    print(f"visible-text length: {len(clean)}")

    if len(clean) < 200:
        print("  (too short — almost certainly an SPA shell, no real content)")
        print(f"  preview: {clean[:200]!r}")
        return

    print(f"  preview (first 400 chars): {clean[:400]}")

    # Keyword scan
    cl = clean.lower()
    for kw in KEYWORDS:
        kwl = kw.lower()
        if kwl in cl:
            idx = cl.find(kwl)
            ctx = clean[max(0, idx - 80) : idx + 200]
            print(f"  HIT [{kw}]: ...{ctx}...")


for f in sorted(SAMPLES.glob("*.html")):
    scan(f)
