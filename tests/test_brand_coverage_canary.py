"""TH-04 brand-coverage quota canary (P2 cheap-bundle, Variant A only).

Asserts >=1 live fixture per active brand seen in last 4 weekly snapshots.
Active-brand list seed: spike-findings-v1.1-brand-name-shapes/SKILL.md L28-32
shape buckets (stereotype, mixed-case, armani, givenchy-baseline).

Failure mode: a brand appearing in production has NO live fixture -> drift
test (TH-03) cannot catch parser regressions on that brand's PDP shape.
Operator response: capture a fresh fixture via `python -m ga_crawler
capture-fixtures --retailer goldapple --url <URL> --slug <slug>` (TH-05).

Behavior:
  - Empty DB (test env): no active brands -> canary passes vacuously
  - At least 1 active brand seen in last 4 weekly runs without a fixture
    in tests/fixtures/goldapple/_live-*.html -> canary fails with brand list

D-902: skipped if P2=NO-GO (this whole test file does not exist in Variant B).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from ga_crawler.storage.sqlite import Snapshot, make_engine

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_GA = REPO_ROOT / "tests" / "fixtures" / "goldapple"
FIXTURES_VILED = REPO_ROOT / "tests" / "fixtures" / "viled"
ACTIVE_RUNS_LOOKBACK = 4   # last 4 weekly runs


def _active_goldapple_brands(db_path: Path) -> set[str]:
    """Return distinct goldapple brand strings seen in snapshots from the
    most-recent ACTIVE_RUNS_LOOKBACK run_ids."""
    if not db_path.exists():
        return set()
    engine = make_engine(db_path)
    with Session(engine) as s:
        # Distinct run_ids order DESC, take top N
        run_ids = list(s.exec(
            select(Snapshot.run_id)
            .where(Snapshot.retailer == "goldapple")
            .distinct()
            .order_by(Snapshot.run_id.desc())
        ))[:ACTIVE_RUNS_LOOKBACK]
        if not run_ids:
            return set()
        brands = s.exec(
            select(Snapshot.brand)
            .where(Snapshot.retailer == "goldapple")
            .where(Snapshot.run_id.in_(run_ids))
            .distinct()
        ).all()
    return {b.strip().lower() for b in brands if b}


def _fixture_brands_from_disk() -> set[str]:
    """Read brand slug from each _live-*.html filename.

    Slug parsing: _live-YYYY-MM-DD-<slug>.html -> first slug token = brand-ish.
    Returns lowercased brand-prefix set.
    """
    out: set[str] = set()
    for f in FIXTURES_GA.glob("_live-*.html"):
        # stem: _live-2026-05-13-stereotype-sago
        # parts[0..3] = ['_live', 'YYYY', 'MM', 'DD'] -> parts[4..] = slug tokens
        stem = f.stem
        parts = stem.split("-")
        if len(parts) >= 5:
            # First slug token is the brand-ish prefix used in canary assertion
            out.add(parts[4].lower())
    return out


def test_each_active_brand_has_a_fixture() -> None:
    """Active goldapple brands without a live fixture trigger this canary.

    In test environments (no prices.db), this test is vacuously skipped.
    In operator environments with a populated DB, any active brand without
    a matching fixture stem fails loudly with an actionable error message.
    """
    db_path = REPO_ROOT / "prices.db"  # production DB path
    active = _active_goldapple_brands(db_path)
    if not active:
        pytest.skip("No active brands in DB (empty/fresh env) — vacuously OK.")
    fixture_brands = _fixture_brands_from_disk()
    missing = active - fixture_brands
    if missing:
        pytest.fail(
            f"Active goldapple brands without _live-*.html fixture: "
            f"{sorted(missing)}. Capture via `python -m ga_crawler "
            f"capture-fixtures --retailer goldapple --url <URL> --slug <slug>` "
            f"(TH-05). See README §8 for runbook."
        )


def test_phase8_shape_buckets_covered() -> None:
    """Three Phase 8 shape buckets (stereotype, armani, contre-jour) must
    each have a live fixture committed (regression guard on SKILL.md L28-32).

    These are the foundational shape buckets discovered during Phase 8 spike:
    - STEREOTYPE-style: most common goldapple PDP shape
    - Armani-style: brand-in-name variant (D-816 softened canary)
    - Contre-Jour-style: viled fixture with legitimate-None volume_raw (D-904)
    """
    ga_fixtures = {p.stem for p in FIXTURES_GA.glob("_live-*.html")}
    viled_fixtures = {p.stem for p in FIXTURES_VILED.glob("_live-*.html")}

    # Stereotype-style: _live-2026-05-13-stereotype*.html (or similar)
    assert any("stereotype" in s for s in ga_fixtures), (
        "Phase 8 stereotype-style shape bucket has no goldapple live fixture. "
        "Capture via `python -m ga_crawler capture-fixtures --retailer goldapple "
        "--url <URL> --slug stereotype-<name>` (TH-05)."
    )
    # Armani-style: _live-2026-05-13-armani-code*.html
    assert any("armani" in s for s in ga_fixtures), (
        "Phase 8 armani-style shape bucket has no goldapple live fixture. "
        "Capture via `python -m ga_crawler capture-fixtures --retailer goldapple "
        "--url <URL> --slug armani-<name>` (TH-05)."
    )
    # Contre-Jour-style: _live-2026-05-13-contre-jour*.html (viled)
    assert any("contre" in s for s in viled_fixtures), (
        "Phase 8 contre-jour shape bucket has no viled live fixture. "
        "Capture via `python -m ga_crawler capture-fixtures --retailer viled "
        "--url <URL> --slug contre-jour` (TH-05)."
    )


def test_canary_handles_empty_db_gracefully(tmp_path: Path) -> None:
    """Fresh test environment (no prices.db) -> no active brands -> canary passes."""
    assert _active_goldapple_brands(tmp_path / "nonexistent.db") == set()
