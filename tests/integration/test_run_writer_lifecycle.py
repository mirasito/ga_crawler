"""DATA-05 — full RunWriter lifecycle integration.

Wave 1 / Plan 02-02 end-to-end test: create a run row, atomic patch_stats with
both viled.* and goldapple.* keys (validates Pitfall 6 namespace coexistence),
read back via get_stats, mark fail with reason, assert row's status column
flips to 'failed'.

Source: 02-RESEARCH.md §Validation Architecture row 7.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
