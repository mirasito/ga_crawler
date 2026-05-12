"""Wave 0 / Plan 07-01 — .env.example shape canary (Phase 7 HC_PING_URL addition).

RED-gate stub: fails until Plan 07-02 appends 'HC_PING_URL=' line.
Covers SCHED-05 ENV template + Pitfall #4 (no '#' in values, no quotes — bash/python-dotenv parser parity).

Threat refs: T-07-04 (HC.io UUID in .env, gitignored), T-07-08 (.env operator-controlled).

Source: 07-CONTEXT.md Action Items line 306 (HC_PING_URL= placeholder); 07-RESEARCH.md Pitfall #4.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


@pytest.fixture
def env_text() -> str:
    assert ENV_EXAMPLE.exists(), f"{ENV_EXAMPLE} must exist"
    return ENV_EXAMPLE.read_text(encoding="utf-8")


# --- Phase 6 placeholders (regression: still present) ---------------

def test_env_example_phase6_tg_bot_token_placeholder(env_text):
    assert "TG_BOT_TOKEN=" in env_text, "Phase 6 placeholder TG_BOT_TOKEN= regressed (D-612)"


def test_env_example_phase6_business_chat_placeholder(env_text):
    assert "TG_BUSINESS_CHAT_ID=" in env_text, "Phase 6 placeholder TG_BUSINESS_CHAT_ID= regressed (D-612)"


def test_env_example_phase6_ops_chat_placeholder(env_text):
    assert "TG_OPS_CHAT_ID=" in env_text, "Phase 6 placeholder TG_OPS_CHAT_ID= regressed (D-612)"


# --- Phase 7 NEW (SCHED-03 / D-703) ---------------------------------

def test_env_example_has_hc_ping_url_placeholder(env_text):
    assert "HC_PING_URL=" in env_text, (
        ".env.example must contain 'HC_PING_URL=' placeholder (Phase 7 SCHED-03 / D-703)"
    )


# --- Value hygiene: all secrets blank (T-07-04 mitigation) ----------

def test_env_example_all_known_placeholders_blank(env_text):
    """T-07-04 mitigation: no real secrets committed; placeholders are bare."""
    known_keys = {"TG_BOT_TOKEN", "TG_BUSINESS_CHAT_ID", "TG_OPS_CHAT_ID", "HC_PING_URL"}
    for line in env_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key in known_keys:
            assert value == "", (
                f"{key} in .env.example must be blank (got {value!r}); "
                f"T-07-04 mitigation — no real secrets in git"
            )


# --- Pitfall #4: bash/python-dotenv parser parity ------------------

def test_env_example_values_have_no_hash_no_quotes_no_newlines(env_text):
    """Pitfall #4: '#' inside values parses differently in bash vs python-dotenv.

    For Phase 7's set of vars (all simple K=V strings — token, URL, numeric chat_id),
    canary asserts values contain no '#', no quote characters, no embedded newlines.
    """
    for line in env_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if not key.replace("_", "").isalnum():
            continue
        assert "#" not in value, f"{key} value contains '#' — Pitfall #4 (bash vs python-dotenv drift); got {value!r}"
        assert '"' not in value, f"{key} value contains '\"' — Pitfall #4 quote escape risk; got {value!r}"
        assert "'" not in value, f"{key} value contains \"'\" — Pitfall #4 quote escape risk; got {value!r}"
