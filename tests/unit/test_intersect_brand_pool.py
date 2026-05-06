"""Unit tests for intersect_brand_pool — Pitfall 3 exact-match guard."""

from __future__ import annotations

from ga_crawler.enumeration.slug import intersect_brand_pool


def test_intersect_exact_match_guard_tom_ford() -> None:
    """Pitfall 3: 'Tom Ford' must NOT match 'tom-ford-beauty' or 'tom-ford-private-blend'."""
    sitemap = {
        "tom-ford": ["https://goldapple.kz/100-tom-ford"],
        "tom-ford-beauty": ["https://goldapple.kz/200-tom-ford-beauty"],
        "tom-ford-private-blend": ["https://goldapple.kz/300-tom-ford-private-blend"],
    }
    aliases = {"tom_ford": ["Tom Ford"]}
    matched, unmatched = intersect_brand_pool(["tom_ford"], aliases, sitemap)
    assert matched == ["https://goldapple.kz/100-tom-ford"]
    assert unmatched == []


def test_intersect_bilingual_hit_returns_both_urls() -> None:
    """Brand alias has both Latin and Cyrillic variants → both slugs hit sitemap."""
    sitemap = {
        "este-lauder": ["https://goldapple.kz/100-este-lauder"],
        "эсте-лаудер": ["https://goldapple.kz/200-эсте-лаудер"],
    }
    aliases = {"estee_lauder": ["Estée Lauder", "Эсте Лаудер"]}
    matched, unmatched = intersect_brand_pool(["estee_lauder"], aliases, sitemap)
    assert sorted(matched) == sorted([
        "https://goldapple.kz/100-este-lauder",
        "https://goldapple.kz/200-эсте-лаудер",
    ])
    assert unmatched == []


def test_intersect_unmatched_brand_surfaces() -> None:
    """Brand with zero slug-matches → goes to unmatched_brands (NORM-06 forward direction)."""
    matched, unmatched = intersect_brand_pool(
        ["unknown_brand"], {"unknown_brand": ["Unknown"]}, {}
    )
    assert matched == []
    assert unmatched == ["unknown_brand"]


def test_intersect_alias_fallback_to_brand_norm() -> None:
    """If aliases dict lacks the brand, fall back to [brand_norm] as the only alias."""
    sitemap = {"givenchy": ["https://goldapple.kz/100-givenchy"]}
    aliases: dict[str, list[str]] = {}  # no entry
    matched, unmatched = intersect_brand_pool(["givenchy"], aliases, sitemap)
    assert matched == ["https://goldapple.kz/100-givenchy"]
    assert unmatched == []


def test_intersect_empty_alias_list_unmatched() -> None:
    """Brand with empty alias list → no slugs → unmatched."""
    matched, unmatched = intersect_brand_pool(["x"], {"x": []}, {"x": ["url"]})
    assert matched == []
    assert unmatched == ["x"]


def test_intersect_multi_url_slug_returns_all() -> None:
    """Sitemap slug with multiple URLs → all returned in matched_urls."""
    sitemap = {"givenchy": [
        "https://goldapple.kz/100-givenchy",
        "https://goldapple.kz/200-givenchy",
        "https://goldapple.kz/300-givenchy",
    ]}
    matched, _ = intersect_brand_pool(["givenchy"], {"givenchy": ["Givenchy"]}, sitemap)
    assert len(matched) == 3
