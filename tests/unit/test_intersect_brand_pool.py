"""Unit tests for intersect_brand_pool — Pitfall 3 / D-305 exact-match guard.

After 03-08 gap-closure (Path A: longest-prefix-in-whitelist):
- Param renamed sitemap_slugs -> brand_bucket
- Bucket is now produced by index_by_brand_token(slug_map, known_brand_tokens)
- intersect_brand_pool still does exact-key dict.get against bucket keys
- D-305 enforcement is STRUCTURAL (precomputed bucket only contains whitelisted
  tokens; longest-prefix-match precludes cross-contamination)
"""

from __future__ import annotations

import inspect

from ga_crawler.enumeration.goldapple_sitemap import index_by_brand_token
from ga_crawler.enumeration.slug import (
    intersect_brand_pool,
    slug_fy_bilingual,
)
from ga_crawler.runner.stats import compute_norm06_forward


def test_intersect_exact_match_guard_tom_ford() -> None:
    """Pitfall 3: 'Tom Ford' must NOT match 'tom-ford-beauty' or 'tom-ford-private-blend'.

    Hand-built bucket keeps testing intersect IN ISOLATION (exact-key dict.get
    contract); the structural full-pipeline guard lives in
    test_brand_token_index_tom_ford_does_not_contaminate_tom_ford_beauty.
    """
    brand_bucket = {
        "tom-ford": ["https://goldapple.kz/100-tom-ford"],
        "tom-ford-beauty": ["https://goldapple.kz/200-tom-ford-beauty"],
        "tom-ford-private-blend": ["https://goldapple.kz/300-tom-ford-private-blend"],
    }
    aliases = {"tom_ford": ["Tom Ford"]}
    matched, unmatched = intersect_brand_pool(["tom_ford"], aliases, brand_bucket)
    assert matched == ["https://goldapple.kz/100-tom-ford"]
    assert unmatched == []


def test_intersect_bilingual_hit_returns_both_urls() -> None:
    """Brand alias has both Latin and Cyrillic variants → both slugs hit bucket."""
    brand_bucket = {
        "este-lauder": ["https://goldapple.kz/100-este-lauder"],
        "эсте-лаудер": ["https://goldapple.kz/200-эсте-лаудер"],
    }
    aliases = {"estee_lauder": ["Estée Lauder", "Эсте Лаудер"]}
    matched, unmatched = intersect_brand_pool(["estee_lauder"], aliases, brand_bucket)
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
    brand_bucket = {"givenchy": ["https://goldapple.kz/100-givenchy"]}
    aliases: dict[str, list[str]] = {}  # no entry
    matched, unmatched = intersect_brand_pool(["givenchy"], aliases, brand_bucket)
    assert matched == ["https://goldapple.kz/100-givenchy"]
    assert unmatched == []


def test_intersect_empty_alias_list_unmatched() -> None:
    """Brand with empty alias list → no slugs → unmatched."""
    matched, unmatched = intersect_brand_pool(["x"], {"x": []}, {"x": ["url"]})
    assert matched == []
    assert unmatched == ["x"]


def test_intersect_multi_url_slug_returns_all() -> None:
    """Bucket key with multiple URLs → all returned in matched_urls."""
    brand_bucket = {"givenchy": [
        "https://goldapple.kz/100-givenchy",
        "https://goldapple.kz/200-givenchy",
        "https://goldapple.kz/300-givenchy",
    ]}
    matched, _ = intersect_brand_pool(["givenchy"], {"givenchy": ["Givenchy"]}, brand_bucket)
    assert len(matched) == 3


