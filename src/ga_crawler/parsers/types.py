"""Shared parser types — StockState enum + parsed-product dataclass.

Source: 02-RESEARCH.md §Pattern 1; 02-CONTEXT.md D-217 stock-state mapping.
PARSE-06: SQLModel storage uses str column; Literal validates at boundary.
"""

from __future__ import annotations

from typing import Literal


# PARSE-06 (D-217): allowed stock-state values. Storage column type is plain
# string; the Literal here is the type-checker enforcement at the parser→
# normalizer→writer boundary. Any value outside this set is a contract bug
# (see _map_stock_state in viled_nextdata.py and _extract_availability in
# goldapple_microdata.py for the producer side).
StockState = Literal[
    "IN_STOCK",
    "OUT_OF_STOCK",
    "UNAVAILABLE",
    "DELISTED",
    "URL_CHANGED",
    "UNKNOWN",
]


__all__ = ["StockState"]
