"""Unit tests for reporter.excel_builder — D-503 headers + D-505/D-508 CF +
D-506 always-4-sheets + T-05-injection sanitization.

Uses openpyxl_workbook_reader fixture for read-back assertions. Per Pitfall 3
we assert *behavioral structure* (sheet exists, freeze coord, CF rule type)
not exact internal representation (hex colors).
"""

from __future__ import annotations

import inspect
import io

import pandas as pd
import pytest

from ga_crawler.reporter.excel_builder import (
    GAPS_HEADERS_RU,
    PER_SKU_HEADERS_RU,
    PROMOS_HEADERS_RU,
    _apply_sheet_chrome,
    _format_for_column,
    _sanitize_cell,
    build_workbook,
)


# ---------- Header constants (D-503 verbatim) ----------


def test_russian_headers_match_d503():
    """D-503 source-lock: each Russian label is exactly as specified in CONTEXT."""
    assert PER_SKU_HEADERS_RU["brand_norm"] == "Бренд"
    assert PER_SKU_HEADERS_RU["name_norm"] == "Название"
    assert PER_SKU_HEADERS_RU["volume_norm"] == "Объём"
    assert PER_SKU_HEADERS_RU["viled_price"] == "Цена viled, ₸"
    assert PER_SKU_HEADERS_RU["viled_was_price"] == "Старая цена viled, ₸"
    assert PER_SKU_HEADERS_RU["viled_url"] == "URL viled"
    assert PER_SKU_HEADERS_RU["goldapple_price"] == "Цена goldapple, ₸"
    assert PER_SKU_HEADERS_RU["goldapple_was_price"] == "Старая цена goldapple, ₸"
    assert PER_SKU_HEADERS_RU["goldapple_url"] == "URL goldapple"
    assert PER_SKU_HEADERS_RU["price_delta"] == "Дельта, ₸"
    assert PER_SKU_HEADERS_RU["price_delta_pct"] == "Дельта, %"
    # gaps
    assert GAPS_HEADERS_RU["current_price"] == "Цена goldapple, ₸"
    assert GAPS_HEADERS_RU["was_price"] == "Старая цена goldapple, ₸"
    assert GAPS_HEADERS_RU["url"] == "URL goldapple"
    # promos
    assert PROMOS_HEADERS_RU["discount_amount"] == "Скидка, ₸"
    assert PROMOS_HEADERS_RU["discount_pct"] == "Скидка, %"


# ---------- Formula-injection sanitization (T-05-injection) ----------


@pytest.mark.parametrize(
    "trigger_char",
    ["=", "+", "-", "@", "\t", "\r"],
)
def test_formula_injection_sanitized_each_trigger_char(trigger_char):
    """T-05-injection: cells starting with formula-trigger char get a single-quote prefix."""
    payload = f"{trigger_char}cmd|/c calc"
    out = _sanitize_cell(payload)
    assert out == "'" + payload


def test_formula_injection_normal_text_unchanged():
    assert _sanitize_cell("givenchy eau de parfum") == "givenchy eau de parfum"
    assert _sanitize_cell(50000) == 50000
    assert _sanitize_cell(None) is None
    assert _sanitize_cell("") == ""


# ---------- Number formats (Pitfall 2 US-locale) ----------


def test_format_for_column_kzt_currency_returns_format():
    """Pitfall 2: '#,##0 ₸' US-locale storage."""
    import xlsxwriter as _x

    wb = _x.Workbook(io.BytesIO())
    fmt = _format_for_column("Цена viled, ₸", wb)
    assert fmt is not None
    # xlsxwriter Format stores num_format on the .num_format attribute.
    assert getattr(fmt, "num_format", None) == "#,##0 ₸"


def test_format_for_column_percent_returns_format():
    import xlsxwriter as _x

    wb = _x.Workbook(io.BytesIO())
    fmt = _format_for_column("Дельта, %", wb)
    assert fmt is not None
    # Per D-405 pre-scaling: '0.00' not '0.00%'.
    assert getattr(fmt, "num_format", None) == "0.00"


def test_format_for_column_url_returns_none():
    import xlsxwriter as _x

    wb = _x.Workbook(io.BytesIO())
    assert _format_for_column("URL viled", wb) is None
    assert _format_for_column("Бренд", wb) is None


# ---------- Build workbook with synthetic data ----------


