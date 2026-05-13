"""Shape survey using the corrected h1 .brand / .name CSS-class extraction.

KEY FINDING (2026-05-13): goldapple PDPs do NOT carry product-level
`<meta itemprop="name">` microdata. The 2 `itemprop="name"` per page are
breadcrumb labels + review-author names + footer Organization name.
The ACTUAL product brand+name is inside the h1:

    <h1 class="_ga-pdp-title__heading_*">
      <a   class="_ga-pdp-title__brand_*" content="Armani">Armani</a>
      <span class="_ga-pdp-title__name_*">armani code</span>
    </h1>

This invalidates Plan 08-03's premise of `<meta itemprop="name">` walking
and pivots the extraction strategy to CSS-class-prefix substring matching
on the h1 children. The CSS hash suffix (e.g. `_1yrfv_339`) is build-
specific and must be matched with substring (not full string).
"""
from __future__ import annotations
import os
import re
import sys
from collections import Counter
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
out_path = SPIKE_DIR / "shape-survey.txt"

H1_HEADING_RE = re.compile(r'<h1[^>]*_ga-pdp-title__heading_[^>]*>(.{0,2000}?)</h1>', re.DOTALL)
BRAND_SPAN_RE = re.compile(r'class="[^"]*_ga-pdp-title__brand_[^"]*"[^>]*content="([^"]*)"', re.DOTALL)
BRAND_SPAN_TEXT_RE = re.compile(r'class="[^"]*_ga-pdp-title__brand_[^"]*"[^>]*>([^<]*)<', re.DOTALL)
NAME_SPAN_RE = re.compile(r'class="[^"]*_ga-pdp-title__name_[^"]*"[^>]*>([^<]*)<', re.DOTALL)
VOL_WORD_RE = re.compile(r"объ[её]м", re.IGNORECASE)
VOL_MLBOX_RE = re.compile(r"объ[её]м[^a-zа-я0-9]{0,30}/[^a-zа-я0-9]{0,5}мл", re.IGNORECASE)


def _bucket(brand: str, name: str) -> str:
    if not brand or not name:
        return "(missing — bug)"
    b_low = brand.lower().strip()
    n_low = name.lower().strip()
    # Armani-style: brand string substring within name (the canonical Bug #2 shape)
    if b_low and b_low in n_low:
        return "armani-style"
    # STEREOTYPE-style: brand is title-case / mixed-case, name is UPPERCASE — the
    # canonical Bug #1 shape (h1 visually reads as "STEREOTYPE" because of CSS
    # uppercase, but raw DOM brand text is "Stereotype").
    if brand.isupper() or name.isupper():
        return "stereotype-style"
    if brand[:1].isupper() and any(c.isupper() for c in name) and not name.isupper():
        return "mixed-case"
    return "givenchy-baseline"


results: list[dict] = []
for html_file in sorted(SPIKE_DIR.glob("pdp-*.html")):
    html = html_file.read_text(encoding="utf-8")

    brand_raw = ""
    h1_match = H1_HEADING_RE.search(html)
    h1_inner = h1_match.group(1) if h1_match else ""
    if h1_inner:
        m = BRAND_SPAN_RE.search(h1_inner)
        if m:
            brand_raw = m.group(1).strip()
        else:
            m = BRAND_SPAN_TEXT_RE.search(h1_inner)
            if m:
                brand_raw = m.group(1).strip()
    name_raw = ""
    if h1_inner:
        m = NAME_SPAN_RE.search(h1_inner)
        if m:
            name_raw = m.group(1).strip()

    has_vol = bool(VOL_WORD_RE.search(html))
    has_mlbox = bool(VOL_MLBOX_RE.search(html))
    shape = _bucket(brand_raw, name_raw)

    results.append(dict(
        file=html_file.name,
        brand=brand_raw,
        name=name_raw,
        shape=shape,
        vol_word=has_vol,
        vol_mlbox=has_mlbox,
    ))

# Render
lines: list[str] = []
lines.append(f"{'file':<58} {'shape':<18} {'brand':<22} {'name':<35} vol_word vol_ml")
lines.append("-" * 165)
for r in results:
    lines.append(
        f"{r['file']:<58} {r['shape']:<18} {r['brand'][:21]:<22} {r['name'][:34]:<35} "
        f"{('Y' if r['vol_word'] else 'N'):<8} {('Y' if r['vol_mlbox'] else 'N')}"
    )

hist = Counter(r["shape"] for r in results)
lines.append("")
lines.append("Shape histogram:")
for shape, n in hist.most_common():
    lines.append(f"  {shape:<22} {n}")

vol_total = sum(1 for r in results if r["vol_word"])
ml_total = sum(1 for r in results if r["vol_mlbox"])
brand_total = sum(1 for r in results if r["brand"])
name_total = sum(1 for r in results if r["name"])
lines.append("")
lines.append(f"h1 .brand extraction:  {brand_total}/{len(results)}")
lines.append(f"h1 .name extraction:   {name_total}/{len(results)}")
lines.append(f"Volume word coverage:  {vol_total}/{len(results)}")
lines.append(f"Volume /МЛ block:      {ml_total}/{len(results)}")

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote shape survey to {out_path}", file=sys.stderr)
