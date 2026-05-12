"""Plan 06-02 (Wave 1) — unit tests for ``delivery/config.py``.

Covers ``DeliverConfig.from_pyproject`` (D-614 6 keys) +
``DeliverEnvConfig.from_env`` (D-611 asymmetric, RESEARCH caveat #4 — NO
``load_dotenv`` import inside the module; only ``cli.py::_cmd_deliver``
calls it once on CLI startup).

Source anchors: 06-CONTEXT.md D-611 + D-614; 06-RESEARCH.md caveat #4.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig


# ----------------------------- DeliverConfig --------------------------------


def test_default_config_values():
    """Defaults mirror pyproject [tool.ga_crawler.deliver] values (D-614)."""
    c = DeliverConfig()
    assert c.retry_max_attempts == 3
    assert c.retry_backoff_min_seconds == 5
    assert c.retry_backoff_max_seconds == 45
    assert c.ops_message_truncate_chars == 3500
    assert c.business_caption_max_chars == 1024
    assert c.parse_mode == "HTML"


def test_from_pyproject_against_repo_pyproject_matches_defaults():
    """Plan 06-01 committed defaults verbatim to pyproject; from_pyproject must read them."""
    c = DeliverConfig.from_pyproject("pyproject.toml")
    assert c.retry_max_attempts == 3
    assert c.retry_backoff_min_seconds == 5
    assert c.retry_backoff_max_seconds == 45
    assert c.ops_message_truncate_chars == 3500
    assert c.business_caption_max_chars == 1024
    assert c.parse_mode == "HTML"


def test_from_pyproject_returns_defaults_for_missing_file(tmp_path):
    """Missing file → defaults (no crash). Mirror ReportConfig.from_pyproject."""
    c = DeliverConfig.from_pyproject(tmp_path / "does-not-exist.toml")
    assert c == DeliverConfig()


def test_from_pyproject_overrides_one_key(tmp_path):
    """Partial override: other keys fall back to dataclass defaults."""
    toml = tmp_path / "custom.toml"
    toml.write_text(
        dedent("""\
            [tool.ga_crawler.deliver]
            retry_max_attempts = 5
        """),
        encoding="utf-8",
    )
    c = DeliverConfig.from_pyproject(toml)
    assert c.retry_max_attempts == 5
    # Untouched keys retain defaults
    assert c.retry_backoff_min_seconds == 5
    assert c.parse_mode == "HTML"
    assert c.ops_message_truncate_chars == 3500


def test_from_pyproject_missing_namespace_falls_back(tmp_path):
    """toml without [tool.ga_crawler.deliver] still returns defaults."""
    toml = tmp_path / "empty.toml"
    toml.write_text("[project]\nname = 'x'\n", encoding="utf-8")
    c = DeliverConfig.from_pyproject(toml)
    assert c == DeliverConfig()


def test_pyproject_parse_mode_is_HTML():
    """D-609 regression: pyproject must declare HTML parse_mode."""
    c = DeliverConfig.from_pyproject("pyproject.toml")
    assert c.parse_mode == "HTML"


# ---------------------------- DeliverEnvConfig ------------------------------


def test_from_env_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_BUSINESS_CHAT_ID", raising=False)
    monkeypatch.delenv("TG_OPS_CHAT_ID", raising=False)
    e = DeliverEnvConfig.from_env()
    assert e.bot_token is None
    assert e.business_chat_id is None
    assert e.ops_chat_id is None


def test_from_env_reads_set_value(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "abc:xyz")
    monkeypatch.delenv("TG_BUSINESS_CHAT_ID", raising=False)
    monkeypatch.delenv("TG_OPS_CHAT_ID", raising=False)
    e = DeliverEnvConfig.from_env()
    assert e.bot_token == "abc:xyz"
    assert e.business_chat_id is None
    assert e.ops_chat_id is None


def test_from_env_reads_all_three(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "token-1")
    monkeypatch.setenv("TG_BUSINESS_CHAT_ID", "-100000001")
    monkeypatch.setenv("TG_OPS_CHAT_ID", "-100000002")
    e = DeliverEnvConfig.from_env()
    assert e.bot_token == "token-1"
    assert e.business_chat_id == "-100000001"
    assert e.ops_chat_id == "-100000002"


def test_from_env_does_not_call_load_dotenv():
    """RESEARCH caveat #4: only ``cli.py::_cmd_deliver`` may call ``load_dotenv``.

    Structural canary: the source text of ``delivery/config.py`` must not
    reference ``load_dotenv`` at all (no import, no call).
    """
    src = Path("src/ga_crawler/delivery/config.py").read_text(encoding="utf-8")
    assert "load_dotenv" not in src, (
        "load_dotenv must NOT appear in delivery/config.py (RESEARCH caveat #4): "
        "credential resolution stays a pure os.getenv read so test runs never "
        "accidentally pick up a real .env file."
    )


def test_from_env_empty_string_is_none(monkeypatch):
    """Empty-string env var is normalised to None (Pitfall 4 sentinel coherence)."""
    monkeypatch.setenv("TG_BOT_TOKEN", "")
    monkeypatch.setenv("TG_BUSINESS_CHAT_ID", "")
    monkeypatch.setenv("TG_OPS_CHAT_ID", "")
    e = DeliverEnvConfig.from_env()
    assert e.bot_token is None
    assert e.business_chat_id is None
    assert e.ops_chat_id is None


def test_dataclasses_are_frozen():
    """D-611 / D-614: both dataclasses immutable to prevent accidental mutation."""
    c = DeliverConfig()
    with pytest.raises((AttributeError, Exception)):
        c.retry_max_attempts = 99  # type: ignore[misc]
    e = DeliverEnvConfig(bot_token=None, business_chat_id=None, ops_chat_id=None)
    with pytest.raises((AttributeError, Exception)):
        e.bot_token = "leaked"  # type: ignore[misc]
