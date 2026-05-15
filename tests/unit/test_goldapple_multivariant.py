"""Unit tests for goldapple_brand multi-variant top-up
(`fetch_product_variants` + `variant_to_raw_product`).

Shapes derived from live probe captures in
``inbox/ga_pdp_card_api/{clinique_lotion,almost_lipstick}.json`` —
inlined here so the tests stay self-contained and survive inbox cleanup.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ga_crawler.enumeration.goldapple_brand import (
    fetch_product_variants,
    variant_to_raw_product,
)
from ga_crawler.parsers.goldapple_microdata import GoldappleRawProduct


# ---- Fixtures (inline shape derived from product-card/base/v3 probes) ----


def _variant_size(item_id: str, name: str, units: str, amount: int) -> dict:
    """Two-size variant card (Clinique Dramatically Different shape)."""
    return {
        "itemId": item_id,
        "name": name,
        "url": f"/{item_id}-dramatically-different-moisturizing-lotion",
        "inStock": True,
        "attributesValue": {"units": units, "colors": ""},
        "price": {
            "regular": {"currency": "KZT", "amount": amount + 9000, "denominator": 1},
            "actual": {"currency": "KZT", "amount": amount, "denominator": 1},
            "old": {"currency": "KZT", "amount": amount + 9000, "denominator": 1},
        },
    }


def _variant_shade(item_id: str, shade: str, amount: int = 13668) -> dict:
    """Single-size, multi-shade variant card (Almost Lipstick shape)."""
    return {
        "itemId": item_id,
        "name": "almost lipstick",
        "url": f"/{item_id}-almost-lipstick",
        "inStock": True,
        "attributesValue": {"units": "1.9", "colors": shade},
        "price": {
            "actual": {"currency": "KZT", "amount": amount, "denominator": 1},
        },
    }


CLINIQUE_PRODUCT_CARD = {
    "data": {
        "id": "15250700066",
        "itemId": "15250700066",
        "name": "Dramatically Different Moisturizing Lotion+ With Pump",
        "brand": "Clinique",
        "productType": "Лосьон увлажняющий",
        "attributes": {
            "units": {"label": "объём", "unit": "мл", "options": []},
        },
        "variants": [
            _variant_size("15250700066", "125ml pump", "125", 20130),
            _variant_size("15250700065", "50ml tube", "50", 11550),
        ],
    },
}


ALMOST_LIPSTICK_CARD = {
    "data": {
        "brand": "Clinique",
        "productType": "Помада губная",
        "attributes": {"units": {"label": "вес", "unit": "г", "options": []}},
        "variants": [
            _variant_shade("19000126321", "Black Honey"),
            _variant_shade("19000247142", "Pink Honey"),
            _variant_shade("19000441665", "Nude honey"),
        ],
    },
}


# ---- variant_to_raw_product: pure logic ----


class TestVariantToRawProduct:
    def test_size_variant_basic_fields(self) -> None:
        v = _variant_size("15250700065", "50ml tube", "50", 11550)
        rp = variant_to_raw_product(
            v, brand="Clinique", product_type="Лосьон увлажняющий", unit_name="мл",
        )
        assert isinstance(rp, GoldappleRawProduct)
        assert rp.sku_id == "15250700065"
        assert rp.current_price == 11550
        assert rp.currency == "KZT"
        assert rp.availability == "InStock"
        assert rp.raw_volume_text == "50 мл"
        # composed name: "{productType} {brand} {variant.name}"
        assert "Лосьон" in rp.name
        assert "Clinique" in rp.name
        assert rp.url.startswith("https://goldapple.kz/")
        assert "15250700065" in rp.url

    def test_size_variant_was_price_when_old_above_actual(self) -> None:
        v = _variant_size("15250700066", "125ml pump", "125", 20130)
        # _variant_size sets old = actual + 9000 = 29130
        rp = variant_to_raw_product(
            v, brand="Clinique", product_type="Лосьон", unit_name="мл",
        )
        assert rp is not None
        assert rp.was_price == 29130

    def test_size_variant_was_price_none_when_old_equals_actual(self) -> None:
        v = _variant_size("999", "x", "1", 5000)
        v["price"]["old"]["amount"] = 5000  # equal → no real discount
        rp = variant_to_raw_product(v, brand="X", product_type="Y", unit_name="мл")
        assert rp is not None
        assert rp.was_price is None

    def test_shade_variant_composes_color_into_name(self) -> None:
        v = _variant_shade("19000126321", "Black Honey")
        rp = variant_to_raw_product(
            v, brand="Clinique", product_type="Помада", unit_name="г",
        )
        assert rp is not None
        # composed name must surface the shade so matcher token-overlap fires
        assert "Black Honey" in rp.name
        assert rp.raw_volume_text == "1.9 г"

    def test_actual_price_falls_back_to_regular(self) -> None:
        v = {
            "itemId": "777",
            "price": {
                "regular": {"currency": "KZT", "amount": 8000, "denominator": 1},
            },
            "attributesValue": {"units": "50", "colors": ""},
            "inStock": True,
        }
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="мл")
        assert rp is not None
        assert rp.current_price == 8000

    def test_missing_item_id_returns_none(self) -> None:
        v = {"name": "x", "price": {"actual": {"amount": 1000}}}
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="мл")
        assert rp is None

    def test_main_variant_item_id_fallback(self) -> None:
        v = {
            "mainVariantItemId": "555",
            "name": "x",
            "price": {"actual": {"currency": "KZT", "amount": 1000, "denominator": 1}},
            "attributesValue": {"units": "50", "colors": ""},
            "inStock": True,
        }
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="мл")
        assert rp is not None
        assert rp.sku_id == "555"

    def test_missing_price_returns_none(self) -> None:
        v = {
            "itemId": "555",
            "name": "x",
            "attributesValue": {"units": "50"},
            "inStock": True,
            # no price node at all
        }
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="мл")
        assert rp is None

    def test_price_below_sanity_floor_returns_none(self) -> None:
        # PARSE-04 sanity range: [100, 1_000_000]. 50 < 100 → reject.
        v = {
            "itemId": "555",
            "name": "x",
            "price": {"actual": {"currency": "KZT", "amount": 50, "denominator": 1}},
            "attributesValue": {"units": "50", "colors": ""},
            "inStock": True,
        }
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="мл")
        assert rp is None

    def test_out_of_stock_maps_to_out_of_stock(self) -> None:
        v = _variant_size("123", "x", "50", 5000)
        v["inStock"] = False
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="мл")
        assert rp is not None
        assert rp.availability == "OutOfStock"

    def test_no_unit_name_skips_raw_volume_text(self) -> None:
        v = _variant_size("123", "x", "50", 5000)
        rp = variant_to_raw_product(v, brand="B", product_type="T", unit_name="")
        assert rp is not None
        assert rp.raw_volume_text is None  # unit_name="" disables composition


# ---- fetch_product_variants: async + mocked page.evaluate ----


class _FakePage:
    """Minimal Playwright Page mock for product-card/base/v3 testing.

    Records the JS source + args of every evaluate() call so tests can
    inspect what was sent, and returns a pre-seeded response payload.
    """

    def __init__(self, *, response: Any = None, raise_exc: Exception | None = None):
        self._response = response
        self._raise = raise_exc
        self.calls: list[tuple[str, dict]] = []

    async def evaluate(self, js: str, args: dict) -> Any:
        self.calls.append((js, args))
        if self._raise is not None:
            raise self._raise
        return self._response


def _run(coro):
    """Run an async coroutine to completion (pytest-asyncio not required)."""
    return asyncio.run(coro)


class TestFetchProductVariants:
    def test_clinique_two_size_variants_expanded(self) -> None:
        page = _FakePage(response=CLINIQUE_PRODUCT_CARD)
        result = _run(fetch_product_variants(page, "15250700066"))
        assert len(result) == 2
        # 125ml at 20130 + 50ml at 11550
        prices = sorted(rp.current_price for rp in result)
        assert prices == [11550, 20130]
        sku_ids = sorted(rp.sku_id for rp in result)
        assert sku_ids == ["15250700065", "15250700066"]
        # Volume text composed via parent attributes.units.unit ("мл")
        volumes = sorted(rp.raw_volume_text for rp in result)
        assert volumes == ["125 мл", "50 мл"]

    def test_almost_lipstick_three_shades_expanded(self) -> None:
        page = _FakePage(response=ALMOST_LIPSTICK_CARD)
        result = _run(fetch_product_variants(page, "19000126321"))
        assert len(result) == 3
        sku_ids = sorted(rp.sku_id for rp in result)
        assert sku_ids == ["19000126321", "19000247142", "19000441665"]
        # Composed name must include each shade so the matcher can disambiguate
        shades = {"Black Honey", "Pink Honey", "Nude honey"}
        assert shades == {
            shade for rp in result for shade in shades if shade in rp.name
        }

    def test_evaluate_exception_returns_empty_list(self) -> None:
        page = _FakePage(raise_exc=RuntimeError("network down"))
        result = _run(fetch_product_variants(page, "999"))
        assert result == []

    def test_http_403_response_returns_empty_list(self) -> None:
        # The JS shim returns {error, status} on non-ok HTTP
        page = _FakePage(response={"error": "HTTP 403", "status": 403})
        result = _run(fetch_product_variants(page, "999"))
        assert result == []

    def test_missing_variants_array_returns_empty_list(self) -> None:
        page = _FakePage(response={"data": {"brand": "X"}})  # no variants
        result = _run(fetch_product_variants(page, "999"))
        assert result == []

    def test_non_dict_response_returns_empty_list(self) -> None:
        page = _FakePage(response="not a dict")
        result = _run(fetch_product_variants(page, "999"))
        assert result == []

    def test_variants_not_a_list_returns_empty_list(self) -> None:
        page = _FakePage(response={"data": {"variants": "not a list"}})
        result = _run(fetch_product_variants(page, "999"))
        assert result == []

    def test_malformed_variant_entries_skipped(self) -> None:
        page = _FakePage(response={
            "data": {
                "brand": "B",
                "productType": "T",
                "attributes": {"units": {"unit": "мл"}},
                "variants": [
                    {"not": "a valid variant"},  # variant_to_raw_product → None
                    _variant_size("777", "x", "50", 5000),
                    None,  # skipped at isinstance(v, dict) check
                ],
            },
        })
        result = _run(fetch_product_variants(page, "999"))
        assert len(result) == 1
        assert result[0].sku_id == "777"

    def test_evaluate_called_with_item_id(self) -> None:
        page = _FakePage(response={"data": {"variants": []}})
        _run(fetch_product_variants(page, "555"))
        assert len(page.calls) == 1
        js, args = page.calls[0]
        assert args == {"itemId": "555"}
        # JS shim must call /front/api/catalog/product-card/base/v3
        assert "/front/api/catalog/product-card/base/v3" in js
