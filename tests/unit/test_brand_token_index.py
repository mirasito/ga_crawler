"""Unit tests for index_by_brand_token (Path A: longest-prefix-in-whitelist).

Closes 03-VERIFICATION.md Truth 1 BLOCKER (CRAWL-02): brand-alias slugs cannot
exact-match product-slug-keyed sitemap dict. The new helper re-keys URLs by the
LONGEST viled-known brand-token prefix using a precomputed whitelist; this makes
D-305 / Pitfall 3 a STRUCTURAL invariant — only viled-known tokens become bucket
keys, and each URL belongs to exactly one bucket (longest-match wins).
"""

from __future__ import annotations

from ga_crawler.enumeration.goldapple_sitemap import (
    BRAND_TOKEN_MAX_DEPTH,
    index_by_brand_token,
)


def test_index_by_brand_token_longest_prefix_match_givenchy() -> None:
    """Single-token brand: 'givenchy-pour-homme-blue-label' falls through to depth-1 'givenchy'."""
    u1 = "https://goldapple.kz/100-givenchy-pour-homme-blue-label"
    slug_map = {"givenchy-pour-homme-blue-label": [u1]}
    known = {"givenchy"}
    bucket = index_by_brand_token(slug_map, known)
    assert bucket == {"givenchy": [u1]}
    assert list(bucket.keys()) == ["givenchy"]


def test_index_by_brand_token_longest_prefix_jo_malone_london() -> None:
    """Depth-3 'jo-malone-london' wins over depth-2 'jo-malone' when both are whitelisted."""
    u1 = "https://goldapple.kz/100-jo-malone-london-cologne"
    slug_map = {"jo-malone-london-cologne": [u1]}
    known = {"jo-malone-london", "jo-malone"}
    bucket = index_by_brand_token(slug_map, known)
    assert bucket == {"jo-malone-london": [u1]}
    assert "jo-malone" not in bucket  # longest-match: shorter prefix gets nothing


def test_brand_token_index_tom_ford_does_not_contaminate_tom_ford_beauty() -> None:
    """D-305 STRUCTURAL GUARD: when both 'tom-ford' and 'tom-ford-beauty' are whitelisted,
    each URL goes to its longest-matched bucket — NO cross-contamination.
    """
    u1 = "https://goldapple.kz/100-tom-ford-noir-extreme"
    u2 = "https://goldapple.kz/200-tom-ford-beauty-eye-cream"
    u3 = "https://goldapple.kz/300-tom-ford-private-blend-tobacco"
    slug_map = {
        "tom-ford-noir-extreme": [u1],
        "tom-ford-beauty-eye-cream": [u2],
        "tom-ford-private-blend-tobacco": [u3],
    }
    known = {"tom-ford", "tom-ford-beauty"}
    bucket = index_by_brand_token(slug_map, known)
    # tom-ford-beauty bucket has ONLY the eye-cream URL (depth-3 'tom-ford-beauty' wins)
    assert bucket["tom-ford-beauty"] == [u2]
    # tom-ford bucket has noir + private-blend (depth-3 'tom-ford-noir' / 'tom-ford-private' miss → fall to depth-2)
    assert sorted(bucket["tom-ford"]) == sorted([u1, u3])
    # NO contamination
    assert u2 not in bucket["tom-ford"]
    assert u1 not in bucket["tom-ford-beauty"]
    assert u3 not in bucket["tom-ford-beauty"]
    # Depth-1 'tom' not in whitelist → no such key
    assert "tom" not in bucket


def test_index_by_brand_token_drops_orphan_slugs_not_in_whitelist() -> None:
    """Slugs with no whitelisted prefix are silently dropped (operator doesn't carry that brand)."""
    u1 = "https://goldapple.kz/100-unknown-brand-product"
    u2 = "https://goldapple.kz/200-givenchy-pour-homme"
    slug_map = {
        "unknown-brand-product": [u1],
        "givenchy-pour-homme": [u2],
    }
    known = {"givenchy"}
    bucket = index_by_brand_token(slug_map, known)
    assert bucket == {"givenchy": [u2]}
    # Orphan slug dropped — no key for it
    assert "unknown-brand-product" not in bucket
    assert "unknown" not in bucket
    assert "unknown-brand" not in bucket


def test_index_by_brand_token_handles_empty_or_malformed_slugs() -> None:
    """Empty / leading-hyphen / single-token slugs are handled without raising."""
    u1 = "https://goldapple.kz/100-empty"
    u2 = "https://goldapple.kz/200-leading-hyphen"
    u3 = "https://goldapple.kz/300-givenchy"
    slug_map = {
        "": [u1],
        "-leading": [u2],
        "givenchy": [u3],
    }
    known = {"givenchy"}
    bucket = index_by_brand_token(slug_map, known)
    assert bucket == {"givenchy": [u3]}


def test_index_by_brand_token_bounded_depth_3() -> None:
    """MAX_DEPTH=3 — depth-4+ prefixes are NOT considered even if in whitelist."""
    assert BRAND_TOKEN_MAX_DEPTH == 3
    u1 = "https://goldapple.kz/100-a-b-c-d-e-f"
    slug_map = {"a-b-c-d-e-f": [u1]}
    known = {"a-b-c-d", "a-b-c", "a-b", "a"}
    bucket = index_by_brand_token(slug_map, known)
    # Depth-3 'a-b-c' wins; depth-4 'a-b-c-d' NOT considered even though whitelisted
    assert bucket == {"a-b-c": [u1]}
    assert "a-b-c-d" not in bucket
    assert "a-b" not in bucket
    assert "a" not in bucket


def test_index_by_brand_token_empty_whitelist_returns_empty_bucket() -> None:
    """Empty known_brand_tokens → empty bucket (no slug can match)."""
    slug_map = {"givenchy": ["https://goldapple.kz/100-givenchy"]}
    bucket = index_by_brand_token(slug_map, set())
    assert bucket == {}
