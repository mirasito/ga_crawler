"""Unit tests for matcher v2 token-overlap name-side logic.

Pins the four match paths defined in ``ga_crawler.matcher.name_match``:
  - Path 2: strict-equality fallback when both Latin token sets are empty
  - Path 3: subset (either direction)
  - Path 4: discriminative-residual with brand-token + stopword strip
  - Reject path: competing distinguishing tokens on both sides

All test cases are sourced from real ground-truth pairs in the user's
228-row manual-match Sheet (.planning notes) and from run-18 false-positive
pairs that the v1 strict matcher would have surfaced under brand+volume
alone.
"""

from __future__ import annotations

import pytest

from ga_crawler.matcher.name_match import (
    brand_tokens,
    en_tokens,
    name_matches,
    slug_tokens,
)


# ---- Token helpers ----


def test_en_tokens_strips_short_and_lowercases() -> None:
    assert en_tokens("Парфюмерная вода Armani Code, 75 мл") == {"armani", "code"}


def test_en_tokens_empty_on_none_and_empty() -> None:
    assert en_tokens(None) == set()
    assert en_tokens("") == set()


def test_slug_tokens_extracts_kebab_segments() -> None:
    url = "https://goldapple.kz/19000126321-almost-lipstick"
    assert slug_tokens(url) == {"almost", "lipstick"}


def test_slug_tokens_empty_when_no_slug() -> None:
    # Synthetic-fixture URLs from unit tests don't have a goldapple slug.
    assert slug_tokens("https://goldapple.kz/G1") == set()
    assert slug_tokens(None) == set()


def test_brand_tokens_splits_multiword_brand_norm() -> None:
    assert brand_tokens("armani_beauty") == {"armani", "beauty"}
    assert brand_tokens("bobbi-brown") == {"bobbi", "brown"}
    assert brand_tokens("mac") == {"mac"}


# ---- Path 2: strict-equality fallback (synthetic fixtures) ----


def test_strict_equality_fallback_single_char_names() -> None:
    """Synthetic test data uses 1-char names that produce no Latin tokens.
    Fallback to byte-equality must accept these so unit-test fixtures still
    pin the SQL formula behavior.
    """
    assert name_matches(
        viled_name_norm="a",
        goldapple_url="https://goldapple.kz/G1",
        goldapple_name_norm="a",
        brand_norm="givenchy",
    )


def test_strict_equality_fallback_rejects_different_short_names() -> None:
    assert not name_matches(
        viled_name_norm="a",
        goldapple_url="https://goldapple.kz/G1",
        goldapple_name_norm="b",
        brand_norm="givenchy",
    )


# ---- Path 3: subset (either direction) ----


def test_subset_ga_slug_in_viled_name() -> None:
    """GT pair v=282355: slug 'almost-lipstick' ⊆ viled 'Almost Lipstick Black Honey'."""
    assert name_matches(
        viled_name_norm="помада блеск для губ almost lipstick оттенок black honey",
        goldapple_url="https://goldapple.kz/19000126321-almost-lipstick",
        goldapple_name_norm="almost lipstick",
        brand_norm="mac",
    )


def test_subset_viled_name_in_ga_slug() -> None:
    """GT pair v=239922: slug 'vitamin-enriched' ⊇ viled tokens.

    viled latin = {deluxe, vitamin, enriched}; GA slug = {vitamin, enriched}.
    GA ⊆ V, accept.
    """
    assert name_matches(
        viled_name_norm="база под макияж deluxe vitamin enriched 100 мл",
        goldapple_url="https://goldapple.kz/19000140361-vitamin-enriched",
        goldapple_name_norm="vitamin enriched",
        brand_norm="bobbi-brown",
    )


# ---- Path 4: discriminative-residual (stopword strip enables match) ----


def test_discriminative_strip_accepts_when_only_diff_is_stopword() -> None:
    """GT pair v=154810: slug 'ultra-facial-cleanser' vs viled 'ultra facial 150 мл'.

    Naive subset fails (cleanser missing from viled). After stripping the
    'cleanser' stopword and numeric tokens, both residuals = {ultra, facial}.
    """
    assert name_matches(
        viled_name_norm="гель для умывания для всех типов кожи ultra facial 150 мл",
        goldapple_url="https://goldapple.kz/15370700001-ultra-facial-cleanser",
        goldapple_name_norm="ultra facial cleanser",
        brand_norm="kiehls",
    )


def test_discriminative_strip_accepts_with_brand_token_stripped() -> None:
    """Multi-word brand_norm tokens must not count as distinguishing.

    Mock case: brand='armani_beauty'. The shared 'armani' would otherwise
    be the only token bridging viled and GA — but it's the brand and gets
    stripped from the discriminative residual.
    """
    assert name_matches(
        viled_name_norm="парфюмерная вода armani code 75 мл",
        goldapple_url="https://goldapple.kz/7381300006-armani-code",
        goldapple_name_norm="armani code",
        brand_norm="armani_beauty",
    )


# ---- Reject path: competing distinguishing tokens ----


def test_rejects_different_perfume_variants_within_same_brand_and_volume() -> None:
    """Run-18 false-positive: 'Stronger With You Absolutely' vs '...Powerfully'.

    Both share {stronger, you} but their distinguishing tail tokens
    (absolutely vs powerfully) are non-stopword and non-overlapping → REJECT.
    """
    assert not name_matches(
        viled_name_norm="парфюмерная вода stronger with you absolutely",
        goldapple_url="https://goldapple.kz/19000493328-armani-stronger-with-you-powerfully",
        goldapple_name_norm="stronger with you powerfully",
        brand_norm="armani_beauty",
    )


def test_rejects_azzaro_chrome_aqua_vs_chrome_united() -> None:
    """Run-18 false-positive: 'Azzaro Chrome Aqua' vs 'Azzaro Chrome United'.

    After stripping brand 'azzaro' the residuals are {chrome, aqua} and
    {chrome, united} — both have a distinct discriminative token.
    """
    assert not name_matches(
        viled_name_norm="туалетная вода azzaro chrome aqua 100 мл",
        goldapple_url="https://goldapple.kz/19000274010-azzaro-chrome-united",
        goldapple_name_norm="azzaro chrome united",
        brand_norm="azzaro",
    )


def test_rejects_no_token_overlap() -> None:
    """No shared Latin tokens at all → REJECT (unless the strict-equality
    fallback applies, which it doesn't here)."""
    assert not name_matches(
        viled_name_norm="карандаш для губ оттенок pale mauve",
        goldapple_url="https://goldapple.kz/19000432737-lip-pencil",
        goldapple_name_norm="lip pencil",
        brand_norm="clinique",
    )
