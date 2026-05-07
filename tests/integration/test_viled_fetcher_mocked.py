"""CRAWL-01 + CRAWL-04 — integration: ViledFetcher.run_loop end-to-end with
monkey-patched _fetch_html.

Plan 02-04 / Wave 3 GREEN. Pitfall 1 + Phase 3 D-302: respx is HTTPX-specific
and silently passes through to real network on curl_cffi. We patch the
`_fetch_html` wrapper directly.

Source: 02-RESEARCH.md §Validation Architecture row 19; §Pitfall 1.
"""

from __future__ import annotations

from unittest.mock import patch

from ga_crawler.fetchers.viled import ViledFetcher


def test_fetch_one_returns_dict_with_status_and_html(viled_pdp_html):
    """Smoke: ViledFetcher.fetch_one returns the spike-style dict with status/url/html."""
    with patch(
        "ga_crawler.fetchers.viled._fetch_html",
        return_value=(200, viled_pdp_html),
    ):
        f = ViledFetcher(run_id=1, pause_seconds=0)
        rec = f.fetch_one("https://viled.kz/item/407682")
    assert rec["status"] == 200
    assert rec["url"] == "https://viled.kz/item/407682"
    assert rec["html"] == viled_pdp_html


def test_run_loop_e2e_mocked(viled_pdp_html):
    """Full 3-URL run with mocked HTTP — every fetch succeeds, all records returned."""
    with patch(
        "ga_crawler.fetchers.viled._fetch_html",
        return_value=(200, viled_pdp_html),
    ):
        f = ViledFetcher(run_id=1, pause_seconds=0)
        stats: dict = {}
        records = f.run_loop(
            [
                "https://viled.kz/item/1",
                "https://viled.kz/item/2",
                "https://viled.kz/item/3",
            ],
            stats,
            sleep_fn=lambda s: None,
        )
    assert len(records) == 3
    assert stats["fetch_count"] == 3
    assert "fetch_failures" not in stats
    assert all(r["status"] == 200 for r in records)


def test_run_loop_e2e_with_one_failure_recovers(viled_pdp_html):
    """One transient failure does NOT abort the run; the other 2 SKUs succeed."""
    state = {"calls": 0}

    def fake(url, *_, **__):
        state["calls"] += 1
        if state["calls"] == 2:
            # Persistent failure — TransientFetchError survives all 3 retries
            # and surfaces to fetch_one_isolated, which counts and continues.
            from ga_crawler.fetchers.viled import TransientFetchError

            raise TransientFetchError("simulated 5xx")
        return (200, viled_pdp_html)

    with patch("ga_crawler.fetchers.viled._fetch_html", side_effect=fake):
        f = ViledFetcher(run_id=1, pause_seconds=0)
        stats: dict = {}
        records = f.run_loop(
            [
                "https://viled.kz/item/1",
                "https://viled.kz/item/2",
                "https://viled.kz/item/3",
            ],
            stats,
            sleep_fn=lambda s: None,
        )
    assert len(records) == 2  # SKU 2 lost
    assert stats["fetch_count"] == 3
    assert stats["fetch_failures"] == 1


def test_no_respx_imported():
    """Pitfall 1: viled fetcher must NOT use respx (HTTPX-only mock; silent
    passthrough on curl_cffi).
    """
    import inspect

    from ga_crawler.fetchers import viled as viled_module

    src = inspect.getsource(viled_module)
    assert "respx" not in src
