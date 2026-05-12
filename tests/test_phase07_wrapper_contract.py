"""Wave 0 / Plan 07-01 — source-lock canary on bin/weekly-run.sh (D-709 contract).

RED-gate stub: fails until Plan 07-03 ships the wrapper.
Covers SCHED-03 (HC pings + flock + fail-loud HC_PING_URL) and SCHED-04 (log redirect).

Threat refs: T-07-02 (flock mitigation), T-07-04 (no UUID hardcoded), T-07-01 (cron MAILTO leak — wrapper redirect mitigation).

Source: 07-CONTEXT.md D-709 (lines 92-131); 07-RESEARCH.md Pattern 1 + Pitfall #3.
Shebang reconciled to '#!/usr/bin/env bash' per project convention (bin/backup.sh:1) —
D-709 verbatim uses '#!/bin/bash' but planner reconciles to project standard.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "bin" / "weekly-run.sh"


@pytest.fixture
def wrapper_text() -> str:
    assert WRAPPER.exists(), f"{WRAPPER} must exist (D-709)"
    return WRAPPER.read_text(encoding="utf-8")


# --- Convention header (matches bin/backup.sh) ----------------------

def test_wrapper_shebang_is_env_bash(wrapper_text):
    """Project convention: bin/backup.sh uses '#!/usr/bin/env bash'.

    07-PATTERNS.md reconciles D-709 verbatim '#!/bin/bash' to project standard.
    """
    first_line = wrapper_text.splitlines()[0]
    assert first_line == "#!/usr/bin/env bash", (
        f"wrapper shebang must be '#!/usr/bin/env bash' (project convention); got {first_line!r}"
    )


def test_wrapper_has_strict_mode(wrapper_text):
    assert "set -euo pipefail" in wrapper_text, (
        "wrapper missing 'set -euo pipefail' (D-709)"
    )


# --- HC_PING_URL fail-loud + pings (SCHED-03 / D-701 + D-703 + T-07-04) ---

def test_wrapper_fails_loud_when_hc_ping_url_missing(wrapper_text):
    """D-703 fail-loud: explicit guard checks HC_PING_URL and exits 4.

    Initially used ${HC_PING_URL:?} bash parameter expansion, but :? exits 1 (not 4)
    under set -e — conflating HC_PING_URL-missing with generic error. CR-01 fix
    replaced it with an explicit if-block that exits 4 per D-703 contract.
    """
    assert '[[ -z "${HC_PING_URL:-}" ]]' in wrapper_text, (
        "wrapper missing explicit HC_PING_URL guard — violates D-703 fail-loud (CR-01)"
    )


def test_wrapper_reserves_exit_4_for_missing_hc_ping_url(wrapper_text):
    """D-703: missing HC_PING_URL must exit 4 (not 1 from bash :? expansion).

    Parallels test_wrapper_reserves_exit_5_for_flock. Source-locks the exit code
    that operators see in cron logs when HC_PING_URL is absent from .env.
    """
    assert "exit 4" in wrapper_text, (
        "wrapper missing 'exit 4' on HC_PING_URL fail-loud — violates D-703 (CR-01)"
    )


def test_wrapper_pings_hc_start(wrapper_text):
    assert "${HC_PING_URL}/start" in wrapper_text, (
        "wrapper missing /start ping — violates D-701"
    )


def test_wrapper_pings_hc_success_bare_url(wrapper_text):
    """Success ping uses bare ${HC_PING_URL} (no /success suffix per HC.io docs)."""
    assert '"${HC_PING_URL}"' in wrapper_text, (
        "wrapper missing bare ${HC_PING_URL} success ping — violates D-701"
    )


def test_wrapper_pings_hc_fail_with_exit_payload(wrapper_text):
    assert "${HC_PING_URL}/fail" in wrapper_text, (
        "wrapper missing /fail ping — violates D-701"
    )
    assert '--data-raw "exit=$EXIT"' in wrapper_text, (
        "wrapper missing --data-raw \"exit=$EXIT\" — D-701 diagnostic body"
    )


def test_wrapper_hc_pings_are_fail_soft(wrapper_text):
    """HC outage must NOT block production — `|| true` after every curl ping."""
    occurrences = wrapper_text.count("|| true")
    assert occurrences >= 3, (
        f"expected >= 3 '|| true' occurrences (HC pings fail-soft per D-701); got {occurrences}"
    )


def test_wrapper_does_not_hardcode_uuid(wrapper_text):
    """T-07-04: HC.io UUID must come from .env via ${HC_PING_URL}, never hardcoded."""
    matches = re.findall(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        wrapper_text,
    )
    assert matches == [], f"wrapper hardcodes a UUID — T-07-04 violation; offending: {matches}"


# --- flock + lock file (SCHED-03 / D-709 / T-07-02) -----------------

def test_wrapper_uses_flock_non_blocking(wrapper_text):
    assert "flock -n 9" in wrapper_text, (
        "wrapper missing 'flock -n 9' — violates D-709 single-writer guard (T-07-02)"
    )


def test_wrapper_reserves_exit_5_for_flock(wrapper_text):
    """Pitfall #3: flock default exit 1 conflated with generic error; reserve 5 explicitly."""
    assert "exit 5" in wrapper_text, (
        "wrapper missing 'exit 5' on flock failure — Pitfall #3 (D-709 reserves exit 5)"
    )


