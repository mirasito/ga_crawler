"""Pitfall 4 stale-SKU vs gate-shell discrimination - anchored to spike row 0."""

from __future__ import annotations

from ga_crawler.parsers.goldapple_microdata import (
    GATE_SHELL_MAX_BYTES,
    GATE_TITLE_MARKER,
    detect_state,
    has_microdata_price,
)


def test_spike_row_0_is_stale_not_gate_shell(tier2_results_json: dict) -> None:
    """Spike row for '7681000002-givenchy-pour-homme-blue-label':
       status=200, html_size~9500 in spike memo (~18027 in actual archived run; both <30KB),
       title="Loading <url>" -> stale-SKU.
    If we mis-classified as gate-shell, every weekly run would falsely alarm.
    """
    rows = tier2_results_json.get("results", [])
    assert len(rows) > 0, "spike results JSON missing data"

    # Find the canonical stale-SKU row (URL contains 7681000002)
    candidates = [r for r in rows if "7681000002" in r.get("url", "")]
    assert len(candidates) == 1, f"expected 1 stale-SKU row in spike data, got {len(candidates)}"
    row = candidates[0]

    assert row["status"] == 200
    assert row["html_size"] is not None
    assert row["html_size"] < GATE_SHELL_MAX_BYTES
    title = row.get("title", "") or ""
    # Title is "Loading <url>" - does NOT contain the gate marker "checking"
    assert GATE_TITLE_MARKER not in title.lower(), f"unexpected gate marker in title: {title!r}"


def test_stale_sku_fixture_classified_correctly(stale_sku_html: str) -> None:
    """Direct round-trip: synthesized stale-SKU HTML + Loading title -> 'stale-sku'."""
    title = "Loading https://goldapple.kz/7681000002-givenchy-pour-homme-blue-label"
    assert detect_state(stale_sku_html, title) == "stale-sku"
    has_offer, _ = has_microdata_price(stale_sku_html)
    assert has_offer is False  # confirms D-303 stale-SKU pattern


def test_stale_sku_no_false_positive_as_gate(stale_sku_html: str) -> None:
    """Even with completely empty title, stale-SKU is NOT classified gate-shell
    (only 'checking' marker triggers gate-shell)."""
    assert detect_state(stale_sku_html, title="") == "stale-sku"


def test_stale_sku_size_band_matches_spike(stale_sku_html: str) -> None:
    """Synthesized fixture is sized within the 5-13KB band (matches spike row 0 ~9.5KB)."""
    assert 5_000 < len(stale_sku_html) < 13_000
