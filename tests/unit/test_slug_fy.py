"""Unit tests for slug.py — 11 mandatory cases per RESEARCH §Pattern 2 lines 427-439."""

from __future__ import annotations

import pytest

from ga_crawler.enumeration.slug import (
    CYRILLIC_TO_LATIN,
    _normalize_punct,
    slug_fy_bilingual,
)


@pytest.mark.parametrize(
    "alias, expected",
    [
        # 11 mandatory cases from RESEARCH lines 427-439
        ("Estée Lauder", ["estee-lauder"]),
        ("Эсте Лаудер", ["este-lauder", "эсте-лаудер"]),
        ("Tom Ford", ["tom-ford"]),
        ("Tom Ford Beauty", ["tom-ford-beauty"]),  # Pitfall 3 false-positive guard
        ("Frédéric Malle", ["frederic-malle"]),
        ("Dolce&Gabbana", ["dolce-gabbana"]),
        ("L'Oréal Paris", ["loreal-paris"]),
        ("Жильет", ["zhilet", "жильет"]),
        ("Givenchy ", ["givenchy"]),
        ("Jo Malone London", ["jo-malone-london"]),
        ("", []),
    ],
)
def test_slug_fy_bilingual_eleven_cases(alias: str, expected: list[str]) -> None:
    assert slug_fy_bilingual(alias) == expected


def test_slug_fy_bilingual_idempotent() -> None:
    """Running slug-fy on already-slug input is stable (no double-transliteration)."""
    once = slug_fy_bilingual("Tom Ford")[0]
    twice = slug_fy_bilingual(once)
    assert twice == ["tom-ford"]


def test_slug_fy_bilingual_kz_glyph() -> None:
    """KZ-specific glyph 'ә' transliterates to 'a' — sanity that map covers KZ brand strings."""
    result = slug_fy_bilingual("Әсем")
    # Cyrillic-preserved slug emitted (input contains Cyrillic-range char)
    assert "әсем" in result
    # ASCII slug uses transliteration map: ә→a, с→s, е→e, м→m
    assert "asem" in result


def test_normalize_punct_collapses_hyphens() -> None:
    assert _normalize_punct("foo  bar---baz") == "foo-bar-baz"


def test_cyrillic_to_latin_table_has_kz_glyphs() -> None:
    """Pitfall 4 — KZ glyphs explicitly mapped (test catches accidental table truncation)."""
    for kz_glyph in ("ә", "ғ", "қ", "ң", "ө", "ұ", "ү", "һ", "і"):
        assert kz_glyph in CYRILLIC_TO_LATIN, f"missing KZ glyph: {kz_glyph}"
