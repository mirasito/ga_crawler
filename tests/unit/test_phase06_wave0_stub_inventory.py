"""Wave 0 / Plan 06-01 — Task 3 RED-gate test.

Asserts the 10 skip-marked stub test files exist with the expected docstring
+ pytest.mark.skip placeholder. Permanent canary: subsequent waves replace
each stub with real tests; the canary fails when a stub is forgotten.

Stub inventory + target plan per Task 3 of 06-01-PLAN.md:
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# (relative-path, target-plan-marker-in-docstring) pairs.
STUB_FILES = [
    ("tests/test_delivery_config.py", "Plan 06-02"),
    ("tests/test_telegram_client.py", "Plan 06-03"),
    ("tests/test_gate.py", "Plan 06-03"),
    ("tests/test_message_builder.py", "Plan 06-02"),
    ("tests/test_delivery_stats.py", "Plan 06-02"),
    ("tests/test_delivery_source_lock.py", "Plan 06-05"),
    ("tests/integration/test_delivery_run.py", "Plan 06-04"),
    ("tests/integration/test_cli_deliver.py", "Plan 06-04"),
    ("tests/integration/test_weekly_run_with_delivery.py", "Plan 06-05"),
    ("tests/unit/test_stats_namespace_five_way.py", "Plan 06-05"),
]


def test_all_ten_stub_files_exist():
    for rel, _ in STUB_FILES:
        path = REPO_ROOT / rel
        assert path.exists(), f"missing stub: {rel}"


def test_all_ten_stub_files_contain_skip_marker():
    for rel, _ in STUB_FILES:
        path = REPO_ROOT / rel
        content = path.read_text(encoding="utf-8")
        assert "pytest.mark.skip" in content, f"{rel} missing pytest.mark.skip marker"


def test_all_ten_stub_files_cite_target_plan_in_docstring():
    for rel, target_plan in STUB_FILES:
        path = REPO_ROOT / rel
        content = path.read_text(encoding="utf-8")
        # Docstring must name the plan that will populate this file (Behavior Test 4).
        first_500 = content[:500]
        assert target_plan in first_500, (
            f"{rel} docstring (first 500 chars) does not cite {target_plan}"
        )


def test_stub_count_is_exactly_ten():
    assert len(STUB_FILES) == 10
