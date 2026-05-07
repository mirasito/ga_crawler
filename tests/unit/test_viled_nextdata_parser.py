"""PARSE-01..04 — viled `__NEXT_DATA__` PDP parser.

Plan 02-04 / Wave 3 GREEN. Cross-references:
  - 02-WAVE0-PROBE.md §A1 REVISED (item.count + item.purchaseType, no in_stock bool)
  - 02-WAVE0-PROBE.md §A2 VERIFIED (price=current, realPrice=was; price < realPrice ⇒ discount)
  - STATE.md plan 01-07 (was_price satisfiable via realPrice; currency hardcoded KZT)

Drives off `viled_pdp_html` and `viled_pdp_discounted_html` Wave 0 fixtures
(see tests/conftest.py and tests/fixtures/viled/).
"""

from __future__ import annotations

import inspect
import json

from ga_crawler.parsers import viled_nextdata
from ga_crawler.parsers.viled_nextdata import ViledRawProduct, parse_pdp


URL = "https://viled.kz/item/407682"


def _make_html_with_nextdata(nd_obj: dict) -> str:
    """Wrap a __NEXT_DATA__ dict into a minimal HTML envelope."""
    payload = json.dumps(nd_obj, ensure_ascii=False)
    return (
        "<html><head></head><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{payload}</script>'
        "</body></html>"
    )


def _base_nextdata(
    *,
    price: int = 15000,
    real_price: int = 15000,
    enable_discount: bool = False,
    currency: str = "₸",
    name: str = "Туалетная вода 50 мл",
    brand_name: str = "Givenchy",
    item_count: int = 5,
    purchase_type: str = "ONLINE",
    item_id: int = 407682,
) -> dict:
    return {
        "props": {
            "pageProps": {
                "item": {
                    "id": item_id,
                    "name": name,
                    "brandName": brand_name,
                    "count": item_count,
                    "purchaseType": purchase_type,
                },
                "attributes": [
                    {
                        "id": 1,
                        "price": price,
                        "realPrice": real_price,
                        "currency": currency,
                        "enableDiscount": enable_discount,
                    }
                ],
            }
        }
    }


# ---------- PARSE-01: extraction happy path against the live fixture ----------


def test_full_extract_from_live_fixture(viled_pdp_html):
    """Wave 0 canonical fixture (item/407682) yields a ViledRawProduct with all
    required fields populated and current_price in PARSE-04 sanity range.
    """
    p = parse_pdp(viled_pdp_html, URL)
    assert isinstance(p, ViledRawProduct), "canonical fixture must parse"
    assert p.name
    assert p.brand_raw == "Alice+Olivia"
    assert 100 <= p.current_price <= 1_000_000
    # canonical fixture is in stock with count=2, purchaseType=ONLINE
    assert p.availability == "IN_STOCK"
    # Currency hardcoded regardless of input
    assert p.currency == "KZT"


# ---------- PARSE-03: discount semantics (Reading A — PROBE A2) ----------


def test_realprice_priority_discounted():
    """PARSE-03: discounted SKU has price < realPrice.
    `price` is the current/sale price the customer pays; `realPrice` is the
    pre-discount MSRP captured as was_price.
    """
    nd = _base_nextdata(price=10000, real_price=15000, enable_discount=True)
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.current_price == 10000  # customer pays this now
    assert p.was_price == 15000  # MSRP (struck-through in UI)


def test_no_discount_was_price_none():
    """When price == realPrice, was_price MUST be None (no discount to record)."""
    nd = _base_nextdata(price=15000, real_price=15000)
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.current_price == 15000
    assert p.was_price is None


def test_realprice_below_price_was_price_none():
    """If realPrice < price (data anomaly), was_price MUST be None — never invert.
    Anti-was/old/crossed-fields invariant: was_price > current_price always, or None.
    """
    nd = _base_nextdata(price=15000, real_price=12000)
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.current_price == 15000
    assert p.was_price is None


def test_discounted_fixture_real_corpus(viled_pdp_discounted_html):
    """Live discounted fixture (item/367251 Frederic Malle): price=356745 <
    realPrice=419700 ⇒ current=356745, was=419700.
    """
    p = parse_pdp(viled_pdp_discounted_html, "https://viled.kz/item/367251")
    assert p is not None
    assert p.current_price == 356745
    assert p.was_price == 419700


# ---------- PARSE-04: sanity range ----------


def test_sanity_range_low():
    """current_price < 100 → reject."""
    nd = _base_nextdata(price=50, real_price=50)
    html = _make_html_with_nextdata(nd)
    assert parse_pdp(html, URL) is None


def test_sanity_range_high():
    """current_price > 1_000_000 → reject."""
    nd = _base_nextdata(price=2_000_000, real_price=2_000_000)
    html = _make_html_with_nextdata(nd)
    assert parse_pdp(html, URL) is None


