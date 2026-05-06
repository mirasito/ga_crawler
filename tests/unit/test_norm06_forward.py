"""NORM-06 forward direction (D-306) — viled brands with zero slug-matches."""

from __future__ import annotations

from ga_crawler.runner.stats import compute_norm06_forward


def test_norm06_forward_partial_match() -> None:
    """Givenchy in sitemap, Tom Ford absent → 1 unmatched brand."""
    sitemap = {"givenchy": ["https://goldapple.kz/100-givenchy"]}
    aliases = {"givenchy": ["Givenchy"], "tom_ford": ["Tom Ford"]}
    matched, unmatched_count, unmatched_list = compute_norm06_forward(
        ["givenchy", "tom_ford"], aliases, sitemap
    )
    assert matched == ["https://goldapple.kz/100-givenchy"]
    assert unmatched_count == 1
    assert unmatched_list == ["tom_ford"]


def test_norm06_forward_all_matched() -> None:
    sitemap = {
        "givenchy": ["https://goldapple.kz/100-givenchy"],
        "tom-ford": ["https://goldapple.kz/200-tom-ford"],
    }
    aliases = {"givenchy": ["Givenchy"], "tom_ford": ["Tom Ford"]}
    matched, unmatched_count, unmatched_list = compute_norm06_forward(
        ["givenchy", "tom_ford"], aliases, sitemap
    )
    assert len(matched) == 2
    assert unmatched_count == 0
    assert unmatched_list == []


def test_norm06_forward_empty_input() -> None:
    matched, unmatched_count, unmatched_list = compute_norm06_forward([], {}, {})
    assert matched == []
    assert unmatched_count == 0
    assert unmatched_list == []


def test_norm06_forward_all_unmatched() -> None:
    """All viled brands missing from sitemap → all unmatched."""
    aliases = {"a": ["A"], "b": ["B"], "c": ["C"]}
    matched, unmatched_count, unmatched_list = compute_norm06_forward(
        ["a", "b", "c"], aliases, {}
    )
    assert matched == []
    assert unmatched_count == 3
    assert sorted(unmatched_list) == ["a", "b", "c"]


def test_norm06_forward_bilingual_match_counts_brand_once() -> None:
    """Bilingual brand hits TWO sitemap slugs (ASCII + Cyrillic) → still matched (count=1 unmatched=0)."""
    sitemap = {
        "este-lauder": ["https://goldapple.kz/100-este-lauder"],
        "эсте-лаудер": ["https://goldapple.kz/200-эсте-лаудер"],
    }
    aliases = {"estee_lauder": ["Estée Lauder", "Эсте Лаудер"]}
    matched, unmatched_count, unmatched_list = compute_norm06_forward(
        ["estee_lauder"], aliases, sitemap
    )
    assert len(matched) == 2
    assert unmatched_count == 0
    assert unmatched_list == []
