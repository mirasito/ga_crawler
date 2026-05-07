"""CRAWL-03 — per-SKU exception isolation in `ViledFetcher`.

Wave 3 / Plan 02-04 implements `src/ga_crawler/fetchers/viled.py::ViledFetcher`
(curl_cffi sync; mirrors Phase 3 GoldappleFetcher per-SKU isolation invariant).

Asserts: an exception during fetch of SKU N does NOT abort the run-loop;
the fetcher records (sku, exception) in a per-run failure log and proceeds
to SKU N+1. Mirrors Phase 3 D-303 + RESEARCH §Pattern 3.

Source: 02-RESEARCH.md §Validation Architecture row 15.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
