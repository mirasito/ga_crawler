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
async def test_smoke_probe_retries_once_on_loading_race(
    goldapple_pdp_html, stale_sku_html
) -> None:
    """Operational Finding #1 fix: URL[0] returns Loading-race shape on first
    attempt, real PDP on retry. URLs 1 + 2 happy path. Smoke passes overall."""
    # Track per-URL call counts so we can return different records on attempt 1 vs 2.
    call_log: list[str] = []

    async def fake_fetch_one(page, url):
        call_log.append(url)
        attempt_for_this_url = call_log.count(url)
        # URL[0] (first URL from SMOKE_URLS): Loading race on attempt 1, recover on 2
        if url == SMOKE_URLS[0]:
            if attempt_for_this_url == 1:
                return {
                    "url": url,
                    "status": 200,
                    "html_size": len(stale_sku_html),
                    "html": stale_sku_html,
                    "title": f"Loading {url}",  # exact Loading-race shape
                    "gate_cleared": True,
                    "block": False,
                    "block_reason": None,
                }
            # Attempt 2 — real PDP
            return {
                "url": url,
                "status": 200,
                "html_size": len(goldapple_pdp_html),
                "html": goldapple_pdp_html,
                "title": "Givenchy Irresistible — купить",
                "gate_cleared": True,
                "block": False,
                "block_reason": None,
            }
        # URL[1] + URL[2]: happy path on first attempt
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

    # Total: 3 initial probes + 1 retry of URL[0] = 4 fetch_one calls
    assert len(call_log) == 4, f"expected exactly 4 fetch_one calls, got {len(call_log)}"
    # URL[0] was called twice; URL[1] + URL[2] once each
    assert call_log.count(SMOKE_URLS[0]) == 2
    assert call_log.count(SMOKE_URLS[1]) == 1
    assert call_log.count(SMOKE_URLS[2]) == 1
    # Overall pass: the retry recovered URL[0]
    assert result["pass"] is True
    # The diagnostics entry for URL[0] reflects the SECOND-attempt record
    url0_entry = next(r for r in result["diagnostics"]["responses"] if r["url"] == SMOKE_URLS[0])
    assert url0_entry["price_extracted"] is True
    assert "Loading " not in (url0_entry["title"] or "")


@pytest.mark.asyncio
async def test_smoke_probe_no_retry_on_happy_path(goldapple_pdp_html) -> None:
    """Happy path: all 3 URLs return real PDP on first attempt. No retry,
    no double-fetch — exactly 3 fetch_one calls total."""
    call_log: list[str] = []

    async def fake_fetch_one(page, url):
        call_log.append(url)
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

    assert result["pass"] is True
    assert len(call_log) == 3, f"happy path must NOT retry; got {len(call_log)} calls"


@pytest.mark.asyncio
async def test_smoke_probe_no_retry_on_gate_shell(
    goldapple_pdp_html, gate_shell_html
) -> None:
    """Gate-shell (Operational Finding #2 — real fingerprint failure):
    URL[0] hits 'checking device' shell. Smoke fails fast — NO retry —
    because gate-shell title MUST NOT trigger the Loading-race retry."""
    call_log: list[str] = []

    async def fake_fetch_one(page, url):
        call_log.append(url)
        if url == SMOKE_URLS[0]:
            return {
                "url": url,
                "status": 200,
                "html_size": len(gate_shell_html),
                "html": None,  # block=True records do not carry html
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

    assert result["pass"] is False, "gate-shell must fail the probe"
    assert len(call_log) == 3, (
        f"gate-shell must NOT trigger retry-once (Operational Finding #2 "
        f"is a real fingerprint failure); got {len(call_log)} calls"
    )
    url0_entry = next(r for r in result["diagnostics"]["responses"] if r["url"] == SMOKE_URLS[0])
    assert url0_entry["block"] is True


@pytest.mark.asyncio
async def test_smoke_probe_no_retry_on_non_200(
    goldapple_pdp_html, stale_sku_html
) -> None:
    """Non-200 + Loading-title (synthetic edge): retry condition requires
    status == 200. Status 503 must fail-fast, no retry."""
    call_log: list[str] = []

    async def fake_fetch_one(page, url):
        call_log.append(url)
        if url == SMOKE_URLS[0]:
            return {
                "url": url,
                "status": 503,
                "html_size": len(stale_sku_html),
                "html": None,
                "title": f"Loading {url}",  # synthetic — wouldn't normally pair with 503
                "gate_cleared": True,
                "block": True,
                "block_reason": "http_503",
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
    assert len(call_log) == 3, (
        f"non-200 status must NOT trigger retry-once; got {len(call_log)} calls"
    )


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
