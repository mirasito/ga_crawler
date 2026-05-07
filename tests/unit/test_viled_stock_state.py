"""PARSE-06 — viled stock-state derivation (focused unit tests).

Plan 02-04 / Wave 3 GREEN. Pairs with test_viled_nextdata_parser.py — those
tests assert end-to-end parse_pdp behaviour; these target the helper
`_map_stock_state` directly so future field-name shifts (e.g. PREORDER spelling
revisions per first weekly run) can be regression-tested without rebuilding
__NEXT_DATA__ envelopes.

Source: 02-WAVE0-PROBE.md A1 REVISED (count + purchaseType, no in_stock bool);
02-CONTEXT.md D-217.
"""

from __future__ import annotations

from ga_crawler.parsers.viled_nextdata import _map_stock_state


def test_in_stock_when_count_positive_online():
    assert _map_stock_state({"count": 5, "purchaseType": "ONLINE"}) == "IN_STOCK"


def test_in_stock_when_count_positive_no_purchase_type():
    """purchaseType missing but count > 0 still → IN_STOCK (most permissive default)."""
    assert _map_stock_state({"count": 1}) == "IN_STOCK"


def test_out_of_stock_when_count_zero():
    assert _map_stock_state({"count": 0, "purchaseType": "ONLINE"}) == "OUT_OF_STOCK"


def test_out_of_stock_when_count_zero_preorder():
    """count == 0 dominates — even if purchaseType says PREORDER."""
    assert _map_stock_state({"count": 0, "purchaseType": "PREORDER"}) == "OUT_OF_STOCK"


def test_unavailable_when_preorder():
    assert _map_stock_state({"count": 3, "purchaseType": "PREORDER"}) == "UNAVAILABLE"


def test_unknown_when_count_missing():
    assert _map_stock_state({"purchaseType": "ONLINE"}) == "UNKNOWN"


def test_unknown_when_count_non_int():
    assert _map_stock_state({"count": "5", "purchaseType": "ONLINE"}) == "UNKNOWN"
    assert _map_stock_state({"count": None}) == "UNKNOWN"


def test_unknown_when_empty_dict():
    assert _map_stock_state({}) == "UNKNOWN"
