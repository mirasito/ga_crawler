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
PRODUCT_CARD_API_FRAGMENT: str = "/front/api/catalog/product-card/base/v3"
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


def variant_to_raw_product(
    variant: dict,
    *,
    brand: str,
    product_type: str,
    unit_name: str,
) -> Optional[GoldappleRawProduct]:
    """Convert one ``data.variants[i]`` entry from the
    product-card/base/v3 API response to ``GoldappleRawProduct``.

    Shape of a variant (probe-captured 2026-05-16, inbox/ga_pdp_card_api/):
      ``{itemId, attributesValue: {units, colors}, url, inStock,
         price: {actual, regular, old, ...}, name}``

    The variant's own ``name`` is the SHADE / SIZE marketing label
    ("Black Honey", "1.9 g"). We compose the snapshot's ``name`` field
    using the parent product's ``brand`` + ``productType`` + variant's
    ``name`` so downstream token-matching has the full context.
    """
    sku_id = variant.get("itemId") or variant.get("mainVariantItemId")
    if not sku_id:
        return None
    price_node = variant.get("price") or {}
    current = _coerce_int_price(price_node.get("actual")) or _coerce_int_price(
        price_node.get("regular")
    )
    if current is None:
        return None
    was = _coerce_int_price(price_node.get("old"))
    if was is not None and was == current:
        was = None

    attr_value = variant.get("attributesValue") or {}
    unit_value = attr_value.get("units")
    color_value = attr_value.get("colors")
    raw_volume_text = f"{unit_value} {unit_name}" if unit_value and unit_name else None

    variant_url_path = variant.get("url") or f"/{sku_id}-"
    url = f"{GOLDAPPLE_HOST}{variant_url_path}"

    variant_name = variant.get("name") or ""
    # variant.name often carries the shade ("Black Honey") OR is empty;
    # _compose_name handles missing components cleanly.
    composed = _compose_name(brand or "", product_type or "", variant_name)
    if color_value:
        composed = f"{composed} {color_value}".strip()

    availability = _map_availability(variant.get("inStock"))
    currency = "KZT"
    actual = price_node.get("actual") if isinstance(price_node, dict) else None
    if isinstance(actual, dict) and actual.get("currency"):
        currency = str(actual["currency"]).upper()

    return GoldappleRawProduct(
        sku_id=str(sku_id),
        url=url,
        name=composed,
        brand_raw=brand or "",
        current_price=current,
        was_price=was,
        currency=currency,
        availability=availability,
        raw_volume_text=raw_volume_text,
    )


async def fetch_product_variants(
    page: Any,
    item_id: str,
    *,
    timeout_ms: int = 15_000,
) -> list[GoldappleRawProduct]:
    """Call product-card/base/v3 for ``item_id`` and yield one
    ``GoldappleRawProduct`` per ``data.variants[]`` entry.

    Returns an empty list on any failure (network, JSON shape, etc.) —
    caller treats this as "no extra variants beyond the cards-list one".

    Parameters
    ----------
    page
        Playwright Page from an active ``GoldappleFetcher`` (so the
        request inherits browser cookies + fingerprint).
    item_id
        The master itemId (typically the one returned by cards-list).
        The API returns this variant PLUS all its siblings.

    Source: matcher-review-2026-05-16 probe sequence
    (inbox/ga_pdp_card_api/, inbox/probe_pdp_variants.log).
    """
    fetch_js = """
        async (args) => {
            const params = new URLSearchParams({
                locale: "ru",
                cityId: "4c26ad1c-ca49-4fc1-af64-f540c6a873e4",
                cityDistrict: "Бостандыкский район",
                regionId: "4da8e628-6856-4e32-95df-60fa493549b8",
                itemId: args.itemId,
            });
            params.append("geoPolygons[]", "KAZ-000000010");
            params.append("geoPolygons[]", "KAZ-000000014");
            const url = "/front/api/catalog/product-card/base/v3?" + params.toString();
            const resp = await fetch(url, {credentials: "include"});
            if (!resp.ok) return {error: `HTTP ${resp.status}`, status: resp.status};
            return await resp.json();
        }
    """
    try:
        result = await page.evaluate(fetch_js, {"itemId": str(item_id)})
    except Exception as e:
        log.warning("product_card_fetch_failed", item_id=item_id, error=str(e))
        return []
    if not isinstance(result, dict) or result.get("error"):
        return []
    data = result.get("data") or {}
    variants = data.get("variants") or []
    if not isinstance(variants, list):
        return []
    brand = data.get("brand") or ""
    product_type = data.get("productType") or ""
    # Unit label lives under attributes.units.unit (e.g. "мл", "г")
    attributes = data.get("attributes") or {}
    units_attr = attributes.get("units") or {}
    unit_name = units_attr.get("unit") or ""
    out: list[GoldappleRawProduct] = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        rp = variant_to_raw_product(
            v, brand=brand, product_type=product_type, unit_name=unit_name,
        )
        if rp is not None:
            out.append(rp)
    return out


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


