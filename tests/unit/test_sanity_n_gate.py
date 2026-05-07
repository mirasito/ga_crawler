"""CRAWL-05 + D-201 verification — `final_threshold_gate` boundary tests.

Wave 4 / Plan 02-05 introduces the retailer-agnostic
`final_threshold_gate(count, threshold)` helper. Asserts the >= semantics
that the orchestrator depends on for both the viled-side N-gate (D-201)
and (via shim) the goldapple-side M-gate.

Audit-trail invariant (gate fails → snapshot rows still persist) is verified
in tests/integration/test_viled_run_e2e_with_real_storage.py.

Source: 02-RESEARCH.md §Validation Architecture row 20; 02-CONTEXT.md D-201..D-203.
"""

import pytest

from ga_crawler.runner.gates import final_threshold_gate


def test_above_threshold_passes():
    assert final_threshold_gate(150, 100) is True


def test_below_threshold_fails():
    assert final_threshold_gate(50, 100) is False


def test_equal_threshold_passes():
    """>= semantics — exactly threshold passes."""
    assert final_threshold_gate(100, 100) is True


def test_zero_count_below_any_positive_threshold():
    assert final_threshold_gate(0, 100) is False
    assert final_threshold_gate(0, 1) is False


def test_zero_threshold_always_passes():
    """Edge case: threshold=0 means any non-negative count passes."""
    assert final_threshold_gate(0, 0) is True
    assert final_threshold_gate(1, 0) is True


@pytest.mark.parametrize(
    "count, threshold, expected",
    [
        (0, 100, False),
        (99, 100, False),
        (100, 100, True),
        (101, 100, True),
        (5000, 100, True),
        # D-201 viled seed
        (120, 100, True),
        (150, 100, True),
    ],
)
def test_boundaries(count, threshold, expected):
    assert final_threshold_gate(count, threshold) is expected
