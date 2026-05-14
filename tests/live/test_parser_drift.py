"""TH-03 live parser-drift harness — two-mode (cassette-replay + --refresh-live).

Two modes documented per D-906:
  - default `pytest -m live`: cassette-replay against 3 Phase 8 fixtures
  - `pytest -m live --refresh-live`: Camoufox/curl_cffi re-fetch + syrupy diff

Retroactively locks Phase 8 parser fixes (PARSE-FIX-01..03) against drift.
If goldapple/viled HTML shape drifts so brand merges back into name, or
volume_raw nulls return, these tests fail loud (the "would have caught run #13"
guarantee — D-905/D-906, Phase 9 CONTEXT.md).

D-905: operator-only opt-in; NO cron wiring; weekly-run.sh unchanged.
D-816: brand-in-name invariant SOFTENED to log-only for Armani-style PDPs
       (brand name is data-redundancy in upstream goldapple catalog — not a
        parser bug). Hard assert only for STEREOTYPE-style (distinct brand+name).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from ga_crawler.parsers.goldapple_microdata import parse_pdp as parse_goldapple
from ga_crawler.parsers.viled_nextdata import parse_pdp as parse_viled

pytestmark = pytest.mark.live  # RESEARCH §5.1 — applies to ALL tests in module

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
_GA_FIXTURES = _FIXTURES / "goldapple"
_VL_FIXTURES = _FIXTURES / "viled"

# Phase 8 D-818 SMOKE_URLS (verbatim per runner/gates.py:34-36 rotation)
_URL_STEREOTYPE = "https://goldapple.kz/19000440474-stereotype-sago"
_URL_ARMANI = "https://goldapple.kz/19000195723-armani-code"
_URL_CONTRE_JOUR = "https://viled.kz/item/408872"


# ---- Goldapple STEREOTYPE drift test (Bug #1 retroactive lock) ----

async def test_goldapple_stereotype_drift(refresh_live: bool, html_snapshot) -> None:
    """STEREOTYPE / SAĜO PDP. Two-mode (D-906).

    Cassette-replay: asserts brand_raw non-empty, name non-empty,
    raw_volume_text non-empty (PARSE-FIX-01 lock), current_price > 0,
    and STEREOTYPE-specific invariant brand NOT in name (distinct brand+name shape).

    --refresh-live: re-fetches via Camoufox, normalizes HTML, syrupy-diffs.
    """
    fixture_path = _GA_FIXTURES / "_live-2026-05-13-stereotype.html"

    if refresh_live:
        from ga_crawler.fetchers.goldapple import GoldappleFetcher
        from tests._html_normalize import normalize_for_snapshot

        async with GoldappleFetcher(run_id=-1, headless=True) as fetcher:
            rec = await fetcher.fetch_one(fetcher._page, _URL_STEREOTYPE)
        normalized = normalize_for_snapshot(rec["html"])
        # Syrupy default: missing snapshot fails (T-09-SOUND).
        # `--snapshot-update` regenerates. RESEARCH §3.2.
        assert normalized == html_snapshot
        # Parse invariants still run against the frozen fixture after refresh:
        html = fixture_path.read_text("utf-8")
    else:
        html = fixture_path.read_text("utf-8")

    product = parse_goldapple(html, _URL_STEREOTYPE)
    assert product is not None, "STEREOTYPE PDP must parse non-None"
    assert product.brand_raw, "brand_raw must be non-empty (Phase 8 D-806 h1 .brand fix)"
    assert product.name, "name must be non-empty (Phase 8 D-806 h1 .name fix)"
    assert product.raw_volume_text, (
        "raw_volume_text must be non-empty (Phase 8 PARSE-FIX-01 selectolax 0.4 Lexbor fix)"
    )
    assert product.current_price > 0
    # STEREOTYPE-specific invariant: brand is distinct from name (not data-redundant).
    # Soft for Armani-style (D-816); hard for Stereotype-style.
    assert product.brand_raw.strip().lower() not in product.name.strip().lower(), (
        "Bug #1 lock — STEREOTYPE brand must NOT be substring of name. "
        "If this fails, the h1 .brand/.name selector split has regressed (PARSE-FIX-02)."
    )


# ---- Goldapple Armani Code drift test (Bug #2 retroactive lock; D-816 SOFTENED) ----

async def test_goldapple_armani_code_drift(refresh_live: bool, html_snapshot) -> None:
    """Armani Code PDP. Two-mode (D-906).

    Brand is a LEGITIMATE substring of name (upstream catalog data redundancy).
    D-816 + SKILL.md L40: brand-in-name invariant SOFTENED to log-only for
    Armani-style PDPs. No hard assert against substring here.

    Cassette-replay asserts: brand_raw non-empty, name non-empty,
    raw_volume_text non-empty (Armani 75 ml block present per SKILL), price > 0.
    """
    fixture_path = _GA_FIXTURES / "_live-2026-05-13-armani-code.html"

    if refresh_live:
        from ga_crawler.fetchers.goldapple import GoldappleFetcher
        from tests._html_normalize import normalize_for_snapshot

        async with GoldappleFetcher(run_id=-1, headless=True) as fetcher:
            rec = await fetcher.fetch_one(fetcher._page, _URL_ARMANI)
        normalized = normalize_for_snapshot(rec["html"])
        assert normalized == html_snapshot
        html = fixture_path.read_text("utf-8")
    else:
        html = fixture_path.read_text("utf-8")

    product = parse_goldapple(html, _URL_ARMANI)
    assert product is not None, "armani-code PDP must parse non-None"
    assert product.brand_raw, "brand_raw must be non-empty (Phase 8 D-806)"
    assert product.name, "name must be non-empty (Phase 8 D-806)"
    assert product.current_price > 0
    # raw_volume_text: Armani Code PDP has volume block per SKILL.md (75 мл)
    assert product.raw_volume_text, "raw_volume_text must be non-empty for Armani Code PDP"
    # NOTE: brand_raw.lower() IS expected to be a substring of name.lower() here —
    # this is the canonical Bug #2 case. D-816 SOFTENED the invariant to log-only.
    # We emit a warning instead of asserting to flag future changes in upstream data.
    if product.brand_raw.strip().lower() not in product.name.strip().lower():
        warnings.warn(
            f"Armani Code: brand '{product.brand_raw}' no longer substring of "
            f"name '{product.name}'. D-816 data-redundancy assumption may have "
            "changed in upstream goldapple catalog. Verify intentionality.",
            UserWarning,
            stacklevel=2,
        )


# ---- Viled Contre-Jour drift test (Bug #3 — legitimate-None volume_raw) ----

def test_viled_contre_jour_drift(refresh_live: bool, html_snapshot) -> None:
    """Frederic Malle Contre-Jour PDP. Two-mode (D-906).

    D-904 viled-relaxed evidence: `Размер` attribute legitimately absent
    => volume_raw=None. Parser MUST NOT raise on None (PARSE-FIX-03 lock).
    This test is sync because ViledFetcher is sync (curl_cffi).
    """
    fixture_path = _VL_FIXTURES / "_live-2026-05-13-contre-jour.html"

    if refresh_live:
        from ga_crawler.fetchers.viled import ViledFetcher
        from tests._html_normalize import normalize_for_snapshot

        rec = ViledFetcher().fetch_one(_URL_CONTRE_JOUR)
        normalized = normalize_for_snapshot(rec["html"])
        assert normalized == html_snapshot
        html = fixture_path.read_text("utf-8")
    else:
        html = fixture_path.read_text("utf-8")

    product = parse_viled(html, _URL_CONTRE_JOUR)
    assert product is not None, "Contre-Jour PDP must parse non-None"
    assert product.brand_raw, "brand_raw must be non-empty (PARSE-FIX-03)"
    assert product.name, "name must be non-empty (PARSE-FIX-03)"
    assert product.current_price > 0
    # volume_raw legitimately None per D-814/D-904 viled-relaxed.
    # No assertion against non-empty — just confirm parser does NOT raise.
    # (volume_raw may be None or str; both are valid for Contre-Jour)
