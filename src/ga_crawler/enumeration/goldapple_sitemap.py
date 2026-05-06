"""Goldapple sitemap enumeration (D-301) + week-over-week NEW slug diff (D-307).

Tier 0 path: curl_cffi GET https://goldapple.kz/sitemap.xml → 3 sub-sitemaps →
~100,779 product URLs. Sitemap is empirically plain-deliverable (spike 01-05
confirmed; not behind GroupIB gate).

Slug extraction: each URL matches r"^https://goldapple\\.kz/(\\d+)-([a-z0-9а-я-]+)$".
Output: {slug: [urls]} map. Use intersect_brand_pool() (slug.py) to filter to
viled-only brands.

Week-over-week diff (D-307 NORM-06 reverse): persist current run's slug set to
.planning/runs/{run_id}/sitemap-slugs.txt; diff vs previous run's file produces
NEW slug list (additions only — removals ignored per Pitfall 8 doc).

Source: 03-RESEARCH.md §Pattern 1 lines 320-349 + §"Code Examples" lines 957-982.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from curl_cffi import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

SITEMAP_INDEX = "https://goldapple.kz/sitemap.xml"

# Whitelist regex per Threat T-04 (sitemap-poisoning): only accept numeric-id URLs
# on goldapple.kz domain. Cyrillic in slug allowed (goldapple has Cyrillic-only slugs).
PRODUCT_URL_RE = re.compile(
    r"^https://goldapple\.kz/(\d+)-([a-z0-9а-я-]+)$",
    re.IGNORECASE,
)

# Sitemap fetch timeout (seconds). Sitemap is plain XML; 30s is generous.
SITEMAP_TIMEOUT_S = 30


class SitemapFetchError(RuntimeError):
    """Raised when sitemap-index or sub-sitemap fetch fails terminally (after retries)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((SitemapFetchError,)),
    reraise=True,
)
def _fetch_xml(url: str) -> str:
    """Fetch one XML resource with curl_cffi impersonate=chrome.
    Raises SitemapFetchError on non-200; tenacity retries with exp+jitter.
    """
    try:
        resp = requests.get(url, impersonate="chrome", timeout=SITEMAP_TIMEOUT_S)
    except Exception as e:
        raise SitemapFetchError(f"connection error fetching {url}: {e}") from e
    if resp.status_code != 200:
        raise SitemapFetchError(f"http {resp.status_code} for {url}")
    return resp.text


def fetch_sitemap_slugs(sitemap_index_url: str = SITEMAP_INDEX) -> dict[str, list[str]]:
    """Returns {slug: [urls]} map. ~1,461 slugs / ~100,779 URLs per spike 01-05.

    Step 1: fetch sitemap-index → 3 sub-sitemap URLs
    Step 2: for each sub-sitemap, fetch + extract <loc>URL</loc> entries
    Step 3: each URL → match PRODUCT_URL_RE → extract numeric-id + slug
    Step 4: group URLs by slug.lower()
    """
    idx_xml = _fetch_xml(sitemap_index_url)
    sub_urls = re.findall(r"<loc>([^<]+)</loc>", idx_xml)
    slug_map: dict[str, list[str]] = {}
    for sub in sub_urls:
        sub_xml = _fetch_xml(sub)
        for url in re.findall(r"<loc>([^<]+)</loc>", sub_xml):
            m = PRODUCT_URL_RE.match(url)
            if m:
                slug = m.group(2).lower()
                slug_map.setdefault(slug, []).append(url)
    return slug_map


def persist_sitemap_slugs(slugs: set[str], run_id: int, root: Path) -> Path:
    """Write current week's slugs to {root}/runs/{run_id}/sitemap-slugs.txt.

    Output is sorted, one slug per line, UTF-8.
    Per RESEARCH §Open Question Q1: file path under {root}/runs/ is the
    Phase 3-recommended location (Phase 2 may consolidate to DB later).
    """
    out = root / f"runs/{run_id}/sitemap-slugs.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sorted(slugs)), encoding="utf-8")
    return out


def find_previous_slug_file(root: Path, current_run_id: int) -> Optional[Path]:
    """Find the latest predecessor sitemap-slugs.txt for week-over-week diff.

    Searches {root}/runs/*/sitemap-slugs.txt; returns the entry with the
    HIGHEST numeric run_id < current_run_id. Returns None if no predecessor.

    Non-numeric directory names under runs/ are skipped silently (e.g. a
    'meta' or 'archive' dir won't crash int(); also future runs >= current
    are filtered out).
    """
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return None
    candidates: list[tuple[int, Path]] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            run_id_int = int(child.name)
        except ValueError:
            continue
        if run_id_int >= current_run_id:
            continue
        f = child / "sitemap-slugs.txt"
        if f.exists():
            candidates.append((run_id_int, f))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def diff_new_slugs(current: set[str], previous_path: Optional[Path]) -> list[str]:
    """Returns sorted list of NEW slugs not in previous week's file.

    First run (previous_path is None) → empty diff per Pitfall 8 doc.
    Removals (slugs in previous, not in current) are IGNORED — week-over-week
    NORM-06 tracks ADDITIONS only per D-307.
    Blank lines in the previous file are skipped.
    """
    if previous_path is None:
        return []
    prev = set(
        ln for ln in previous_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    )
    return sorted(current - prev)


__all__ = [
    "SITEMAP_INDEX",
    "PRODUCT_URL_RE",
    "SITEMAP_TIMEOUT_S",
    "SitemapFetchError",
    "fetch_sitemap_slugs",
    "persist_sitemap_slugs",
    "find_previous_slug_file",
    "diff_new_slugs",
]
