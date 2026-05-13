"""PARSE-FIX-04 parser-drift null-rate gate tests.

Pure-function unit tests for `parser_drift_null_rate_gate`. Mirrors shape of
tests/unit/test_parse_quality_gate.py — same boundary + threshold style. The
new gate adds 2-input semantics + frozen-dataclass return value + priority
ordering on dual-failure (D-815 volume-wins-over-brand).

Source: 08-CONTEXT.md D-813/D-814/D-815/D-817; 08-PATTERNS.md lines 614-678.
"""

from __future__ import annotations

import pytest

from ga_crawler.runner.gates import (
    ParserDriftGateResult,
    parser_drift_null_rate_gate,
)


def test_both_rates_below_threshold_passes() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.1, brand_null_rate=0.05)
    assert r.passed
    assert r.failure_reason is None
    assert r.volume_null_rate == 0.1
    assert r.brand_null_rate == 0.05


def test_exactly_at_threshold_passes() -> None:
    """D-815: STRICT > threshold — exactly 0.5 PASSES."""
    r = parser_drift_null_rate_gate(volume_null_rate=0.5, brand_null_rate=0.5)
    assert r.passed
    assert r.failure_reason is None


def test_volume_exceeds_threshold_fails() -> None:
    """Synthetic regression (Success Criteria #5): 60% null volume."""
    r = parser_drift_null_rate_gate(volume_null_rate=0.6, brand_null_rate=0.0)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"
    assert r.volume_null_rate == 0.6


def test_brand_exceeds_threshold_fails() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.0, brand_null_rate=0.7)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_brand_rate"
    assert r.brand_null_rate == 0.7


def test_both_exceed_volume_wins_priority() -> None:
    """D-815 priority: volume_null_rate wins when both exceed."""
    r = parser_drift_null_rate_gate(volume_null_rate=0.8, brand_null_rate=0.7)
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"


def test_custom_threshold() -> None:
    r = parser_drift_null_rate_gate(
        volume_null_rate=0.3,
        brand_null_rate=0.0,
        threshold=0.2,
    )
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_volume_rate"


def test_zero_rates_passes() -> None:
    r = parser_drift_null_rate_gate(volume_null_rate=0.0, brand_null_rate=0.0)
    assert r.passed
    assert r.failure_reason is None


def test_result_is_frozen_dataclass() -> None:
    r = parser_drift_null_rate_gate(0.0, 0.0)
    assert isinstance(r, ParserDriftGateResult)
    with pytest.raises(Exception):
        r.passed = False  # type: ignore[misc]  # frozen


def test_brand_custom_threshold_fails_with_brand_reason() -> None:
    """Custom threshold + only brand exceeds → brand reason (defensive boundary)."""
    r = parser_drift_null_rate_gate(
        volume_null_rate=0.1,
        brand_null_rate=0.3,
        threshold=0.2,
    )
    assert not r.passed
    assert r.failure_reason == "parser_drift_null_brand_rate"
