"""Unit tests for goldapple_sitemap.py: regex whitelist + mocked sitemap fetch."""

from __future__ import annotations

import re

import pytest

from ga_crawler.enumeration.goldapple_sitemap import (
    PRODUCT_URL_RE,
    SITEMAP_INDEX,
    SitemapFetchError,
    fetch_sitemap_slugs,
)


class TestProductUrlRegex:
    """Whitelist enforcement (Threat T-04 sitemap-poisoning prevention)."""

    def test_matches_numeric_id_latin_slug(self) -> None:
        m = PRODUCT_URL_RE.match("https://goldapple.kz/123-givenchy-pour-homme")
        assert m is not None
        assert m.group(1) == "123"
        assert m.group(2) == "givenchy-pour-homme"

    def test_matches_cyrillic_slug(self) -> None:
        m = PRODUCT_URL_RE.match("https://goldapple.kz/123-эсте-лаудер")
        assert m is not None
        assert m.group(2) == "эсте-лаудер"

    def test_rejects_non_numeric_id(self) -> None:
        assert PRODUCT_URL_RE.match("https://goldapple.kz/abc-foo") is None

    def test_rejects_brands_facet(self) -> None:
        assert PRODUCT_URL_RE.match("https://goldapple.kz/brands/givenchy") is None

    def test_rejects_wrong_domain(self) -> None:
        assert PRODUCT_URL_RE.match("https://goldapple.ru/123-foo") is None
        assert PRODUCT_URL_RE.match("https://evil.example.com/123-foo") is None

    def test_rejects_no_slug(self) -> None:
        assert PRODUCT_URL_RE.match("https://goldapple.kz/123-") is None


def test_sitemap_excerpt_regex_extraction(sitemap_xml: str) -> None:
    """Real spike fixture parses to >=10 URLs; mix of product + facet/search.

    The fixture uses the `ns0:loc` namespaced form (etree-serialized excerpt),
    so we match both shapes. The production sitemap (per spike 01-05) serves
    plain `<loc>` — `fetch_sitemap_slugs` is exercised on that shape via
    `test_fetch_sitemap_slugs_mocked` below.

    The fixture mixes numeric-id product URLs (`/10022600003-profilaktika-gribka`)
    with search-facet URLs (`/s/...`, `/f/...`). The whitelist must accept the
    former and reject the latter — both invariants asserted here.
    """
    urls = re.findall(r"<(?:ns0:)?loc>([^<]+)</(?:ns0:)?loc>", sitemap_xml)
    assert len(urls) >= 10
    product_urls = [u for u in urls if PRODUCT_URL_RE.match(u)]
    facet_urls = [u for u in urls if "/s/" in u or "/f/" in u]
    # At least some product URLs accepted by the whitelist (Threat T-04 forward
    # direction: product URLs pass).
    assert len(product_urls) >= 5
    # And every facet URL was rejected (Threat T-04 reverse direction: poison
    # surface excluded).
    facet_passed = [u for u in facet_urls if PRODUCT_URL_RE.match(u)]
    assert facet_passed == [], (
        f"facet/search URLs leaked through whitelist: {facet_passed[:5]}"
    )


def test_fetch_sitemap_slugs_mocked() -> None:
    """End-to-end mock: index → 1 sub-sitemap → 3 product URLs in 2 slug groups.

    NOTE: respx is httpx-based, not curl_cffi-compatible. We monkey-patch
    _fetch_xml directly to avoid coupling to curl_cffi internals. Per the
    plan §2.3 "Note on respx + curl_cffi": this approach is intentional.
    """
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://goldapple.kz/sitemap-1.xml</loc></sitemap>
</sitemapindex>"""
    sub_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
<url><loc>https://goldapple.kz/100-givenchy-one</loc></url>
<url><loc>https://goldapple.kz/200-givenchy-two</loc></url>
<url><loc>https://goldapple.kz/300-tom-ford-private-blend</loc></url>
<url><loc>https://goldapple.kz/brands/givenchy</loc></url>
</urlset>"""

    from ga_crawler.enumeration import goldapple_sitemap as mod

    orig = mod._fetch_xml
    calls: list[str] = []

    def fake_fetch(url: str) -> str:
        calls.append(url)
        if url == SITEMAP_INDEX:
            return index_xml
        if url == "https://goldapple.kz/sitemap-1.xml":
            return sub_xml
        raise mod.SitemapFetchError(f"unexpected url {url}")

    mod._fetch_xml = fake_fetch
    try:
        slugs = fetch_sitemap_slugs()
    finally:
        mod._fetch_xml = orig

    assert "givenchy-one" in slugs
    assert "givenchy-two" in slugs
    assert "tom-ford-private-blend" in slugs
    # /brands/givenchy was rejected by PRODUCT_URL_RE
    assert "givenchy" not in slugs
    assert calls == [SITEMAP_INDEX, "https://goldapple.kz/sitemap-1.xml"]


def test_fetch_xml_raises_on_non_200() -> None:
    """tenacity retries 3 times, then re-raises SitemapFetchError."""
    from unittest.mock import patch

    from ga_crawler.enumeration import goldapple_sitemap as mod

    class FakeResp:
        status_code = 503
        text = ""

    with patch.object(mod.requests, "get", return_value=FakeResp()):
        with pytest.raises(SitemapFetchError, match="http 503"):
            mod._fetch_xml("https://goldapple.kz/sitemap.xml")
