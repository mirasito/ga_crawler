"""TH-06d — schema_rejected_rate_gate threshold semantics + SCHEMA_STATS_KEYS.

Mirrors tests/runner/test_parser_drift_gate.py shape (Phase 8 D-815 helper).
STRICT > convention: exactly threshold passes; anything above fails.
"""

from __future__ import annotations

import pytest

from ga_crawler.runner import gates as gates_mod
from ga_crawler.runner import stats as stats_mod
from ga_crawler.runner.gates import (
    SchemaRejectedGateResult,
    schema_rejected_rate_gate,
)


def test_below_threshold_passes() -> None:
    r = schema_rejected_rate_gate(rejected_count=4, total_attempted=100)
    assert r.passed is True
    assert r.failure_reason is None
    assert r.rejected_rate == pytest.approx(0.04)
    assert r.rejected_count == 4
    assert r.total_attempted == 100


def test_exactly_at_threshold_passes() -> None:
    """STRICT > 0.05 — exactly 5% PASSES (mirror parser_drift_null_rate_gate D-815)."""
    r = schema_rejected_rate_gate(rejected_count=5, total_attempted=100)
    assert r.passed is True
    assert r.failure_reason is None


def test_just_above_threshold_fails() -> None:
    """0.0501 (6/100 = 0.06) fails."""
    r = schema_rejected_rate_gate(rejected_count=6, total_attempted=100)
    assert r.passed is False
    assert r.failure_reason == "schema_validation_rejected_rate"
    assert r.rejected_rate == pytest.approx(0.06)


def test_zero_total_attempted_passes() -> None:
    """Empty-input safety: rate undefined -> pass cleanly (matches gate skeleton §6.3)."""
    r = schema_rejected_rate_gate(rejected_count=0, total_attempted=0)
    assert r.passed is True
    assert r.rejected_rate == 0.0
    assert r.failure_reason is None


def test_custom_threshold_fails() -> None:
    r = schema_rejected_rate_gate(rejected_count=3, total_attempted=10, threshold=0.2)
    assert r.passed is False
    assert r.failure_reason == "schema_validation_rejected_rate"


def test_custom_threshold_passes_at_boundary() -> None:
    r = schema_rejected_rate_gate(rejected_count=2, total_attempted=10, threshold=0.2)
    assert r.passed is True


def test_result_is_frozen_dataclass() -> None:
    r = schema_rejected_rate_gate(0, 100)
    assert isinstance(r, SchemaRejectedGateResult)
    with pytest.raises(Exception):
        r.passed = False  # type: ignore[misc]


def test_gate_in_all_export() -> None:
    assert "schema_rejected_rate_gate" in gates_mod.__all__
    assert "SchemaRejectedGateResult" in gates_mod.__all__


def test_schema_stats_keys_namespace() -> None:
    assert hasattr(stats_mod, "SCHEMA_STATS_KEYS")
    assert "SCHEMA_STATS_KEYS" in stats_mod.__all__
    keys = stats_mod.SCHEMA_STATS_KEYS
    assert "schema.rejected_count" in keys
    assert "schema.rejected_rate" in keys
    assert "schema.rejected_reasons" in keys
    # All keys must carry the schema. namespace prefix (run-level not retailer)
    for k in keys:
        assert k.startswith("schema."), f"key {k!r} not in schema.* namespace"