def test_sanity_range_boundaries_inclusive():
    """current_price == 100 and == 1_000_000 are valid (inclusive)."""
    for boundary in (100, 1_000_000):
        nd = _base_nextdata(price=boundary, real_price=boundary)
        html = _make_html_with_nextdata(nd)
        p = parse_pdp(html, URL)
        assert p is not None, f"boundary {boundary} should be valid"
        assert p.current_price == boundary


# ---------- PARSE-02 inversion: NO JSON-LD path ----------


def test_no_jsonld_path():
    """PARSE-02 inversion: viled parser MUST NOT contain JSON-LD code paths.
    Anti-fixture: spike 01-07 found 0/15 JSON-LD on viled PDPs; the parser is
    __NEXT_DATA__-only by design.
    """
    src = inspect.getsource(viled_nextdata)
    # Strip line comments and docstrings to allow free-form prose mention.
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.strip().startswith("#")
    )
    # Within actual code, no jsonld constants / strings / imports.
    lower = code_only.lower()
    assert 'application/ld+json' not in lower, "viled parser must not look for JSON-LD"
    assert 'jsonld' not in lower, "viled parser must not import or reference jsonld"


# ---------- Currency hardcode (STATE.md plan 01-07 lock) ----------


def test_currency_hardcode_tenge_symbol():
    """₸ raw → KZT canonical."""
    nd = _base_nextdata(currency="₸")
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.currency == "KZT"


def test_currency_hardcode_unknown_input_still_kzt():
    """Even an unexpected raw currency does not propagate — KZT unconditional."""
    nd = _base_nextdata(currency="USD")
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.currency == "KZT"


# ---------- PARSE-06: stock-state derivation per A1 REVISED ----------


def test_stock_state_in_stock_count_positive_online():
    """count > 0 AND purchaseType == 'ONLINE' → IN_STOCK."""
    nd = _base_nextdata(item_count=10, purchase_type="ONLINE")
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.availability == "IN_STOCK"


def test_stock_state_out_of_stock_count_zero():
    """count == 0 → OUT_OF_STOCK regardless of purchaseType."""
    nd = _base_nextdata(item_count=0, purchase_type="ONLINE")
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.availability == "OUT_OF_STOCK"


def test_stock_state_unavailable_preorder():
    """count > 0 AND purchaseType == 'PREORDER' → UNAVAILABLE."""
    nd = _base_nextdata(item_count=5, purchase_type="PREORDER")
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.availability == "UNAVAILABLE"


def test_stock_state_unknown_when_count_missing():
    """item.count absent / non-int → UNKNOWN."""
    nd = {
        "props": {
            "pageProps": {
                "item": {"id": 1, "name": "x", "brandName": "y"},  # no count
                "attributes": [{"price": 1000, "realPrice": 1000, "currency": "₸"}],
            }
        }
    }
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.availability == "UNKNOWN"


# ---------- Negative-path guards ----------


def test_returns_none_when_no_nextdata():
    html = "<html><body>no script tag here</body></html>"
    assert parse_pdp(html, URL) is None


def test_returns_none_when_attributes_empty():
    """Pitfall 2 guard: empty attributes list ⇒ no canonical price ⇒ None."""
    nd = {
        "props": {
            "pageProps": {
                "item": {"id": 1, "name": "x", "brandName": "y", "count": 1, "purchaseType": "ONLINE"},
                "attributes": [],
            }
        }
    }
    html = _make_html_with_nextdata(nd)
    assert parse_pdp(html, URL) is None


def test_returns_none_when_name_missing():
    nd = _base_nextdata(name="")
    html = _make_html_with_nextdata(nd)
    assert parse_pdp(html, URL) is None


def test_returns_none_when_brand_missing():
    nd = _base_nextdata(brand_name="")
    html = _make_html_with_nextdata(nd)
    assert parse_pdp(html, URL) is None


def test_returns_none_on_malformed_json():
    html = (
        "<html><body>"
        '<script id="__NEXT_DATA__" type="application/json">{not json}</script>'
        "</body></html>"
    )
    assert parse_pdp(html, URL) is None


def test_returns_none_when_price_non_numeric():
    """attributes[0].price not coercible → None (no fallback fabrication)."""
    nd = _base_nextdata()
    nd["props"]["pageProps"]["attributes"][0]["price"] = "not-a-number"
    html = _make_html_with_nextdata(nd)
    assert parse_pdp(html, URL) is None


# ---------- sku_id derivation ----------


def test_sku_id_extracted_from_item_url():
    nd = _base_nextdata()
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, "https://viled.kz/item/407682")
    assert p is not None
    assert p.sku_id == "407682"


def test_sku_id_fallback_last_path_segment():
    """When URL has no /item/N pattern, fall back to last path segment."""
    nd = _base_nextdata()
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, "https://viled.kz/some/random/path/X9")
    assert p is not None
    assert p.sku_id == "X9"


def test_raw_volume_text_passthrough_is_name():
    nd = _base_nextdata(name="Парфюмерная вода 100 мл")
    html = _make_html_with_nextdata(nd)
    p = parse_pdp(html, URL)
    assert p is not None
    assert p.raw_volume_text == "Парфюмерная вода 100 мл"
