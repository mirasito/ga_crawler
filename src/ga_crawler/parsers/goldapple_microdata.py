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

import structlog
from selectolax.parser import HTMLParser, Node

log = structlog.get_logger(__name__)

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
    """True if price_meta has a SIBLING <link itemprop='priceType' href='.../StrikethroughPrice'>
    or '.../ListPrice' in the same scope (NOT in a nested priceSpecification descendant).

    selectolax `css_first` searches the whole subtree, so a naive lookup on parent
    would falsely match a priceType inside a nested <... itemprop='priceSpecification'>
    block - that block is the OTHER price (was_price) and is NOT a sibling annotation
    of the current price_meta. We filter it out by checking the chain of itemscopes
    between the priceType and the parent.
    """
    if price_meta.parent is None:
        return False
    parent = price_meta.parent
    for pt in parent.css('link[itemprop="priceType"]'):
        # Walk up from pt to parent. If any ancestor on that chain (exclusive of
        # parent itself) has itemprop='priceSpecification', this priceType belongs
        # to that nested priceSpecification - NOT a sibling of price_meta.
        cursor = pt.parent
        in_nested_spec = False
        while cursor is not None and cursor != parent:
            if cursor.attributes.get("itemprop") == "priceSpecification":
                in_nested_spec = True
                break
            cursor = cursor.parent
        if in_nested_spec:
            continue
        href = pt.attributes.get("href", "") or ""
        if ("StrikethroughPrice" in href) or ("ListPrice" in href):
            return True
    return False


_GOLD_CARD_LABEL_TAGS = {"span", "div", "p", "label", "small", "h1", "h2", "h3", "h4", "h5", "h6"}


def _sibling_text_shallow(sibling: Node) -> str:
    """Return shallow text of a sibling node, ignoring deep descendants.

    Falls back to recursive text extraction on selectolax versions whose
    Node.text() does not accept the `deep=` keyword (very old releases).
    """
    try:
        return sibling.text(deep=False, strip=True) or ""
    except TypeError:
        return sibling.text(strip=True) or ""


def _is_in_gold_card_section(price_meta: Node) -> bool:
    """Heuristic: True iff a direct sibling of price_meta is a label element
    (span/div/p/etc.) whose own shallow text is "при авторизации".

    Why direct-sibling-shallow instead of walk-up-deep:
    - On test fixtures and well-formed PDPs the Gold Card curtain looks like
      `<span class="price-row__row">при авторизации</span>` adjacent to a
      `<meta itemprop="price" content="...">` — both are direct children of
      the same offer wrapper. Direct-sibling shallow check catches that.
    - On real PDPs the bonus-badge button can contain "при авторизации" deep
      in its descendant text (e.g. `<button>...при авторизации увидите...</button>`)
      but the button is a *bonus promo*, not a price curtain. The previous
      walk-up + recursive `text()` falsely poisoned every price in the offer.
      Restricting the search to direct siblings AND excluding non-label tags
      (button, i, img, svg) prevents that false-positive.

    PROJECT.md still excludes Gold Card prices from comparison; this version
    is strictly narrower than the previous heuristic and only differs on
    pages where "при авторизации" appears inside an unrelated subtree.
    """
    parent = price_meta.parent
    if parent is None:
        return False
    for sibling in parent.iter():
        if sibling is price_meta:
            continue
        tag = (sibling.tag or "").lower()
        if tag not in _GOLD_CARD_LABEL_TAGS:
            continue
        if "при авторизации" in _sibling_text_shallow(sibling).lower():
            return True
    return False


