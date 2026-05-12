"""Plan 06-03 (Wave 2) — unit tests for delivery/gate.py::evaluate_gate.

Tests use synthetic_delivered_run fixture (Plan 06-01) as the gate-pass
base, then mutate one field per test to trigger each of the 4 fail paths.
Short-circuit ordering verified via spy on run_writer.get_stats.

Per D-604 4-check first-fail-wins composition:
  1. runs.status == 'success' (REUSE matcher.strict_key.read_run_status)
  2. report.xlsx_path non-empty
  3. report.size_guard_passed == True
  4. report.summary_text non-empty (after strip)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from ga_crawler.delivery.gate import GateDecision, evaluate_gate


def test_gate_decision_is_frozen_dataclass():
    """GateDecision must be a frozen dataclass with 3 named fields."""
    import dataclasses

    d = GateDecision(route="business", gate_failed_check=None, gate_failure_reason=None)
    fields = {f.name for f in dataclasses.fields(GateDecision)}
    assert fields == {"route", "gate_failed_check", "gate_failure_reason"}
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.route = "ops_only"  # type: ignore[misc]


def test_gate_pass_happy_path(synthetic_delivered_run):
    """All 4 checks pass → route=business + None None."""
    engine, run_writer, run_id, _ = synthetic_delivered_run
    # synthetic_report_run already finalized as 'success', no need to re-update.
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.route == "business"
    assert result.gate_failed_check is None
    assert result.gate_failure_reason is None


def test_gate_fails_on_run_status_failed(synthetic_delivered_run):
    """Check #1 fail: runs.status='failed' → upstream_status_failed."""
    engine, run_writer, run_id, _ = synthetic_delivered_run
    run_writer.fail(run_id, "deliberate test failure")
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.route == "ops_only"
    assert result.gate_failed_check == "run_status"
    assert result.gate_failure_reason == "upstream_status_failed"


def test_gate_fails_on_missing_run_row(synthetic_delivered_run):
    """Check #1 fail: run row absent (read_run_status returns None) → upstream_status_None.

    We probe a run_id that does not exist (synthetic fixture used run_id=1; we
    ask the gate about run_id=99999). DELETE of the seeded row would cascade-fail
    against snapshots/matches FK — using a never-created id is cleaner and
    exactly matches the production scenario the canary cares about.
    """
    engine, run_writer, _run_id, _ = synthetic_delivered_run
    nonexistent_run_id = 99999
    result = evaluate_gate(engine, run_writer, nonexistent_run_id)
    assert result.route == "ops_only"
    assert result.gate_failed_check == "run_status"
    assert result.gate_failure_reason == "upstream_status_None"


def test_gate_fails_on_empty_xlsx_path(synthetic_delivered_run):
    """Check #2 fail: report.xlsx_path empty string → no_xlsx_in_stats."""
    engine, run_writer, run_id, _ = synthetic_delivered_run
    run_writer.patch_stats(run_id, {"report.xlsx_path": ""})
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.route == "ops_only"
    assert result.gate_failed_check == "xlsx_path"
    assert result.gate_failure_reason == "no_xlsx_in_stats"


def test_gate_fails_on_size_guard_failed(synthetic_delivered_run):
    """Check #3 fail: report.size_guard_passed=False → xlsx_oversize."""
    engine, run_writer, run_id, _ = synthetic_delivered_run
    run_writer.patch_stats(run_id, {"report.size_guard_passed": False})
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.route == "ops_only"
    assert result.gate_failed_check == "size_guard"
    assert result.gate_failure_reason == "xlsx_oversize"


def test_gate_fails_on_empty_summary(synthetic_delivered_run):
    """Check #4 fail: report.summary_text empty → empty_summary_text."""
    engine, run_writer, run_id, _ = synthetic_delivered_run
    run_writer.patch_stats(run_id, {"report.summary_text": ""})
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.route == "ops_only"
    assert result.gate_failed_check == "summary_text"
    assert result.gate_failure_reason == "empty_summary_text"


def test_gate_fails_on_whitespace_only_summary(synthetic_delivered_run):
    """Check #4 fail: report.summary_text whitespace-only → empty_summary_text (uses .strip())."""
    engine, run_writer, run_id, _ = synthetic_delivered_run
    run_writer.patch_stats(run_id, {"report.summary_text": "   \n  \t  "})
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.route == "ops_only"
    assert result.gate_failed_check == "summary_text"
    assert result.gate_failure_reason == "empty_summary_text"


def test_gate_short_circuits_on_first_fail(synthetic_delivered_run, mocker):
    """Short-circuit: when check #1 fails, run_writer.get_stats MUST NOT be called.

    Also pre-mutates size_guard_passed so that checks #3 would ALSO fail —
    proves that check #1's failure short-circuits before check #2/3/4 evaluate.
    """
    engine, run_writer, run_id, _ = synthetic_delivered_run
    # Plant a second failure that should be invisible if check #1 short-circuits.
    run_writer.patch_stats(run_id, {"report.size_guard_passed": False})
    run_writer.fail(run_id, "fail upstream")
    spy = mocker.spy(run_writer, "get_stats")
    result = evaluate_gate(engine, run_writer, run_id)
    assert result.gate_failed_check == "run_status"
    assert result.gate_failure_reason == "upstream_status_failed"
    assert spy.call_count == 0, (
        "Short-circuit violated: get_stats was called even though check #1 failed"
    )


def test_read_run_status_imported_from_matcher():
    """Structural canary: REUSE not re-implementation (D-604 step 1).

    The gate.py source MUST import read_run_status from matcher.strict_key
    (mirrors reporter_run.py D-507 reuse) — no second copy of the SQL.
    """
    repo_root = Path(__file__).resolve().parents[1]
    src = (repo_root / "src" / "ga_crawler" / "delivery" / "gate.py").read_text(
        encoding="utf-8"
    )
    assert "from ga_crawler.matcher.strict_key import read_run_status" in src, (
        "gate.py must REUSE matcher.strict_key.read_run_status, not re-implement"
    )
