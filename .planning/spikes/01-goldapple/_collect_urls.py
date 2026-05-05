"""Collect 100 goldapple product URLs for plan 01-08 Camoufox 100-fetch run.

Strategy:
1. Filter sitemap to product-id URLs (pattern: /<digits>-<slug>).
2. Take brand-keyword matches (givenchy/creed/frederic/tom-ford/jo-malone) —
   first 25 each.
3. Top up with random product URLs from sitemap until 100, deterministic seed.
"""
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SITEMAP = ROOT / ".planning" / "spikes" / "01-goldapple" / "sample-payloads" / "goldapple-all-urls.txt"
OUT = ROOT / ".planning" / "spikes" / "01-goldapple" / "sample-payloads" / "goldapple-product-urls.txt"

PRODUCT_RE = re.compile(r"^https://goldapple\.kz/\d+-")
BRAND_KEYWORDS = ["givenchy", "creed", "frederic", "tom-ford", "jo-malone"]


def main() -> None:
    all_urls = [
        line.strip()
        for line in SITEMAP.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    products = [u for u in all_urls if PRODUCT_RE.match(u)]
    print(f"Total product URLs in sitemap: {len(products)}")

    selected: list[str] = []
    for kw in BRAND_KEYWORDS:
        matches = [u for u in products if kw in u.lower()]
        head = matches[:25]
        selected.extend(head)
        print(f"  {kw}: {len(matches)} sitemap matches (took {len(head)})")

    selected = list(dict.fromkeys(selected))
    print(f"After brand-match + dedup: {len(selected)}")

    if len(selected) < 100:
        rng = random.Random(20260506)
        pool = [u for u in products if u not in selected]
        rng.shuffle(pool)
        need = 100 - len(selected)
        topup = pool[:need]
        selected.extend(topup)
        print(f"  + topped up with {len(topup)} random product URLs")

    selected = selected[:100]
    OUT.write_text("\n".join(selected) + "\n", encoding="utf-8")
    print(f"Wrote {len(selected)} URLs to {OUT}")


if __name__ == "__main__":
    main()
