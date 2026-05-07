"""D-203 retailer-agnostic auto-suggest verification.

Plan 02-05 refactors `runner/gates.py`:
  - NEW: `auto_suggest_threshold(history, factor=0.7, min_runs=4)` — generic
  - NEW: `final_threshold_gate(count, threshold)` — generic
  - SHIMS: `auto_suggest_m`, `final_m_gate`, `final_n_gate` — forward to new helpers

These tests ensure (a) the new helpers behave correctly and (b) Phase 3
backward-compat shims still work so callers in `runners/goldapple_run.py`
don't break.

Source: 02-CONTEXT.md D-203; 02-RESEARCH.md §"auto_suggest_threshold refactor".
"""

from ga_crawler.runner.gates import (
    auto_suggest_m,
    auto_suggest_threshold,
    final_m_gate,
    final_n_gate,
)


def test_returns_int_factor_median():
    # median([100,200,300,400]) = 250; int(0.7 * 250) = 175
    assert auto_suggest_threshold([100, 200, 300, 400], 0.7, 4) == 175


def test_min_runs_guard():
    """<min_runs of history → returns None (no suggestion yet)."""
    assert auto_suggest_threshold([100, 200, 300], 0.7, 4) is None


def test_only_last_min_runs_used():
    """First entry should NOT skew the median."""
    result = auto_suggest_threshold([99999, 100, 200, 300, 400], 0.7, 4)
    # median of last 4 = 250; int(0.7 * 250) = 175
    assert result == 175


def test_backward_compat_auto_suggest_m():
    """Phase 3 shim: auto_suggest_m == auto_suggest_threshold(h, 0.7, 4)."""
    history = [1000, 1000, 1000, 1000]
    assert auto_suggest_m(history) == auto_suggest_threshold(history, 0.7, 4)


def test_backward_compat_final_m_gate():
    """Phase 3 shim: final_m_gate semantics unchanged after refactor."""
    assert final_m_gate(1500, 1000) is True
    assert final_m_gate(500, 1000) is False
    # Default M=1000
    assert final_m_gate(1000) is True
    assert final_m_gate(999) is False


def test_final_n_gate_seed():
    """D-201 N=100 seed; final_n_gate is the viled-side shim."""
    assert final_n_gate(150, 100) is True
    assert final_n_gate(99, 100) is False
    assert final_n_gate(100, 100) is True  # >= semantics


def test_custom_factor():
    """factor parameter overridable (config-driven; D-203)."""
    # median([100,200,300,400])=250; 0.5*250 = 125
    assert auto_suggest_threshold([100, 200, 300, 400], factor=0.5) == 125


def test_custom_min_runs():
    """min_runs overridable (e.g. min_runs=2 lets early-week suggest)."""
    # median([100,200])=150; 0.7*150 = 105
    assert auto_suggest_threshold([100, 200], factor=0.7, min_runs=2) == 105
    # <2 history → still None
    assert auto_suggest_threshold([100], factor=0.7, min_runs=2) is None
