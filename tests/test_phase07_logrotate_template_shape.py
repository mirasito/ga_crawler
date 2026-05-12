"""Wave 0 / Plan 07-01 — shape-canary on deploy/etc-logrotate-d-ga_crawler.

RED-gate stub: fails until Plan 07-02 ships the logrotate template per D-705.
Covers SCHED-04 (7 directives + path glob).

Source: 07-CONTEXT.md D-705 (lines 33-43 verbatim); 07-RESEARCH.md Example 2 + Pitfall #5.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LOGROTATE_FILE = REPO_ROOT / "deploy" / "etc-logrotate-d-ga_crawler"


@pytest.fixture
def logrotate_text() -> str:
    assert LOGROTATE_FILE.exists(), f"{LOGROTATE_FILE} must exist (D-705)"
    return LOGROTATE_FILE.read_text(encoding="utf-8")


def test_logrotate_has_path_glob(logrotate_text):
    assert "/var/log/ga_crawler/*.log" in logrotate_text, (
        "logrotate template missing path glob /var/log/ga_crawler/*.log (D-705)"
    )


def test_logrotate_has_weekly(logrotate_text):
    assert "weekly" in logrotate_text, "logrotate missing 'weekly' (D-705)"


def test_logrotate_has_rotate_13(logrotate_text):
    assert "rotate 13" in logrotate_text, "logrotate missing 'rotate 13' (D-705 — 3 months retention)"


def test_logrotate_has_compress(logrotate_text):
    assert "compress" in logrotate_text, "logrotate missing 'compress' (D-705)"


def test_logrotate_has_delaycompress(logrotate_text):
    assert "delaycompress" in logrotate_text, "logrotate missing 'delaycompress' (D-705)"


def test_logrotate_has_missingok(logrotate_text):
    assert "missingok" in logrotate_text, "logrotate missing 'missingok' (D-705 + Pitfall #5)"


def test_logrotate_has_notifempty(logrotate_text):
    assert "notifempty" in logrotate_text, "logrotate missing 'notifempty' (D-705 + Pitfall #5b)"


def test_logrotate_has_create_directive(logrotate_text):
    assert "create 0644 ga_crawler ga_crawler" in logrotate_text, (
        "logrotate missing 'create 0644 ga_crawler ga_crawler' — V12 Files mitigation T-07-05 (D-705)"
    )
