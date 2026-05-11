"""Smoke tests for the Phase 5 conftest fixtures (synthetic_report_run +
tmp_reports_dir + openpyxl_workbook_reader).

These are temporary canaries to lock the fixture contract Plan 05-01
exposes. Real consumption happens in Plans 05-02 / 05-03 / 05-04 / 05-05;
this file just verifies the shape so any drift surfaces immediately.

Source: 05-VALIDATION.md Wave 0 Requirements; 05-01-PLAN.md Task 3 behavior tests.
"""

from __future__ import annotations

import io
from pathlib import Path

import xlsxwriter
from sqlalchemy import text


def test_tmp_reports_dir_exists(tmp_reports_dir):
    assert isinstance(tmp_reports_dir, Path)
    assert tmp_reports_dir.exists()
    assert tmp_reports_dir.is_dir()
    assert tmp_reports_dir.name == "reports"


def test_openpyxl_workbook_reader_opens_bytes(openpyxl_workbook_reader):
    # Build a minimal xlsx in memory with xlsxwriter; read back with the fixture.
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("Summary")
    ws.write(0, 0, "hello")
    wb.close()

    workbook = openpyxl_workbook_reader(buf.getvalue())
    assert "Summary" in workbook.sheetnames
    assert workbook["Summary"]["A1"].value == "hello"


def test_synthetic_report_run_shape(synthetic_report_run):
    engine, run_writer, run_id, repo_root = synthetic_report_run

    # Run row exists and is success
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, started_at FROM runs WHERE run_id = :rid"),
            {"rid": run_id},
        ).one()
    assert row.status == "success"

    # 3 viled + 8 goldapple snapshots
    with engine.connect() as conn:
        viled_count = conn.execute(
            text("SELECT COUNT(*) FROM snapshots WHERE run_id=:rid AND retailer='viled'"),
            {"rid": run_id},
        ).scalar()
        gold_count = conn.execute(
            text("SELECT COUNT(*) FROM snapshots WHERE run_id=:rid AND retailer='goldapple'"),
            {"rid": run_id},
        ).scalar()
    assert viled_count == 3
    assert gold_count == 8

    # 3 matches with known delta_pct values (Top-3 = creed > givenchy > dior by ABS)
    with engine.connect() as conn:
        matches = conn.execute(
            text(
                "SELECT brand_norm, name_norm, price_delta_pct FROM matches "
                "WHERE run_id=:rid ORDER BY ABS(price_delta_pct) DESC"
            ),
            {"rid": run_id},
        ).all()
    assert len(matches) == 3
    assert matches[0].brand_norm == "creed"
    assert matches[0].price_delta_pct == -22.30
    assert matches[1].brand_norm == "givenchy"
    assert matches[1].price_delta_pct == 15.50
    assert matches[2].brand_norm == "dior"
    assert matches[2].price_delta_pct == 5.00

    # 2 goldapple promos (was_price > current_price)
    with engine.connect() as conn:
        promo_count = conn.execute(
            text(
                "SELECT COUNT(*) FROM snapshots "
                "WHERE run_id=:rid AND retailer='goldapple' "
                "AND was_price IS NOT NULL AND was_price > current_price"
            ),
            {"rid": run_id},
        ).scalar()
    assert promo_count == 2

    # runs.stats pre-populated with upstream namespaces
    stats = run_writer.get_stats(run_id)
    assert stats["viled.fetch_count"] == 3
    assert stats["goldapple.fetch_count"] == 8
    assert stats["match.count"] == 3
    assert stats["match.rate"] == 60.0


def test_golden_summary_file_exists():
    p = Path("tests/fixtures/reporter/expected-summary-text.txt")
    assert p.exists(), f"missing golden file at {p}"
    text = p.read_text(encoding="utf-8")
    assert "Неделя 2026-W19" in text
    assert "Совпало" in text
    assert "Топ-3" in text
    assert "creed aventus" in text
    # Trailing newline
    assert text.endswith("\n")
