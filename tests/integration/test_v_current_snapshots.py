"""DATA-03 + CRAWL-01 (provenance) — `v_current_snapshots` SQL view.

Wave 1 / Plan 02-02 creates the view per D-221:
    CREATE VIEW v_current_snapshots AS
    SELECT * FROM snapshots
    WHERE run_id = (SELECT MAX(run_id) FROM runs WHERE status = 'success');

Tests insert multi-run synthetic data and assert the view returns only the
latest-success run's rows. This view is the single source of truth for Phase 3
brand-pool derivation (`WHERE retailer='viled'`).

Source: 02-RESEARCH.md §Validation Architecture row 6; 02-CONTEXT.md D-221.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 1 not implemented yet — Plan 02-02")


def test_placeholder():
    """Placeholder. Plan 02-02 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-02"
