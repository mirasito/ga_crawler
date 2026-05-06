"""Final M-gate (D-308/D-309) + auto-suggest M (D-310) boundary tests."""

from __future__ import annotations

import statistics

import pytest

from ga_crawler.runner.gates import auto_suggest_m, final_m_gate


# ---- final_m_gate boundary tests ----

@pytest.mark.parametrize("count, M, expected", [
    (0, 1000, False),
    (999, 1000, False),       # boundary: 999 < M
    (1000, 1000, True),       # boundary inclusive: count >= M
    (1001, 1000, True),
    (5000, 1000, True),
    (1, 1, True),             # M=1 trivial pass
    (0, 1, False),
])
def test_final_m_gate_boundaries(count: int, M: int, expected: bool) -> None:
    assert final_m_gate(count, M) is expected


def test_final_m_gate_default_M_1000() -> None:
    """Default M=1000 per D-308."""
    assert final_m_gate(999) is False
    assert final_m_gate(1000) is True


# ---- auto_suggest_m tests ----

def test_auto_suggest_empty_history_returns_none() -> None:
    assert auto_suggest_m([]) is None


@pytest.mark.parametrize("hist", [[100], [100, 200], [100, 200, 300]])
def test_auto_suggest_under_4_runs_returns_none(hist: list[int]) -> None:
    """D-310: needs 4+ runs of history before suggesting."""
    assert auto_suggest_m(hist) is None


def test_auto_suggest_exactly_4_runs() -> None:
    """median([1000, 2000, 3000, 4000]) = 2500; 0.7 × 2500 = 1750."""
    assert auto_suggest_m([1000, 2000, 3000, 4000]) == 1750


def test_auto_suggest_uses_last_4_only() -> None:
    """Older runs ignored; only last 4 matter.

    NOTE: 0.7 cannot be exactly represented in IEEE 754 binary float, so
    `0.7 * 2700.0 == 1889.9999999999998`, which `int()` truncates to 1889
    (NOT 1890 as the plan optimistically suggested). This is the documented
    behavior of `int(0.7 * median)` per D-310 — operator gets a value that
    is a hair below the "exact" 0.7 multiplication. Acceptable: this is a
    suggestion, not auto-tune (D-310 contra), so 1-unit drift is irrelevant.
    """
    # Last 4: [300, 400, 5000, 6000]; median = (400+5000)/2 = 2700.0
    # int(0.7 * 2700.0) = int(1889.9999999999998) = 1889 (IEEE 754 truncation)
    assert auto_suggest_m([100, 200, 300, 400, 5000, 6000]) == 1889


def test_auto_suggest_even_length_median() -> None:
    """Even-length window: median is mean of two middle. [3000, 3000, 4000, 4000] → 3500 → 0.7×3500 = 2450."""
    assert auto_suggest_m([3000, 3000, 4000, 4000]) == 2450


def test_auto_suggest_int_truncates() -> None:
    """0.7 × 1234.5 = 864.15 → int() truncates to 864."""
    # median([1234, 1235, 1234, 1235]) = (1234+1235)/2 = 1234.5; 0.7×1234.5 = 864.15
    assert auto_suggest_m([1234, 1235, 1234, 1235]) == 864


def test_auto_suggest_returns_int() -> None:
    """Return type is int (not float; not None when 4+ runs)."""
    result = auto_suggest_m([1000, 2000, 3000, 4000])
    assert isinstance(result, int)


def test_auto_suggest_formula_documented() -> None:
    """Cross-check formula matches D-310 spec: 0.7 × 4-week-median."""
    history = [1500, 1600, 1700, 1800]
    expected = int(0.7 * statistics.median(history))
    assert auto_suggest_m(history) == expected
