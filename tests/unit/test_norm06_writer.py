"""NORM-06 — `Norm06Writer.persist(run_id, viled_unmatched, goldapple_new_slugs)`.

Wave 1 / Plan 02-02 ships the writer that renders
`.planning/runs/{run_id}/norm06-review.md` per D-208 schema (markdown table
with brand_or_slug / source / run_id / status columns; default status=pending).

Source: 02-RESEARCH.md §Validation Architecture row 4; 02-CONTEXT.md D-208 D-211.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
