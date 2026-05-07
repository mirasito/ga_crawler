"""CRAWL-01 — viled catalog page enumerator (pagination over /catalog/1310).

Wave 3 / Plan 02-04 implements `src/ga_crawler/enumeration/viled_sitemap.py`
(name retained for interface symmetry with goldapple_sitemap.py — actual
mechanism is catalog-page enumeration per D-223).

Reads `viled_catalog_html` fixture, asserts pageProps.items.{content,
totalPages, total, pageSize, pageNumber} extraction (per 02-WAVE0-PROBE.md A4
REVISED — keys live under `pageProps.items`, NOT `pageProps.products`).
Asserts product URL list construction via `f"https://viled.kz/item/{r['id']}"`.

Source: 02-RESEARCH.md §Validation Architecture row 14 + Pattern 2 (REVISED);
02-CONTEXT.md D-224.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