async def enumerate_brand_via_api(
    fetcher: Any,
    slug: str,
    *,
    max_pages: int = 30,
    inter_page_delay_ms: int = 4_000,
    post_goto_settle_ms: int = 5_000,
    post_burst_cooldown_ms: int = 20_000,
    pages_per_burst: int = 3,
    max_403_retries_per_page: int = 3,
    max_403_budget_per_brand: int = 12,
) -> BrandEnumerationResult:
    """API-driven enumeration: open brand page once, then loop cards-list
    directly via ``page.evaluate('fetch(...)')`` for full pagination.

    Why this exists alongside the scroll-based ``enumerate_brand``:
    big brands (Clinique 220, MAC 176) didn't paginate via scroll because
    the SPA's intersection observer doesn't fire reliably under fast
    programmatic scrolling. Calling the API directly from the page's JS
    context gets all cookies + the page's fetch fingerprint, so the API
    server sees the same request shape as the SPA's own internal calls —
    no HTTP 403, no scroll-pacing dependency.

    Strategy
    --------
    1. ``page.goto('/brands/{slug}')`` once to settle session cookies and
       extract ``categoryId`` from the page's ``og:image`` meta tag
       (pattern: ``pcdn.goldapple.ru/p/c/{categoryId}/...``).
    2. If ``og:image`` lacks a category-shaped id, the slug is invalid
       (slug page falls through to the SPA shell). Return early with
       empty raw_products + error.
    3. Loop ``page.evaluate(fetch_cards_list_js)`` with paginating
       ``pageNumber`` until ``pagination.nextPage`` is false or ``max_pages``
       is reached. Pacing ``inter_page_delay_ms`` between calls keeps the
       per-host rate-limit happy.
    """
    page = fetcher._page
    cards_collected: list[dict] = []
    cards_list_calls = 0

    url = f"{GOLDAPPLE_HOST}/brands/{slug}"
    log.info("brand_enum_api_start", slug=slug, url=url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=BRAND_PAGE_GOTO_TIMEOUT_MS)
    except Exception as e:
        log.warning("brand_enum_goto_failed", slug=slug, error=str(e))
        return BrandEnumerationResult(
            slug=slug, product_count_badge=None, cards_collected=0,
            raw_products=[], cards_list_calls=0,
            error=f"goto_failed: {e}",
        )

    # Tuned via matcher-review-2026-05-15 smoke run: 2.5s was insufficient for
    # Clinique/Tom Ford/Givenchy — the og:image meta hadn't been injected yet
    # so categoryId extraction returned None and we falsely flagged the slug
    # as invalid. 5s settle reliably surfaces the meta tag.
    await page.wait_for_timeout(post_goto_settle_ms)

    # Extract categoryId from og:image meta. Pattern: pcdn.goldapple.ru/p/c/{id}/...
    import re
    try:
        html = await page.content()
    except Exception as e:
        return BrandEnumerationResult(
            slug=slug, product_count_badge=None, cards_collected=0,
            raw_products=[], cards_list_calls=0,
            error=f"content_read_failed: {e}",
        )
    cat_match = re.search(r'pcdn\.goldapple\.ru/p/c/(\d+)/', html)
    if not cat_match:
        log.warning("brand_enum_no_category_id", slug=slug,
                    note="slug likely invalid — fell through to SPA shell")
        return BrandEnumerationResult(
            slug=slug, product_count_badge=None, cards_collected=0,
            raw_products=[], cards_list_calls=0,
            error="no_category_id_in_og_image",
        )
    category_id = cat_match.group(1)
    badge_match = re.search(r"(\d+)\s*продукт", html, re.IGNORECASE)
    badge = int(badge_match.group(1)) if badge_match else None
    log.info("brand_enum_category_id_resolved", slug=slug,
             category_id=category_id, badge=badge)

    # Drive cards-list directly from JS context. Use the same request body the
    # SPA emits (probe-captured in inbox/ga_cards_api/call_00_request.json).
    fetch_js = """
        async (args) => {
            const body = {
                categoryId: args.categoryId,
                pageNumber: args.pageNumber,
                pageSize: 20,
                filters: [],
                mode: "dynamic",
                cityId: "4c26ad1c-ca49-4fc1-af64-f540c6a873e4",
                cityDistrict: "Бостандыкский район",
                geoPolygons: ["KAZ-000000010", "KAZ-000000014"],
                regionId: "4da8e628-6856-4e32-95df-60fa493549b8"
            };
            const resp = await fetch("/front/api/catalog/cards-list?locale=ru", {
                method: "POST",
                headers: {"content-type": "application/json"},
                body: JSON.stringify(body),
                credentials: "include"
            });
            if (!resp.ok) return { error: `HTTP ${resp.status}`, status: resp.status };
            return await resp.json();
        }
    """

    # Per-brand 403 budget — break only when systemic blocking is evident.
    # Per-page retry — exponential backoff (12s → 24s → 48s) before SKIPPING
    # the page (not breaking the brand): zielinski_rozen v2 postmortem showed
    # the old "break on first stuck page" path costs ~17 unread pages worth
    # of SKUs when only one page is rate-limited.
    backoff_ms = [12_000, 24_000, 48_000]
    total_403 = 0
    successful_pages_since_cooldown = 0
    last_pagination_seen_nextpage = True

    async def _fetch_page(p_num: int) -> Optional[dict]:
        try:
            return await page.evaluate(fetch_js, {
                "categoryId": category_id, "pageNumber": p_num,
            })
        except Exception as e:
            log.warning("brand_enum_fetch_failed",
                        slug=slug, page=p_num, error=str(e))
            return None

    for page_num in range(1, max_pages + 1):
        # Anti-burst cooldown: after pages_per_burst successful pages, sleep
        # post_burst_cooldown_ms to let the server-side rate-counter decay.
        # Empirically the 403-after-4-pages pattern indicates a burst limit.
        if successful_pages_since_cooldown >= pages_per_burst:
            log.info("brand_enum_api_burst_cooldown",
                     slug=slug, before_page=page_num,
                     cooldown_ms=post_burst_cooldown_ms)
            await page.wait_for_timeout(post_burst_cooldown_ms)
            successful_pages_since_cooldown = 0

        result = await _fetch_page(page_num)
        cards_list_calls += 1
        if result is None:
            break  # transport-level fetch failure → bail brand
        if not isinstance(result, dict):
            break

        # Per-page 403 retry loop with exponential backoff.
        retry_attempt = 0
        while result.get("status") == 403 and retry_attempt < max_403_retries_per_page:
            total_403 += 1
            if total_403 > max_403_budget_per_brand:
                log.warning("brand_enum_api_403_budget_exhausted",
                            slug=slug, page=page_num, total_403=total_403)
                result = None
                break
            cooldown = backoff_ms[min(retry_attempt, len(backoff_ms) - 1)]
            log.info("brand_enum_api_403_retry",
                     slug=slug, page=page_num,
                     attempt=retry_attempt + 1, cooldown_ms=cooldown,
                     total_403=total_403)
            await page.wait_for_timeout(cooldown)
            result = await _fetch_page(page_num)
            cards_list_calls += 1
            retry_attempt += 1
            if result is None:
                break

        if result is None:
            break  # 403 budget exhausted → can't continue safely

        # If still 403 after exhausting page-level retries: SKIP this page,
        # try the next. (Pre-fix behaviour broke the entire brand here —
        # costing zielinski_rozen ~14 unread pages of SKUs in v2.)
        if isinstance(result, dict) and result.get("status") == 403:
            log.warning("brand_enum_api_403_page_skipped",
                        slug=slug, page=page_num,
                        retries_used=retry_attempt,
                        total_403=total_403)
            successful_pages_since_cooldown = 0  # reset burst counter
            # Conservative pause before next page so we don't immediately
            # re-trigger the rate-limiter.
            await page.wait_for_timeout(inter_page_delay_ms * 2)
            continue

        if result.get("error"):
            log.warning("brand_enum_api_error",
                        slug=slug, page=page_num, error=result.get("error"))
            break

        data = result.get("data") or {}
        page_cards = data.get("cards") or []
        cards_collected.extend(page_cards)
        pag = data.get("pagination") or {}
        last_pagination_seen_nextpage = bool(pag.get("nextPage"))
        successful_pages_since_cooldown += 1
        if not last_pagination_seen_nextpage:
            break
        await page.wait_for_timeout(inter_page_delay_ms)

    # Deduplicate + convert.
    seen: set[str] = set()
    raw_products: list[GoldappleRawProduct] = []
    multivariant_master_ids: list[str] = []
    slug_path_default = f"/-{slug}"
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
        # Multi-variant trigger: when attributes carry >1 unit OR >1
        # colour, cards-list returned only this "master" card and the
        # sibling size/shade variants are missing. Queue the master
        # itemId for a product-card/base/v3 fetch that returns all
        # variants. Source: matcher-review-2026-05-16.
        attrs = p.get("attributes") or {}
        units = attrs.get("units") or {}
        colors = attrs.get("colors") or {}
        if (units.get("count", 0) or 0) > 1 or (colors.get("count", 0) or 0) > 1:
            multivariant_master_ids.append(str(sku_id))

    # ---- Multi-variant top-up ----
    variant_calls = 0
    extra_variants = 0
    for master_id in multivariant_master_ids:
        variants = await fetch_product_variants(page, master_id)
        variant_calls += 1
        for rp in variants:
            if rp.sku_id in seen:
                continue
            seen.add(rp.sku_id)
            raw_products.append(rp)
            extra_variants += 1
        await page.wait_for_timeout(600)

    log.info(
        "brand_enum_api_complete",
        slug=slug,
        cards_collected=len(cards_collected),
        distinct_raw_products=len(raw_products),
        cards_list_calls=cards_list_calls,
        multivariant_calls=variant_calls,
        extra_variants_added=extra_variants,
        badge=badge,
        category_id=category_id,
    )
    return BrandEnumerationResult(
        slug=slug,
        product_count_badge=badge,
        cards_collected=len(cards_collected),
        raw_products=raw_products,
        cards_list_calls=cards_list_calls,
    )


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


