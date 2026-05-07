"""CRAWL-06 — viled rate-limit (2.0 s sequential pause between fetches).

Wave 3 / Plan 02-04 — `ViledFetcher` invokes `time.sleep(pause_seconds)` between
each fetch. pause_seconds is read from
`pyproject.toml [tool.ga_crawler.crawl.viled].pause_seconds = 2.0` (D-225,
verified WAVE0-PROBE 8/8 success).

Asserts: monkey-patch `time.sleep` to record call args, run a 3-SKU loop,
assert sleep called 2 times (between SKU 1→2, 2→3) with 2.0 s arg.

Source: 02-RESEARCH.md §Validation Architecture row 17; 02-CONTEXT.md D-225.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 3 not implemented yet — Plan 02-04")


def test_placeholder():
    """Placeholder. Plan 02-04 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-04"
