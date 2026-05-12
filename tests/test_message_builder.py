"""Plan 06-02 (Wave 1) — unit tests for ``delivery/message_builder.py``.

Pure-function tests + golden-file regression. Covers:
- D-610 single ops-alert template (5 scenarios via golden file).
- Pitfall A: ``html.escape`` applied to every dynamic str field.
- Pitfall E: Asia/Almaty tz conversion via ``%z`` numeric offset
  (W1 fix — cross-platform stable, no platform-dependent ``%Z``).
- D-614 ``ops_message_truncate_chars`` truncation (error_short ≤ 3500).
- ``REASON_SHORT`` dict completeness.
- ``business_caption`` pass-through vs split helper.

Source anchors: 06-CONTEXT.md D-609 + D-610; 06-RESEARCH.md Pattern 4 +
Pitfall A + Pitfall E; 06-PATTERNS.md "src/ga_crawler/delivery/message_builder.py".
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ga_crawler.delivery.message_builder import (
    REASON_SHORT,
    build_ops_alert,
    business_caption,
)


# --- fixtures (single shared scenario set; golden file echoes these) -------

FIXED_RUN_ID = 42
FIXED_STARTED_AT = datetime(2026, 5, 11, 17, 0, tzinfo=timezone.utc)
# Asia/Almaty is UTC+5 year-round (no DST) → expected formatted prefix:
EXPECTED_ALMATY_PREFIX = "2026-05-11 22:00 +0500"


def _base_kwargs(**overrides):
    base = dict(
        run_id=FIXED_RUN_ID,
        reason_key="upstream_status_failed",
        started_at_utc=FIXED_STARTED_AT,
        run_status="failed",
        gate_failed_check="run_status",
        viled_count=120,
        goldapple_count=540,
        match_count=0,
        match_rate=0.0,
        size_guard_failed=False,
        xlsx_size_mb=0.0,
        size_limit_mb=45,
        error_short="",
    )
    base.update(overrides)
    return base


# --- behavior tests ----------------------------------------------------------


def test_build_ops_alert_xlsx_oversize_starts_with_emoji():
    out = build_ops_alert(
        **_base_kwargs(
            reason_key="xlsx_oversize",
            run_status="success",
            gate_failed_check="size_guard",
            size_guard_failed=True,
            xlsx_size_mb=48.7,
            match_count=30,
            match_rate=25.0,
        )
    )
    # First line: "🚨 <b>Weekly run #42</b> — xlsx too large for Telegram"
    first_line = out.splitlines()[0]
    assert first_line == "🚨 <b>Weekly run #42</b> — xlsx too large for Telegram"


def test_html_escape_applied_to_error():
    """Pitfall A: untrusted ``error_short`` must be HTML-escaped."""
    payload = "<script>alert(1)</script>"
    out = build_ops_alert(**_base_kwargs(error_short=payload))
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "<script>" not in out  # raw must be gone


def test_html_escape_applied_to_run_status():
    """Pitfall A regression: gate_failed_check is also user-controlled."""
    out = build_ops_alert(
        **_base_kwargs(gate_failed_check="x<y&z")
    )
    assert "x&lt;y&amp;z" in out
    assert "x<y&z" not in out


def test_almaty_timezone_aware_datetime():
    """Pitfall E (W1 fix): %z numeric offset, cross-platform stable."""
    out = build_ops_alert(**_base_kwargs())
    assert EXPECTED_ALMATY_PREFIX in out, (
        f"expected substring {EXPECTED_ALMATY_PREFIX!r} not in:\n{out}"
    )


def test_almaty_naive_datetime_treated_as_utc():
    """Naive datetime is assumed UTC, then converted to Almaty."""
    from ga_crawler.delivery.message_builder import _format_almaty

    naive = datetime(2026, 5, 11, 17, 0)
    aware = datetime(2026, 5, 11, 17, 0, tzinfo=timezone.utc)
    assert _format_almaty(naive) == _format_almaty(aware)


def test_error_truncated_to_3500_chars():
    """D-614 ops_message_truncate_chars: error_short of 4000 chars is truncated."""
    huge = "A" * 4000
    out = build_ops_alert(**_base_kwargs(error_short=huge))
    # The block uses <pre>...</pre>; the truncated payload must be exactly 3500 'A's.
    pre_start = out.index("<pre>")
    pre_end = out.index("</pre>")
    payload = out[pre_start + len("<pre>"):pre_end]
    assert len(payload) == 3500
    assert payload == "A" * 3500


def test_size_guard_line_present_when_failed():
    out = build_ops_alert(
        **_base_kwargs(
            reason_key="xlsx_oversize",
            run_status="success",
            gate_failed_check="size_guard",
            size_guard_failed=True,
            xlsx_size_mb=48.7,
        )
    )
    assert "xlsx size: 48.7 MB (limit: 45 MB)" in out


def test_size_guard_line_absent_when_passed():
    out = build_ops_alert(**_base_kwargs(size_guard_failed=False))
    assert "xlsx size:" not in out


def test_no_error_block_when_error_empty():
    """Test 7: empty error_short sentinel suppresses the Error: line."""
    out = build_ops_alert(**_base_kwargs(error_short=""))
    assert "<i>Error:</i>" not in out
    assert "<pre>" not in out


def test_error_block_present_when_error_nonempty():
    out = build_ops_alert(**_base_kwargs(error_short="boom"))
    assert "<i>Error:</i> <pre>boom</pre>" in out


def test_manual_recovery_line_at_end():
    """Test 8: output ENDS with the manual recovery instruction."""
    out = build_ops_alert(**_base_kwargs())
    assert out.endswith(
        "<i>Manual recovery:</i> <code>python -m ga_crawler deliver-run --run-id 42</code>"
    )


def test_reason_short_dict_complete():
    """Test 10: required reason keys per D-610 mapping."""
    required = {
        "upstream_status_failed",
        "upstream_status_running",
        "upstream_status_None",
        "no_xlsx_in_stats",
        "xlsx_oversize",
        "empty_summary_text",
        "missing_env_TG_BUSINESS_CHAT_ID",
        "delivery_exception",
    }
    assert required.issubset(set(REASON_SHORT))


def test_reason_short_fallback_uses_raw_key():
    """Unknown reason_key falls back to the raw key string."""
    out = build_ops_alert(**_base_kwargs(reason_key="some_new_reason_we_did_not_map"))
    # _esc is applied to the fallback too
    assert "— some_new_reason_we_did_not_map" in out


# --- business_caption helper ------------------------------------------------


def test_business_caption_passthrough_when_short():
    text = "📊 Неделя 2026-W19"
    caption, split = business_caption(text, max_chars=1024)
    assert caption == text
    assert split is False


def test_business_caption_split_when_long():
    text = "x" * 1500
    caption, split = business_caption(text, max_chars=1024)
    assert caption == "См. сводку выше"
    assert split is True


def test_business_caption_boundary_exactly_max():
    text = "x" * 1024
    caption, split = business_caption(text, max_chars=1024)
    assert caption == text
    assert split is False


# --- golden-file regression --------------------------------------------------


GOLDEN_PATH = Path("tests/fixtures/delivery/ops-alert-templates.txt")


def _parse_golden_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).rstrip("\n")
            current_key = line[4:-4].strip()
            current_lines = []
        elif line.startswith("#") and current_key is None:
            # File-level comment — only valid before any section header.
            continue
        elif current_key is None:
            # Pre-section blank lines or stray content — ignore.
            continue
        else:
            current_lines.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).rstrip("\n")
    return sections


# Scenario kwargs aligned with the golden file headers (5 scenarios per D-610).
GOLDEN_SCENARIOS: dict[str, dict] = {
    "upstream_status_failed": dict(
        reason_key="upstream_status_failed",
        run_status="failed",
        gate_failed_check="run_status",
        size_guard_failed=False,
        xlsx_size_mb=0.0,
        match_count=0,
        match_rate=0.0,
        error_short="",
    ),
    "xlsx_oversize": dict(
        reason_key="xlsx_oversize",
        run_status="success",
        gate_failed_check="size_guard",
        size_guard_failed=True,
        xlsx_size_mb=48.7,
        match_count=30,
        match_rate=25.0,
        error_short="",
    ),
    "empty_summary_text": dict(
        reason_key="empty_summary_text",
        run_status="success",
        gate_failed_check="summary_text",
        size_guard_failed=False,
        xlsx_size_mb=0.0,
        match_count=0,
        match_rate=0.0,
        error_short="",
    ),
    "no_xlsx_in_stats": dict(
        reason_key="no_xlsx_in_stats",
        run_status="success",
        gate_failed_check="xlsx_path",
        size_guard_failed=False,
        xlsx_size_mb=0.0,
        match_count=0,
        match_rate=0.0,
        error_short="",
    ),
    "delivery_exception": dict(
        reason_key="delivery_exception",
        run_status="success",
        gate_failed_check=None,
        size_guard_failed=False,
        xlsx_size_mb=0.0,
        match_count=0,
        match_rate=0.0,
        error_short="TelegramBadRequest: chat not found\n  at line 42",
    ),
}


def test_golden_file_has_no_wave0_placeholders():
    """Wave-1 must replace the Wave-0 ``<PLACEHOLDER`` lines with real output."""
    text = GOLDEN_PATH.read_text(encoding="utf-8")
    assert "PLACEHOLDER" not in text
    assert text.count("=== ") >= 5
    assert "+0500" in text


@pytest.mark.parametrize("scenario", list(GOLDEN_SCENARIOS))
def test_golden_file_5_scenarios(scenario):
    sections = _parse_golden_file(GOLDEN_PATH)
    assert scenario in sections, f"missing '{scenario}' section in golden file"
    kwargs = _base_kwargs(**GOLDEN_SCENARIOS[scenario])
    expected = sections[scenario]
    actual = build_ops_alert(**kwargs)
    assert actual == expected, (
        f"golden-file drift for scenario {scenario!r}.\n"
        f"--- expected ---\n{expected!r}\n"
        f"--- actual ---\n{actual!r}\n"
    )
