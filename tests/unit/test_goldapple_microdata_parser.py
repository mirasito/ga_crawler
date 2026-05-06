"""Goldapple microdata parser tests - round-trip + priceType + sanity + enum."""

from __future__ import annotations

import pytest
from selectolax.parser import HTMLParser

from ga_crawler.parsers.goldapple_microdata import (
    GoldappleRawProduct,
    _extract_availability,
    _extract_strikethrough,
    parse_pdp,
)

# ---- Round-trip on real PDP fixture (PARSE-01 / PARSE-06) ----

GIVENCHY_URL = "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label"


def test_parse_real_pdp_returns_product(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert isinstance(product, GoldappleRawProduct)


def test_parse_real_pdp_brand_is_givenchy(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert product.brand_raw.strip().lower() == "givenchy"


def test_parse_real_pdp_price_in_sanity_range(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert 100 <= product.current_price <= 1_000_000  # PARSE-04


def test_parse_real_pdp_currency_kzt(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert product.currency == "KZT"


def test_parse_real_pdp_availability_in_enum(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert product.availability in {"InStock", "OutOfStock", "Discontinued", "PreOrder", "Unknown"}


def test_parse_real_pdp_name_non_empty(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert product.name
    assert len(product.name) > 5


def test_parse_real_pdp_sku_numeric(goldapple_pdp_html: str) -> None:
    product = parse_pdp(goldapple_pdp_html, GIVENCHY_URL)
    assert product is not None
    assert product.sku_id.isdigit()


# ---- Gate-shell / stale-SKU rejection ----


def test_parse_gate_shell_returns_none(gate_shell_html: str) -> None:
    assert parse_pdp(gate_shell_html, GIVENCHY_URL) is None


def test_parse_stale_sku_returns_none(stale_sku_html: str) -> None:
    assert parse_pdp(stale_sku_html, GIVENCHY_URL) is None


# ---- PARSE-03 priceType discrimination (Pitfall 2) ----


def _make_html_two_prices(top_price: str, strikethrough_price: str) -> str:
    """Synthetic >=30KB HTML with one top-level Offer + one StrikethroughPrice priceSpecification."""
    filler = "<!-- " + ("x" * 35000) + " -->"
    return f"""<!DOCTYPE html>
<html><head><title>Test PDP</title></head><body>
{filler}
<h1>Test Product</h1>
<div itemprop="offers" itemtype="https://schema.org/Offer">
  <link itemprop="availability" href="https://schema.org/InStock"/>
  <span itemprop="brand" itemscope itemtype="https://schema.org/Brand">
    <meta itemprop="name" content="Test Brand"/>
  </span>
  <meta itemprop="price" content="{top_price}"/>
  <meta itemprop="priceCurrency" content="KZT"/>
  <div itemprop="priceSpecification" itemscope itemtype="https://schema.org/UnitPriceSpecification">
    <link itemprop="priceType" href="https://schema.org/StrikethroughPrice"/>
    <meta itemprop="price" content="{strikethrough_price}"/>
  </div>
</div>
</body></html>"""


def test_pricetype_filter_picks_top_level_not_strikethrough() -> None:
    html = _make_html_two_prices(top_price="4990", strikethrough_price="6990")
    product = parse_pdp(html, "https://goldapple.kz/100-test")
    assert product is not None
    assert product.current_price == 4990
    assert product.was_price == 6990


def test_pricetype_only_listprice_returns_none() -> None:
    """Synthetic PDP with ONLY ListPrice priceSpecification (no top-level offer block)."""
    filler = "<!-- " + ("x" * 35000) + " -->"
    html = f"""<!DOCTYPE html><html><head><title>Test</title></head><body>
{filler}
<h1>From Test Product</h1>
<div itemprop="priceSpecification" itemscope itemtype="https://schema.org/UnitPriceSpecification">
  <link itemprop="priceType" href="https://schema.org/ListPrice"/>
  <meta itemprop="price" content="3000"/>
</div>
</body></html>"""
    assert parse_pdp(html, "https://goldapple.kz/100-test") is None


def test_pricetype_gold_card_section_excluded() -> None:
    """Top-level offer wraps both public price AND nested 'при авторизации' block.
    Public price (4990) wins; Gold Card (4490) inside section is excluded.
    """
    filler = "<!-- " + ("x" * 35000) + " -->"
    html = f"""<!DOCTYPE html><html><head><title>Test</title></head><body>
{filler}
<h1>Test Product</h1>
<div itemprop="offers" itemtype="https://schema.org/Offer">
  <link itemprop="availability" href="https://schema.org/InStock"/>
  <meta itemprop="price" content="4990"/>
</div>
<div itemprop="offers" itemtype="https://schema.org/Offer">
  <link itemprop="availability" href="https://schema.org/InStock"/>
  <span class="price-row__row">при авторизации</span>
  <meta itemprop="price" content="4490"/>
</div>
</body></html>"""
    product = parse_pdp(html, "https://goldapple.kz/100-test")
    assert product is not None
    assert product.current_price == 4990


def test_bonus_button_with_login_text_does_not_poison_price() -> None:
    """Regression for 03-07 live-smoke: a `<button>` containing "при авторизации"
    inside a bonus-badge subtree must NOT cause adjacent price metas to be
    classified as Gold Card. Both prices are public; the lower one is current.
    """
    filler = "<!-- " + ("x" * 35000) + " -->"
    html = f"""<!DOCTYPE html><html><head><title>Test</title></head><body>
{filler}
<h1>Test Product</h1>
<div itemprop="offers" itemtype="http://schema.org/Offer">
  <div class="hidden-availability"><link itemprop="availability" href="http://schema.org/InStock"/></div>
  <button class="bonus-badge"><div><i class="ico"></i><span>Бонусы при авторизации</span></div></button>
  <meta itemprop="price" content="72020"/>
  <meta itemprop="priceCurrency" content="KZT"/>
  <meta itemprop="price" content="43212"/>
  <meta itemprop="priceCurrency" content="KZT"/>
</div>
</body></html>"""
    product = parse_pdp(html, "https://goldapple.kz/100-test")
    assert product is not None
    # Min-value selection: 43212 (sale) wins over 72020 (was)
    assert product.current_price == 43212
    assert product.currency == "KZT"


def test_zero_filler_price_is_skipped() -> None:
    """PARSE-04 sanity range must skip price=0 sentinel filler metas even when
    they are syntactically valid offer entries (live PDPs sometimes emit
    `<meta itemprop="price" content="0"/>` for unavailable variants).
    """
    filler = "<!-- " + ("x" * 35000) + " -->"
    html = f"""<!DOCTYPE html><html><head><title>Test</title></head><body>
{filler}
<h1>Test</h1>
<div itemprop="offers" itemtype="https://schema.org/Offer">
  <link itemprop="availability" href="https://schema.org/InStock"/>
  <meta itemprop="price" content="5000"/>
</div>
<div itemprop="offers" itemtype="https://schema.org/Offer">
  <link itemprop="availability" href="https://schema.org/InStock"/>
  <meta itemprop="price" content="0"/>
</div>
</body></html>"""
    product = parse_pdp(html, "https://goldapple.kz/100-test")
    assert product is not None
    assert product.current_price == 5000


# ---- PARSE-04 sanity range ----


@pytest.mark.parametrize(
    "price,should_pass",
    [
        ("50", False),  # below 100 - out of range
        ("99", False),
        ("100", True),  # boundary: 100 inclusive
        ("4990", True),
        ("1000000", True),  # boundary: 1M inclusive
        ("1000001", False),
        ("2000000", False),
    ],
)
def test_parse04_sanity_range(price: str, should_pass: bool) -> None:
    html = _make_html_two_prices(top_price=price, strikethrough_price="9999")
    product = parse_pdp(html, "https://goldapple.kz/100-test")
    if should_pass:
        assert product is not None
        assert product.current_price == int(price)
    else:
        assert product is None


# ---- PARSE-06 availability enum mapping ----


@pytest.mark.parametrize(
    "href, expected",
    [
        ("https://schema.org/InStock", "InStock"),
        ("https://schema.org/OutOfStock", "OutOfStock"),
        ("https://schema.org/Discontinued", "Discontinued"),
        ("https://schema.org/PreOrder", "PreOrder"),
        ("https://schema.org/SoldOut", "Unknown"),  # unknown type -> Unknown
        ("", "Unknown"),
    ],
)
def test_parse06_availability_enum(href: str, expected: str) -> None:
    html = f"<html><body><link itemprop='availability' href='{href}'/></body></html>"
    tree = HTMLParser(html)
    assert _extract_availability(tree) == expected


def test_parse06_no_availability_link_unknown() -> None:
    tree = HTMLParser("<html><body></body></html>")
    assert _extract_availability(tree) == "Unknown"


# ---- JSON-LD anti-fixture: confirm goldapple has only OfferShippingDetails ----


def test_goldapple_jsonld_has_no_product_schema(jsonld_blocks_anti_fixture) -> None:
    """D-14 revision: goldapple emits ONLY OfferShippingDetails JSON-LD.
    Parser MUST NOT use JSON-LD path for goldapple.

    The fixture is the empirical proof. Anti-fixture style assertion.
    """
    blocks = jsonld_blocks_anti_fixture
    # Accept either list-of-blocks or dict shape
    if isinstance(blocks, dict):
        blocks = [blocks]
    if not isinstance(blocks, list):
        return  # tolerant - fixture may be empty
    types_found: list[str] = []
    for blk in blocks:
        if not isinstance(blk, dict):
            continue
        t = blk.get("@type", "")
        if isinstance(t, list):
            types_found.extend(t)
        else:
            types_found.append(str(t))
    # No Product schema present (per spike 01-06 finding + plan 01-08 confirmation)
    assert "Product" not in types_found, (
        f"unexpected Product JSON-LD found in goldapple anti-fixture; "
        f"D-14 revision says microdata-only. types={types_found}"
    )


# ---- Strikethrough extractor unit ----


def test_extract_strikethrough_returns_int_when_present() -> None:
    html = """<html><body>
<div itemprop="priceSpecification">
  <link itemprop="priceType" href="https://schema.org/StrikethroughPrice"/>
  <meta itemprop="price" content="6990"/>
</div>
</body></html>"""
    tree = HTMLParser(html)
    assert _extract_strikethrough(tree) == 6990


def test_extract_strikethrough_none_when_absent() -> None:
    tree = HTMLParser("<html><body></body></html>")
    assert _extract_strikethrough(tree) is None


def test_extract_strikethrough_none_when_listprice_only() -> None:
    html = """<html><body>
<div itemprop="priceSpecification">
  <link itemprop="priceType" href="https://schema.org/ListPrice"/>
  <meta itemprop="price" content="6990"/>
</div>
</body></html>"""
    tree = HTMLParser(html)
    assert _extract_strikethrough(tree) is None
