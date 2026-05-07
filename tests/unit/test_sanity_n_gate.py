"""CRAWL-05 — final N-gate sanity check for viled run.

Wave 4 / Plan 02-05 implements `final_n_gate(viled_count, N)` (mirror Phase 3's
final_m_gate). Asserts:
  - viled_count >= N → run status='success'
  - viled_count < N → run status='failed', reason='sanity_gate_n_failed'
  - rows still persist (audit trail invariant per D-218)

Plus auto_suggest_threshold(history, factor=0.7, min_runs=4) shared helper —
either refactored from Phase 3's auto_suggest_m or parametrized per D-203.

Source: 02-RESEARCH.md §Validation Architecture row 20; 02-CONTEXT.md D-201..D-203.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 4 not implemented yet — Plan 02-05")


def test_placeholder():
    """Placeholder. Plan 02-05 flips this from skip to GREEN."""
    assert False, "implement in Plan 02-05"
