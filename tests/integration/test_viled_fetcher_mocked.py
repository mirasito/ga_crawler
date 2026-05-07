"""CRAWL-01, CRAWL-04 — full ViledFetcher run-loop with mocked HTTP layer.

Wave 3 / Plan 02-04 — integration: a fake `_fetch_html` wrapper (NOT respx;
respx is incompatible with curl_cffi per Phase 3 D-302) returns canned bytes
for a list of catalog URLs. Asserts:
  - rate-limit honored (2 s pauses)
  - retry policy fires on injected transient failures
  - per-SKU isolation (one URL fails, others continue)
  - product list returned in input order

Source: 02-RESEARCH.md §Validation Architecture row 19 + Pitfall 1.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
