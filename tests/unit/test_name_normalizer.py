"""NORM-05 — product-name normalizer (lowercase + punctuation strip + collapse spaces).

Wave 2 / Plan 02-03 implements `src/ga_crawler/normalizers/name.py`. Each
input: lowercase → strip punctuation (.,!?'"«»()) → collapse whitespace →
NFKD accent-strip → result is the joinable token for the strict
(brand_norm, name_norm, volume_norm) match key.

Source: 02-RESEARCH.md §Validation Architecture row 11.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 2 not implemented yet — Plan 02-03")


def test_placeholder():
    """Placeholder. Plan 02-03 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-03"
