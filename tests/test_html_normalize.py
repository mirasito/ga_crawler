"""T-09-DRIFT normalization helper unit tests (RESEARCH §7.1)."""
from __future__ import annotations

from tests._html_normalize import normalize_for_snapshot


_SAMPLE = (
    '<meta name="csrf-token" content="aBc123XYZ">'
    '<script>cf_clearance=secretValueXYZ; path=/</script>'
    '<div class="_ga-pdp-title__heading_1yrfv_339">'
    '  <span class="_ga-pdp-title__brand_1yrfv_350">B</span>'
    '  <span class="_ga-pdp-title__name_1yrfv_360">N</span>'
    '</div>'
    '<script id="__NEXT_DATA__">{"buildId":"abc-XYZ-123","page":"/"}</script>'
)


def test_idempotent() -> None:
    once = normalize_for_snapshot(_SAMPLE)
    twice = normalize_for_snapshot(once)
    assert once == twice


def test_strips_csrf_token() -> None:
    out = normalize_for_snapshot(_SAMPLE)
    assert 'content="NORM"' in out
    assert "aBc123XYZ" not in out


def test_strips_cf_clearance() -> None:
    out = normalize_for_snapshot(_SAMPLE)
    assert "cf_clearance=NORM" in out
    assert "secretValueXYZ" not in out


def test_strips_build_hash_for_heading_brand_name() -> None:
    out = normalize_for_snapshot(_SAMPLE)
    assert "_ga-pdp-title__heading_NORM" in out
    assert "_ga-pdp-title__brand_NORM" in out
    assert "_ga-pdp-title__name_NORM" in out
    assert "1yrfv_339" not in out


def test_strips_next_data_build_id() -> None:
    out = normalize_for_snapshot(_SAMPLE)
    assert '"buildId":"NORM"' in out
    assert "abc-XYZ-123" not in out
