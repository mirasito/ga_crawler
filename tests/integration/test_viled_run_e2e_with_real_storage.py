"""End-to-end viled run: enumerate → fetch → parse → normalize → persist → gate.

Wave 4 / Plan 02-05 wires `runners/viled_run.py` and exercises the full pipeline
against a real on-disk SQLite (tmp_path) + the canonical viled fixtures
(viled_catalog_html, viled_pdp_html, viled_pdp_discounted_html). HTTP layer
mocked via wrapper-monkeypatch (NOT respx).

Asserts:
  - snapshots row count == catalog enumerator output
  - was_price set on discounted SKU, NULL on canonical SKU
  - runs.status='success' when count >= N (N=2 for this micro-corpus)
  - runs.stats has viled.* namespace keys atomically merged
  - v_current_snapshots view returns these rows after run completes

Source: 02-RESEARCH.md §Validation Architecture row 22.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 4 not implemented yet — Plan 02-05")


def test_placeholder():
    """Placeholder. Plan 02-05 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-05"
