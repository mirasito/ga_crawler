"""Wave 0 / Plan 06-01 — Task 3 RED-gate test.

Asserts the remaining skip-marked stub test files still exist with the
expected ``pytest.mark.skip`` placeholder + docstring naming the plan
that will replace them. Permanent canary: subsequent waves replace each
stub with real tests; the canary fails when a stub is forgotten.

Wave-1 (Plan 06-02) replaced 4 of the original 10 stubs with real tests
(``test_delivery_config.py``, ``test_message_builder.py``,
``test_delivery_stats.py``, ``tests/unit/test_stats_namespace_five_way.py``).
Wave-2 (Plan 06-03) replaces 2 more (``test_gate.py``,
``test_telegram_client.py``). The remaining 4 still belong to
Plans 06-04 / 06-05 and continue to require this canary until they
are turned GREEN. The total-count assertion below tracks the originally
planned 10 stubs minus those already populated.

Stub inventory + target plan per Task 3 of 06-01-PLAN.md (minus
Wave-1 + Wave-2 closures):
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Remaining (relative-path, target-plan-marker-in-docstring) pairs.
# Wave-1 closures (no longer stubs):
#   - tests/test_delivery_config.py            → Plan 06-02 GREEN
#   - tests/test_message_builder.py            → Plan 06-02 GREEN
#   - tests/test_delivery_stats.py             → Plan 06-02 GREEN
#   - tests/unit/test_stats_namespace_five_way.py → Plan 06-02 GREEN
# Wave-2 closures (no longer stubs):
#   - tests/test_gate.py                       → Plan 06-03 GREEN (Task 1)
#   - tests/test_telegram_client.py            → Plan 06-03 GREEN (Task 2)
STUB_FILES = [
    ("tests/test_telegram_client.py", "Plan 06-03"),
    ("tests/test_delivery_source_lock.py", "Plan 06-05"),
    ("tests/integration/test_delivery_run.py", "Plan 06-04"),
    ("tests/integration/test_cli_deliver.py", "Plan 06-04"),
    ("tests/integration/test_weekly_run_with_delivery.py", "Plan 06-05"),
]

# Wave-1 + Wave-2 stub closures — these files must NOT contain
# pytest.mark.skip any more; the canary below pins that.
WAVE1_CLOSURES = [
    "tests/test_delivery_config.py",
    "tests/test_message_builder.py",
    "tests/test_delivery_stats.py",
    "tests/unit/test_stats_namespace_five_way.py",
]

# Wave-2 closures are added incrementally: Task 1 adds test_gate.py;
# Task 2 (next commit) appends test_telegram_client.py.
WAVE2_CLOSURES = [
    "tests/test_gate.py",
]


def test_all_remaining_stub_files_exist():
    for rel, _ in STUB_FILES:
        path = REPO_ROOT / rel
        assert path.exists(), f"missing stub: {rel}"


def test_all_remaining_stub_files_contain_skip_marker():
    for rel, _ in STUB_FILES:
        path = REPO_ROOT / rel
        content = path.read_text(encoding="utf-8")
        assert "pytest.mark.skip" in content, f"{rel} missing pytest.mark.skip marker"


def test_all_remaining_stub_files_cite_target_plan_in_docstring():
    for rel, target_plan in STUB_FILES:
        path = REPO_ROOT / rel
        content = path.read_text(encoding="utf-8")
        # Docstring must name the plan that will populate this file (Behavior Test 4).
        first_500 = content[:500]
        assert target_plan in first_500, (
            f"{rel} docstring (first 500 chars) does not cite {target_plan}"
        )


def test_remaining_stub_count_after_wave2_task1():
    """Wave-0 planned 10 stubs; Wave-1 closed 4 + Wave-2 Task 1 closed 1 →
    5 remain (Plan 06-03 Task 2 closes one more)."""
    assert len(STUB_FILES) == 5


def test_wave1_closures_no_longer_have_skip_marker():
    """Regression: files closed by Plan 06-02 must have no ``pytest.mark.skip``."""
    for rel in WAVE1_CLOSURES:
        path = REPO_ROOT / rel
        content = path.read_text(encoding="utf-8")
        assert "pytest.mark.skip" not in content, (
            f"{rel} should be GREEN after Plan 06-02 but still contains "
            f"a pytest.mark.skip marker"
        )


def test_wave2_closures_no_longer_have_skip_marker():
    """Regression: files closed by Plan 06-03 must have no ``pytest.mark.skip``."""
    for rel in WAVE2_CLOSURES:
        path = REPO_ROOT / rel
        content = path.read_text(encoding="utf-8")
        assert "pytest.mark.skip" not in content, (
            f"{rel} should be GREEN after Plan 06-03 but still contains "
            f"a pytest.mark.skip marker"
        )
