"""Phase 5 reporter Excel workbook builder.

Pure transform: DataFrames + summary_text → xlsx bytes. No filesystem I/O
(Plan 05-03 archive owns disk write).

Source:
  - 05-CONTEXT.md D-503 (Russian headers verbatim), D-505 (3-color CF colors
    + mid_value=0 parity anchor), D-506 (always 4 sheets even when empty),
    D-508 (CF on 2 sheets only)
  - 05-RESEARCH.md Patterns 1-5 + Pitfalls 1 (engine='xlsxwriter' explicit),
    2 (US-locale num_format), 3 (assert behavioral structure not exact colors)
    + Security Domain (formula injection)
  - 05-PATTERNS.md "src/ga_crawler/reporter/excel_builder.py" section
"""

from __future__ import annotations

import io
from typing import Any, Optional

import pandas as pd
from xlsxwriter.utility import xl_col_to_name


# ---------------------------------------------------------------------------
# D-503 — Russian column headers, source-locked. Operator changes via git PR.
# ---------------------------------------------------------------------------

PER_SKU_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "viled_price": "Цена viled, ₸",
    "viled_was_price": "Старая цена viled, ₸",
    "viled_url": "URL viled",
    "goldapple_price": "Цена goldapple, ₸",
    "goldapple_was_price": "Старая цена goldapple, ₸",
    "goldapple_url": "URL goldapple",
    "price_delta": "Дельта, ₸",
    "price_delta_pct": "Дельта, %",
}

GAPS_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "current_price": "Цена goldapple, ₸",
    "was_price": "Старая цена goldapple, ₸",
    "url": "URL goldapple",
}

PROMOS_HEADERS_RU: dict[str, str] = {
    "brand_norm": "Бренд",
    "name_norm": "Название",
    "volume_norm": "Объём",
    "current_price": "Цена goldapple, ₸",
    "was_price": "Старая цена goldapple, ₸",
    "discount_amount": "Скидка, ₸",
    "discount_pct": "Скидка, %",
    "url": "URL goldapple",
}


# Formula-injection guard (T-05-injection). Cells starting with these chars
# are prefixed with a single quote so Excel treats them as literal text.
_FORMULA_TRIGGER_CHARS: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value: Any) -> Any:
    """Prefix cell text starting with formula trigger chars with a single quote.

    Numeric and None values pass through unchanged. See 05-RESEARCH.md
    Security Domain row 1 (Excel formula injection).
    """
    if not isinstance(value, str):
        return value
    if len(value) == 0:
        return value
    if value[0] in _FORMULA_TRIGGER_CHARS:
        return "'" + value
    return value


