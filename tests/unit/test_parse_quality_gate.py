"""PARSE-05 — parse-quality gate (>5% null required-field ⇒ run fails).

Wave 4 / Plan 02-05 implements:
    null_rate = count(rows where name OR current_price OR url is NULL) / total
    if null_rate > 0.05: run.status='failed' reason='parse_quality_below_threshold'

Gate fires AFTER snapshot persistence (audit trail invariant) and BEFORE
sanity_n_gate (D-218). Both gates can fail same run independently.

Source: 02-RESEARCH.md §Validation Architecture row 21; 02-CONTEXT.md D-218.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 4 not implemented yet — Plan 02-05")


def test_placeholder():
    """Placeholder. Plan 02-05 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-05"
