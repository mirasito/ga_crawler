"""Wave 0 / Plan 07-01 — README.md section structure canary (D-707 + Phase 9 D-905).

RED-gate stub: fails until Plan 07-04 ships the README.
Covers SCHED-05 documentation requirement; D-707 mandates RU-primary sections in exact order.

Phase 9 Plan 09-03 (D-905): added §8 «Live HTML harness» operator runbook between «Логи»
and «Dev setup» — section count extended from 10 → 11.

Source: 07-CONTEXT.md D-707 (lines 59-79); 09-CONTEXT.md D-905.
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
    "## Live HTML harness",   # Phase 9 D-905: operator runbook for live-HTML harness
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
    # Phase 9 D-905 extended from 10 → 11 sections (added § «Live HTML harness»)
    assert len(h2_headings) == 11, (
        f"README must have exactly 11 H2 sections (D-707 + Phase 9 D-905); got {len(h2_headings)}: {h2_headings}"
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
