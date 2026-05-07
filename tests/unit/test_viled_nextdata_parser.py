"""PARSE-01..04 + PARSE-06 — viled `__NEXT_DATA__` PDP parser.

Wave 3 / Plan 02-04 implements `src/ga_crawler/parsers/viled_nextdata.py`.
Extracts from `props.pageProps`:
  - PARSE-01 product fields: name (item.name), brand (item.brandName),
    sku_id (item.id), url (passed in), volume_raw (parsed from item.name or
    item.selectAttributes), images (item.images)
  - PARSE-02 dispatch path: `__NEXT_DATA__`-first (no JSON-LD on viled per spike 01-07)
  - PARSE-03 prices: current = attributes[0].price; was =
    attributes[0].realPrice if attributes[0].enableDiscount else None
  - PARSE-04 multipack-flag: derived NORM-04 invocation
  - PARSE-06 stock_state: derived from item.count + item.purchaseType per
    02-WAVE0-PROBE.md A1 REVISED (no in_stock boolean — count > 0 ⇒ IN_STOCK,
    count == 0 ⇒ OUT_OF_STOCK, purchaseType=="PREORDER" ⇒ UNAVAILABLE)

Drives off `viled_pdp_html`, `viled_pdp_discounted_html`,
`viled_pdp_multipack_html` fixtures.

Source: 02-RESEARCH.md §Validation Architecture row 13 + Pattern 1 (REVISED);
02-WAVE0-PROBE.md A1 + A2.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