async def enumerate_brand_hybrid(
    fetcher: Any,
    slug: str,
) -> BrandEnumerationResult:
    """Try scroll first, then top up via API pagination.

    Scroll-based ``enumerate_brand`` reliably fires the SPA's natural
    cards-list calls for ~30s and captures whatever the page paginates
    on its own. For big brands (Clinique 220, MAC 176) the natural
    pagination doesn't always reach the end. After scroll completes we
    optionally invoke the API-pagination path for additional pages —
    starting from ``floor(cards / 20) + 1`` so we don't refetch what
    scroll already gave us.

    Fall-through when scroll yields nothing: try API outright (the brand
    page might exist but its lazy-load is broken in headless mode).
    """
    result = await enumerate_brand(fetcher, slug)
    # If scroll captured >= 80% of the badge total, we're done.
    if (
        result.product_count_badge
        and len(result.raw_products) >= int(result.product_count_badge * 0.8)
    ):
        return result
    # Otherwise: try API top-up. enumerate_brand_via_api re-navigates and
    # rebuilds; it will return its own set of cards. Take whichever set
    # is larger.
    api_result = await enumerate_brand_via_api(fetcher, slug)
    if len(api_result.raw_products) > len(result.raw_products):
        log.info("brand_enum_hybrid_api_wins",
                 slug=slug,
                 scroll_count=len(result.raw_products),
                 api_count=len(api_result.raw_products))
        return api_result
    return result


