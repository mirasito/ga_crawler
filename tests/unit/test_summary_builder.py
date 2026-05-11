"""Unit tests for reporter.summary_builder — D-504 template freeze + golden file canary.

Source-locks the multi-line emoji caption shape via golden-file comparison
against tests/fixtures/reporter/expected-summary-text.txt (Plan 05-01).
"""

from __future__ import annotations

from pathlib import Path

from ga_crawler.reporter.summary_builder import (
    SUMMARY_TEMPLATE,
    TOP3_HEADER,
    TOP3_LINE,
    build_summary,
)


# ---------- Template source-lock canary ----------


def test_summary_template_contains_each_d504_line():
    """D-504 source-lock: every emoji-prefixed line is present in the constant."""
    assert "📊 Неделя" in SUMMARY_TEMPLATE
    assert "📦 viled:" in SUMMARY_TEMPLATE
    assert "🎯 Совпало:" in SUMMARY_TEMPLATE
    assert "🆕 Гэпы:" in SUMMARY_TEMPLATE
    assert "💸 Промо у goldapple:" in SUMMARY_TEMPLATE


def test_top3_header_constant():
    """D-504: top-3 section title verbatim."""
    assert TOP3_HEADER == "\n🔝 Топ-3 дельты (viled vs goldapple):"


def test_top3_line_template_placeholders_present():
    """Each numbered top-N row format must use the contract placeholders."""
    assert "{n}." in TOP3_LINE
    assert "{brand}" in TOP3_LINE
    assert "{name}" in TOP3_LINE
    assert "{volume}" in TOP3_LINE
    assert "{delta_pct}%" in TOP3_LINE


# ---------- Golden file canary (week-1 baseline) ----------


def _synthetic_inputs():
    """Mirror of conftest.synthetic_report_run state at summary-build time."""
    stats = {
        "viled.fetch_count": 3,
        "goldapple.fetch_count": 8,
        "match.count": 3,
        "match.rate": 60.0,
    }
    top3 = [
        {
            "brand_norm": "creed",
            "name_norm": "aventus",
            "volume_norm": "(100, ml, 1)",
            "price_delta_pct": -22.3,
        },
        {
            "brand_norm": "givenchy",
            "name_norm": "eau de parfum",
            "volume_norm": "(50, ml, 1)",
            "price_delta_pct": 15.5,
        },
        {
            "brand_norm": "dior",
            "name_norm": "sauvage",
            "volume_norm": "(100, ml, 1)",
            "price_delta_pct": 5.0,
        },
    ]
    return stats, top3


def test_build_summary_golden_file_canary():
    """D-504 source-lock: synthetic inputs reproduce the committed golden file
    byte-for-byte. Any drift in the template shape fails here.
    """
    stats, top3 = _synthetic_inputs()
    out = build_summary(
        stats=stats, top3=top3, gaps_count=5, promo_count=2, iso_week="2026-W19"
    )
    golden = Path("tests/fixtures/reporter/expected-summary-text.txt").read_text(encoding="utf-8")
    assert out == golden, (
        f"Summary drift detected.\n"
        f"--- expected ({len(golden)} bytes) ---\n{golden!r}\n"
        f"--- actual ({len(out)} bytes) ---\n{out!r}"
    )


# ---------- Branch coverage ----------


def test_build_summary_zero_match_omits_top3_header():
    """D-504: match_count=0 → Top-3 header omitted entirely."""
    out = build_summary(
        stats={
            "viled.fetch_count": 10,
            "goldapple.fetch_count": 20,
            "match.count": 0,
            "match.rate": 0.0,
        },
        top3=[],
        gaps_count=20,
        promo_count=3,
        iso_week="2026-W19",
    )
    assert "🔝 Топ-3" not in out
    assert "🎯 Совпало: 0 (0.0%)" in out


def test_build_summary_match_count_less_than_3():
    """match_count=1 with top3=[1 row] → Top-3 header present + 1 numbered row."""
    out = build_summary(
        stats={
            "viled.fetch_count": 5,
            "goldapple.fetch_count": 5,
            "match.count": 1,
            "match.rate": 20.0,
        },
        top3=[
            {
                "brand_norm": "creed",
                "name_norm": "aventus",
                "volume_norm": "(100, ml, 1)",
                "price_delta_pct": -22.3,
            }
        ],
        gaps_count=4,
        promo_count=1,
        iso_week="2026-W19",
    )
    assert "🔝 Топ-3" in out
    assert " 1. creed aventus" in out
    assert " 2." not in out
    assert " 3." not in out


