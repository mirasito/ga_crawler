"""Wave 0 / Plan 07-01 — README.md 10-section structure canary (D-707).

RED-gate stub: fails until Plan 07-04 ships the README.
Covers SCHED-05 documentation requirement; D-707 mandates RU-primary 10 H2 sections in exact order.

Source: 07-CONTEXT.md D-707 (lines 59-79).
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


EXPECTED_HEADINGS = [
    "## Что это",
    "## VPS setup from-scratch",
    "## ENV vars",
    "## Cron entry",
    "## Healthchecks.io setup",
    "## Telegram bot setup",
    "## Deliberate-failure test",
    "## Operations runbook",
    "## Логи",
    "## Dev setup",
]


@pytest.fixture
def readme_text() -> str:
    assert README.exists(), f"{README} must exist at repo root (SCHED-05 / D-707)"
    return README.read_text(encoding="utf-8")


@pytest.fixture
def h2_headings(readme_text) -> list[str]:
    return [
        line.strip()
        for line in readme_text.splitlines()
        if line.startswith("## ")
    ]


def test_readme_has_exactly_10_h2_sections(h2_headings):
    assert len(h2_headings) == 10, (
        f"README must have exactly 10 H2 sections per D-707; got {len(h2_headings)}: {h2_headings}"
    )


def test_readme_h2_order_matches_d707(h2_headings):
    assert h2_headings == EXPECTED_HEADINGS, (
        f"README H2 order must match D-707 exactly.\nExpected: {EXPECTED_HEADINGS}\nGot:      {h2_headings}"
    )


def test_readme_is_ru_primary():
    """D-707: RU primary prose; Cyrillic must appear in headings."""
    readme_text = README.read_text(encoding="utf-8")
    assert "## Что это" in readme_text and "## Логи" in readme_text, (
        "README must be RU-primary per D-707 (Что это + Логи headings)"
    )
