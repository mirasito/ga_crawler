"""PARSE-06 — viled stock-state derivation (split out from test_viled_nextdata_parser).

Wave 3 / Plan 02-04 — focused test of the `detect_stock_state(pp)` helper:
  - item.count > 0 AND purchaseType == 'ONLINE' → IN_STOCK
  - item.count == 0 → OUT_OF_STOCK
  - item.count missing / non-int → UNKNOWN
  - purchaseType == 'PREORDER' → UNAVAILABLE (TBD: verify field-value spelling
    empirically Wave 1 of Plan 04; revise per first weekly run)
  - HTTP 404 / no __NEXT_DATA__ at all → DELISTED (handled at fetcher level)

Drives off `viled_pdp_html` (canonical IN_STOCK) and a synthesized
out-of-stock fixture (Plan 04 Wave 1 task — clone canonical, patch count=0).

Source: 02-RESEARCH.md §Validation Architecture (PARSE-06 row split);
02-CONTEXT.md D-217; 02-WAVE0-PROBE.md A1 REVISED.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