@pytest.fixture
def matches_df_synthetic():
    return pd.DataFrame(
        [
            {
                "brand_norm": "creed",
                "name_norm": "aventus",
                "volume_norm": "(100, ml, 1)",
                "viled_price": 180000,
                "viled_was_price": None,
                "viled_url": "https://viled.kz/p/creed",
                "goldapple_price": 139860,
                "goldapple_was_price": None,
                "goldapple_url": "https://goldapple.kz/p/creed",
                "price_delta": -40140,
                "price_delta_pct": -22.30,
            },
            {
                "brand_norm": "givenchy",
                "name_norm": "eau de parfum",
                "volume_norm": "(50, ml, 1)",
                "viled_price": 50000,
                "viled_was_price": None,
                "viled_url": "https://viled.kz/p/givenchy",
                "goldapple_price": 57750,
                "goldapple_was_price": None,
                "goldapple_url": "https://goldapple.kz/p/givenchy",
                "price_delta": 7750,
                "price_delta_pct": 15.50,
            },
        ]
    )


@pytest.fixture
def gaps_df_synthetic():
    return pd.DataFrame(
        [
            {
                "brand_norm": "chanel",
                "name_norm": "no 5",
                "volume_norm": "(50, ml, 1)",
                "current_price": 70000,
                "was_price": None,
                "url": "https://goldapple.kz/p/chanel",
            }
        ]
    )


@pytest.fixture
def promos_df_synthetic():
    return pd.DataFrame(
        [
            {
                "brand_norm": "tom ford",
                "name_norm": "noir",
                "volume_norm": "(50, ml, 1)",
                "current_price": 80000,
                "was_price": 100000,
                "discount_amount": 20000,
                "discount_pct": 20.00,
                "url": "https://goldapple.kz/p/tom-ford-noir",
            }
        ]
    )


def test_build_workbook_returns_bytes(
    matches_df_synthetic, gaps_df_synthetic, promos_df_synthetic
):
    out = build_workbook(
        matches_df_synthetic,
        gaps_df_synthetic,
        promos_df_synthetic,
        summary_text="📊 Неделя 2026-W19 — viled vs goldapple",
    )
    assert isinstance(out, bytes)
    assert len(out) > 1000  # xlsx has nontrivial size


def test_build_workbook_has_four_sheets_in_order(
    matches_df_synthetic,
    gaps_df_synthetic,
    promos_df_synthetic,
    openpyxl_workbook_reader,
):
    out = build_workbook(
        matches_df_synthetic,
        gaps_df_synthetic,
        promos_df_synthetic,
        summary_text="📊 test",
    )
    wb = openpyxl_workbook_reader(out)
    assert wb.sheetnames == [
        "Summary",
        "Per-SKU deltas",
        "Assortment gaps",
        "Goldapple promos",
    ]


def test_summary_a1_contains_text(
    matches_df_synthetic,
    gaps_df_synthetic,
    promos_df_synthetic,
    openpyxl_workbook_reader,
):
    summary = "📊 Неделя 2026-W19 — viled vs goldapple\n\n📦 viled: 3"
    out = build_workbook(matches_df_synthetic, gaps_df_synthetic, promos_df_synthetic, summary)
    wb = openpyxl_workbook_reader(out)
    a1_value = wb["Summary"]["A1"].value
    assert a1_value is not None
    assert "📊 Неделя" in a1_value
    assert "viled: 3" in a1_value


def test_d506_empty_dataframes_still_produce_4_sheets(openpyxl_workbook_reader):
    """D-506: reporter always builds all 4 sheets even with empty inputs."""
    out = build_workbook(
        pd.DataFrame(columns=list(PER_SKU_HEADERS_RU.keys())),
        pd.DataFrame(columns=list(GAPS_HEADERS_RU.keys())),
        pd.DataFrame(columns=list(PROMOS_HEADERS_RU.keys())),
        summary_text="",
    )
    wb = openpyxl_workbook_reader(out)
    assert wb.sheetnames == [
        "Summary",
        "Per-SKU deltas",
        "Assortment gaps",
        "Goldapple promos",
    ]


def test_freeze_panes_on_data_sheets(
    matches_df_synthetic,
    gaps_df_synthetic,
    promos_df_synthetic,
    openpyxl_workbook_reader,
):
    out = build_workbook(matches_df_synthetic, gaps_df_synthetic, promos_df_synthetic, "x")
    wb = openpyxl_workbook_reader(out)
    for sheet_name in ("Per-SKU deltas", "Assortment gaps", "Goldapple promos"):
        assert wb[sheet_name].freeze_panes == "A2", f"{sheet_name} freeze_panes mismatch"


def test_autofilter_on_data_sheets(
    matches_df_synthetic,
    gaps_df_synthetic,
    promos_df_synthetic,
    openpyxl_workbook_reader,
):
    out = build_workbook(matches_df_synthetic, gaps_df_synthetic, promos_df_synthetic, "x")
    wb = openpyxl_workbook_reader(out)
    for sheet_name in ("Per-SKU deltas", "Assortment gaps", "Goldapple promos"):
        ref = wb[sheet_name].auto_filter.ref
        assert ref is not None and len(ref) > 0, f"{sheet_name} autofilter ref missing"