def test_build_summary_top3_preserves_order():
    """build_summary does NOT re-sort; caller pre-sorts by ABS DESC."""
    out = build_summary(
        stats={
            "viled.fetch_count": 10,
            "goldapple.fetch_count": 10,
            "match.count": 5,
            "match.rate": 50.0,
        },
        top3=[
            {"brand_norm": "b3", "name_norm": "n3", "volume_norm": "v3", "price_delta_pct": 30.0},
            {"brand_norm": "b1", "name_norm": "n1", "volume_norm": "v1", "price_delta_pct": -25.0},
            {"brand_norm": "b2", "name_norm": "n2", "volume_norm": "v2", "price_delta_pct": 20.0},
        ],
        gaps_count=0,
        promo_count=0,
        iso_week="2026-W19",
    )
    idx_b3 = out.index("b3")
    idx_b1 = out.index("b1")
    idx_b2 = out.index("b2")
    assert idx_b3 < idx_b1 < idx_b2


def test_build_summary_missing_stats_default_to_zero():
    """Empty stats dict → counts=0, rate=0.0 (no KeyError); D-504 zero-match fallback."""
    out = build_summary(
        stats={},  # empty — all keys missing
        top3=[],
        gaps_count=0,
        promo_count=0,
        iso_week="2026-W19",
    )
    assert "viled: 0 SKU" in out
    assert "goldapple: 0 SKU" in out
    assert "Совпало: 0 (0.0%)" in out
    assert "Гэпы: 0" in out
    assert "Промо у goldapple: 0" in out
    assert "🔝 Топ-3" not in out


def test_build_summary_iso_week_in_title():
    out = build_summary(
        stats={}, top3=[], gaps_count=0, promo_count=0, iso_week="2026-W19"
    )
    assert "📊 Неделя 2026-W19 — viled vs goldapple" in out


def test_build_summary_uses_flat_stats_keys():
    """Pitfall 6: keys are 'match.count' not nested {'match':{'count':...}}."""
    flat = {
        "match.count": 42,
        "match.rate": 84.5,
        "viled.fetch_count": 100,
        "goldapple.fetch_count": 50,
    }
    out = build_summary(
        stats=flat, top3=[], gaps_count=0, promo_count=0, iso_week="2026-W01"
    )
    assert "Совпало: 42 (84.5%)" in out
    assert "viled: 100 SKU" in out
    assert "goldapple: 50 SKU" in out


def test_build_summary_slices_top3_to_three_when_more_provided():
    """Defensive: if caller passes >3 rows, output uses only first 3."""
    out = build_summary(
        stats={
            "viled.fetch_count": 10,
            "goldapple.fetch_count": 10,
            "match.count": 10,
            "match.rate": 100.0,
        },
        top3=[
            {"brand_norm": f"b{i}", "name_norm": f"n{i}", "volume_norm": "v", "price_delta_pct": float(i)}
            for i in range(1, 6)
        ],
        gaps_count=0,
        promo_count=0,
        iso_week="2026-W19",
    )
    assert " 1. b1" in out
    assert " 2. b2" in out
    assert " 3. b3" in out
    assert " 4." not in out
    assert " 5." not in out


# ---------- Integration smoke with excel_builder ----------


def test_summary_text_renders_in_excel_a1(openpyxl_workbook_reader):
    """Smoke: summary text passes through build_workbook → cell A1 verbatim."""
    import pandas as pd

    from ga_crawler.reporter.excel_builder import build_workbook

    stats, top3 = _synthetic_inputs()
    summary = build_summary(
        stats=stats, top3=top3, gaps_count=5, promo_count=2, iso_week="2026-W19"
    )
    out = build_workbook(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), summary)
    wb = openpyxl_workbook_reader(out)
    a1 = wb["Summary"]["A1"].value
    assert a1 == summary
