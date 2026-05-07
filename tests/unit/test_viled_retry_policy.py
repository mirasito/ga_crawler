"""CRAWL-04 — tenacity retry policy on viled fetch.

Wave 3 / Plan 02-04 wraps `ViledFetcher.fetch_one` with
`@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(2, 30),
       retry=retry_if_exception_type((Timeout, ConnectionError, HTTPError, RequestException)))`.

CRITICAL — exception classes import from `curl_cffi.requests.exceptions`,
NOT `curl_cffi.requests.errors` (the latter is missing Timeout/ConnectionError).
See 02-WAVE0-PROBE.md A10 REVISED.

Source: 02-RESEARCH.md §Validation Architecture row 16; 02-WAVE0-PROBE.md A10.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
