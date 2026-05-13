"""One-shot URL sampler for Plan 08-01 Task 1.

Fetches goldapple.kz/sitemap.xml + 3 sub-sitemaps via the existing
curl_cffi helper, buckets product URLs by slug-prefix keyword (5 buckets
per D-801), randomly samples 6 per bucket, and prints a Python literal
suitable for direct paste into capture.py.

Run with:
    uv run python .planning/spikes/v1.1-brand-name-shapes/sample_urls.py

The script does NOT modify capture.py — orchestrator copies its output
into the URLS list manually after operator inspection.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ga_crawler.enumeration.goldapple_sitemap import fetch_sitemap_slugs  # noqa: E402

# Slug-prefix keywords per CONTEXT.md D-801 bucket definitions.
# A URL is assigned to the FIRST bucket (iteration order below) whose keyword
# matches the slug — so put multi-word brands FIRST so they claim Tom Ford /
# Maison Margiela before lux gets them.
BUCKETS: dict[str, list[str]] = {
    "multi": [
        # Multi-word brand tests for _strip_brand_prefix fallback. Claim
        # Tom Ford / Maison Margiela first (most common multi-word brands in
        # goldapple); fall back to single-word multi-token brands.
        "tom-ford", "maison-margiela",
        "jo-malone", "jo-malone-london", "atelier-cologne",
        "by-kilian", "kilian", "diptyque", "issey-miyake",
        "paco-rabanne", "narciso-rodriguez", "carolina-herrera",
    ],
    "niche": [
        # Niche / indie brands — bug source STEREOTYPE/sago first.
        "stereotype", "sago", "byredo", "le-labo", "maison-crivelli",
        "profumum-roma", "profumum", "memo-paris", "memo",
        "nasomatto", "escentric-molecules", "kenzo",
    ],
    "lux": [
        # High-margin SKUs likely to exhibit STEREOTYPE-style uppercase brand UI.
        "creed", "frederic-malle", "chanel", "dior",
        "amouage", "guerlain", "hermes", "lancome", "estee-lauder",
    ],
    "mass": [
        # Mass-market — Bug #2 source Armani-code first.
        "armani", "giorgio-armani", "emporio-armani",
        "givenchy", "ysl", "yves-saint-laurent", "versace",
        "calvin-klein", "ck", "hugo-boss", "hugo", "boss",
    ],
    "ru": [
        "natura-siberica", "natura-siberika",
        "chistaya-liniya", "black-pearl", "loshadinaya-sila",
        "nevskaya-kosmetika", "sibirskie-travy",
        "natura", "siberica",
        # Cyrillic literals (PRODUCT_URL_RE allows а-я)
        "натура-сибирика",
        "чистая-линия",
        "лошадиная-сила",
        "невская-косметика",
        "сибирские-травы",
    ],
}


def _bucket_match(slug: str, keywords: list[str]) -> bool:
    """True if any keyword appears as a hyphen-bounded token prefix in slug."""
    for kw in keywords:
        # Match start-of-slug (most common — brand is leading token)
        if slug.startswith(kw + "-") or slug == kw:
            return True
        # Or hyphen-bounded interior (rare but covers things like
        # 'parfums-de-marly-tom-ford' — unlikely on goldapple but cheap to allow)
        if f"-{kw}-" in slug:
            return True
    return False


def main() -> None:
    print("Fetching goldapple.kz/sitemap.xml + 3 sub-sitemaps via curl_cffi …", file=sys.stderr)
    slug_map = fetch_sitemap_slugs()
    total_urls = sum(len(v) for v in slug_map.values())
    print(f"  → {len(slug_map):>6} unique slugs / {total_urls:>6} URLs", file=sys.stderr)

    # Bucket assignment: each URL gets exactly one bucket (first match wins).
    buckets: dict[str, list[tuple[str, str]]] = {k: [] for k in BUCKETS}
    for slug, urls in slug_map.items():
        for bucket_name, keywords in BUCKETS.items():
            if _bucket_match(slug, keywords):
                for url in urls:
                    buckets[bucket_name].append((slug, url))
                break

    rng = random.Random(20260513)  # deterministic for re-run-ability
    sampled: dict[str, list[tuple[str, str]]] = {}
    for bucket_name, candidates in buckets.items():
        n = min(6, len(candidates))
        sampled[bucket_name] = rng.sample(candidates, n) if n else []
        print(
            f"  bucket {bucket_name:<6} candidates={len(candidates):>5}  sampled={len(sampled[bucket_name])}",
            file=sys.stderr,
        )

    # Emit a Python literal — write to file (utf-8) to avoid Windows cp1251 stdout issues.
    bucket_labels = {
        "lux": "Bucket 1: Lux (Creed / Frederic Malle / Chanel / Dior / Amouage / Guerlain / Hermes / Lancome)",
        "mass": "Bucket 2: Mass-market (Armani / Givenchy / YSL / Versace / Calvin Klein / Hugo Boss)",
        "niche": "Bucket 3: Niche (STEREOTYPE / sago / Byredo / Le Labo / Maison Crivelli / Profumum / Memo / Nasomatto)",
        "ru": "Bucket 4: RU-brands (Natura Siberica / Chistaya Liniya / Black Pearl / Loshadinaya Sila / Nevskaya Kosmetika / Sibirskie Travy)",
        "multi": "Bucket 5: Multi-word brands (Tom Ford / Maison Margiela / Jo Malone / Atelier Cologne / By Kilian / Diptyque)",
    }
    out_path = Path(__file__).resolve().parent / "sampled-urls.py.snippet"
    bucket_order = ["lux", "mass", "niche", "ru", "multi"]
    lines: list[str] = []
    lines.append("URLS: list[tuple[str, str]] = [")
    for bucket_name in bucket_order:
        lines.append(f"    # ---- {bucket_labels[bucket_name]}")
        if not sampled[bucket_name]:
            lines.append("    # !!! EMPTY BUCKET - substitute from another bucket before commit")
        for slug, url in sampled[bucket_name]:
            tag = f"{bucket_name}-{slug[:40]}"
            # Use repr() to preserve Cyrillic safely via ASCII escapes if needed.
            lines.append(f"    ({tag!r}, {url!r}),")
    lines.append("]")
    total = sum(len(v) for v in sampled.values())
    lines.append(f"# Total sampled: {total}/30  (deterministic seed=20260513)")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {total}/30 sampled URLs to {out_path}", file=sys.stderr)
    print(f"\nPer-bucket summary:", file=sys.stderr)
    for bn in bucket_order:
        print(f"  {bn:<6} {len(sampled[bn])}/6", file=sys.stderr)


if __name__ == "__main__":
    main()
