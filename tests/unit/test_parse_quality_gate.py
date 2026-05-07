"""PARSE-05 + D-218 aggregate parse-quality gate.

Wave 4 / Plan 02-05 implements `parse_quality_gate(null_rate, threshold=0.05)`:
  null_rate = count(rows where name OR current_price OR url is NULL) / total
  if null_rate > 0.05: run.status='failed' reason='parse_quality_below_threshold'

Gate fires AFTER snapshot persistence (audit trail invariant — rows persist
regardless of gate outcome) and BEFORE sanity_n_gate (D-218 sequential).
Both gates can fail same run independently; orchestrator returns the
first-encountered reason.

Source: 02-RESEARCH.md §Validation Architecture row 21; 02-CONTEXT.md D-218.
"""

from ga_crawler.runner.gates import parse_quality_gate


def test_low_null_rate_passes():
    """3% null rate (e.g. 3/100) → gate PASSES."""
    assert parse_quality_gate(0.03) is True


def test_high_null_rate_fails():
    """8% null rate → gate FAILS."""
    assert parse_quality_gate(0.08) is False


def test_threshold_boundary():
    """≤ semantics — exactly 5% passes; 5.01% fails."""
    assert parse_quality_gate(0.05) is True
    assert parse_quality_gate(0.0501) is False


def test_zero_null_rate_passes():
    """Pristine data (0% nulls) — always passes."""
    assert parse_quality_gate(0.0) is True


def test_one_hundred_percent_null_fails():
    """100% nulls — pathological; obviously fails."""
    assert parse_quality_gate(1.0) is False


def test_custom_threshold():
    """Threshold overridable for ops-tunable strictness."""
    assert parse_quality_gate(0.10, threshold=0.10) is True
    assert parse_quality_gate(0.11, threshold=0.10) is False


def test_zero_rows_passes():
    """Documented behavior: caller passes 0.0 when total=0 (no data → no failure).

    The orchestrator computes null_rate = 0.0 when records list is empty so
    the gate trivially passes; the sanity-N gate downstream catches "no data".
    """
    assert parse_quality_gate(0.0) is True
