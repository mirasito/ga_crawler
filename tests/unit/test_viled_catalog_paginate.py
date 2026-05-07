"""CRAWL-01 — viled catalog enumeration via __NEXT_DATA__ pagination.

Plan 02-04 / Wave 3 GREEN. Per 02-WAVE0-PROBE.md A4 REVISED, the catalog
shape is `pageProps.items.{content, total, totalPages, pageSize, pageNumber}`
(NOT `pageProps.products[] / totalCount`). Each `content[i]` exposes a
numeric `id` field that maps to `https://viled.kz/item/{id}`.

Tests inject `fetch_callable` directly (Pitfall 1 — respx incompatible with
curl_cffi) and patch `time.sleep` for pacing assertions.

Source: 02-RESEARCH.md §Pattern 2 (REVISED); 02-WAVE0-PROBE.md A4.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from ga_crawler.enumeration.viled_catalog import fetch_catalog_urls


def _items_block_html(content: list, *, total_pages: int = 1, page_number: int = 1, total: int | None = None) -> str:
    """Wrap `items.content` rows in a __NEXT_DATA__ envelope per A4 REVISED shape."""
    if total is None:
        total = len(content)
    nd = {
        "props": {
            "pageProps": {
                "items": {
                    "content": content,
                    "pageNumber": page_number,
                    "totalPages": total_pages,
                    "total": total,
                    "pageSize": 60,
                }
            }
        }
    }
    return (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd, ensure_ascii=False)}</script>'
        "</body></html>"
    )


def _make_fake_fetch(pages: list[list[dict]]):
    """Build a fetch_callable that returns successive pages.

    Each page response advertises totalPages = len(pages) so the enumerator
    walks the full set; pageNumber is 1-indexed by call order.
    """
    state = {"call": 0}
    total_pages = len(pages)
    total_items = sum(len(p) for p in pages)

    def fake(url, *_, **__):
        idx = state["call"]
        state["call"] += 1
        if idx < len(pages):
            return 200, _items_block_html(
                pages[idx],
                total_pages=total_pages,
                page_number=idx + 1,
                total=total_items,
            )
        # Beyond planned pages — return empty content to terminate cleanly.
        return 200, _items_block_html(
            [],
            total_pages=total_pages,
            page_number=idx + 1,
            total=total_items,
        )

    return fake


# ---------- Single-page extraction ----------


def test_single_page_extract():
    content = [{"id": 100 + i} for i in range(5)]
    fake = _make_fake_fetch([content])
    urls = fetch_catalog_urls(
        "https://viled.kz/men/catalog/1310",
        fetch_callable=fake,
    )
    assert len(urls) == 5
    assert urls[0] == "https://viled.kz/item/100"
    assert all(u.startswith("https://viled.kz/item/") for u in urls)


def test_content_to_urls_synthesizes_via_id_field():
    """A4 REVISED catalog rows expose `id`, not `url`. Enumerator must
    synthesize `https://viled.kz/item/{id}`.
    """
    content = [{"id": 407682, "brandName": "Alice+Olivia"}]
    fake = _make_fake_fetch([content])
    urls = fetch_catalog_urls(
        "https://viled.kz/men/catalog/1310",
        fetch_callable=fake,
    )
    assert urls == ["https://viled.kz/item/407682"]


# ---------- Multi-page pagination (synthetic — server cooperative) ----------


def test_multi_page_pagination_when_server_cooperates():
    """If the server actually paginates (synthetic test fetcher does), the
    enumerator collects every page.
    """
    page1 = [{"id": i} for i in range(20)]
    page2 = [{"id": i} for i in range(20, 40)]
    page3 = [{"id": i} for i in range(40, 45)]
    fake = _make_fake_fetch([page1, page2, page3])
    urls = fetch_catalog_urls(
        "https://viled.kz/men/catalog/1310",
        fetch_callable=fake,
        pause_seconds=0,
    )
    assert len(urls) == 45
    assert urls[0] == "https://viled.kz/item/0"
    assert urls[-1] == "https://viled.kz/item/44"


def test_2s_pause_between_pages():
    """D-225: 2 s pause between page fetches when totalPages > 1."""
    page1 = [{"id": i} for i in range(20)]
    page2 = [{"id": i} for i in range(20, 40)]
    page3 = [{"id": i} for i in range(40, 60)]
    fake = _make_fake_fetch([page1, page2, page3])
    sleep_calls: list[float] = []
    with patch(
        "ga_crawler.enumeration.viled_catalog.time.sleep",
        side_effect=lambda s: sleep_calls.append(s),
    ):
        fetch_catalog_urls(
            "https://viled.kz/men/catalog/1310",
            fetch_callable=fake,
            pause_seconds=2.0,
        )
    # 3 pages → 2 inter-page sleeps; both at 2.0 s.
    assert sleep_calls.count(2.0) >= 2


# ---------- SSR-not-paginating guard (live finding 2026-05-07) ----------


def test_breaks_when_server_returns_same_page1_for_page2():
    """Live probe (2026-05-07) found viled SSR ignores `?page=N` and returns
    page 1 every time. Enumerator detects this (pageNumber unchanged) and
    breaks early — returning page-1 URLs as the v1 limitation.
    """
    page1_content = [{"id": 100 + i} for i in range(20)]

    def stuck_fake(url, *_, **__):
        # totalPages=3 advertises three pages, but every fetch returns page 1.
        return 200, _items_block_html(
            page1_content,
            total_pages=3,
            page_number=1,
            total=60,
        )

    urls = fetch_catalog_urls(
        "https://viled.kz/men/catalog/1310",
        fetch_callable=stuck_fake,
        pause_seconds=0,
    )
    assert len(urls) == 20  # only page-1 URLs
    assert urls[0] == "https://viled.kz/item/100"


# ---------- Empty / non-200 / shape-drift guards ----------


def test_empty_content_returns_empty():
    fake = _make_fake_fetch([[]])
    assert (
        fetch_catalog_urls("https://viled.kz/men/catalog/1310", fetch_callable=fake)
        == []
    )


def test_non_200_returns_empty():
    """Pitfall 8 fallback: 403 / 404 → enumerator returns []."""
    def fake(url, *_, **__):
        return 403, "<html>blocked</html>"

    assert (
        fetch_catalog_urls("https://viled.kz/men/catalog/1310", fetch_callable=fake)
        == []
    )


def test_no_nextdata_returns_empty():
    def fake(url, *_, **__):
        return 200, "<html><body>no script</body></html>"

    assert (
        fetch_catalog_urls("https://viled.kz/men/catalog/1310", fetch_callable=fake)
        == []
    )


def test_no_items_block_returns_empty():
    """Shape drift: __NEXT_DATA__ present but `pageProps.items` missing."""
    nd = {"props": {"pageProps": {}}}
    body = (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script>'
        "</body></html>"
    )

    def fake(url, *_, **__):
        return 200, body

    assert (
        fetch_catalog_urls("https://viled.kz/men/catalog/1310", fetch_callable=fake)
        == []
    )


def test_dedup_preserves_first_seen_order():
    """If the same id appears on multiple pages (server quirk), keep first seen."""
    page1 = [{"id": 1}, {"id": 2}, {"id": 3}]
    page2 = [{"id": 3}, {"id": 4}, {"id": 5}]  # 3 repeats
    fake = _make_fake_fetch([page1, page2])
    urls = fetch_catalog_urls(
        "https://viled.kz/men/catalog/1310",
        fetch_callable=fake,
        pause_seconds=0,
    )
    # 5 unique ids
    assert len(urls) == 5
    assert urls == [
        "https://viled.kz/item/1",
        "https://viled.kz/item/2",
        "https://viled.kz/item/3",
        "https://viled.kz/item/4",
        "https://viled.kz/item/5",
    ]


# ---------- Integration with the live Wave 0 catalog fixture ----------


def test_real_catalog_fixture_extracts_60_urls(viled_catalog_html):
    """Live page-1 catalog HTML (men/catalog/1310, 60 items per A4 REVISED).
    Enumerator must produce 60 URLs from page 1; downstream pagination is the
    SSR-not-supported case so we expect the function to break after page 1.
    """
    def fake(url, *_, **__):
        # On the recursive page-2 fetch the test fixture would actually
        # return page 1 again. Simulate that by always returning the same HTML.
        return 200, viled_catalog_html

    urls = fetch_catalog_urls(
        "https://viled.kz/men/catalog/1310",
        fetch_callable=fake,
        pause_seconds=0,
    )
    # Live fixture has 60 items; SSR-not-paginating guard breaks page-2 attempt.
    assert len(urls) == 60
    assert all(u.startswith("https://viled.kz/item/") for u in urls)
