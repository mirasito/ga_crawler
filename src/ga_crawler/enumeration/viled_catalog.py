"""Catalog enumeration for viled (`/{gender}/catalog/1310`) — CRAWL-01.

D-223: NOT sitemap-only; viled.kz sitemap exposes all 42 k luxury items
without category metadata. The catalog endpoints (`/men/catalog/1310` and
`/women/catalog/1310`) carry the `__NEXT_DATA__` block we need for both
product-id enumeration AND pagination metadata.

D-224 / 02-WAVE0-PROBE.md §A4 REVISED: pagination metadata lives at
`props.pageProps.items.{content, total, totalPages, pageSize, pageNumber}`
(NOT `pageProps.products[]/totalCount/currentPage` as RESEARCH §Pattern 2
originally ASSUMED). Each `content[i]` row exposes a numeric `id` field that
maps to the canonical PDP URL `https://viled.kz/item/{id}`.

D-225: 2 s pause between page fetches; concurrency = 1.

Pagination URL convention — OPEN ITEM (per Wave 0 PROBE follow-up):
  Live probe (run during Plan 02-04 implementation, 2026-05-07) confirmed
  that NONE of the obvious URL conventions paginate the SSR HTML — every
  attempt returned page 1:
    /men/catalog/1310?page=2          → pageNumber=1
    /men/catalog/1310?pageNumber=2    → pageNumber=1
    /men/catalog/1310?p=2             → pageNumber=1
    /men/catalog/1310?offset=60       → pageNumber=1
    /men/catalog/1310/page/2          → 404
    /men/catalog/1310/2               → 404
    /_next/data/{buildId}/men/catalog/1310.json?page=2 → pageNumber=1
    /api/{items,catalog,products,...} → 404
  The catalog page appears to use client-side JS-driven XHR pagination that
  the public surface does not expose to a simple GET. Reverse-engineering
  the exact request signature is deferred to Phase 3/7 ops follow-up.
  v1 limitation: this enumerator returns ONLY page-1 product IDs (60 per
  catalog × 2 catalogs = 120 SKUs total). That is enough to seed the
  D-201 sanity_gate_n=100 catastrophic-failure detector; the auto-suggest
  mechanism (D-203) takes over from week-5.

Pitfall 8: if a catalog endpoint returns non-200 (auth gate or 403), the
enumerator returns an empty list for that base — the orchestrator can fall
back to sitemap+brand-allowlist as documented in 02-WAVE0-PROBE.md.

Source: 02-RESEARCH.md §Pattern 2 (REVISED per WAVE0 PROBE);
        02-PATTERNS.md lines 351-389 (analog viled_catalog adaptation).
"""

from __future__ import annotations

import time
from typing import Callable, Optional
from urllib.parse import urlparse

import structlog
from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ga_crawler.parsers.viled_nextdata import _extract_next_data

log = structlog.get_logger(__name__)


CATALOG_TIMEOUT_S: int = 30
CATALOG_PAUSE_S: float = 2.0  # D-225 — overridable via fetch_catalog_urls(pause_seconds=...)
ITEM_URL_TEMPLATE: str = "https://viled.kz/item/{item_id}"


