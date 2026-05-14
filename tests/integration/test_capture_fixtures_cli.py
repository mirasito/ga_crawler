"""TH-05 capture-fixtures CLI integration tests.

Argparse wiring + dry-run + scrub semantics. Does NOT exercise live fetch
(operator-only path); fetch mocking is left for an end-to-end test deferred
to v1.2 if needed.

Tests:
  1. test_capture_fixtures_help_exits_zero        — argparse wired, --help works
  2. test_capture_fixtures_invalid_retailer_exits_nonzero — unknown retailer rejected
  3. test_scrub_strips_cf_clearance               — D-907 scrub: cf_clearance removed
  4. test_scrub_strips_bot_token                  — D-907 scrub: TG bot token removed
  5. test_scrub_strips_hc_ping_path               — D-907 scrub: hc-ping token removed
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from ga_crawler.cli import _scrub_html_for_fixture


def test_capture_fixtures_help_exits_zero() -> None:
    """capture-fixtures subcommand is wired to argparse; --help exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "ga_crawler", "capture-fixtures", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "--retailer" in result.stdout
    assert "--url" in result.stdout
    assert "--slug" in result.stdout


def test_capture_fixtures_invalid_retailer_exits_nonzero() -> None:
    """--retailer with an unsupported value causes argparse error (exit != 0)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "ga_crawler", "capture-fixtures",
            "--retailer", "unknown",
            "--url", "https://example.com",
            "--slug", "x",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        f"Expected non-zero exit for invalid retailer but got {result.returncode}"
    )


def test_scrub_strips_cf_clearance() -> None:
    """D-907: cf_clearance cookie value is replaced with SCRUBBED sentinel."""
    dirty = "<html>cf_clearance=secretValue; path=/</html>"
    clean = _scrub_html_for_fixture(dirty)
    assert "cf_clearance=SCRUBBED" in clean
    assert "secretValue" not in clean


def test_scrub_strips_bot_token() -> None:
    """D-907: Telegram bot tokens (bot<digits>:<b64>) are scrubbed."""
    dirty = '<script>const t="bot1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";</script>'
    clean = _scrub_html_for_fixture(dirty)
    # The original token substring should not appear
    assert "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in clean


def test_scrub_strips_hc_ping_path() -> None:
    """D-907: hc-ping.com health-check UUID paths are scrubbed."""
    # 32 hex chars = typical healthchecks.io ping UUID (without hyphens)
    dirty = "<a href='https://hc-ping.com/abcdef0123456789abcdef0123456789'></a>"
    clean = _scrub_html_for_fixture(dirty)
    assert "hc-ping.com/SCRUBBED" in clean
    assert "abcdef0123456789abcdef0123456789" not in clean
