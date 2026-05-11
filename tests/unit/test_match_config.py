"""Phase 4 / Plan 04-01: MatchConfig loader tests + pyproject namespace presence.

Mirrors `tests/unit/test_viled_stats_builder.py` shape for stats and the
existing ViledConfig.from_pyproject pattern (no dedicated test file exists for
ViledConfig — we anchor here for the matcher equivalent).

Source: 04-CONTEXT.md D-406..D-408, D-413; 04-PATTERNS.md §"AMEND pyproject.toml"
+ §"NEW src/ga_crawler/matcher/config.py".
"""
from __future__ import annotations

from pathlib import Path

from ga_crawler.matcher.config import MatchConfig


def test_match_config_defaults():
    """D-406/D-408: seed P=20; D-407: factor=0.7, after_runs=4. Dataclass
    defaults MUST mirror pyproject.toml so tests can construct MatchConfig()
    directly and get production values."""
    c = MatchConfig()
    assert c.sanity_gate_p == 20
    assert c.p_auto_suggest_factor == 0.7
    assert c.p_auto_suggest_after_runs == 4


def test_from_pyproject_reads_match_namespace(tmp_path):
    """from_pyproject reads [tool.ga_crawler.match] keys; absent keys fall back
    to dataclass defaults (mirror ViledConfig.from_pyproject semantics)."""
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        '[tool.ga_crawler.match]\nsanity_gate_p = 33\n',
        encoding="utf-8",
    )
    c = MatchConfig.from_pyproject(pyp)
    assert c.sanity_gate_p == 33
    assert c.p_auto_suggest_factor == 0.7  # default
    assert c.p_auto_suggest_after_runs == 4  # default


def test_from_pyproject_missing_file_returns_defaults():
    """Missing pyproject path → return dataclass defaults (no error)."""
    c = MatchConfig.from_pyproject("/non/existent/path.toml")
    assert c == MatchConfig()


def test_from_pyproject_partial_namespace_uses_defaults(tmp_path):
    """Only some keys present → others fall back. Validates that the loader
    treats every key independently (not all-or-nothing)."""
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        "[tool.ga_crawler.match]\n"
        "sanity_gate_p = 50\n"
        "p_auto_suggest_after_runs = 6\n",
        encoding="utf-8",
    )
    c = MatchConfig.from_pyproject(pyp)
    assert c.sanity_gate_p == 50
    assert c.p_auto_suggest_factor == 0.7  # default — key absent
    assert c.p_auto_suggest_after_runs == 6


def test_pyproject_has_match_namespace():
    """Production pyproject.toml MUST carry the [tool.ga_crawler.match] block
    with the canonical D-406..D-408 seed values. Regression canary against
    accidental TOML removal/rename."""
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ga_crawler.match]" in text
    assert "sanity_gate_p = 20" in text
    assert "p_auto_suggest_factor = 0.7" in text
    assert "p_auto_suggest_after_runs = 4" in text
