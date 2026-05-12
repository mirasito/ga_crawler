"""Wave 0 / Plan 07-01 — shape-canary on deploy/etc-cron-d-ga_crawler.

RED-gate stub: fails until Plan 07-02 ships the cron template per D-708.
Covers SCHED-01 + SCHED-02 (CRON_TZ + Sunday 23:00 weekly-run + daily 01:00 backup).
Pitfall #1 guard: filename has NO dot.

Source: 07-CONTEXT.md D-708 (lines 84-89 verbatim); 07-RESEARCH.md Example 1 + Pitfall #1.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CRON_FILE = REPO_ROOT / "deploy" / "etc-cron-d-ga_crawler"


@pytest.fixture
def cron_text() -> str:
    assert CRON_FILE.exists(), f"{CRON_FILE} must exist (D-708)"
    return CRON_FILE.read_text(encoding="utf-8")


def test_filename_has_no_dot_pitfall_1():
    """Pitfall #1: Vixie cron silently skips /etc/cron.d/* files with dots."""
    assert "." not in CRON_FILE.name, (
        f"deploy/etc-cron-d-ga_crawler filename must NOT contain a dot — "
        f"Vixie cron silently ignores such files (Pitfall #1). Got: {CRON_FILE.name!r}"
    )


def test_cron_contains_cron_tz_almaty(cron_text):
    assert "CRON_TZ=Asia/Almaty" in cron_text, (
        "cron template missing 'CRON_TZ=Asia/Almaty' — violates SCHED-02 (D-708)"
    )


def test_cron_contains_mailto_empty(cron_text):
    """Pitfall #2: MAILTO unset would route stdout to root@localhost mailbox."""
    assert 'MAILTO=""' in cron_text, (
        'cron template missing \'MAILTO=""\' — Pitfall #2 (silent mailbox bloat); D-708'
    )


def test_cron_contains_weekly_run_row(cron_text):
    assert "0 23 * * 0 ga_crawler /opt/ga_crawler/bin/weekly-run.sh" in cron_text, (
        "cron template missing Sunday 23:00 weekly-run row — violates SCHED-01 (D-708)"
    )


def test_cron_contains_daily_backup_row(cron_text):
    # Match D-708 verbatim (two spaces between "1" and "* * *")
    assert "0 1  * * * ga_crawler /opt/ga_crawler/bin/backup.sh" in cron_text, (
        "cron template missing daily 01:00 backup row — violates D-708 + DATA-06 cascade"
    )
