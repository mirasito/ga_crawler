"""Smoke probe (D-312) tests — mocked GoldappleFetcher, no live network."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ga_crawler.enumeration.goldapple_sitemap import PRODUCT_URL_RE
from ga_crawler.runner.gates import SMOKE_URLS, smoke_probe


def test_smoke_urls_constant_shape() -> None:
    """3 hardcoded Givenchy URLs; all match PRODUCT_URL_RE."""
    assert isinstance(SMOKE_URLS, tuple)
    assert len(SMOKE_URLS) == 3
    for url in SMOKE_URLS:
        assert PRODUCT_URL_RE.match(url) is not None, f"smoke URL {url!r} fails whitelist regex"


def test_smoke_urls_exclude_stale_row_0() -> None:
    """A12 mitigation: spike row 0 (URL contains 7681000002) is stale; must NOT be in SMOKE_URLS."""
    for url in SMOKE_URLS:
        assert "7681000002" not in url, (
            "SMOKE_URLS contains spike row 0 which is empirically stale (A12). "
            "Use other Givenchy URLs from spike."
        )


@pytest.fixture
def real_pdp_fetcher_pass(goldapple_pdp_html):
    """Build a fake fetcher whose fetch_one returns 200+real-PDP for any URL."""

    async def fake_fetch_one(page, url):
        return {
            "url": url,
            "status": 200,
            "html_size": len(goldapple_pdp_html),
            "html": goldapple_pdp_html,
            "title": "Givenchy ПАРФЮМЕРНАЯ ВОДА — купить ...",
            "gate_cleared": True,
            "block": False,
            "block_reason": None,
        }

    fetcher = MagicMock()
    fetcher._page = MagicMock()
    fetcher.fetch_one = fake_fetch_one
    return fetcher


@pytest.mark.asyncio
async def test_smoke_pass_all_real_pdp(real_pdp_fetcher_pass) -> None:
    """All 3 smoke URLs return real-PDP → pass=True."""
    result = await smoke_probe(real_pdp_fetcher_pass)
    assert result["pass"] is True
    assert "diagnostics" in result
    assert "camoufox_version" in result["diagnostics"]
    assert len(result["diagnostics"]["responses"]) == 3
    for r in result["diagnostics"]["responses"]:
        assert r["status"] == 200
        assert r["block"] is False
        assert r["price_extracted"] is True


@pytest.mark.asyncio
async def test_smoke_fail_one_gate_shell(goldapple_pdp_html, gate_shell_html) -> None:
    """First URL OK; second URL gate-shell → pass=False."""
    call_idx = {"i": 0}

    async def fake_fetch_one(page, url):
        call_idx["i"] += 1
        if call_idx["i"] == 2:
            return {
                "url": url,
                "status": 200,
                "html_size": len(gate_shell_html),
                "title": "Gold Apple — checking device",
                "gate_cleared": False,
                "block": True,
                "block_reason": "gate_shell_not_cleared",
            }
        return {
            "url": url,
            "status": 200,
            "html_size": len(goldapple_pdp_html),
            "html": goldapple_pdp_html,
            "title": "Givenchy",
            "gate_cleared": True,
            "block": False,
        }

    fetcher = MagicMock()
    fetcher._page = MagicMock()
    fetcher.fetch_one = fake_fetch_one

    result = await smoke_probe(fetcher)
    assert result["pass"] is False
    # The 2nd response shows block=True
    assert result["diagnostics"]["responses"][1]["block"] is True


@pytest.mark.asyncio
async def test_smoke_fail_parse_returns_none(stale_sku_html) -> None:
    """200 + body but parse_pdp returns None (no microdata) → pass=False."""

    async def fake_fetch_one(page, url):
        return {
            "url": url,
            "status": 200,
            "html_size": len(stale_sku_html),
            "html": stale_sku_html,  # state=stale-sku → parse_pdp returns None
            "title": "Loading https://goldapple.kz/foo",
            "gate_cleared": True,
            "block": False,
        }

    fetcher = MagicMock()
    fetcher._page = MagicMock()
    fetcher.fetch_one = fake_fetch_one

    result = await smoke_probe(fetcher)
    assert result["pass"] is False
    for r in result["diagnostics"]["responses"]:
        assert r["price_extracted"] is False


@pytest.mark.asyncio
async def test_smoke_diagnostics_shape(real_pdp_fetcher_pass) -> None:
    """Diagnostics dict has expected schema."""
    result = await smoke_probe(real_pdp_fetcher_pass)
    diag = result["diagnostics"]
    assert isinstance(diag["camoufox_version"], str)
    assert isinstance(diag["responses"], list)
    for r in diag["responses"]:
        for key in ("url", "status", "size", "title", "block", "price_extracted"):
            assert key in r, f"diagnostics response missing key: {key}"


@pytest.mark.asyncio
async def test_smoke_with_custom_url_list(goldapple_pdp_html) -> None:
    """Caller can pass override smoke_urls= to test rotation."""

    async def fake_fetch_one(page, url):
        return {
            "url": url,
            "status": 200,
            "html_size": len(goldapple_pdp_html),
            "html": goldapple_pdp_html,
            "title": "Givenchy",
            "block": False,
        }

    fetcher = MagicMock()
    fetcher._page = MagicMock()
    fetcher.fetch_one = fake_fetch_one

    custom = ("https://goldapple.kz/100-givenchy-x", "https://goldapple.kz/200-givenchy-y")
    result = await smoke_probe(fetcher, smoke_urls=custom)
    assert len(result["diagnostics"]["responses"]) == 2
    assert result["diagnostics"]["responses"][0]["url"] == custom[0]