class TransientFetchError(RuntimeError):
    """Raised on retryable network failures (5xx, network error, timeout)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((TransientFetchError, RequestException)),
    reraise=True,
)
def _fetch_html(url: str, timeout_s: int = CATALOG_TIMEOUT_S) -> tuple[int, str]:
    """Fetch a catalog page with curl_cffi `impersonate="chrome"`.

    Returns (status, body). Raises TransientFetchError on 5xx / network error.
    Same retry semantics as fetchers/viled.py::_fetch_html — kept module-local
    so the catalog enumerator and the PDP fetcher can be patched independently
    in tests.
    """
    try:
        resp = requests.get(url, impersonate="chrome", timeout=timeout_s)
    except RequestException:
        raise
    except Exception as e:
        raise TransientFetchError(f"connection error fetching {url}: {e}") from e
    if 500 <= resp.status_code < 600:
        raise TransientFetchError(f"http {resp.status_code} for {url}")
    return resp.status_code, resp.text


def _items_block(nd: dict) -> Optional[dict]:
    """Extract the `props.pageProps.items` block from a parsed __NEXT_DATA__.
    Returns None on shape mismatch.
    """
    try:
        return nd["props"]["pageProps"]["items"]
    except (KeyError, TypeError):
        return None


def _content_to_urls(content: list, catalog_base: str) -> list[str]:
    """Map `items.content[]` rows to absolute viled PDP URLs via item.id."""
    urls: list[str] = []
    parsed = urlparse(catalog_base)
    base_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else "https://viled.kz"
    for row in content:
        if not isinstance(row, dict):
            continue
        item_id = row.get("id")
        if item_id is None:
            continue
        # Canonical PDP form is /item/{id}; row.url field is not present in
        # the WAVE0-PROBE-pinned shape, so we synthesize.
        urls.append(f"{base_origin}/item/{item_id}")
    return urls


def fetch_catalog_urls(
    catalog_base: str,
    *,
    pause_seconds: float = CATALOG_PAUSE_S,
    fetch_callable: Optional[Callable[[str], tuple[int, str]]] = None,
) -> list[str]:
    """Walk a viled catalog base URL and return the union of product URLs across pages.

    Algorithm:
      1. Fetch page 1; extract `pageProps.items.{content, totalPages, pageNumber}`.
      2. Map page-1 `content[]` rows to `https://viled.kz/item/{id}` URLs.
      3. For pages 2..totalPages: build `?page=N`, sleep `pause_seconds`,
         fetch, verify the response's `pageNumber` matches the request — if
         the server ignores the query param (live probe finding 2026-05-07,
         documented in module docstring), log a warning and break out (we
         cannot get past page 1 with the current public surface).
      4. Return the deduplicated list of product URLs in original page order.

    Args:
      catalog_base:    e.g. `"https://viled.kz/men/catalog/1310"`.
      pause_seconds:   inter-page delay (D-225, default 2 s).
      fetch_callable:  injected for tests (Pitfall 1 — respx incompatible
                       with curl_cffi, so we monkey-patch this wrapper).
                       Default: module-level _fetch_html.

    Returns:
      list of absolute product URLs. Empty on:
        - non-200 response on page 1 (Pitfall 8 — caller falls back)
        - missing __NEXT_DATA__ (auth gate or shape drift)
        - empty `items.content` (catalog has no products)
    """
    if fetch_callable is None:
        fetch_callable = _fetch_html
    try:
        status, page1_html = fetch_callable(catalog_base)
    except Exception as e:
        log.warning("catalog_fetch_exception", url=catalog_base, error=str(e))
        return []
    if status != 200:
        log.warning("catalog_fetch_non_200", url=catalog_base, status=status)
        return []

    nd = _extract_next_data(page1_html)
    if nd is None:
        log.warning("catalog_no_nextdata", url=catalog_base)
        return []
    items = _items_block(nd)
    if items is None:
        log.warning("catalog_no_items_block", url=catalog_base)
        return []

    content = items.get("content") or []
    total_pages = int(items.get("totalPages") or 1)
    page_number = int(items.get("pageNumber") or 1)
    total = int(items.get("total") or len(content))

    urls: list[str] = list(_content_to_urls(content, catalog_base))

    # Pages 2..totalPages — best-effort. If the server ignores ?page=N (live
    # probe finding), break early on the first non-incrementing pageNumber.
    if total_pages > 1:
        seen_first_id: Optional[int] = None
        if content:
            seen_first_id = content[0].get("id") if isinstance(content[0], dict) else None
        for page in range(2, total_pages + 1):
            time.sleep(pause_seconds)  # D-225 inter-page pacing
            page_url = f"{catalog_base}?page={page}"
            try:
                page_status, page_html = fetch_callable(page_url)
            except Exception as e:
                log.error(
                    "catalog_page_failed",
                    page=page,
                    url=page_url,
                    error=str(e),
                )
                continue
            if page_status != 200:
                log.warning(
                    "catalog_page_non_200",
                    page=page,
                    status=page_status,
                )
                continue
            page_nd = _extract_next_data(page_html)
            if page_nd is None:
                continue
            page_items = _items_block(page_nd) or {}
            page_content = page_items.get("content") or []
            returned_page_num = page_items.get("pageNumber")
            # Detect SSR-not-paginating: server returned page-1 again.
            if (
                returned_page_num == page_number
                or (
                    page_content
                    and isinstance(page_content[0], dict)
                    and seen_first_id is not None
                    and page_content[0].get("id") == seen_first_id
                )
            ):
                log.warning(
                    "catalog_pagination_not_supported",
                    catalog_base=catalog_base,
                    requested_page=page,
                    returned_page_number=returned_page_num,
                    note=(
                        "viled SSR ignores ?page=N (verified 2026-05-07). "
                        "Returning page-1 URLs only as v1 limitation; deferred "
                        "to Phase 3/7 ops follow-up."
                    ),
                )
                break
            urls.extend(_content_to_urls(page_content, catalog_base))

    # Dedup while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    log.info(
        "catalog_enumeration_complete",
        catalog_base=catalog_base,
        total_meta=total,
        urls_collected=len(deduped),
        total_pages_meta=total_pages,
    )
    return deduped


__all__ = [
    "ITEM_URL_TEMPLATE",
    "CATALOG_TIMEOUT_S",
    "CATALOG_PAUSE_S",
    "TransientFetchError",
    "fetch_catalog_urls",
    "_fetch_html",
    "_items_block",
    "_content_to_urls",
]
