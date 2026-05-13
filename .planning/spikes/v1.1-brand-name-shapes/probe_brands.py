"""Quick probe: check which known indie brand slugs exist in goldapple sitemap.

Run once to validate niche-bucket keyword list against real data.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ga_crawler.enumeration.goldapple_sitemap import fetch_sitemap_slugs

PROBES = [
    "stereotype", "sago", "byredo", "le-labo", "kilian",
    "maison-crivelli", "profumum", "memo", "nasomatto",
    "amouage", "creed", "frederic-malle", "tom-ford",
    "atelier-cologne", "diptyque", "jo-malone", "issey-miyake",
    "natura-siberica", "natura-siberika",
    # RU brand probes
    "chistaya-liniya", "black-pearl", "loshadinaya-sila",
    "nevskaya-kosmetika", "sibirskie-travy",
    "fresh-juice", "agafia",
    "babuska-agafa", "babushka-agafa",
    "art-stylist", "smasciai",
    # additional luxe/multi
    "chanel", "dior", "lancome", "estee-lauder", "ysl",
    "paco-rabanne", "carolina-herrera", "narciso-rodriguez",
    "maison-margiela", "givenchy", "armani", "versace",
    "calvin-klein", "hugo", "hugo-boss", "boss",
]

slug_map = fetch_sitemap_slugs()
print(f"Total slugs: {len(slug_map)}", file=sys.stderr)

out = Path(__file__).resolve().parent / "brand-probe.txt"
lines: list[str] = []
for kw in PROBES:
    matches = [s for s in slug_map if s.startswith(kw + "-") or s == kw]
    lines.append(f"{kw:<20} {len(matches):>4}  examples: {matches[:3]}")
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote probe to {out}", file=sys.stderr)