# --- log redirect (SCHED-04 / D-704) --------------------------------

def test_wrapper_redirects_stdout_stderr_to_logfile(wrapper_text):
    assert '>> "$LOG_FILE" 2>&1' in wrapper_text, (
        "wrapper missing '>> \"$LOG_FILE\" 2>&1' — violates SCHED-04 (D-704)"
    )


def test_wrapper_log_file_path_has_datestamp(wrapper_text):
    assert "/var/log/ga_crawler/weekly-run-$(date +%F).log" in wrapper_text, (
        "wrapper missing datestamped log path — violates D-704 + SCHED-04"
    )


# --- ENV loading (D-709 + Phase 6 RESEARCH caveat #4) ---------------

def test_wrapper_loads_env_via_set_a_source(wrapper_text):
    """RESEARCH caveat #4 bypass — bash wrapper is the env-loading authority for cron."""
    assert "set -a" in wrapper_text, "wrapper missing 'set -a' before source .env (D-709)"
    assert "source .env" in wrapper_text, "wrapper missing 'source .env' (D-709)"
    assert "set +a" in wrapper_text, "wrapper missing 'set +a' after source .env (D-709)"


# --- Exit-code preservation (D-709) ---------------------------------

def test_wrapper_preserves_python_exit_code(wrapper_text):
    """`set +e ... EXIT=$? ... set -e` dance preserves Python exit through HC ping branch."""
    assert "set +e" in wrapper_text, "wrapper missing 'set +e' before uv run python (D-709)"
    assert "EXIT=$?" in wrapper_text, "wrapper missing 'EXIT=$?' capture (D-709)"
    assert "set -e" in wrapper_text, "wrapper missing 'set -e' after exit capture (D-709)"
    assert "exit $EXIT" in wrapper_text, "wrapper missing final 'exit $EXIT' passthrough (D-709)"


# --- Production invocation (D-709) ----------------------------------

def test_wrapper_invokes_uv_run(wrapper_text):
    assert "uv run python -m ga_crawler weekly-run" in wrapper_text, (
        "wrapper must invoke production via 'uv run python -m ga_crawler weekly-run' (D-709)"
    )


def test_wrapper_passes_through_args(wrapper_text):
    """'$@' pass-through allows bin/test-failure-alert.sh to inject --viled-only ..."""
    assert '"$@"' in wrapper_text, (
        "wrapper missing '\"$@\"' pass-through — violates D-709"
    )


# --- Forbidden patterns ---------------------------------------------

def test_wrapper_no_simulate_failure_substring(wrapper_text):
    """Phase 7 specifics line 259: no production-binary testing-mode toggle."""
    for forbidden in ("simulate-failure", "simulate_failure", "fail.mode", "fail_mode"):
        assert forbidden not in wrapper_text, (
            f"wrapper contains forbidden testing-mode substring {forbidden!r} — Phase 7 anti-pattern"
        )