async def enumerate_brands(
    fetcher: Any,
    slugs: Iterable[str],
    *,
    inter_brand_pause_seconds: float = 3.0,
    mode: str = "hybrid",
) -> list[BrandEnumerationResult]:
    """Enumerate a list of GA brand slugs.

    Parameters
    ----------
    mode : {"api", "scroll"}
        ``"api"`` (default) — uses ``enumerate_brand_via_api``, which opens
        each brand page once to extract ``categoryId`` from ``og:image``
        then drives ``cards-list`` directly from the page's JS context.
        Fully paginates regardless of brand-page size.

        ``"scroll"`` — legacy scroll + XHR-capture path
        (``enumerate_brand``). Kept for tests / fallback; may miss pages
        on big brands.
    """
    results: list[BrandEnumerationResult] = []
    slugs_list = list(slugs)
    for i, slug in enumerate(slugs_list):
        if mode == "hybrid":
            result = await enumerate_brand_hybrid(fetcher, slug)
        elif mode == "api":
            result = await enumerate_brand_via_api(fetcher, slug)
        else:
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
    "PRODUCT_CARD_API_FRAGMENT",
    "card_to_raw_product",
    "enumerate_brand",
    "enumerate_brand_hybrid",
    "enumerate_brand_via_api",
    "enumerate_brands",
    "fetch_product_variants",
    "variant_to_raw_product",
]