def test_cf_only_on_per_sku_deltas_and_promos(
    matches_df_synthetic,
    gaps_df_synthetic,
    promos_df_synthetic,
    openpyxl_workbook_reader,
):
    """D-508: CF on Per-SKU deltas + Goldapple promos only. NOT on Summary or Assortment gaps."""
    out = build_workbook(matches_df_synthetic, gaps_df_synthetic, promos_df_synthetic, "x")
    wb = openpyxl_workbook_reader(out)

    def _has_color_scale(ws) -> bool:
        for cf_range in ws.conditional_formatting:
            rules = ws.conditional_formatting[cf_range]
            for r in rules:
                if r.type == "colorScale":
                    return True
        return False

    assert _has_color_scale(wb["Per-SKU deltas"]) is True
    assert _has_color_scale(wb["Goldapple promos"]) is True
    assert _has_color_scale(wb["Summary"]) is False
    assert _has_color_scale(wb["Assortment gaps"]) is False


def test_formula_injection_persists_through_workbook(openpyxl_workbook_reader):
    """T-05-injection end-to-end: malicious string sanitized in final xlsx."""
    matches = pd.DataFrame(
        [
            {
                "brand_norm": "=cmd|/c calc",  # formula trigger at start
                "name_norm": "+attack",
                "volume_norm": "@bad",
                "viled_price": 100,
                "viled_was_price": None,
                "viled_url": "https://x",
                "goldapple_price": 200,
                "goldapple_was_price": None,
                "goldapple_url": "https://y",
                "price_delta": 100,
                "price_delta_pct": 100.0,
            }
        ]
    )
    out = build_workbook(matches, pd.DataFrame(), pd.DataFrame(), "x")
    wb = openpyxl_workbook_reader(out)
    ws = wb["Per-SKU deltas"]
    a2 = ws["A2"].value
    b2 = ws["B2"].value
    c2 = ws["C2"].value
    assert a2.startswith("'="), f"A2={a2!r} not sanitized"
    assert b2.startswith("'+"), f"B2={b2!r} not sanitized"
    assert c2.startswith("'@"), f"C2={c2!r} not sanitized"


def test_was_price_null_renders_empty(openpyxl_workbook_reader):
    """Claude's Discretion: was_price IS NULL → empty cell (not '—' / '0' / 'N/A')."""
    matches = pd.DataFrame(
        [
            {
                "brand_norm": "givenchy",
                "name_norm": "x",
                "volume_norm": "(50, ml, 1)",
                "viled_price": 100,
                "viled_was_price": None,
                "viled_url": "u",
                "goldapple_price": 200,
                "goldapple_was_price": None,
                "goldapple_url": "g",
                "price_delta": 100,
                "price_delta_pct": 100.0,
            }
        ]
    )
    out = build_workbook(matches, pd.DataFrame(), pd.DataFrame(), "x")
    wb = openpyxl_workbook_reader(out)
    ws = wb["Per-SKU deltas"]
    # viled_was_price = E (5th col); goldapple_was_price = H (8th col)
    assert ws["E2"].value in (None, "")
    assert ws["H2"].value in (None, "")


def test_column_widths_capped_at_50():
    """Claude's Discretion: max width = 50 chars. xlsxwriter set_column doesn't
    expose a read-back API, so we test indirectly via source inspection of the
    helper's clamp constant.
    """
    long_val = "x" * 100
    df = pd.DataFrame({"brand_norm": [long_val] * 5})
    import xlsxwriter as _x

    wb = _x.Workbook(io.BytesIO())
    ws = wb.add_worksheet("test")
    df_ru = df.rename(columns={"brand_norm": "Бренд"})
    _apply_sheet_chrome(ws, wb, df_ru)
    # The regression value is the constant in the source file.
    from ga_crawler.reporter import excel_builder as eb

    src = inspect.getsource(eb._apply_sheet_chrome)
    assert "50" in src and "min(" in src, "width-cap constant missing from source"


def test_cf_mid_value_is_zero_anchor():
    """D-505: 3-color-scale must have mid_value=0 (parity anchor). Without this,
    a sheet of all-positive deltas would show red at lowest positive — misleading.
    Assertion via source inspection (xlsxwriter doesn't round-trip the rule shape
    through openpyxl with full fidelity per Pitfall 3).
    """
    from ga_crawler.reporter import excel_builder as eb

    src = inspect.getsource(eb)
    assert '"mid_value": 0' in src or "'mid_value': 0" in src
    assert '"mid_type": "num"' in src or "'mid_type': 'num'" in src


def test_engine_explicit_xlsxwriter():
    """Pitfall 1: ExcelWriter MUST be constructed with engine='xlsxwriter' explicitly."""
    from ga_crawler.reporter import excel_builder as eb

    src = inspect.getsource(eb.build_workbook)
    assert 'engine="xlsxwriter"' in src or "engine='xlsxwriter'" in src
