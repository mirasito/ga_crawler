"""Final URL curation for Plan 08-01 Task 1.

Fetches sitemap, picks specific URLs by slug pattern, writes the 30-URL
literal to sampled-urls.py.snippet for paste into capture.py.

Forced pins:
  - 'stereotype' + 'sago' slugs    -> Bug #1 + Bug #2 shape source
  - 'armani-code' slug             -> Bug #2 shape source
  - 'frederic-malle-contre-jour'   -> Bug #3 viled fixture handled separately (NOT in goldapple capture)

Buckets revised for real goldapple.kz/KZ inventory:
  - Lux         (6): creed x3, dior x2, frederic-malle x1   (Bucket 1 "lux" semantics)
  - Mass        (6): armani-code FORCED + armani x1 + givenchy x2 + hugo x1 + boss x1
  - Niche       (6): stereotype x3 (incl. STEREOTYPE-flow) + sago FORCED + byredo + memo
  - RU          (6): black-pearl x3 + natura-siberica x2 + sibirskie-travy x1
  - Multi-word  (6): maison-margiela x2 + calvin-klein x2 + carolina-herrera x1 + kilian-paris x1
"""

from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ga_crawler.enumeration.goldapple_sitemap import fetch_sitemap_slugs

slug_map = fetch_sitemap_slugs()


def pick(prefix: str, *, limit: int = 999, must_include: list[str] | None = None) -> list[tuple[str, str]]:
    """Return [(slug, url)] for slugs starting with prefix; must_include slugs come first."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    must = must_include or []
    for s in must:
        if s in slug_map and s not in seen:
            out.append((s, slug_map[s][0]))
            seen.add(s)
    for slug, urls in slug_map.items():
        if slug in seen:
            continue
        if slug.startswith(prefix + "-") or slug == prefix:
            out.append((slug, urls[0]))
            seen.add(slug)
        if len(out) >= limit:
            break
    return out[:limit]


def pick_multi(prefixes: list[str], limit: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for pref in prefixes:
        out.extend(pick(pref, limit=limit - len(out)))
        if len(out) >= limit:
            break
    return out[:limit]


sampled: dict[str, list[tuple[str, str]]] = {
    "lux": pick_multi(["creed", "dior", "frederic-malle"], limit=6),
    "mass": (
        pick("armani", limit=2, must_include=["armani-code"])
        + pick_multi(["givenchy", "hugo", "boss"], limit=4)
    )[:6],
    "niche": pick_multi(
        ["stereotype", "sago", "byredo", "kilian", "memo"], limit=6
    ),
    "ru": pick_multi(["black-pearl", "natura-siberica", "sibirskie-travy"], limit=6),
    "multi": pick_multi(
        ["maison-margiela", "calvin-klein", "carolina-herrera", "kilian"],
        limit=6,
    ),
}

# Deduplicate across buckets (kilian appears in both niche and multi).
seen: set[str] = set()
for bucket_name in ["lux", "mass", "niche", "ru", "multi"]:
    keep: list[tuple[str, str]] = []
    for slug, url in sampled[bucket_name]:
        if slug in seen:
            continue
        seen.add(slug)
        keep.append((slug, url))
    sampled[bucket_name] = keep

print("Per-bucket:", file=sys.stderr)
for bn, items in sampled.items():
    print(f"  {bn:<6} {len(items)}/6", file=sys.stderr)

bucket_labels = {
    "lux": "Bucket 1: Lux (Creed / Dior / Frederic Malle)",
    "mass": "Bucket 2: Mass-market (Armani [armani-code FORCED Bug#2] / Givenchy / Hugo / Boss)",
    "niche": "Bucket 3: Niche (STEREOTYPE [Bug#1+#2 FORCED] / sago [FORCED] / Byredo / Kilian / Memo)",
    "ru": "Bucket 4: RU-brands (Black Pearl / Natura Siberica / Sibirskie Travy)",
    "multi": "Bucket 5: Multi-word (Maison Margiela / Calvin Klein / Carolina Herrera / Kilian-Paris)",
}

lines: list[str] = ["URLS: list[tuple[str, str]] = ["]
for bn in ["lux", "mass", "niche", "ru", "multi"]:
    lines.append(f"    # ---- {bucket_labels[bn]}")
    for slug, url in sampled[bn]:
        tag = f"{bn}-{slug[:48]}"
        lines.append(f"    ({tag!r}, {url!r}),")
lines.append("]")
total = sum(len(v) for v in sampled.values())
lines.append(f"# Total sampled: {total}/30")

out = Path(__file__).resolve().parent / "sampled-urls.py.snippet"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"\nTotal: {total}/30 -> {out}", file=sys.stderr)
