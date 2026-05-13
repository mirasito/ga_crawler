"""Goldapple brand+name extraction tests — PARSE-FIX-02 (Plan 08-03).

RED → GREEN per Plan 08-03 strict TDD. Fixture-driven against:
- tests/fixtures/goldapple/_live-2026-05-13-stereotype.html (Bug #1)
- tests/fixtures/goldapple/_live-2026-05-13-armani-code.html (Bug #2)
- tests/fixtures/goldapple/_debug-product-page.html (Givenchy backward-compat baseline)

Strategy follows Phase 8 W0 spike evidence (.planning/spikes/v1.1-brand-name-shapes/
MEMO.md, .claude/skills/spike-findings-v1.1-brand-name-shapes/SKILL.md):

  - The microdata-walk approach proposed in the plan's PATTERNS.md is INVALIDATED
    by W0 evidence (0/30 PDPs carry product-level `<meta itemprop="name">`).
  - The actual brand+name source is h1 child spans:
      `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__brand_"]`
      `h1[class*="_ga-pdp-title__heading_"] [class*="_ga-pdp-title__name_"]`
  - 100% (30/30) coverage in W0 sample.

Invariant canary (CONTEXT.md D-816, softened per W0 §"Decisions" §4 to log-only
in production code, but the test enforces the invariant for fixtures within the
clean-separation buckets — stereotype + Givenchy baseline. Armani is an
upstream-data-redundancy bucket where the invariant legitimately fails 2/30
times — for that bucket we assert non-concatenation form (`Armani` + `armani code`
are physically separate spans, even though substring-containment holds).
"""

from __future__ import annotations

import pytest

from ga_crawler.parsers.goldapple_microdata import GoldappleRawProduct, parse_pdp

# Canonical URLs from .planning/spikes/v1.1-brand-name-shapes/shape-table.md
# "SMOKE_URLs rotation" section (D-818).
STEREOTYPE_URL = "https://goldapple.kz/19000440474-stereotype-sago"
ARMANI_URL = "https://goldapple.kz/19000195723-armani-code"
GIVENCHY_BASELINE_URL = (
    "https://goldapple.kz/7681000001-givenchy-pour-homme-blue-label"
)


def test_armani_brand_and_name_are_separately_extracted(
    goldapple_pdp_html_live_armani: str,
) -> None:
    """Armani PDP: brand extracted from h1 .brand span as 'Armani'; name extracted
    from h1 .name span as 'armani code' — both ARE physically separate DOM nodes,
    so even though `brand.lower() in name.lower()` holds for this upstream-data
    bucket, the parser is no longer doing naive h1.text() deep-concat that v1.0
    produced ('Armaniarmani code').

    Pre-v1.1: parser returns name='Armaniarmani code' (concat from h1.text()).
    Post-v1.1: parser returns brand_raw='Armani', name='armani code'.
    """
    p = parse_pdp(goldapple_pdp_html_live_armani, ARMANI_URL)
    assert p is not None
    assert isinstance(p, GoldappleRawProduct)
    assert p.brand_raw.lower() == "armani", (
        f"expected brand_raw to be 'Armani' (case-insensitive), got {p.brand_raw!r}"
    )
    # The name must be 'armani code' — NOT 'Armaniarmani code' (the v1.0 concat bug).
    assert p.name.lower() == "armani code", (
        f"expected name to be 'armani code' (case-insensitive), got {p.name!r} "
        f"— v1.0 parser would return 'Armaniarmani code' here"
    )
    # Explicit anti-regression assertion: the v1.0 concat string must NOT appear.
    assert "armaniarmani" not in p.name.lower(), (
        f"INVARIANT VIOLATION (v1.0 concat regression): name {p.name!r}"
    )


def test_stereotype_brand_and_name_are_separately_extracted(
    goldapple_pdp_html_live_stereotype: str,
) -> None:
    """STEREOTYPE PDP: brand='Stereotype', name='SAĜO' (Esperanto-style Ĝ).

    Pre-v1.1: parser returns name='StereotypeSAĜO' (h1.text() concat).
    Post-v1.1: parser returns brand_raw='Stereotype', name='SAĜO'.
    """
    p = parse_pdp(goldapple_pdp_html_live_stereotype, STEREOTYPE_URL)
    assert p is not None
    assert p.brand_raw.lower() == "stereotype", (
        f"expected brand_raw='Stereotype', got {p.brand_raw!r}"
    )
    # name must come from h1 .name span ('SAĜO'), not h1.text() concat.
    assert p.name.lower() == "saĝo", (
        f"expected name to be 'SAĜO' (case-insensitive), got {p.name!r}"
    )
    # Invariant: brand must NOT appear as a prefix of name (the v1.0 concat bug).
    assert "stereotype" not in p.name.lower(), (
        f"INVARIANT VIOLATION: brand prefix found in name {p.name!r}"
    )


