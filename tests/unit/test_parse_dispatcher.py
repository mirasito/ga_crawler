"""PARSE-02 — `ParseDispatcher` retailer-keyed parser dispatch.

Plan 02-04 / Wave 3 GREEN. Concrete dispatcher routes:
  - "viled"     → ga_crawler.parsers.viled_nextdata.parse_pdp
  - "goldapple" → ga_crawler.parsers.goldapple_microdata.parse_pdp (Phase 3 FROZEN)
  - any other   → None

Source: 02-RESEARCH.md §Validation Architecture row 18; 02-CONTEXT.md D-213.
"""

from __future__ import annotations

import json

from ga_crawler.interfaces import ParseDispatcherProtocol
from ga_crawler.parsers.dispatcher import ParseDispatcher


def _viled_nextdata_html(*, price: int = 10000, real_price: int = 10000) -> str:
    nd = {
        "props": {
            "pageProps": {
                "item": {
                    "id": 1,
                    "name": "Eau de Parfum 50 ml",
                    "brandName": "Givenchy",
                    "count": 5,
                    "purchaseType": "ONLINE",
                },
                "attributes": [
                    {
                        "id": 1,
                        "price": price,
                        "realPrice": real_price,
                        "currency": "₸",
                    }
                ],
            }
        }
    }
    return (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd, ensure_ascii=False)}</script>'
        "</body></html>"
    )


def test_dispatch_viled_routes_to_nextdata_parser():
    d = ParseDispatcher()
    result = d.dispatch("viled", _viled_nextdata_html(price=15000), "https://viled.kz/item/1")
    assert result is not None
    assert isinstance(result, dict)
    assert result["current_price"] == 15000
    assert result["brand_raw"] == "Givenchy"
    assert result["currency"] == "KZT"
    assert result["sku_id"] == "1"


def test_dispatch_unknown_retailer_returns_none():
    d = ParseDispatcher()
    assert d.dispatch("amazon", "<html></html>", "u") is None


def test_dispatch_goldapple_routes_to_microdata_parser(monkeypatch):
    """Goldapple Phase 3 parser is registered & live; here we verify routing
    by monkey-patching the registry entry to a mock that returns a known
    GoldappleRawProduct (saving us from building a full microdata HTML envelope
    — those tests already exist in Phase 3 unit-test suite).
    """
    from ga_crawler.parsers.goldapple_microdata import GoldappleRawProduct

    def _fake_goldapple_parser(html: str, url: str = "") -> GoldappleRawProduct:
        return GoldappleRawProduct(
            sku_id="GA1",
            url=url,
            name="x",
            brand_raw="b",
            current_price=1000,
            was_price=None,
            currency="KZT",
            availability="InStock",
            raw_volume_text=None,
        )

    monkeypatch.setitem(ParseDispatcher._registry, "goldapple", _fake_goldapple_parser)
    out = ParseDispatcher().dispatch(
        "goldapple", "<html></html>", "https://goldapple.kz/123-foo"
    )
    assert out is not None
    assert out["sku_id"] == "GA1"
    assert out["currency"] == "KZT"


def test_dispatch_returns_none_when_parser_returns_none(monkeypatch):
    """Routing handles the parser-returns-None case (gate-shell, malformed HTML)."""
    monkeypatch.setitem(ParseDispatcher._registry, "viled", lambda h, u="": None)
    assert ParseDispatcher().dispatch("viled", "<html></html>", "u") is None


def test_satisfies_protocol():
    """Concrete impl must satisfy the runtime_checkable Protocol."""
    assert isinstance(ParseDispatcher(), ParseDispatcherProtocol)


def test_registry_contains_both_retailers():
    """Defensive: both Phase 2 (viled) and Phase 3 (goldapple) registered."""
    assert "viled" in ParseDispatcher._registry
    assert "goldapple" in ParseDispatcher._registry
