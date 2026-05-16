"""Resolve the 21 viled brand_norms unmatched in run-19's Norm06 review
against the authoritative goldapple /front/api/brands list captured by
probe_ga_brands_index_v2.py.

For each unmatched brand_norm:
  1. Normalize both sides (lower, strip suffixes like "_beauty",
     "-beauty", "-perfume", punctuation, hyphens, underscores).
  2. Look for exact normalized-label match.
  3. Look for fuzzy partial/contained match.
  4. Print a recommended override line to add to data/ga_brand_slugs.yaml.

Usage:
    uv run python scripts/resolve_unmatched_brands_v2.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BRANDS_JSON = Path("inbox/ga_brands_index/v2_xhr_bodies/012__brands.json")
NORM06 = Path(".planning/runs/19/norm06-review.md")
SLUGS_YAML = Path("data/ga_brand_slugs.yaml")

# Suffixes/prefixes viled appends that GA generally drops
SUFFIXES = (
    "-beauty", "_beauty", " beauty",
    "-perfume", "_perfume", " perfume",
    "-parfums", "_parfums", " parfums",
    "-london", "_london", " london",
    "-paris", "_paris", " paris",
    "-cosmetics", "_cosmetics", " cosmetics",
)


def _norm(s: str) -> str:
    """Aggressive normalization for matching: lowercase, strip suffixes,
    drop all punctuation/whitespace."""
    s = s.lower().strip()
    # iterate to strip multiple compounding suffixes (rare, but safe)
    changed = True
    while changed:
        changed = False
        for suf in SUFFIXES:
            if s.endswith(suf):
                s = s[: -len(suf)].rstrip(" -_")
                changed = True
    s = re.sub(r"[\s\-_'’]+", "", s)
    return s


def read_unmatched() -> list[str]:
    out: list[str] = []
    for line in NORM06.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("brand_or_slug", "---------------"):
            continue
        if cells[1] == "viled-unmatched" and cells[3] == "pending":
            out.append(cells[0])
    return out


def main() -> int:
    brands = json.loads(BRANDS_JSON.read_text(encoding="utf-8"))["data"]["brands"]
    # build lookup: normalized_label -> brand record
    by_norm: dict[str, dict] = {}
    for b in brands:
        label = b.get("label") or ""
        orig = b.get("labelOriginal") or label
        for source in (label, orig):
            key = _norm(source)
            if key and key not in by_norm:
                by_norm[key] = b

    unmatched = read_unmatched()
    print(f"=== Resolving {len(unmatched)} unmatched brand_norms against "
          f"{len(brands)} GA brands ({len(by_norm)} normalized keys) ===\n")

    proposed_overrides: list[tuple[str, str, str]] = []  # (brand_norm, slug, ga_label)
    for bn in unmatched:
        bn_norm = _norm(bn)
        exact = by_norm.get(bn_norm)
        if exact:
            slug = (exact.get("url") or "").lstrip("/").removeprefix("brands/")
            print(f"  ✓ EXACT  {bn:30s}  ->  {slug:30s}  (label={exact.get('label')})")
            proposed_overrides.append((bn, slug, exact.get("label") or ""))
            continue

        # Fuzzy partial-contains scan
        candidates = []
        for k, b in by_norm.items():
            if bn_norm and (bn_norm in k or k in bn_norm) and len(k) >= 3:
                candidates.append((k, b))
        candidates.sort(key=lambda kv: abs(len(kv[0]) - len(bn_norm)))
        if candidates:
            top = candidates[:5]
            print(f"  ? FUZZY  {bn:30s}  -> top candidates:")
            for k, b in top:
                slug = (b.get("url") or "").lstrip("/").removeprefix("brands/")
                print(f"        {slug:30s}  (label={b.get('label')}, norm_key={k!r})")
            # If top candidate's normalized key is a strict prefix or
            # contains bn_norm cleanly, recommend it
            k0, b0 = top[0]
            slug0 = (b0.get("url") or "").lstrip("/").removeprefix("brands/")
            if k0.startswith(bn_norm) or bn_norm.startswith(k0):
                proposed_overrides.append((bn, slug0, b0.get("label") or ""))
        else:
            print(f"  ✗ MISS   {bn:30s}  (not found in GA brands index)")

    print("\n=== Proposed overrides for data/ga_brand_slugs.yaml ===")
    for bn, slug, label in proposed_overrides:
        print(f"  {bn}: {slug}  # {label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