def test_invariant_canary_stereotype(
    goldapple_pdp_html_live_stereotype: str,
) -> None:
    """D-816 invariant: brand_raw.lower() MUST NOT be substring of name.lower()
    for the STEREOTYPE bucket (clean-separation shape). Currently FAILS pre-v1.1
    because parser returns name='StereotypeSAĜO' (brand+name concatenated)."""
    p = parse_pdp(goldapple_pdp_html_live_stereotype, STEREOTYPE_URL)
    assert p is not None
    assert p.brand_raw, "expected brand_raw to be non-empty"
    assert p.name, "expected name to be non-empty"
    assert p.brand_raw.lower() not in p.name.lower(), (
        f"INVARIANT VIOLATION: brand '{p.brand_raw}' contained in name '{p.name}'"
    )


def test_givenchy_baseline_clean_after_pivot(
    goldapple_pdp_html: str,
) -> None:
    """Backward-compat: existing Givenchy debug fixture also exhibits the v1.0
    concat bug (h1.text() returns 'GivenchyPOUR HOMME BLUE LABEL'). After
    pivoting to h1 .brand / .name spans, brand_raw='Givenchy', name='POUR HOMME
    BLUE LABEL' — clean separation.

    Note: the existing 60+ goldapple parser tests assert only `name` is
    non-empty and `len(name) > 5`; they do NOT pin a specific string. The
    pivot therefore preserves backward-compat in spirit (full surface coverage)
    while delivering the actual fix.
    """
    p = parse_pdp(goldapple_pdp_html, GIVENCHY_BASELINE_URL)
    assert p is not None
    assert p.brand_raw.lower() == "givenchy", (
        f"expected brand_raw='Givenchy', got {p.brand_raw!r}"
    )
    assert p.name, "name must be non-empty"
    # Invariant: brand must not appear in name after the fix.
    assert "givenchy" not in p.name.lower(), (
        f"INVARIANT VIOLATION (Givenchy baseline): brand prefix found in name {p.name!r}"
    )


@pytest.mark.parametrize(
    "fixture_name, url, expected_brand_substring",
    [
        ("goldapple_pdp_html", GIVENCHY_BASELINE_URL, "givenchy"),
        ("goldapple_pdp_html_live_stereotype", STEREOTYPE_URL, "stereotype"),
        # Armani is the upstream-data-redundancy bucket — the invariant
        # `brand not in name` legitimately fails (name='armani code' contains
        # 'armani'). For Armani we assert clean SEPARATION (no double-prefix
        # concat) — see test_armani_brand_and_name_are_separately_extracted.
    ],
)
def test_invariant_canary_across_clean_buckets(
    request, fixture_name: str, url: str, expected_brand_substring: str
) -> None:
    """D-816 invariant across the two CLEAN-SEPARATION buckets (Givenchy
    baseline + STEREOTYPE). The Armani bucket is excluded because its name
    legitimately contains the brand string ('armani code') — that case is
    covered by test_armani_brand_and_name_are_separately_extracted, which
    asserts non-CONCATENATION rather than non-CONTAINMENT.

    Per W0 spike MEMO §"Decisions" §4: D-816 canary is SOFTENED to log-only
    in production code because 2/30 PDPs legitimately fail it. The TEST
    enforces it strictly for the clean-separation buckets so regression to
    the v1.0 h1.text() concat behaviour is caught.
    """
    html = request.getfixturevalue(fixture_name)
    p = parse_pdp(html, url)
    assert p is not None
    assert expected_brand_substring in p.brand_raw.lower(), (
        f"brand_raw {p.brand_raw!r} missing expected substring "
        f"{expected_brand_substring!r}"
    )
    assert p.brand_raw.lower() not in p.name.lower(), (
        f"INVARIANT VIOLATION: brand '{p.brand_raw}' is contained in name '{p.name}'"
    )
