"""PARSE-FIX-05 SMOKE_URLs rotation canary (D-818).

After Phase 8, SMOKE_URLS must rotate to 1-URL-per-shape-variant to catch
single-shape-blindness that masked run #13 parser drift. Specific URLs are
sourced from W0 spike shape-table.md (Plan 08-01 output):
  - STEREOTYPE-style: 19000440474-stereotype-sago
  - Armani-style:     19000195723-armani-code
  - Givenchy baseline (retained per D-818): 19000488678-givenchy-irresistible

Source: 08-CONTEXT.md D-818; 08-PATTERNS.md lines 822-843; 08-01-SUMMARY.md.
"""

from __future__ import annotations

from ga_crawler.enumeration.goldapple_sitemap import PRODUCT_URL_RE
from ga_crawler.runner.gates import SMOKE_URLS


def test_smoke_urls_length_three() -> None:
    assert isinstance(SMOKE_URLS, tuple)
    assert len(SMOKE_URLS) == 3


def test_smoke_urls_all_whitelist_regex_match() -> None:
    for url in SMOKE_URLS:
        assert PRODUCT_URL_RE.match(url) is not None, (
            f"smoke URL {url!r} fails whitelist regex"
        )


def test_smoke_urls_givenchy_baseline_retained() -> None:
    """Givenchy-baseline `19000488678-givenchy-irresistible` is the known-good
    anchor (rotation 2026-05-11). Phase 8 keeps it as one of the 3 slots (D-818)."""
    assert any("19000488678-givenchy-irresistible" in u for u in SMOKE_URLS), (
        "Givenchy baseline `19000488678-givenchy-irresistible` is required to "
        "remain in SMOKE_URLS per D-818."
    )


def test_smoke_urls_have_shape_variety() -> None:
    """Distinct slugs — protects against accidental triple-copy of any baseline."""
    slugs = [u.rsplit("/", 1)[-1] for u in SMOKE_URLS]
    assert len(set(slugs)) == 3, (
        f"SMOKE_URLS must have 3 distinct slugs; got {slugs}"
    )
