"""TH-02a + TH-02b PII canary + 50/200 MB size budget.

Collected by default `pytest` invocation (NOT gated on -m live). D-907
enforcement point #2 (standalone test). Enforcement point #1 is fixture-
loader integration in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import _assert_fixture_clean

# pytest.fail() raises pytest.fail.Exception which is a BaseException subclass,
# NOT Exception. Use this alias for clean pytest.raises() assertions.
_CanaryError = pytest.fail.Exception


REPO_FIXTURES_GOLDAPPLE = Path(__file__).parent / "fixtures" / "goldapple"
REPO_FIXTURES_VILED = Path(__file__).parent / "fixtures" / "viled"


def test_dirty_fixture_cf_clearance_fails(tmp_path: Path) -> None:
    """T-09-PII: cf_clearance cookie -> fail; matched secret value NOT leaked into error."""
    dirty = tmp_path / "_live-dirty.html"
    dirty.write_text("<html>cf_clearance=secret_value_should_not_leak</html>", encoding="utf-8")
    with pytest.raises(_CanaryError) as exc:
        _assert_fixture_clean(dirty)
    assert "cf_clearance" in str(exc.value)
    assert "secret_value_should_not_leak" not in str(exc.value)


def test_dirty_fixture_bot_token_fails(tmp_path: Path) -> None:
    dirty = tmp_path / "_live-bot.html"
    dirty.write_text(
        '<script>const token="bot1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";</script>',
        encoding="utf-8",
    )
    with pytest.raises(_CanaryError):
        _assert_fixture_clean(dirty)


def test_dirty_fixture_uuid_hc_ping_via_hc_pattern_fails(tmp_path: Path) -> None:
    """UUID in hc-ping context is caught by hc-ping pattern (not standalone UUID).

    Note: standalone UUID v4 is NOT in _PII_PATTERNS because goldapple HTML
    legitimately embeds buildId in UUID format. The hc-ping-specific pattern
    handles the operator healthcheck token threat. (Rule 1 fix: false-positive
    on Phase 8 stereotype fixture buildId caused removal of standalone UUID pattern.)
    """
    dirty = tmp_path / "_live-hcping-uuid.html"
    dirty.write_text(
        "<a href='https://hc-ping.com/12345678-1234-4abc-89de-1234567890ab'></a>",
        encoding="utf-8",
    )
    with pytest.raises(_CanaryError):
        _assert_fixture_clean(dirty)


def test_dirty_fixture_hc_ping_fails(tmp_path: Path) -> None:
    dirty = tmp_path / "_live-hcping.html"
    dirty.write_text("<a href='https://hc-ping.com/abcdef0123456789abcdef0123456789'></a>", encoding="utf-8")
    with pytest.raises(_CanaryError):
        _assert_fixture_clean(dirty)


def test_dirty_fixture_authorization_bearer_fails(tmp_path: Path) -> None:
    dirty = tmp_path / "_live-auth.html"
    dirty.write_text("<pre>Authorization: Bearer eyJABC123</pre>", encoding="utf-8")
    with pytest.raises(_CanaryError):
        _assert_fixture_clean(dirty)


def test_oversize_rejected(tmp_path: Path) -> None:
    """T-09-SIZE: 50 MB per-file budget."""
    huge = tmp_path / "_live-huge.html"
    huge.write_bytes(b"x" * (51 * 1024 * 1024))
    with pytest.raises(_CanaryError) as exc:
        _assert_fixture_clean(huge)
    err = str(exc.value).lower()
    assert "byte" in err or "size" in err or "50" in err or "51" in err


def test_clean_phase8_goldapple_stereotype_passes() -> None:
    """RESEARCH A6 verification — Phase 8 W0 fixtures are PII-clean."""
    _assert_fixture_clean(REPO_FIXTURES_GOLDAPPLE / "_live-2026-05-13-stereotype.html")


def test_clean_phase8_goldapple_armani_passes() -> None:
    _assert_fixture_clean(REPO_FIXTURES_GOLDAPPLE / "_live-2026-05-13-armani-code.html")


def test_clean_phase8_viled_contre_jour_passes() -> None:
    _assert_fixture_clean(REPO_FIXTURES_VILED / "_live-2026-05-13-contre-jour.html")