def test_intersect_against_real_sitemap_shape() -> None:
    """Full-pipeline regression — proves Truth 1 closure end-to-end against a synthetic
    slug_map mimicking the real 45,490-slug sitemap shape (live run-42 evidence).

    Pipeline: slug_map -> known_brand_tokens (via slug_fy_bilingual on aliases) ->
    index_by_brand_token -> intersect_brand_pool. Asserts matched_url_count > 0
    for each viled brand AND no cross-contamination when both Tom Ford / Tom Ford
    Beauty are operator-disambiguated.
    """
    slug_map = {
        "givenchy-pour-homme-blue-label": ["https://goldapple.kz/100-givenchy-pour-homme-blue-label"],
        "givenchy-gentleman-reserve-privee": ["https://goldapple.kz/200-givenchy-gentleman-reserve-privee"],
        "givenchy-irresistible-eau-de-parfum": ["https://goldapple.kz/300-givenchy-irresistible-eau-de-parfum"],
        "jo-malone-london-wood-sage-and-sea-salt": ["https://goldapple.kz/400-jo-malone-london-wood-sage-and-sea-salt"],
        "jo-malone-london-english-pear-and-freesia": ["https://goldapple.kz/500-jo-malone-london-english-pear-and-freesia"],
        "tom-ford-noir-extreme": ["https://goldapple.kz/600-tom-ford-noir-extreme"],
        "tom-ford-beauty-lipstick-shade-12": ["https://goldapple.kz/700-tom-ford-beauty-lipstick-shade-12"],
        "estee-lauder-advanced-night-repair": ["https://goldapple.kz/800-estee-lauder-advanced-night-repair"],
        "эсте-лаудер-double-wear": ["https://goldapple.kz/900-эсте-лаудер-double-wear"],
        "category-listing-perfume": ["https://goldapple.kz/910-category-listing-perfume"],
        "another-noise-product": ["https://goldapple.kz/920-another-noise-product"],
        "yet-another-noise-page": ["https://goldapple.kz/930-yet-another-noise-page"],
    }

    # Sub-test 7a: givenchy only
    aliases_a = {"givenchy": ["Givenchy"]}
    known_a = set()
    for alias in aliases_a["givenchy"]:
        known_a.update(slug_fy_bilingual(alias))
    bucket_a = index_by_brand_token(slug_map, known_a)
    matched_a, unmatched_a = intersect_brand_pool(["givenchy"], aliases_a, bucket_a)
    assert len(matched_a) == 3, matched_a
    assert "https://goldapple.kz/100-givenchy-pour-homme-blue-label" in matched_a
    assert "https://goldapple.kz/200-givenchy-gentleman-reserve-privee" in matched_a
    assert "https://goldapple.kz/300-givenchy-irresistible-eau-de-parfum" in matched_a
    assert unmatched_a == []

    # Sub-test 7b: jo_malone_london
    aliases_b = {"jo_malone_london": ["Jo Malone London"]}
    known_b = set()
    for alias in aliases_b["jo_malone_london"]:
        known_b.update(slug_fy_bilingual(alias))
    bucket_b = index_by_brand_token(slug_map, known_b)
    matched_b, unmatched_b = intersect_brand_pool(["jo_malone_london"], aliases_b, bucket_b)
    assert len(matched_b) == 2, matched_b
    assert unmatched_b == []

    # Sub-test 7c: tom_ford WITHOUT tom_ford_beauty disambiguation
    # Operator chose not to disambiguate -> all tom-ford-* URLs land in tom-ford bucket
    aliases_c = {"tom_ford": ["Tom Ford"]}
    known_c = set()
    for alias in aliases_c["tom_ford"]:
        known_c.update(slug_fy_bilingual(alias))
    bucket_c = index_by_brand_token(slug_map, known_c)
    matched_c, unmatched_c = intersect_brand_pool(["tom_ford"], aliases_c, bucket_c)
    assert len(matched_c) == 2, matched_c  # noir-extreme + beauty-lipstick (depth-3 'tom-ford-beauty' not whitelisted -> falls to depth-2)
    assert "https://goldapple.kz/600-tom-ford-noir-extreme" in matched_c
    assert "https://goldapple.kz/700-tom-ford-beauty-lipstick-shade-12" in matched_c
    assert unmatched_c == []

    # Sub-test 7d: tom_ford WITH tom_ford_beauty operator-disambiguated
    # D-305 STRUCTURAL guard: longest-prefix-match against whitelist preserves separation
    aliases_d = {"tom_ford": ["Tom Ford"], "tom_ford_beauty": ["Tom Ford Beauty"]}
    known_d = set()
    for alias_list in aliases_d.values():
        for alias in alias_list:
            known_d.update(slug_fy_bilingual(alias))
    bucket_d = index_by_brand_token(slug_map, known_d)
    # tom_ford only → only noir-extreme
    matched_d_tf, _ = intersect_brand_pool(["tom_ford"], aliases_d, bucket_d)
    assert matched_d_tf == ["https://goldapple.kz/600-tom-ford-noir-extreme"]
    # tom_ford_beauty only → only the beauty-lipstick URL
    matched_d_tfb, _ = intersect_brand_pool(["tom_ford_beauty"], aliases_d, bucket_d)
    assert matched_d_tfb == ["https://goldapple.kz/700-tom-ford-beauty-lipstick-shade-12"]
    # NO cross-contamination
    assert "https://goldapple.kz/700-tom-ford-beauty-lipstick-shade-12" not in matched_d_tf
    assert "https://goldapple.kz/600-tom-ford-noir-extreme" not in matched_d_tfb

    # Sub-test 7e: estee_lauder bilingual
    aliases_e = {"estee_lauder": ["Estée Lauder", "Эсте Лаудер"]}
    known_e = set()
    for alias in aliases_e["estee_lauder"]:
        known_e.update(slug_fy_bilingual(alias))
    bucket_e = index_by_brand_token(slug_map, known_e)
    matched_e, unmatched_e = intersect_brand_pool(["estee_lauder"], aliases_e, bucket_e)
    assert len(matched_e) == 2, matched_e  # both ASCII and Cyrillic variants found
    assert "https://goldapple.kz/800-estee-lauder-advanced-night-repair" in matched_e
    assert "https://goldapple.kz/900-эсте-лаудер-double-wear" in matched_e
    assert unmatched_e == []

    # Sub-test 7f: unknown brand
    aliases_f = {"unknown_brand": ["Unknown"]}
    known_f = set()
    for alias in aliases_f["unknown_brand"]:
        known_f.update(slug_fy_bilingual(alias))
    bucket_f = index_by_brand_token(slug_map, known_f)
    matched_f, unmatched_f = intersect_brand_pool(["unknown_brand"], aliases_f, bucket_f)
    assert matched_f == []
    assert unmatched_f == ["unknown_brand"]

    # Top-level: matched count > 0 across givenchy + jo_malone_london (proves Truth 1 fix)
    assert len(matched_a) + len(matched_b) >= 5


def test_intersect_no_substring_lookup_in_function_body() -> None:
    """D-305 STRUCTURAL: intersect_brand_pool body must use exact-key dict.get only.

    Uses inspect.getsource (NOT byte-range slicing) to scope the assertion to the
    function body. Iterator idioms like `for ... in brand_slugs` are fine — they
    iterate over a set; not substring tests against the bucket.
    """
    src = inspect.getsource(intersect_brand_pool)
    assert ".startswith(" not in src, "D-305 violated: substring lookup"
    assert ".find(" not in src, "D-305 violated: substring lookup"
    assert ".endswith(" not in src, "D-305 violated: substring lookup"
    assert ".contains" not in src, "D-305 violated: substring lookup"


def test_compute_norm06_forward_with_brand_bucket_shape() -> None:
    """compute_norm06_forward accepts brand_bucket (NOT raw sitemap_slugs)."""
    brand_bucket = {"givenchy": ["url1"]}
    matched, unmatched_count, unmatched_brands = compute_norm06_forward(
        ["givenchy"], {"givenchy": ["Givenchy"]}, brand_bucket
    )
    assert matched == ["url1"]
    assert unmatched_count == 0
    assert unmatched_brands == []
