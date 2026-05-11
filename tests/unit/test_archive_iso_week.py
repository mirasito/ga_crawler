"""Unit tests for archive.derive_filename — D-512 ISO-week derivation + Pitfall 4 year boundary.

Source-lock against ISO 8601 Thursday-rule semantics. Year-boundary cases
cited in 05-RESEARCH.md Pitfall 4 (L712-724) + Python stdlib isocalendar docs.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ga_crawler.reporter.archive import derive_filename


# ---------- Year-boundary canary cases (Pitfall 4) ----------


@pytest.mark.parametrize(
    "started_at_utc, expected_filename",
    [
        # 2026-05-10 14:00 UTC → Sunday 19:00 Almaty → ISO 2026-W19
        (datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc), "2026-W19.xlsx"),
        # 2027-01-01 12:00 UTC (Fri) → ISO 2026-W53 (Pitfall 4 — Thursday Dec 31 in 2026)
        (datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc), "2026-W53.xlsx"),
        # 2025-12-29 12:00 UTC (Mon) → ISO 2026-W01 (first Thursday of 2026 is in this week)
        (datetime(2025, 12, 29, 12, 0, tzinfo=timezone.utc), "2026-W01.xlsx"),
        # 2026-01-04 18:00 UTC (Sun) → ISO 2026-W01 (Thursday Jan 1 in 2026)
        (datetime(2026, 1, 4, 18, 0, tzinfo=timezone.utc), "2026-W01.xlsx"),
        # 2026-12-31 23:00 UTC (Thu) → Almaty 04:00 Fri 2027-01-01 → ISO 2026-W53
        (datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc), "2026-W53.xlsx"),
    ],
)
def test_derive_filename_year_boundary(started_at_utc, expected_filename):
    """Pitfall 4: ISO 8601 Thursday-rule year boundaries."""
    assert derive_filename(started_at_utc) == expected_filename


# ---------- TZ validation ----------


def test_derive_filename_rejects_naive_datetime():
    """DATA-05 invariant: started_at must be tz-aware in production."""
    naive = datetime(2026, 5, 10, 14)
    with pytest.raises(ValueError, match="timezone-aware"):
        derive_filename(naive)


def test_derive_filename_custom_tz():
    """tz_name override works — same UTC moment yields different ISO week in another tz.

    2026-01-04 22:00 UTC:
      - In Asia/Almaty (UTC+5): 2026-01-05 03:00 Mon → ISO 2026-W02
      - In UTC tz_name: still 2026-01-04 22:00 Sun → ISO 2026-W01
    """
    utc_moment = datetime(2026, 1, 4, 22, 0, tzinfo=timezone.utc)
    almaty = derive_filename(utc_moment, tz_name="Asia/Almaty")
    assert almaty == "2026-W02.xlsx"
    utc_filename = derive_filename(utc_moment, tz_name="UTC")
    assert utc_filename == "2026-W01.xlsx"


def test_derive_filename_almaty_offset_crosses_day_boundary():
    """UTC late evening + Almaty +5h crosses calendar day; ISO week derives from local.

    2026-05-10 22:30 UTC = 2026-05-11 03:30 Almaty (Mon) → ISO 2026-W20.
    """
    dt = datetime(2026, 5, 10, 22, 30, tzinfo=timezone.utc)
    assert derive_filename(dt) == "2026-W20.xlsx"


def test_derive_filename_format_padding():
    """Single-digit weeks are zero-padded (W01 not W1)."""
    dt = datetime(2026, 1, 4, 12, tzinfo=timezone.utc)
    out = derive_filename(dt)
    assert out == "2026-W01.xlsx"
    assert "-W1." not in out  # padding canary


def test_derive_filename_returns_str():
    """Return type is str — used as filename in Path composition."""
    dt = datetime(2026, 5, 10, 14, tzinfo=timezone.utc)
    out = derive_filename(dt)
    assert isinstance(out, str)
    assert out.endswith(".xlsx")
