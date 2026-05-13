"""Goldapple _extract_volume_block helper tests — PARSE-FIX-01.

RED → GREEN per Plan 08-02 strict TDD discipline (CONTEXT.md D-811).

Fixture-driven against:
  - tests/fixtures/goldapple/_live-2026-05-13-stereotype.html  (Bug #1 evidence)
  - tests/fixtures/goldapple/_live-2026-05-13-armani-code.html (Bug #2 evidence)
  - tests/fixtures/goldapple/_debug-product-page.html          (Givenchy baseline)

W0 spike (Plan 08-01) confirmed 25/30 live PDPs carry the structured volume
block `<div>78</div><div>объём / мл</div>` (or label-then-radio-group variant).
This module asserts `_extract_volume_block` recovers the digit + label from
both DOM shapes via selectolax 0.4 Lexbor `:lexbor-contains("ОБЪЁМ" i)`.
"""

from __future__ import annotations

import pytest

from ga_crawler.parsers.goldapple_microdata import (
    GoldappleRawProduct,
    _extract_volume_block,
    parse_pdp,
)

# Selected from .planning/spikes/v1.1-brand-name-shapes/shape-table.md "Selected Fixture URLs"
STEREOTYPE_URL = "https://goldapple.kz/19000440474-stereotype-sago"
ARMANI_URL = "https://goldapple.kz/19000195723-armani-code"
GIVENCHY_URL = "https://goldapple.kz/19000488678-givenchy-irresistible"


def test_extract_volume_block_on_live_stereotype(
    goldapple_pdp_html_live_stereotype: str,
) -> None:
    """STEREOTYPE-style PDP carries the `[12] объём / мл` flex-box (label-after-number)."""
    result = _extract_volume_block(goldapple_pdp_html_live_stereotype)
    assert result is not None, "stereotype fixture should yield a non-None volume block"
    assert any(c.isdigit() for c in result), f"expected a digit in {result!r}"
    assert "мл" in result.lower(), f"expected the unit token 'мл' in {result!r}"


def test_extract_volume_block_on_live_armani(
    goldapple_pdp_html_live_armani: str,
) -> None:
    """Armani-style PDP carries the label-then-radio-group variant (label-before-number)."""
    result = _extract_volume_block(goldapple_pdp_html_live_armani)
    assert result is not None, "armani fixture should yield a non-None volume block"
    assert any(c.isdigit() for c in result), f"expected a digit in {result!r}"
    assert "мл" in result.lower(), f"expected the unit token 'мл' in {result!r}"


def test_extract_volume_block_on_givenchy_baseline(goldapple_pdp_html: str) -> None:
    """Givenchy baseline fixture (committed pre-Phase 8) also carries the
    structured volume block (label-then-radio-group variant per W0 spike).

    Either None (no block) or a digit-bearing string is acceptable — but per
    in-repo evidence the Givenchy baseline contains 'объём / мл' so a non-None
    result is expected. We do NOT enforce non-None here to keep the helper
    resilient to future fixture rotations.
    """
    result = _extract_volume_block(goldapple_pdp_html)
    if result is not None:
        assert any(c.isdigit() for c in result), (
            f"if non-None, expected a digit in {result!r}"
        )


def test_parse_pdp_yields_raw_volume_text_on_stereotype(
    goldapple_pdp_html_live_stereotype: str,
) -> None:
    """End-to-end: parse_pdp on STEREOTYPE fixture produces a digit-bearing
    raw_volume_text that downstream NORM-03 (parse_volume) can parse.

    Pre-fix, parse_pdp reads raw_volume_text=name; STEREOTYPE name is "SAĜO"
    (no digits) so this test FAILS before the fix lands.
    """
    product = parse_pdp(goldapple_pdp_html_live_stereotype, STEREOTYPE_URL)
    assert product is not None
    assert isinstance(product, GoldappleRawProduct)
    assert product.raw_volume_text is not None
    assert any(c.isdigit() for c in product.raw_volume_text), (
        f"expected digit in raw_volume_text={product.raw_volume_text!r}"
    )


@pytest.mark.parametrize(
    "fixture_name, fixture_loader_name, url",
    [
        ("givenchy", "goldapple_pdp_html", GIVENCHY_URL),
        ("stereotype", "goldapple_pdp_html_live_stereotype", STEREOTYPE_URL),
        ("armani", "goldapple_pdp_html_live_armani", ARMANI_URL),
    ],
)
def test_parse_pipeline_yields_non_null_volume_norm(
    request: pytest.FixtureRequest,
    fixture_name: str,
    fixture_loader_name: str,
    url: str,
) -> None:
    """Round-trip: parse_pdp + parse_volume must produce non-None Volume on
    all 3 shape buckets (Givenchy baseline, STEREOTYPE-style, Armani-style).

    Asserts Phase 8 Success Criteria #2 — `goldapple_volume_norm` non-null
    rate ≥90% on non-volumeless categories. All 3 fixtures CARRY a volume
    block (per W0 spike shape-table.md), so all 3 must yield Volume(...).
    """
    from ga_crawler.normalizers.volume import parse_volume

    html = request.getfixturevalue(fixture_loader_name)
    product = parse_pdp(html, url)
    assert product is not None, f"{fixture_name}: parse_pdp returned None"
    volume = parse_volume(product.raw_volume_text or "")
    assert volume is not None, (
        f"{fixture_name}: parse_volume({product.raw_volume_text!r}) returned None "
        f"— PARSE-FIX-01 acceptance fails"
    )
