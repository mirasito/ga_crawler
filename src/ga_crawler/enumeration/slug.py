"""Bilingual slug-fy + brand intersection (CRAWL-02 / D-304 / D-305).

Algorithm: for each alias string, produce TWO slug variants:
1. ASCII slug — NFKD + accent strip + Cyrillic→Latin transliterate + lowercase
2. Cyrillic slug — NFKD + accent strip + lowercase, BUT only emit if input contains Cyrillic
Then exact-match against sitemap-slug pool (NOT substring — Pitfall 3 / D-305).

Source: 03-RESEARCH.md §Pattern 2 lines 358-423 (verbatim).
Test cases: 03-RESEARCH.md table lines 427-439 (all 11 enumerated cases mandatory).
"""

from __future__ import annotations

import re
import unicodedata

# Cyrillic→Latin transliteration table.
# Russian: GOST 7.79-2000 System B (popular subset).
# Kazakh-specific glyphs included per Pitfall 4 (KZ brand names in alias-pool).
CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
    # KZ-specific
    "ә": "a", "ғ": "g", "қ": "q", "ң": "n", "ө": "o",
    "ұ": "u", "ү": "u", "һ": "h", "і": "i",
}


def _normalize_punct(s: str) -> str:
    """Lowercase, NFKD, strip combining marks + apostrophes, non-alphanum→hyphen,
    collapse multi-hyphen, strip outer hyphens.

    Apostrophes (straight ', curly ’, ʼ) are stripped (NOT replaced with hyphen)
    so "L'Oréal Paris" → "loreal-paris" (not "l-oreal-paris") — per RESEARCH
    §Pattern 2 line 435 ("apostrophe stripped").
    """
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Strip apostrophes (and similar zero-width separators) before hyphen-replacement.
    s = re.sub(r"['’ʼʹ]", "", s)
    # Whitelist alphanum + Cyrillic (Russian range U+0430-U+044F + ё) +
    # KZ-specific glyphs explicitly (ә ғ қ ң ө ұ ү һ і — some lie outside the
    # U+0430-U+044F range; using a regex range like [ә-і] is ill-defined).
    s = re.sub(r"[^a-z0-9а-яёәғқңөұүһі]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def slug_fy_bilingual(alias: str) -> list[str]:
    """Returns [ascii_slug, cyrillic_slug] (filtered: empty / None excluded).

    Examples (test cases planner mandates — see test_slug_fy.py):
      'Estée Lauder'  -> ['estee-lauder']
      'Эсте Лаудер'   -> ['este-lauder', 'эсте-лаудер']
      'Tom Ford'      -> ['tom-ford']
      'Tom Ford Beauty' -> ['tom-ford-beauty']  # Pitfall 3 guard via exact-match
      'L\\'Oréal Paris' -> ['loreal-paris']
      'Жильет'        -> ['zhilet', 'жильет']
      ''              -> []
    """
    cyrillic_slug: str | None = _normalize_punct(alias)
    # Detect Cyrillic presence in NORMALIZED slug (after lowercase + accent strip).
    # Range a-я covers Russian; KZ-specific glyphs (ә ғ қ ң ө ұ ү һ і) are listed
    # explicitly because some lie outside U+0430-U+044F (e.g. ә=U+04D9, і=U+0456),
    # and a contiguous regex range like [ә-і] is ill-defined (would raise re.error).
    if not re.search(r"[а-яёәғқңөұүһі]", cyrillic_slug):
        cyrillic_slug = None
    ascii_input = "".join(CYRILLIC_TO_LATIN.get(c, c) for c in alias.lower())
    ascii_slug = _normalize_punct(ascii_input)
    return [s for s in (ascii_slug, cyrillic_slug) if s]


def intersect_brand_pool(
    viled_brands: list[str],
    aliases: dict[str, list[str]],
    sitemap_slugs: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    """Returns (matched_urls, unmatched_brands).

    For each viled brand: get all aliases (fallback to [brand] if absent),
    slug-fy each, EXACT-MATCH against sitemap_slugs dict via .get() (NOT
    substring iteration — Pitfall 3 / D-305).

    Brand is "matched" iff ANY of its slug-variants hits the sitemap.
    """
    matched_urls: list[str] = []
    unmatched_brands: list[str] = []
    for brand in viled_brands:
        brand_slugs: set[str] = set()
        for alias in aliases.get(brand, [brand]):
            brand_slugs.update(slug_fy_bilingual(alias))
        hit_urls: list[str] = []
        for slug in brand_slugs:
            urls_for_slug = sitemap_slugs.get(slug)  # exact-match via dict.get
            if urls_for_slug:
                hit_urls.extend(urls_for_slug)
        if hit_urls:
            matched_urls.extend(hit_urls)
        else:
            unmatched_brands.append(brand)
    return matched_urls, unmatched_brands


__all__ = [
    "CYRILLIC_TO_LATIN",
    "slug_fy_bilingual",
    "intersect_brand_pool",
    "_normalize_punct",
]
