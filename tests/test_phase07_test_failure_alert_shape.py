"""Wave 0 / Plan 07-01 — source-lock canary on bin/test-failure-alert.sh (D-706).

RED-gate stub: fails until Plan 07-03 ships the orchestrator.
Covers SCHED-05 deliberate-failure procedure (D-706 5-step recipe).

Source: 07-CONTEXT.md D-706 (lines 48-55); 07-RESEARCH.md Example 4.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "bin" / "test-failure-alert.sh"


@pytest.fixture
def script_text() -> str:
    assert SCRIPT.exists(), f"{SCRIPT} must exist (D-706)"
    return SCRIPT.read_text(encoding="utf-8")


def test_script_shebang(script_text):
    first_line = script_text.splitlines()[0]
    assert first_line == "#!/usr/bin/env bash", (
        f"script shebang must be '#!/usr/bin/env bash' (project convention); got {first_line!r}"
    )


def test_script_step1_forced_sanity_n_fail(script_text):
    """D-706 step 1: bin/weekly-run.sh --viled-only --sanity-gate-n 999999"""
    assert "--viled-only" in script_text, "script missing --viled-only flag (D-706 step 1)"
    assert "--sanity-gate-n 999999" in script_text, (
        "script missing --sanity-gate-n 999999 (D-706 step 1)"
    )


def test_script_step3_deliver_run_invocation(script_text):
    """D-706 step 3: invoke deliver-run for ops alert"""
    assert "deliver-run --run-id" in script_text, (
        "script missing 'deliver-run --run-id' invocation (D-706 step 3)"
    )


def test_script_step4_checklist_ops_chat(script_text):
    """D-706 step 4: checklist item — Telegram ops chat verification"""
    assert "Telegram ops chat" in script_text, (
        "script missing 'Telegram ops chat' checklist line (D-706 step 4)"
    )


def test_script_step4_checklist_business_chat(script_text):
    assert "Telegram business chat" in script_text, (
        "script missing 'Telegram business chat' checklist line (D-706 step 4)"
    )


def test_script_step4_checklist_hc_dashboard(script_text):
    assert "Healthchecks.io dashboard" in script_text, (
        "script missing 'Healthchecks.io dashboard' checklist line (D-706 step 4)"
    )


def test_script_step4_expected_delivery_status(script_text):
    """Expected DB state after deliberate failure: delivered_ops_only enum (D-606)."""
    assert "delivered_ops_only" in script_text, (
        "script missing expected 'delivered_ops_only' check (D-706 step 4 / D-606)"
    )


def test_script_step4_expected_run_reason(script_text):
    """Expected DB state: reason captures the sanity gate trigger."""
    assert "sanity_gate_n_failed:120<999999" in script_text, (
        "script missing expected reason 'sanity_gate_n_failed:120<999999' (D-706 step 4)"
    )


def test_script_idempotent_no_cleanup(script_text):
    """D-706 step 5: NO cleanup at end — failed run stays in DB as evidence."""
    for forbidden in ("DELETE FROM runs", "rm -rf prices.db", "DROP TABLE"):
        assert forbidden not in script_text, (
            f"script contains cleanup command {forbidden!r} — violates D-706 step 5 (idempotent, no cleanup)"
        )
