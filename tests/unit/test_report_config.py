"""Unit tests for ReportConfig — D-516 seed values + from_pyproject loader.

Mirrors tests/unit/test_match_config.py shape.

Source: 05-CONTEXT.md D-516; 05-PATTERNS.md §"src/ga_crawler/reporter/config.py".
"""

from __future__ import annotations

from pathlib import Path

from ga_crawler.reporter.config import ReportConfig


def test_report_config_defaults():
    """D-516: output_dir='reports', size_limit_mb=45, top_n_deltas=3, timezone='Asia/Almaty'.

    Dataclass defaults MUST mirror pyproject.toml so tests can construct
    ReportConfig() directly and get production values.
    """
    c = ReportConfig()
    assert c.output_dir == "reports"
    assert c.size_limit_mb == 45
    assert c.top_n_deltas == 3
    assert c.timezone == "Asia/Almaty"


def test_from_pyproject_reads_report_namespace(tmp_path):
    """from_pyproject reads [tool.ga_crawler.report] keys; absent keys fall back
    to dataclass defaults (mirror MatchConfig.from_pyproject semantics)."""
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        "[tool.ga_crawler.report]\nsize_limit_mb = 50\n",
        encoding="utf-8",
    )
    c = ReportConfig.from_pyproject(pyp)
    assert c.size_limit_mb == 50
    # Others fall back to defaults
    assert c.output_dir == "reports"
    assert c.top_n_deltas == 3
    assert c.timezone == "Asia/Almaty"


def test_from_pyproject_missing_file_returns_defaults():
    """Missing pyproject path → return dataclass defaults (no error)."""
    c = ReportConfig.from_pyproject("/non/existent/path.toml")
    assert c == ReportConfig()


def test_from_pyproject_partial_namespace_uses_defaults(tmp_path):
    """Only some keys present → others fall back. Validates that the loader
    treats every key independently (not all-or-nothing)."""
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        '[tool.ga_crawler.report]\noutput_dir = "custom_reports"\ntop_n_deltas = 5\n',
        encoding="utf-8",
    )
    c = ReportConfig.from_pyproject(pyp)
    assert c.output_dir == "custom_reports"
    assert c.top_n_deltas == 5
    assert c.size_limit_mb == 45  # default
    assert c.timezone == "Asia/Almaty"  # default


def test_pyproject_has_report_namespace():
    """Production pyproject.toml MUST carry the [tool.ga_crawler.report] block
    with the canonical D-516 seed values. Regression canary against accidental
    TOML removal/rename.
    """
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ga_crawler.report]" in text
    assert 'output_dir = "reports"' in text
    assert "size_limit_mb = 45" in text
    assert "top_n_deltas = 3" in text
    assert 'timezone = "Asia/Almaty"' in text
