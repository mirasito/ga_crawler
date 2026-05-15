"""Goldapple brand-page enumeration (RU-RU pipeline) — discovery via
``/front/api/catalog/cards-list``.

Why this exists
---------------
The original sitemap-based goldapple discovery yields ~89-207 SKUs per run
(see runs 10-18) — a tiny fraction of GA's actual catalog. With viled
carrying 6019 SKUs, this kills downstream match coverage even with the v2
token matcher: only 18 brands overlap, and within those brands, GA's
sample is too narrow to match against viled's hundreds of per-brand SKUs.

The brand pages (e.g. ``/brands/clinique`` → 220 products,
``/brands/la-sultane-de-saba`` → 62 products) are GA's authoritative
per-brand product list. Each brand-page render fires multiple
``/front/api/catalog/cards-list`` XHR calls that return rich JSON
**without** requiring a PDP fetch per SKU.

The cards-list JSON gives us, per SKU:
  - itemId             → GoldappleRawProduct.sku_id
  - brand              → brand_raw
  - productType (RU!)  → composed into raw_volume_text-adjacent fields
  - name (EN)          → name
  - attributes.units   → exact volume + unit (no regex parse needed)
  - price.actual       → current_price
  - price.old          → was_price (when discounted)
  - price.regular      → fallback when not discounted
  - inStock            → availability mapping
  - url                → "/SKU-slug" canonical PDP path

This module exposes a function that, given a list of GA brand slugs and a
ready ``GoldappleFetcher``, yields ``GoldappleRawProduct`` instances —
bypassing the PDP fetch+parse loop entirely.

Strategy (rate-limit resistant)
-------------------------------
Direct curl_cffi calls to ``cards-list`` get HTTP 403 after ~3 sequential
requests (anti-bot heuristic on the API surface). The SPA's native scroll
behavior, however, fully paginates without errors — the page's own JS
sets the right inter-request cadence and reuses cookies. We piggy-back:

  1. Navigate the Camoufox page to ``/brands/{slug}``.
  2. Install a ``page.on("response", ...)`` handler that captures every
     cards-list JSON response.
  3. Aggressively scroll the page (window.scrollBy) on a fixed interval;
     the SPA's intersection-observer fires cards-list per page-worth of
     scroll. The handler accumulates all cards.
  4. After scrolling stops + a settle delay, deduplicate by ``itemId``
     and emit ``GoldappleRawProduct``.

This costs ~25-40 seconds per brand (page boot is amortized once, then
the scroll itself dominates) — at 18 brands this is ~10 minutes total,
versus ~30+ minutes for the equivalent number of PDP fetches.

Source: matcher-review-2026-05-15 brand-page probe sequence in
``inbox/ga_brand_xhr/`` and ``inbox/ga_cards_api/``.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import structlog

from ga_crawler.parsers.goldapple_microdata import GoldappleRawProduct

log = structlog.get_logger(__name__)


# ---- Constants ----

CARDS_LIST_URL_FRAGMENT: str = "/front/api/catalog/cards-list"
GOLDAPPLE_HOST: str = "https://goldapple.kz"

# Scroll pacing — empirically tuned on probe runs:
#   - 120 iterations × 1500 px / 250ms = 30 s of scroll
#   - Then 5 s settle for in-flight XHR to land
SCROLL_ITERATIONS: int = 120
SCROLL_STEP_PX: int = 1500
SCROLL_INTERVAL_MS: int = 250
POST_SCROLL_SETTLE_MS: int = 5_000

# Brand-page navigation timeout
BRAND_PAGE_GOTO_TIMEOUT_MS: int = 45_000


# ---- Card-to-RawProduct conversion ----


def _coerce_int_price(price_node: Any) -> Optional[int]:
    """Extract integer KZT amount from a price node like
    ``{"amount": 30500, "currency": "KZT", "denominator": 1}``.

    Returns None if the node is missing, has no amount, or amount is 0
    (PARSE-04 sanity-range filter: prices in [100, 1_000_000]).
    """
    if not isinstance(price_node, dict):
        return None
    amount = price_node.get("amount")
    if not isinstance(amount, (int, float)):
        return None
    iv = int(amount)
    if iv < 100 or iv > 1_000_000:
        return None
    return iv


def _compose_volume_raw(units_node: Any) -> Optional[str]:
    """Compose the raw volume string (e.g. ``"125 мл"``) from the
    attributes.units node. Returns None when no unit info is present.

    Cards-list shape:
      ``"units": {"count": 2, "values": ["50", "125"],
                  "currentUnitValue": "125", "name": "мл"}``

    We always pick ``currentUnitValue`` — that's the size of THIS specific
    ``itemId`` (other sizes are separate itemIds with their own cards).
    """
    if not isinstance(units_node, dict):
        return None
    value = units_node.get("currentUnitValue")
    unit_name = units_node.get("name")
    if not value or not unit_name:
        return None
    return f"{value} {unit_name}"


def _compose_name(brand: str, product_type: str, name: str) -> str:
    """Compose a viled-shaped name string from cards-list fields.

    viled emits names like ``"Парфюмерная вода Armani Code, 75 мл"``;
    cards-list splits this into ``productType="Парфюмерная вода"``,
    ``brand="Armani"``, ``name="code"`` (lowercase EN tail). Concatenating
    them gives the matcher token-filter a much richer string to compare
    against viled's ``name_norm``.

    Brand is intentionally included even though ``brand_norm`` is also
    matched by the JOIN — the redundancy harms nothing and helps when GA
    uses an alias (e.g. brand="Giorgio Armani" but viled has "Armani").
    """
    return " ".join(s for s in (product_type, brand, name) if s).strip()


def _map_availability(in_stock: Any) -> str:
    """Map cards-list ``inStock`` flag to the schema-org enum used by
    the rest of the pipeline.

    cards-list lacks the full schema.org availability enum (Discontinued,
    PreOrder, etc.). We collapse to InStock / OutOfStock; downstream NORM
    rules treat anything outside `DELISTED` identically for matching, so
    no information is lost.
    """
    return "InStock" if bool(in_stock) else "OutOfStock"


def card_to_raw_product(card: dict, slug_path: str) -> Optional[GoldappleRawProduct]:
    """Convert a single cards-list ``card`` to ``GoldappleRawProduct``.

    Returns None on any of:
      - missing required fields (itemId, name, brand)
      - PARSE-04 price sanity failure (no price in [100, 1_000_000])

    The composed ``name`` is ``"{productType} {brand} {name}"`` — see
    ``_compose_name`` for rationale.

    ``raw_volume_text`` becomes the viled-shape string ``"125 мл"`` from
    ``attributes.units``; downstream NORM-03 ``parse_volume`` parses it.
    """
    p = card.get("product") if card.get("cardType") == "product" else None
    if not isinstance(p, dict):
        return None
    sku_id = p.get("itemId") or p.get("mainVariantItemId")
    brand_raw = (p.get("brand") or "").strip()
    name = (p.get("name") or "").strip()
    product_type = (p.get("productType") or "").strip()
    if not sku_id or not brand_raw or not name:
        return None
    price_node = p.get("price") or {}
    current = _coerce_int_price(price_node.get("actual")) or _coerce_int_price(
        price_node.get("regular")
    )
    if current is None:
        return None
    was = _coerce_int_price(price_node.get("old"))
    # If "old" equals "actual", there's no real discount — emit None for was.
    if was is not None and was == current:
        was = None

    units = (p.get("attributes") or {}).get("units")
    raw_volume_text = _compose_volume_raw(units)

    url = f"{GOLDAPPLE_HOST}{p.get('url') or slug_path}"
    composed_name = _compose_name(brand_raw, product_type, name)
    availability = _map_availability(p.get("inStock"))

    currency = "KZT"
    actual = price_node.get("actual") if isinstance(price_node, dict) else None
    if isinstance(actual, dict) and actual.get("currency"):
        currency = str(actual["currency"]).upper()

    return GoldappleRawProduct(
        sku_id=str(sku_id),
        url=url,
        name=composed_name,
        brand_raw=brand_raw,
        current_price=current,
        was_price=was,
        currency=currency,
        availability=availability,
        raw_volume_text=raw_volume_text,
    )


# ---- Enumeration ----


@dataclass
class BrandEnumerationResult:
    """Outcome of enumerating one brand."""

    slug: str
    product_count_badge: Optional[int]  # value GA shows as "N продуктов" (sanity)
    cards_collected: int                # total card events captured (may include duplicates)
    raw_products: list[GoldappleRawProduct]
    cards_list_calls: int
    error: Optional[str] = None


async def enumerate_brand(
    fetcher: Any,
    slug: str,
    *,
    scroll_iterations: int = SCROLL_ITERATIONS,
    scroll_step_px: int = SCROLL_STEP_PX,
    scroll_interval_ms: int = SCROLL_INTERVAL_MS,
    post_scroll_settle_ms: int = POST_SCROLL_SETTLE_MS,
) -> BrandEnumerationResult:
    """Enumerate one GA brand by navigating to ``/brands/{slug}`` and
    capturing cards-list XHR responses while scrolling.

    Parameters
    ----------
    fetcher
        Active ``GoldappleFetcher`` (already inside its async-with context).
        Used solely to access ``fetcher._page`` and the SPA session it
        carries.
    slug
        GA brand slug (kebab-case, e.g. ``"clinique"``,
        ``"la-sultane-de-saba"``).

    Returns
    -------
    BrandEnumerationResult
        Contains the deduplicated ``raw_products`` list. On any failure
        (timeout, 0 cards captured) the ``error`` field is populated and
        ``raw_products`` is empty.
    """
    page = fetcher._page

    cards_collected: list[dict] = []
    cards_list_calls = 0

    # Hook responses BEFORE navigating so we don't miss the first batch
    # the SPA fires during initial render.
    def _on_response(resp):
        nonlocal cards_list_calls
        url = resp.url
        if CARDS_LIST_URL_FRAGMENT in url:
            cards_list_calls += 1
            asyncio.create_task(_capture(resp))

    async def _capture(resp):
        try:
            data = await resp.json()
        except Exception:
            return
        cards = (data or {}).get("data", {}).get("cards") or []
        cards_collected.extend(cards)

    page.on("response", _on_response)

    url = f"{GOLDAPPLE_HOST}/brands/{slug}"
    log.info("brand_enum_start", slug=slug, url=url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=BRAND_PAGE_GOTO_TIMEOUT_MS)
    except Exception as e:
        log.warning("brand_enum_goto_failed", slug=slug, error=str(e))
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            pass
        return BrandEnumerationResult(
            slug=slug,
            product_count_badge=None,
            cards_collected=0,
            raw_products=[],
            cards_list_calls=cards_list_calls,
            error=f"goto_failed: {e}",
        )

    # Initial settle so the first cards-list XHR can fire before we
    # start scrolling — otherwise the first batch occasionally races.
    await page.wait_for_timeout(2_500)

    # Continuous fixed scroll. We tried an adaptive stall-detect variant
    # (matcher-review-2026-05-15) but the SPA's pagination pauses
    # exceeded the stall threshold mid-stream, causing big brands
    # (Clinique 220, MAC 176, Clarins 248) to abort early at ~40 cards.
    # A single uninterrupted scroll for the full ``scroll_iterations`` ×
    # ``scroll_interval_ms`` budget reliably paginates to the end for
    # all brands observed so far.
    scroll_js = (
        "(args) => new Promise(r => { "
        "let i=0; const id=setInterval(()=>{ "
        "window.scrollBy(0, args.step); i++; "
        "if(i>=args.iters){clearInterval(id); r();} "
        "}, args.interval); })"
    )
    try:
        await page.evaluate(
            scroll_js,
            {"step": scroll_step_px, "iters": scroll_iterations, "interval": scroll_interval_ms},
        )
    except Exception as e:
        log.warning("brand_enum_scroll_failed", slug=slug, error=str(e))

    # Settle for in-flight XHRs.
    await page.wait_for_timeout(post_scroll_settle_ms)

    # Extract badge from final HTML for sanity-checking.
    try:
        html = await page.content()
        import re
        m = re.search(r"(\d+)\s*продукт", html, re.IGNORECASE)
        badge = int(m.group(1)) if m else None
    except Exception:
        badge = None

    try:
        page.remove_listener("response", _on_response)
    except Exception:
        pass

    # Deduplicate by itemId and convert to GoldappleRawProduct.
    seen: set[str] = set()
    raw_products: list[GoldappleRawProduct] = []
    slug_path_default = f"/-{slug}"  # placeholder if a card lacks ``product.url``
    for card in cards_collected:
        p = card.get("product") if isinstance(card, dict) else None
        if not isinstance(p, dict):
            continue
        sku_id = p.get("itemId") or p.get("mainVariantItemId")
        if not sku_id or sku_id in seen:
            continue
        seen.add(sku_id)
        rp = card_to_raw_product(card, slug_path_default)
        if rp is None:
            continue
        raw_products.append(rp)

    log.info(
        "brand_enum_complete",
        slug=slug,
        cards_collected=len(cards_collected),
        distinct_raw_products=len(raw_products),
        cards_list_calls=cards_list_calls,
        badge=badge,
    )
    return BrandEnumerationResult(
        slug=slug,
        product_count_badge=badge,
        cards_collected=len(cards_collected),
        raw_products=raw_products,
        cards_list_calls=cards_list_calls,
    )


async def enumerate_brands(
    fetcher: Any,
    slugs: Iterable[str],
    *,
    inter_brand_pause_seconds: float = 3.0,
) -> list[BrandEnumerationResult]:
    """Enumerate a list of GA brand slugs in series, with a pause between
    brands to avoid stacking up against any per-host rate limits."""
    results: list[BrandEnumerationResult] = []
    slugs_list = list(slugs)
    for i, slug in enumerate(slugs_list):
        result = await enumerate_brand(fetcher, slug)
        results.append(result)
        if i + 1 < len(slugs_list):
            await asyncio.sleep(inter_brand_pause_seconds)
    return results


__all__ = [
    "BRAND_PAGE_GOTO_TIMEOUT_MS",
    "BrandEnumerationResult",
    "CARDS_LIST_URL_FRAGMENT",
    "POST_SCROLL_SETTLE_MS",
    "SCROLL_INTERVAL_MS",
    "SCROLL_ITERATIONS",
    "SCROLL_STEP_PX",
    "card_to_raw_product",
    "enumerate_brand",
    "enumerate_brands",
]
