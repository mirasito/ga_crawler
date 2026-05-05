"""Plan 01-07 Task 1 (substituted): autonomous probe для виледовских product URLs.

Plan 01-07 Task 1 нормально checkpoint:human-action — пользователь вручную
открывает viled.kz, копирует 10-15 product URLs из DevTools. Чтобы honor
user's YOLO/autonomous preference (per MEMORY.md) и устранить hard-blocking
checkpoint, этот скрипт делает то же автоматически:

  1. Фетчит viled.kz/sitemap.xml через curl_cffi impersonate=chrome
     (в 01-04 подтверждено что viled robots.txt + privacy plain-deliverable;
      sitemap скорее всего тоже).
  2. Если sitemap = sitemapindex — фетчит первый product-sitemap.
  3. Извлекает URLs которые выглядят как product pages (heuristics: contains
     `/p/`, `/product/`, OR slug-based pattern с дефисами; не категориальные).
  4. Подсчитывает per-host counts чтобы найти продуктовые роуты.
  5. Печатает 10-15 кандидатов и сохраняет в viled-product-urls.txt.

Honor committed rate-limit: viled.kz = 2s sequential.

Run from repo root:
    uv run python .planning/spikes/01-goldapple/_fetch_viled_urls.py
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# Force UTF-8 stdout on Windows (per 01-05 deviation 2 lesson).
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from curl_cffi import requests

OUT = Path(".planning/spikes/01-goldapple/sample-payloads")
OUT.mkdir(parents=True, exist_ok=True)
URLS_OUT = OUT / "viled-product-urls.txt"

SITEMAP_INDEX = "https://viled.kz/sitemap.xml"
PAUSE = 2.0  # per tos-audit.md committed rate-limit
TIMEOUT = 30


def fetch(url: str) -> str:
    print(f"  GET {url}")
    r = requests.get(url, impersonate="chrome", timeout=TIMEOUT)
    print(f"    -> HTTP {r.status_code}, {len(r.content)} bytes, "
          f"content-type={r.headers.get('content-type', '')}")
    if r.status_code != 200:
        raise RuntimeError(f"non-200 from {url}: {r.status_code}")
    return r.text


def extract_locs(xml_text: str) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", xml_text)


def main() -> int:
    print(f"Fetching viled sitemap-index: {SITEMAP_INDEX}")
    try:
        index_xml = fetch(SITEMAP_INDEX)
    except Exception as e:
        print(f"ERROR fetching sitemap: {e}")
        return 1

    # Save snapshot
    (OUT / "viled-sitemap.xml").write_text(index_xml, encoding="utf-8")

    # Detect sitemapindex vs urlset
    is_index = "<sitemapindex" in index_xml
    print(f"  is_sitemapindex={is_index}")

    all_urls: list[str] = []

    if is_index:
        sub_sitemaps = extract_locs(index_xml)
        print(f"  Found {len(sub_sitemaps)} sub-sitemaps")
        for i, sub in enumerate(sub_sitemaps, 1):
            print(f"  [{i}/{len(sub_sitemaps)}] sub-sitemap: {sub}")
            time.sleep(PAUSE)
            try:
                sub_xml = fetch(sub)
            except Exception as e:
                print(f"    ERROR: {e}")
                continue
            sub_urls = extract_locs(sub_xml)
            print(f"    -> {len(sub_urls)} URLs in this sub-sitemap")
            all_urls.extend(sub_urls)
            # Save one sub-sitemap as evidence excerpt (first 50 URLs only)
            if i == 1:
                excerpt_lines = sub_xml.split("\n")[:200]
                (OUT / "viled-sitemap-1-excerpt.xml").write_text(
                    "\n".join(excerpt_lines), encoding="utf-8"
                )
    else:
        all_urls = extract_locs(index_xml)
        print(f"  Plain urlset: {len(all_urls)} URLs")

    print(f"\nTotal URLs harvested from viled sitemap: {len(all_urls)}")

    # Save full list as deterministic input (per artifact-hygiene from 01-05)
    (OUT / "viled-all-urls.txt").write_text(
        "\n".join(all_urls), encoding="utf-8"
    )

    # Classify URLs by first path segment to spot product route patterns
    seg_counter: Counter[str] = Counter()
    for u in all_urls:
        path = urlparse(u).path
        parts = [p for p in path.split("/") if p]
        first = parts[0] if parts else "(root)"
        seg_counter[first] += 1

    print("\nTop 15 first-path-segments (URL count):")
    for seg, n in seg_counter.most_common(15):
        print(f"  {seg!r}: {n}")

    # Heuristic: viled is Next.js/Magento-like; product URLs often have
    # numeric ID OR specific slug patterns. Try to find them.
    candidates: list[str] = []

    # Pattern 1: /product/<slug> or /p/<slug>
    p1 = [u for u in all_urls if "/product/" in u or "/p/" in u or "/products/" in u]
    print(f"\nPattern '/product*/' or '/p/': {len(p1)} URLs")
    candidates.extend(p1[:50])

    # Pattern 2: looks like product slug — last path segment has multiple
    # hyphens AND parent path is single-segment (category-like)
    if not candidates:
        slug_re = re.compile(r"[a-zA-Z0-9]+-[a-zA-Z0-9-]+")
        for u in all_urls:
            path = urlparse(u).path
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and slug_re.fullmatch(parts[-1]) and "-" in parts[-1]:
                candidates.append(u)
        print(f"Pattern 'slug-with-hyphens at last segment': {len(candidates)} URLs")

    if not candidates:
        print("WARNING: no obvious product URL pattern found — sampling top "
              "URLs from the longest segment bucket.")
        # Take URLs whose first segment is the most common non-root one.
        most_common_seg = seg_counter.most_common(2)
        if most_common_seg:
            seg = most_common_seg[0][0] if most_common_seg[0][0] != "(root)" else (
                most_common_seg[1][0] if len(most_common_seg) > 1 else None
            )
            if seg:
                candidates = [
                    u for u in all_urls
                    if urlparse(u).path.split("/", 2)[1:2] == [seg]
                ][:50]
                print(f"Fallback: sampled {len(candidates)} URLs from /{seg}/...")

    # Diversify: pick 15 URLs from across the candidate space (not first 15
    # which might all be one brand).
    if len(candidates) > 15:
        step = max(1, len(candidates) // 15)
        sampled = [candidates[i] for i in range(0, len(candidates), step)][:15]
    else:
        sampled = candidates[:15]

    print(f"\n=== Selected {len(sampled)} viled product URL candidates ===")
    for i, u in enumerate(sampled, 1):
        print(f"  {i:>2}. {u}")

    if len(sampled) < 10:
        print(f"\nERROR: only {len(sampled)} URLs collected (need >=10).")
        return 2

    URLS_OUT.write_text("\n".join(sampled) + "\n", encoding="utf-8")
    print(f"\n[OK] Saved {len(sampled)} URLs to {URLS_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
