"""viled __NEXT_DATA__ extractor.

PARSE-02 inversion: viled emits __NEXT_DATA__ for 15/15 PDPs and 0/15 JSON-LD per
spike 01-07. There is NO JSON-LD fallback path here; the only data source is the
inline `<script id="__NEXT_DATA__" type="application/json">` payload.

Source: 02-RESEARCH.md §Pattern 1 (paths originally ASSUMED, then revised).
Wave-0-corrected paths: see
.planning/phases/02-project-skeleton-viled-crawl-storage/02-WAVE0-PROBE.md
  - A1 REVISED: viled has NO `attributes[0].in_stock` boolean. Stock-state
    derives from `props.pageProps.item.count` (int) plus
    `props.pageProps.item.purchaseType` (str enum: 'ONLINE' / 'PREORDER' / ...).
  - A2 VERIFIED: `attributes[0].price` is the **current** selling price (after
    discount) and `attributes[0].realPrice` is the **was/MSRP** price. Discount
    detection: `price < realPrice`. (Plan 02-04 source code originally inverted
    these; corrected here per probe + STATE.md plan 01-07 finding "was_price
    requirement directly satisfiable from week 1 via realPrice field".)

Decisions: D-217 stock-state mapping; PARSE-04 sanity range [100, 1_000_000];
currency hardcoded to "KZT" (STATE.md plan 01-07 lock — viled is KZ-only).
Pitfall 2: attributes[0] picks first variant — beauty SKUs typically have ≤1
size variant; multi-variant skew is a documented v1 limitation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import structlog
from selectolax.parser import HTMLParser

log = structlog.get_logger(__name__)

# Sanity range per PARSE-04 (mirror Phase 3 microdata `100 ≤ price ≤ 1_000_000`).
_PRICE_MIN: int = 100
_PRICE_MAX: int = 1_000_000

_SKU_FROM_URL_RE = re.compile(r"/item/(\d+)")


@dataclass(frozen=True)
class ViledRawProduct:
    """Raw extracted product from a viled PDP. Plan 05 normalizers consume this.

    9-field shape mirrors Phase 3 GoldappleRawProduct (parsers/goldapple_microdata.py)
    so the dispatcher's `dict` view is uniform across retailers.
    """

    sku_id: str
    url: str
    name: str
    brand_raw: str
    current_price: int
    was_price: Optional[int]
    currency: str
    availability: str  # StockState value
    raw_volume_text: Optional[str]


def _extract_next_data(html: str) -> Optional[dict]:
    """Extract `<script id="__NEXT_DATA__" type="application/json">` payload.

    Returns the parsed JSON dict, or None on absence / malformed JSON. Reused
    by enumeration/viled_catalog.py for catalog-page inspection (key_links
    reuse declared in 02-04-PLAN.md frontmatter).
    """
    if not html:
        return None
    tree = HTMLParser(html)
    node = tree.css_first('script#__NEXT_DATA__')
    if node is None:
        return None
    raw = node.text(strip=False)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("viled_nextdata_parse_error", error=str(e))
        return None


def _map_stock_state(item: dict) -> str:
    """D-217 mapping; per 02-WAVE0-PROBE.md §A1 REVISED.

    Stock-state is derived from `item.count` (inventory int) and
    `item.purchaseType` (string enum):

      - count > 0 AND purchaseType == "ONLINE"   → IN_STOCK
      - count > 0 AND purchaseType == "PREORDER" → UNAVAILABLE (purchasable
            but not yet shippable; treated as "not currently available" for
            comparison purposes)
      - count == 0                                → OUT_OF_STOCK
      - count missing / non-int                  → UNKNOWN

    DELISTED and URL_CHANGED are higher-level states the fetcher (404/410
    response) and run-orchestrator (URL-shift detection) emit; this helper
    only sees a successfully fetched & parsed PDP.
    """
    count = item.get("count")
    purchase_type = item.get("purchaseType")
    if not isinstance(count, int):
        return "UNKNOWN"
    if count == 0:
        return "OUT_OF_STOCK"
    if purchase_type == "PREORDER":
        return "UNAVAILABLE"
    return "IN_STOCK"


def _extract_volume_from_nextdata(a0: dict) -> Optional[str]:
    """Extract raw volume text from viled __NEXT_DATA__ price-variant attributes.

    Reads the nested descriptive-attributes array at:
        props.pageProps.attributes[0].attributes[]
    and returns the first entry whose name matches Размер / объем / объём
    (case-insensitive, whitespace-stripped).

    Returns the raw value (e.g. "50 мл", "S") or None when absent. The
    downstream NORM-03 normalizer (parse_volume) handles disambiguation
    of clothing sizes ("S" → None) vs volumes ("50 мл" → Volume(50,ml,1)).

    Source: 08-RESEARCH.md §"viled NextData attributes" (verified against
    all 3 in-repo fixtures: viled-pdp-407682, multipack, discounted) plus
    live Contre-Jour fixture from Plan 08-01 W0 spike.

    PARSE-FIX-03 (Plan 08-04). Threat T-08-13 mitigation: isinstance guards
    on `descriptive` (list) and `entry` (dict) per STRIDE register.
    """
    descriptive = a0.get("attributes")
    if not isinstance(descriptive, list):
        return None
    for entry in descriptive:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip().lower()
        if name in ("размер", "объем", "объём"):
            value = entry.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _coerce_int(v: Any) -> Optional[int]:
    """Best-effort int coercion. Returns None on failure (so callers can early-out)."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_pdp(html: str, url: str = "") -> Optional[ViledRawProduct]:
    """Extract product fields from a viled __NEXT_DATA__-bearing PDP HTML.

    Returns None on:
      - missing __NEXT_DATA__ (likely 404 / gate / non-PDP page)
      - JSON parse failure
      - empty `attributes` list (Pitfall 2 — no canonical price variant)
      - missing required fields (item.name, item.brandName)
      - current_price outside the PARSE-04 sanity range [100, 1_000_000]

    Field mapping (per 02-WAVE0-PROBE.md A1 + A2):
      - sku_id            ← url regex /item/(\\d+)/, fall back to last path segment
      - name              ← props.pageProps.item.name
      - brand_raw         ← props.pageProps.item.brandName
      - current_price     ← props.pageProps.attributes[0].price       (Reading A)
      - was_price         ← realPrice if realPrice > price else None
      - currency          ← unconditional "KZT" (STATE.md plan 01-07 lock)
      - availability      ← _map_stock_state(item)  (D-217)
      - raw_volume_text   ← _extract_volume_from_nextdata(a0) OR name fallback
                            (PARSE-FIX-03; reads Размер attr first, falls back
                            to full name for SKUs lacking the attr — Frederic
                            Malle Contre-Jour case per D-814)
    """
    nd = _extract_next_data(html)
    if nd is None:
        return None
    try:
        page_props = nd["props"]["pageProps"]
    except (KeyError, TypeError):
        return None
    item = page_props.get("item") or {}
    attrs = page_props.get("attributes") or []
    if not attrs or not isinstance(attrs, list):
        return None  # Pitfall 2 — no canonical variant
    a0 = attrs[0]
    if not isinstance(a0, dict):
        return None

    # PARSE-03: Reading A (verified empirically via canonical & discounted
    # fixtures; see 02-WAVE0-PROBE.md §A2): `price` is the customer-facing
    # current/sale price; `realPrice` is the MSRP/was-price. Discount detected
    # when realPrice > price.
    current_price = _coerce_int(a0.get("price"))
    if current_price is None:
        return None
    if not (_PRICE_MIN <= current_price <= _PRICE_MAX):
        return None  # PARSE-04 sanity range
    real_price = _coerce_int(a0.get("realPrice"))
    if real_price is not None and real_price > current_price:
        was_price: Optional[int] = real_price
    else:
        was_price = None

    # Currency: unconditional "KZT" per STATE.md plan 01-07 lock. viled is
    # a KZ-only retailer; any non-₸/non-KZT raw value is logged for
    # observability but never propagates to the snapshot.
    currency_raw = (a0.get("currency") or "").strip()
    if currency_raw and currency_raw not in ("₸", "KZT"):
        log.warning(
            "viled_unexpected_currency",
            raw=currency_raw,
            sku_id=item.get("id"),
            url=url,
        )
    currency = "KZT"

    # Stock-state (PARSE-06 / D-217 / WAVE0-PROBE A1 REVISED).
    availability = _map_stock_state(item)

    # SKU id from /item/(\d+)/; fall back to last URL path segment.
    sku_match = _SKU_FROM_URL_RE.search(url)
    if sku_match:
        sku_id = sku_match.group(1)
    elif url:
        sku_id = url.rstrip("/").rsplit("/", 1)[-1]
    else:
        # Final fallback: __NEXT_DATA__'s own item.id (stringified).
        item_id = item.get("id")
        sku_id = str(item_id) if item_id is not None else ""

    name = (item.get("name") or "").strip()
    brand_raw = (item.get("brandName") or "").strip()
    if not name or not brand_raw:
        return None

    return ViledRawProduct(
        sku_id=sku_id,
        url=url,
        name=name,
        brand_raw=brand_raw,
        current_price=current_price,
        was_price=was_price,
        currency=currency,
        availability=availability,
        raw_volume_text=_extract_volume_from_nextdata(a0) or name,  # PARSE-FIX-03
    )


__all__ = [
    "ViledRawProduct",
    "parse_pdp",
    "_extract_next_data",
    "_extract_volume_from_nextdata",
    "_map_stock_state",
]
