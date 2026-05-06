"""Goldapple microdata parser (PARSE-01..06 for retailer='goldapple').

Why microdata not JSON-LD (D-14 revision 2026-05-06):
  goldapple.kz PDP emits ONLY OfferShippingDetails JSON-LD (shipping policy);
  there is NO Product schema JSON-LD. Naive PARSE-02 priority would return 0% hit.
  Real product data lives in inline microdata: <meta itemprop="price" content="...">,
  <span itemprop="brand"><meta itemprop="name" content="Givenchy">, etc.

Why priceType discrimination (Pitfall 2):
  A single PDP can contain up to 4 different <meta itemprop="price"> blocks:
    1. top-level [itemprop="offers"][itemtype$="/Offer"] without priceType -> CURRENT public price
    2. priceSpecification with priceType=".../StrikethroughPrice" -> was_price (crossed)
    3. priceSpecification with priceType=".../ListPrice" -> "от" prefix variant (related products)
    4. nested in "при авторизации" section -> Gold Card loyalty price (EXCLUDED per PROJECT.md)
  We pick block #1 only.

Three-axis state classifier (Pitfall 4):
  - gate-shell: GroupIB challenge ("checking device" title + <30KB)
  - stale-sku: de-listed SKU returns 200 OK + ~9.5KB shell + no microdata + title="Loading <url>"
  - real-pdp: full HTML >=30KB with microdata
  Discriminator = title-marker + size; parse_pdp also requires microdata-presence.

Source: 03-RESEARCH.md §Pattern 4 lines 493-672 (verbatim algorithm + verified against
.planning/spikes/01-goldapple/sample-payloads/_debug-product-page.html).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from selectolax.parser import HTMLParser, Node

# Re-declared from spike notebook.py L48-49 so parser is self-contained.
# Wave 0 pyproject.toml [tool.ga_crawler.crawl.goldapple] also exposes these
# for runtime config, but the parser is a pure-logic module - defaults here
# are acceptable; Wave 5 orchestrator passes runtime values via fetcher params.
GATE_SHELL_MAX_BYTES: int = 30_000
GATE_TITLE_MARKER: str = "checking"


@dataclass(frozen=True)
class GoldappleRawProduct:
    """Raw extracted product from a goldapple PDP. Phase 2 normalizers consume this.

    - sku_id: numeric portion of URL slug (e.g. '7681000001' from /7681000001-givenchy-...)
    - name: <h1> text (PARSE-01)
    - brand_raw: <meta itemprop="name"> within [itemprop="brand"] (PARSE-01)
    - current_price: integer KZT, 100..1_000_000 sanity range (PARSE-04)
    - was_price: int or None - extracted from StrikethroughPrice priceSpecification
    - currency: "KZT" expected; sibling meta[itemprop="priceCurrency"]
    - availability: enum string from schema.org URL (PARSE-06)
    - raw_volume_text: passthrough name; Phase 2 NORM-03 regex extracts ml/g/oz
    """

    sku_id: str
    url: str
    name: str
    brand_raw: str
    current_price: int
    was_price: Optional[int]
    currency: str
    availability: str
    raw_volume_text: Optional[str]


def detect_state(html: str, title: str) -> Literal["gate-shell", "stale-sku", "real-pdp"]:
    """Classify a fetched HTML response. Pitfall 4 - distinguish 3 outcomes.

    Returns:
      "gate-shell" - anti-bot challenge (title contains 'checking' + size <30KB).
                     Should NEVER appear on a healthy run if smoke-probe passed.
      "stale-sku"  - de-listed SKU 200 OK + size <30KB but no challenge markers.
                     D-303: log to runs.stats.stale_count and skip per-SKU isolation.
      "real-pdp"   - full PDP HTML >=30KB. Caller proceeds to parse_pdp().

    Source: 03-RESEARCH.md §Pattern 4 lines 531-541 (verbatim).
    """
    sz = len(html)
    if GATE_TITLE_MARKER in title.lower() and sz < GATE_SHELL_MAX_BYTES:
        return "gate-shell"
    if sz < GATE_SHELL_MAX_BYTES:
        return "stale-sku"
    return "real-pdp"


def has_microdata_price(html: str) -> tuple[bool, bool]:
    """Returns (has_offer_marker, has_price_value).

    Foundation primitive (re-implementation of spike notebook.py L94-110).
    has_offer_marker - any <meta itemprop="price"> present.
    has_price_value - at least one such meta has a non-zero content attr.

    Used by Wave 4 smoke probe to assert microdata extracted before crawl.
    """
    tree = HTMLParser(html)
    nodes = tree.css('meta[itemprop="price"]')
    if not nodes:
        return False, False
    has_value = False
    for n in nodes:
        v = (n.attributes.get("content") or "").strip()
        if v and v != "0":
            has_value = True
            break
    return True, has_value


# ---------------------------------------------------------------------------
# Helper functions for parse_pdp (Task 2 of plan 03-03).
# Kept module-private (underscore prefix) but importable by tests for unit
# coverage of priceType discrimination.
# ---------------------------------------------------------------------------


def _walks_into_priceSpecification(price_meta: Node, offer_root: Node) -> bool:
    """True if price_meta is nested inside a [itemprop='priceSpecification'] subtree
    within offer_root. Used to skip nested priceSpec blocks when picking top-level price.
    """
    parent = price_meta.parent
    while parent is not None and parent != offer_root:
        if parent.attributes.get("itemprop") == "priceSpecification":
            return True
        parent = parent.parent
    return False


def _has_excluded_priceType_sibling(price_meta: Node) -> bool:
    """True if price_meta has a sibling <link itemprop='priceType' href='.../StrikethroughPrice'>
    or '.../ListPrice'. These are PARSE-03 excluded.
    """
    if price_meta.parent is None:
        return False
    sibling_pt = price_meta.parent.css_first('link[itemprop="priceType"]')
    if sibling_pt is None:
        return False
    href = sibling_pt.attributes.get("href", "") or ""
    return ("StrikethroughPrice" in href) or ("ListPrice" in href)


def _is_in_gold_card_section(price_meta: Node) -> bool:
    """Heuristic: walks up from price_meta looking for a label "при авторизации"
    (Gold Card / loyalty pricing). Returns True if found within ancestor text.
    PROJECT.md explicitly excludes Gold Card prices from comparison.
    """
    parent = price_meta.parent
    depth = 0
    while parent is not None and depth < 6:
        try:
            txt = parent.text(strip=False) or ""
        except Exception:
            txt = ""
        if "при авторизации" in txt.lower():
            return True
        parent = parent.parent
        depth += 1
    return False


def _extract_top_level_offer(tree: HTMLParser) -> Optional[Node]:
    """Pick the meta[itemprop='price'] whose container is the top-level Offer
    (has [itemprop='availability'] sibling) AND has no excluded priceType
    AND is not in a 'при авторизации' (Gold Card) section.

    Source: 03-RESEARCH.md §Pattern 4 lines 543-578 (verbatim; expanded slightly
    for Gold Card heuristic per PROJECT.md scope).
    """
    offer_nodes = tree.css('[itemprop="offers"][itemtype$="/Offer"]')
    for offer in offer_nodes:
        avail = offer.css_first('link[itemprop="availability"]')
        if avail is None:
            continue
        for price_meta in offer.css('meta[itemprop="price"]'):
            if _walks_into_priceSpecification(price_meta, offer):
                continue
            if _has_excluded_priceType_sibling(price_meta):
                continue
            if _is_in_gold_card_section(price_meta):
                continue
            return price_meta
    return None


def _extract_strikethrough(tree: HTMLParser) -> Optional[int]:
    """First StrikethroughPrice in priceSpecification -> was_price.

    Source: 03-RESEARCH.md §Pattern 4 lines 580-590 (verbatim).
    """
    for spec in tree.css('[itemprop="priceSpecification"]'):
        ptype = spec.css_first('link[itemprop="priceType"]')
        if ptype and "StrikethroughPrice" in (ptype.attributes.get("href", "") or ""):
            p = spec.css_first('meta[itemprop="price"]')
            if p:
                v = (p.attributes.get("content") or "").strip()
                if v.isdigit():
                    return int(v)
    return None


def _extract_availability(tree: HTMLParser) -> str:
    """Map schema.org availability URL to enum string (PARSE-06).

    Returns one of: "InStock", "OutOfStock", "Discontinued", "PreOrder", "Unknown".
    """
    avail_link = tree.css_first('link[itemprop="availability"]')
    avail_url = (avail_link.attributes.get("href", "") if avail_link else "") or ""
    if "InStock" in avail_url:
        return "InStock"
    if "OutOfStock" in avail_url:
        return "OutOfStock"
    if "Discontinued" in avail_url:
        return "Discontinued"
    if "PreOrder" in avail_url:
        return "PreOrder"
    return "Unknown"


def parse_pdp(html: str, url: str) -> Optional[GoldappleRawProduct]:
    """Returns the parsed product, or None on any of:
       - state != "real-pdp" (gate-shell or stale-sku)
       - missing required fields (top-level price, name)
       - PARSE-04 sanity range fail (price not in [100, 1_000_000])

    Caller (Wave 5 orchestrator) increments runs.stats counters based on rejection
    cause:
       - state="gate-shell"   -> goldapple.gate_shell_count++
       - state="stale-sku"    -> goldapple.stale_count++
       - state="real-pdp" but None -> goldapple.parse_failures++

    Source: 03-RESEARCH.md §Pattern 4 lines 592-672 (verbatim, with PARSE-06 enum
    extraction extracted into _extract_availability helper for testability).
    """
    tree = HTMLParser(html)
    title_el = tree.css_first("title")
    title = (title_el.text() if title_el else "")
    state = detect_state(html, title)
    if state != "real-pdp":
        return None

    # SKU
    sku_meta = tree.css_first('[itemprop="sku"]')
    if sku_meta is not None and sku_meta.attributes.get("content"):
        sku_id = sku_meta.attributes["content"]
    else:
        # Fallback: extract numeric prefix from URL slug
        sku_id = url.rsplit("/", 1)[-1].split("-", 1)[0]

    # Brand: <span itemprop="brand"><meta itemprop="name" content="Givenchy ">
    brand_raw = ""
    brand_node = tree.css_first('[itemprop="brand"]')
    if brand_node is not None:
        brand_meta = brand_node.css_first('meta[itemprop="name"]')
        if brand_meta is not None:
            brand_raw = (brand_meta.attributes.get("content") or "").strip()

    # Name: <h1>; fallback to <title> stripped of " — купить ..."
    name = ""
    h1 = tree.css_first("h1")
    if h1 is not None:
        name = h1.text(strip=True)
    if not name and title:
        name = title.split(" — купить", 1)[0].strip()

    # Current price (top-level offer, no priceType, no Gold Card)
    price_meta = _extract_top_level_offer(tree)
    if price_meta is None:
        return None
    price_str = (price_meta.attributes.get("content") or "").strip()
    if not price_str.isdigit():
        return None
    current_price = int(price_str)
    if not (100 <= current_price <= 1_000_000):  # PARSE-04
        return None

    # Currency (sibling within same parent)
    currency = "KZT"
    if price_meta.parent is not None:
        cur_meta = price_meta.parent.css_first('meta[itemprop="priceCurrency"]')
        if cur_meta is not None:
            currency = (cur_meta.attributes.get("content") or "KZT").strip().upper()

    # was_price (StrikethroughPrice priceSpecification)
    was_price = _extract_strikethrough(tree)

    # Availability (PARSE-06)
    availability = _extract_availability(tree)

    # Volume passthrough - Phase 2 NORM-03 owns regex extraction
    raw_volume_text = name or None

    # Final required-fields check (PARSE-05): name must be non-empty
    if not name:
        return None

    return GoldappleRawProduct(
        sku_id=sku_id,
        url=url,
        name=name,
        brand_raw=brand_raw,
        current_price=current_price,
        was_price=was_price,
        currency=currency,
        availability=availability,
        raw_volume_text=raw_volume_text,
    )


__all__ = [
    "GATE_SHELL_MAX_BYTES",
    "GATE_TITLE_MARKER",
    "GoldappleRawProduct",
    "detect_state",
    "has_microdata_price",
    "parse_pdp",
]
