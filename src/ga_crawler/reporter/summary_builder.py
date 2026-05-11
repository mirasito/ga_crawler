"""Phase 5 reporter summary builder.

D-504 canonical template — week-1 baseline locked. Source-of-truth lives
here as module constants; changing requires git PR (mirror D-405 KPI formula
freeze pattern). The companion golden file
``tests/fixtures/reporter/expected-summary-text.txt`` is the regression
canary — any drift in this template shape vs the synthetic_report_run
fixture inputs fails ``test_build_summary_golden_file_canary``.

Pitfall 6 invariant: reads stats as dotted-flat dict (``stats["match.count"]``)
NOT nested. ``patch_stats`` writes flat-keyed JSON; ``get_stats`` reads flat-keyed.

Source: 05-CONTEXT.md D-504; 05-RESEARCH.md Pattern 6 + Pitfall 6 + Pitfall 11;
05-PATTERNS.md "src/ga_crawler/reporter/summary_builder.py" section.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# D-504 — canonical template. Source-locked. Changes require git PR + the
# regression test test_build_summary_golden_file_canary update + golden file
# regeneration.
# ---------------------------------------------------------------------------

SUMMARY_TEMPLATE = """\
📊 Неделя {iso_week} — viled vs goldapple

📦 viled: {viled_count} SKU  •  goldapple: {goldapple_count} SKU
🎯 Совпало: {match_count} ({match_rate}%)
🆕 Гэпы: {gaps_count} SKU у goldapple без viled-пары
💸 Промо у goldapple: {promo_count} SKU
"""

# D-504: Top-3 header is OMITTED entirely when match_count == 0.
# When match_count in {1, 2} we still emit the header and list what we have.
TOP3_HEADER = "\n🔝 Топ-3 дельты (viled vs goldapple):"
TOP3_LINE = " {n}. {brand} {name} {volume}: {delta_pct}%"


def build_summary(
    *,
    stats: dict[str, Any],
    top3: list[dict],
    gaps_count: int,
    promo_count: int,
    iso_week: str,
) -> str:
    """D-504 canonical template.

    Args:
      stats: flat dot-keyed dict (Pitfall 6). Reads ``viled.fetch_count``,
             ``goldapple.fetch_count``, ``match.count``, ``match.rate``.
             Missing keys default to 0 / 0.0 — no KeyError.
      top3: list of dicts with keys ``brand_norm`` / ``name_norm`` /
            ``volume_norm`` / ``price_delta_pct``, pre-sorted by
            ``ABS(price_delta_pct) DESC`` by caller. Sliced to ≤3.
      gaps_count: row count of Assortment gaps sheet.
      promo_count: row count of Goldapple promos sheet.
      iso_week: filename stem (e.g. "2026-W19").

    Returns:
      Multi-line emoji caption (D-504 verbatim shape).
    """
    viled_count = stats.get("viled.fetch_count", 0)
    goldapple_count = stats.get("goldapple.fetch_count", 0)
    match_count = stats.get("match.count", 0)
    match_rate = stats.get("match.rate", 0.0)

    body = SUMMARY_TEMPLATE.format(
        iso_week=iso_week,
        viled_count=viled_count,
        goldapple_count=goldapple_count,
        match_count=match_count,
        match_rate=match_rate,
        gaps_count=gaps_count,
        promo_count=promo_count,
    )

    # D-504: omit Top-3 header entirely if match_count == 0.
    if match_count > 0 and top3:
        body += TOP3_HEADER + "\n"
        for n, row in enumerate(top3[:3], start=1):
            body += (
                TOP3_LINE.format(
                    n=n,
                    brand=row["brand_norm"],
                    name=row["name_norm"],
                    volume=row["volume_norm"],
                    delta_pct=row["price_delta_pct"],
                )
                + "\n"
            )
    return body


__all__ = [
    "SUMMARY_TEMPLATE",
    "TOP3_HEADER",
    "TOP3_LINE",
    "build_summary",
]