def _extract_top_level_offer(tree: HTMLParser) -> Optional[Node]:
    """Pick the meta[itemprop='price'] whose container is the top-level Offer
    (has [itemprop='availability'] descendant) AND passes the priceType/Gold Card
    filters AND has the lowest sane value among siblings (current/sale price wins).

    Selection rule for non-priceType price metas in a single offer:
    - Filter out priceSpecification descendants, excluded priceType siblings,
      and Gold Card section members.
    - Apply PARSE-04 sanity range (100..1_000_000) up-front so price=0 fillers
      cannot be picked.
    - Of the remaining candidates within the SAME offer, return the one with
      the **lowest integer value** — this matches e-commerce convention
      (sale price < was price when both are emitted as bare `<meta itemprop="price">`).

    Source: 03-RESEARCH.md §Pattern 4 lines 543-578 (verbatim) + 03-07 live-smoke
    finding that some PDPs emit both current and was price as bare meta tags
    without StrikethroughPrice markup; min-value selection makes selection
    deterministic without breaking the canonical priceType-keyed pages.
    """
    offer_nodes = tree.css('[itemprop="offers"][itemtype$="/Offer"]')
    for offer in offer_nodes:
        avail = offer.css_first('link[itemprop="availability"]')
        if avail is None:
            continue
        candidates: list[tuple[int, Node]] = []
        for price_meta in offer.css('meta[itemprop="price"]'):
            if _walks_into_priceSpecification(price_meta, offer):
                continue
            if _has_excluded_priceType_sibling(price_meta):
                continue
            if _is_in_gold_card_section(price_meta):
                continue
            value_str = (price_meta.attributes.get("content") or "").strip()
            if not value_str.isdigit():
                continue
            value = int(value_str)
            if not (100 <= value <= 1_000_000):  # PARSE-04 applied early
                continue
            candidates.append((value, price_meta))
        if candidates:
            candidates.sort(key=lambda kv: kv[0])
            return candidates[0][1]
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