def _sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply _sanitize_cell to every object-dtype column. Numeric columns untouched."""
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(_sanitize_cell)
    return out


def _format_for_column(col_name: str, workbook):
    """Map Russian header → xlsxwriter Format object. US-locale format strings
    per Pitfall 2 — Excel stores '#,##0' regardless of reader locale and
    renders per OS regional settings.

    Returns None for columns that need no special format (URL, brand, name, volume).
    """
    if col_name in (
        "Цена viled, ₸",
        "Старая цена viled, ₸",
        "Цена goldapple, ₸",
        "Старая цена goldapple, ₸",
        "Дельта, ₸",
        "Скидка, ₸",
    ):
        return workbook.add_format({"num_format": "#,##0 ₸"})
    if col_name in ("Дельта, %", "Скидка, %"):
        # Pre-scaled ×100 per D-405 — use '0.00' NOT '0.00%'.
        return workbook.add_format({"num_format": "0.00"})
    return None


def _apply_3_color_scale(worksheet, df_ru: pd.DataFrame, conditional_col: str) -> None:
    """D-505 + D-508. Anchor mid at 0 (parity)."""
    col_idx = list(df_ru.columns).index(conditional_col)
    col_letter = xl_col_to_name(col_idx)
    n_rows = len(df_ru)
    if n_rows == 0:
        return
    cf_range = f"{col_letter}2:{col_letter}{1 + n_rows}"
    worksheet.conditional_format(
        cf_range,
        {
            "type": "3_color_scale",
            "min_color": "#F8696B",  # red — viled more expensive (negative delta)
            "mid_color": "#FFEB84",  # yellow — near parity
            "max_color": "#63BE7B",  # green — viled cheaper (positive delta)
            "mid_type": "num",
            "mid_value": 0,  # D-505 — anchor at parity
        },
    )


def _apply_sheet_chrome(
    worksheet,
    workbook,
    df_ru: pd.DataFrame,
    conditional_col: Optional[str] = None,
) -> None:
    """Apply frozen top row + autofilter + autosized column widths + (optional) CF.

    D-506: empty DataFrames still get freeze_panes + autofilter on header row.
    D-508: only Per-SKU deltas and Goldapple promos get CF (pass conditional_col).
    Column width cap = 50 chars (Claude's Discretion).
    """
    n_rows, n_cols = df_ru.shape

    worksheet.freeze_panes(1, 0)

    # Autofilter: full data range if rows present, else header-only (D-506).
    if n_rows > 0:
        worksheet.autofilter(0, 0, n_rows, n_cols - 1)
    else:
        worksheet.autofilter(0, 0, 0, max(0, n_cols - 1))

    # Auto column widths with 50-char cap (min(...,50) clamp).
    for col_idx, col_name in enumerate(df_ru.columns):
        if n_rows > 0:
            col_data = df_ru[col_name].astype(str)
            max_content = max([len(str(col_name))] + [len(v) for v in col_data])
        else:
            max_content = len(str(col_name))
        width = min(max_content + 2, 50)  # +2 padding, cap at 50
        fmt = _format_for_column(col_name, workbook)
        if fmt is not None:
            worksheet.set_column(col_idx, col_idx, width, fmt)
        else:
            worksheet.set_column(col_idx, col_idx, width)

    if conditional_col and conditional_col in df_ru.columns and n_rows > 0:
        _apply_3_color_scale(worksheet, df_ru, conditional_col)


def build_workbook(
    matches_df: pd.DataFrame,
    gaps_df: pd.DataFrame,
    promos_df: pd.DataFrame,
    summary_text: str,
) -> bytes:
    """Build the 4-sheet xlsx workbook (D-506 always 4 sheets).

    Inputs:
      matches_df: columns from queries.PER_SKU_DELTAS_SQL (raw SQL names —
                  will be renamed via PER_SKU_HEADERS_RU)
      gaps_df:    columns from queries.ASSORTMENT_GAPS_SQL
      promos_df:  columns from queries.GOLDAPPLE_PROMOS_SQL
      summary_text: D-504 multi-line emoji caption (rendered in Summary cell A1)

    Returns: xlsx file body as bytes (consumer writes to disk via
    archive.write_atomic in Plan 05-03).

    Engine: xlsxwriter (Pitfall 1 — explicit; never rely on pandas default).
    """
    buffer = io.BytesIO()
    # Pitfall 1: ALWAYS pass engine="xlsxwriter" explicitly. Never rely on defaults.
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # -------- Sheet 1: Summary (text in A1; D-506 always present) --------
        # Empty placeholder DataFrame anchors the sheet; we write A1 cell-by-cell.
        pd.DataFrame().to_excel(writer, sheet_name="Summary", index=False, header=False)
        workbook = writer.book
        ws_summary = writer.sheets["Summary"]
        # text_wrap=True so the multi-line emoji block renders as wrapped text
        # instead of single-line concatenation (A5 assumption mitigation).
        wrap_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
        ws_summary.set_column(0, 0, 60, wrap_fmt)
        # 12 lines × ~16px ≈ 192px row height for the multi-line block.
        ws_summary.set_row(0, 192, wrap_fmt)
        ws_summary.write_string(0, 0, summary_text, wrap_fmt)
        # No freeze/autofilter on Summary — no tabular data.

        # -------- Sheet 2: Per-SKU deltas (CF on Дельта, %) --------
        matches_ru = _sanitize_dataframe(matches_df.rename(columns=PER_SKU_HEADERS_RU))
        matches_ru.to_excel(writer, sheet_name="Per-SKU deltas", index=False)
        _apply_sheet_chrome(
            writer.sheets["Per-SKU deltas"],
            workbook,
            matches_ru,
            conditional_col="Дельта, %",
        )

        # -------- Sheet 3: Assortment gaps (no CF per D-508) --------
        gaps_ru = _sanitize_dataframe(gaps_df.rename(columns=GAPS_HEADERS_RU))
        gaps_ru.to_excel(writer, sheet_name="Assortment gaps", index=False)
        _apply_sheet_chrome(writer.sheets["Assortment gaps"], workbook, gaps_ru)

        # -------- Sheet 4: Goldapple promos (CF on Скидка, %) --------
        promos_ru = _sanitize_dataframe(promos_df.rename(columns=PROMOS_HEADERS_RU))
        promos_ru.to_excel(writer, sheet_name="Goldapple promos", index=False)
        _apply_sheet_chrome(
            writer.sheets["Goldapple promos"],
            workbook,
            promos_ru,
            conditional_col="Скидка, %",
        )

    # On __exit__ pd.ExcelWriter calls workbook.close() which finalizes the xlsx
    # zip into buffer. buffer.getvalue() returns the complete byte string.
    return buffer.getvalue()


__all__ = [
    "PER_SKU_HEADERS_RU",
    "GAPS_HEADERS_RU",
    "PROMOS_HEADERS_RU",
    "build_workbook",
]