def _extract_volume_block(html: str) -> Optional[str]:
    """Extract goldapple PDP structured volume block (single-variant only).

    Uses selectolax 0.4 Lexbor backend (CONTEXT.md D-806 — Lexbor import is
    LOCAL to this helper, keeping module-top Modest-only per blast-radius
    isolation D-807).

    DOM shape variants observed in W0 spike (Plan 08-01 shape-table.md):
      - STEREOTYPE-style: parent `_ga-pdp-attribute-few` has child <div>12</div>
        + child <div>объём / мл</div>  (label-after-number, single-variant)
      - Armani-style: parent `_ga-pdp-attribute-few` has child label
        + radio-group children "50", "75", "125" (label-before-number, multi)
      - Givenchy baseline: same Armani-style label-before-radio-group shape.

    PARSE-FIX-V2 (post-v1 review): the previous heuristic of "first digit-run in
    ancestor text" silently concatenated multi-variant radio-button labels into
    garbage values (e.g. `volume_raw='5075125 мл'` → `(5075125,ml,1)`). This
    poisoned ~23% of GA snapshots and killed all matcher JOINs. The fix:
      1. Find ALL digit-runs in the ancestor text.
      2. If exactly ONE distinct digit-run → that's the volume (single-variant).
      3. If MULTIPLE distinct digit-runs → return None (multi-variant ambiguous;
         caller MUST NOT fall back to product name).
    A future improvement can detect the selected radio-button to pick the active
    variant; for v1 we conservatively reject multi-variant PDPs from matching.

    Returns None when:
      - the "объём" label is not found (volumeless category — 5/30 in W0)
      - no digit appears within depth-3 ancestor chain
      - multiple distinct digit-runs exist (multi-variant — undecidable)

    Source: 08-RESEARCH.md § "selectolax 0.4 Lexbor" + § "Bug #1 (Volume Block)"
    + matcher-review-2026-05-15 root-cause analysis showing 48/207 GA snapshots
    were poisoned by multi-variant concatenation.

    PARSE-FIX-01 (Plan 08-02). Pitfall 1 (leading space before `i` flag)
    sidestepped by using lowercase literal directly. Pitfall 2 (Ё vs Е): W0
    spike confirms 25/25 volumed PDPs use Ё — single-selector form suffices.
    """
    import re
    from selectolax.lexbor import LexborHTMLParser  # local import per D-806

    tree = LexborHTMLParser(html)
    label_nodes = tree.css('div:lexbor-contains("объём")')
    if not label_nodes:
        return None
    label = label_nodes[0]
    label_text = (label.text(deep=False, strip=True) or "")
    unit_match = re.search(r"(мл|г|гр|oz|унц)", label_text, re.IGNORECASE)
    unit = unit_match.group(1) if unit_match else "мл"
    ancestor = label.parent
    for _ in range(3):
        if ancestor is None:
            return None
        composed = (ancestor.text(deep=True, strip=True) or "")
        digits = re.findall(r"\d+(?:[.,]\d+)?", composed)
        if digits:
            distinct = set(digits)
            if len(distinct) == 1:
                return f"{digits[0]} {unit}"
            return None  # multi-variant — undecidable, do NOT poison data
        ancestor = ancestor.parent
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

    # Brand + name: PARSE-FIX-02 / D-816 (Plan 08-03).
    #
    # W0 spike (.planning/spikes/v1.1-brand-name-shapes/MEMO.md) invalidated the
    # original product-scope <meta itemprop="name"> walk: 0/30 captured PDPs
    # carry product-level microdata; the `[itemprop="brand"]` matches that v1.0
    # produced were against bottom-of-page "you may also like" cards, not the
    # main product (cross-product contamination — see run #13 evidence).
    #
    # Empirical strategy per W0 (.claude/skills/spike-findings-v1.1-brand-name-shapes/
    # SKILL.md): brand and name live in separate h1 child spans, both 30/30
    # coverage:
    #   h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]
    #   h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__name_"]
    # The hash suffix is build-specific (e.g. _1yrfv_339) — substring-match only.
    # Brand `content` attribute preserves authored whitespace (e.g. "Givenchy ");
    # the normalizer strips it downstream.
    brand_raw = ""
    name = ""
    h1 = tree.css_first('h1[class*="_ga-pdp-title__heading_"]')
    if h1 is not None:
        brand_span = h1.css_first('[class*="_ga-pdp-title__brand_"]')
        if brand_span is not None:
            brand_raw = (
                brand_span.attributes.get("content")
                or brand_span.text(strip=True)
                or ""
            ).strip()
        name_span = h1.css_first('[class*="_ga-pdp-title__name_"]')
        if name_span is not None:
            name = name_span.text(strip=True)

    # Fallback chain when the h1 child-span shape is absent (W0 spike showed
    # 30/30 coverage, but defensive fallback preserves graceful degradation
    # on unseen layouts):
    #   1. plain <h1> deep text (v1.0 path — concatenates brand+name, last resort)
    #   2. <title> stripped of " — купить ..."
    if not name:
        h1_any = tree.css_first("h1")
        if h1_any is not None:
            name = h1_any.text(strip=True)
    if not name and title:
        name = title.split(" — купить", 1)[0].strip()

    # D-816 per-SKU brand-canary invariant (SOFTENED to log-only per W0 §4:
    # 2/30 PDPs in the Armani-style bucket legitimately have brand-substring
    # in name due to upstream data redundancy — `Armani`/`armani code`,
    # `GIVENCHY`/`GIVENCHY GENTLEMAN RESERVE PRIVEE`). Hard-fail at parse time
    # would block runs on upstream data quality; the aggregate parser-drift
    # gate (PARSE-FIX-04, Plan 08-05) catches the "all SKUs broken" mode.
    # _strip_brand_prefix fallback is NOT NEEDED per W0 §2: the .name span
    # cleanly excludes the .brand span in 28/30 sampled PDPs.
    if brand_raw and name and brand_raw.lower() in name.lower():
        log.warning(
            "goldapple_brand_in_name_canary_violation",
            brand_raw=brand_raw,
            name=name,
            url=url,
        )

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

    # Volume: structured flex-box (PARSE-FIX-01).
    #
    # PARSE-FIX-V2 (post-v1 review): the original code fell back to `name` when
    # `_extract_volume_block` returned None — this leaked product titles like
    # `'Dazzlelips Crayon'` into `volume_raw`, which downstream `parse_volume`
    # then either rejected (volume_norm=NULL) or worse, accidentally parsed
    # numeric substrings as bogus volumes. Across run-18 this corrupted 30% of
    # GA snapshots. Removed the fallback: volumeless categories yield None and
    # are excluded from the matcher's comparable filter — correct behavior per
    # D-402 (volume_norm IS NOT NULL gate).
    raw_volume_text = _extract_volume_block(html)

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
