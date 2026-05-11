"""Integration tests for run_reporter_phase — Phase 5 orchestrator.

Real on-disk SQLite (via synthetic_report_run conftest fixture) + real xlsx
output (BytesIO → write_atomic → tmp_path-rooted repo_root) + openpyxl
read-back assertions. Covers all 6 REPORT-XX + D-507 skip + D-510 overwrite
+ D-515 flag-only + Pitfall 6 single patch_stats invariants.

Source: 05-VALIDATION.md Task 5-04-01..05; 05-CONTEXT.md D-507/510/514/515.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ga_crawler.reporter.config import ReportConfig
from ga_crawler.runners.reporter_run import ReporterPhaseResult, run_reporter_phase


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers — the synthetic_report_run fixture finalizes the run as 'success'
# already (see conftest.py line 578). For D-507 skip tests we manually flip
# the status back to 'running' / 'failed' / DELETE the row.
# ---------------------------------------------------------------------------


def _set_status_running(engine, run_id):
    """Reset run row to 'running' state (D-507 in-progress case)."""
    from sqlalchemy import text as _text
    with engine.begin() as conn:
        conn.execute(
            _text(
                "UPDATE runs SET status='running', finished_at=NULL "
                "WHERE run_id=:rid"
            ),
            {"rid": run_id},
        )


# ---------------------------------------------------------------------------
# D-507 skip-gate tests (3 status cases)
# ---------------------------------------------------------------------------


def test_d507_skip_on_failed_run(synthetic_report_run):
    """Failed upstream → reporter skips with reason='failed_upstream'."""
    engine, run_writer, run_id, repo_root = synthetic_report_run
    # Fixture finalized as success; flip back to running first so fail() can act
    # (fail() has no status guard but we keep semantics clean).
    _set_status_running(engine, run_id)
    run_writer.fail(run_id, "goldapple_sanity_gate_failed")

    cfg = ReportConfig(output_dir="reports_d507_failed")
    result = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    assert result.status == "skipped"
    assert result.reason == "failed_upstream"

    # No xlsx written on skip path
    assert not (repo_root / cfg.output_dir / "2026-W19.xlsx").exists()

    # All 7 D-514 keys present in stats (skip-path patch_stats)
    stats = run_writer.get_stats(run_id)
    for k in (
        "report.xlsx_path",
        "report.xlsx_size_bytes",
        "report.summary_text",
        "report.sheet_row_counts",
        "report.skipped_reason",
        "report.size_guard_passed",
        "report.generated_at",
    ):
        assert k in stats, f"{k} missing after D-507 skip"
    assert stats["report.skipped_reason"] == "failed_upstream"
    assert stats["report.size_guard_passed"] is False
    assert stats["report.xlsx_path"] == ""
    assert stats["report.xlsx_size_bytes"] == 0


def test_d507_skip_on_running_run(synthetic_report_run):
    """Running upstream (still in progress) → skip with 'in_progress_upstream'."""
    engine, run_writer, run_id, repo_root = synthetic_report_run
    _set_status_running(engine, run_id)

    # Verify by reading current status via the REUSED helper from matcher
    from ga_crawler.matcher.strict_key import read_run_status
    assert read_run_status(engine, run_id) == "running"

    cfg = ReportConfig(output_dir="reports_d507_running")
    result = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    assert result.status == "skipped"
    assert result.reason == "in_progress_upstream"

    stats = run_writer.get_stats(run_id)
    assert stats["report.skipped_reason"] == "in_progress_upstream"
    assert not (repo_root / cfg.output_dir / "2026-W19.xlsx").exists()


def test_d507_skip_on_missing_run(synthetic_report_run):
    """Non-existent run_id → skip with 'missing_run_row'."""
    engine, run_writer, _, repo_root = synthetic_report_run
    cfg = ReportConfig(output_dir="reports_d507_missing")
    result = run_reporter_phase(
        run_id=99999, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    assert result.status == "skipped"
    assert result.reason == "missing_run_row"


# ---------------------------------------------------------------------------
# Success path tests — 4 sheets, Russian headers, CF, ISO filename
# ---------------------------------------------------------------------------


def test_xlsx_has_four_sheets_with_russian_headers(
    synthetic_report_run, openpyxl_workbook_reader
):
    """REPORT-01 + REPORT-03: 4 sheets + D-503 verbatim Russian column headers."""
    engine, run_writer, run_id, repo_root = synthetic_report_run
    # Fixture is already finalized 'success'.

    cfg = ReportConfig(output_dir="reports_t4")
    result = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    assert result.status == "success"
    assert isinstance(result, ReporterPhaseResult)

    xlsx_abs = repo_root / cfg.output_dir / "2026-W19.xlsx"
    assert xlsx_abs.exists()
    wb = openpyxl_workbook_reader(xlsx_abs)
    assert wb.sheetnames == [
        "Summary", "Per-SKU deltas", "Assortment gaps", "Goldapple promos",
    ]

    # D-503 verbatim header check on Per-SKU deltas (11 cols)
    ws = wb["Per-SKU deltas"]
    headers = [cell.value for cell in ws[1]]
    for required in (
        "Бренд", "Название", "Объём",
        "Цена viled, ₸", "Цена goldapple, ₸",
        "Дельта, ₸", "Дельта, %",
    ):
        assert required in headers, f"missing Russian header {required!r}"


def test_xlsx_cf_freeze_autofilter(synthetic_report_run, openpyxl_workbook_reader):
    """REPORT-02 + D-505 + D-508: CF on 2 sheets, freeze + autofilter on data sheets."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t5")
    run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    xlsx_abs = repo_root / cfg.output_dir / "2026-W19.xlsx"
    wb = openpyxl_workbook_reader(xlsx_abs)

    def _has_color_scale(ws):
        for rng in ws.conditional_formatting:
            for rule in ws.conditional_formatting[rng]:
                if rule.type == "colorScale":
                    return True
        return False

    # D-508 — CF on per-SKU deltas + goldapple promos only
    assert _has_color_scale(wb["Per-SKU deltas"]) is True
    assert _has_color_scale(wb["Goldapple promos"]) is True
    assert _has_color_scale(wb["Summary"]) is False
    assert _has_color_scale(wb["Assortment gaps"]) is False

    # Freeze + autofilter on data sheets
    for sheet in ("Per-SKU deltas", "Assortment gaps", "Goldapple promos"):
        assert wb[sheet].freeze_panes == "A2", f"{sheet} freeze_panes!=A2"
        assert wb[sheet].auto_filter.ref, f"{sheet} autofilter missing"


def test_filename_iso_week_and_overwrite(
    synthetic_report_run, openpyxl_workbook_reader
):
    """REPORT-05 + D-510: filename derives from started_at → 2026-W19; second call overwrites."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t6")
    r1 = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    xlsx_abs = repo_root / cfg.output_dir / "2026-W19.xlsx"
    assert xlsx_abs.exists()
    assert r1.xlsx_path.endswith("2026-W19.xlsx")
    assert r1.xlsx_size_bytes > 0

    # Second call — should overwrite without error
    r2 = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    assert r2.status == "success"
    assert xlsx_abs.exists()
    assert xlsx_abs.stat().st_size > 0
    # Same logical file (path + sheet counts must be identical)
    assert r1.xlsx_path == r2.xlsx_path
    assert r1.sheet_row_counts == r2.sheet_row_counts


# ---------------------------------------------------------------------------
# Stats namespace tests (D-514 + Pitfall 6 atomic merge)
# ---------------------------------------------------------------------------


def test_report_stats_namespace_keys(synthetic_report_run):
    """D-514: after success, all 7 report.* keys present alongside upstream namespaces."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t7")
    run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    stats = run_writer.get_stats(run_id)

    # All 7 D-514 keys
    for k in (
        "report.xlsx_path",
        "report.xlsx_size_bytes",
        "report.summary_text",
        "report.sheet_row_counts",
        "report.skipped_reason",
        "report.size_guard_passed",
        "report.generated_at",
    ):
        assert k in stats, f"D-514 key {k} missing"

    # Upstream namespaces preserved (Pitfall 6 atomic merge)
    assert "viled.fetch_count" in stats
    assert "goldapple.fetch_count" in stats
    assert "match.count" in stats
    assert "match.rate" in stats

    # Non-skip path: skipped_reason is empty sentinel (Pitfall 4 None-rejection)
    assert stats["report.skipped_reason"] == ""
    assert stats["report.size_guard_passed"] is True
    assert stats["report.xlsx_path"] == "reports_t7/2026-W19.xlsx"
    counts = stats["report.sheet_row_counts"]
    assert counts == {
        "summary": 1,
        "per_sku_deltas": 3,
        "assortment_gaps": 5,
        "goldapple_promos": 2,
    }


def test_single_patch_stats_call(synthetic_report_run):
    """Pitfall 6: success path makes EXACTLY ONE patch_stats call."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t10")
    with patch.object(
        run_writer, "patch_stats", wraps=run_writer.patch_stats
    ) as mocked:
        run_reporter_phase(
            run_id=run_id, engine=engine, run_writer=run_writer,
            repo_root=repo_root, config=cfg,
        )
    assert mocked.call_count == 1, (
        f"Pitfall 6 violation: patch_stats called {mocked.call_count} times "
        "(expected exactly 1)"
    )


def test_single_patch_stats_call_on_skip_path(synthetic_report_run):
    """Pitfall 6: skip path also makes EXACTLY ONE patch_stats call."""
    engine, run_writer, run_id, repo_root = synthetic_report_run
    _set_status_running(engine, run_id)
    run_writer.fail(run_id, "test")

    cfg = ReportConfig(output_dir="reports_t10b")
    with patch.object(
        run_writer, "patch_stats", wraps=run_writer.patch_stats
    ) as mocked:
        run_reporter_phase(
            run_id=run_id, engine=engine, run_writer=run_writer,
            repo_root=repo_root, config=cfg,
        )
    assert mocked.call_count == 1, (
        f"Skip-path Pitfall 6 violation: patch_stats called {mocked.call_count} times"
    )


# ---------------------------------------------------------------------------
# D-515 size-guard flag-only test
# ---------------------------------------------------------------------------


def test_size_guard_flag_does_not_fail_run(synthetic_report_run):
    """D-515: size > limit → flag false + log warning, but status='success' + xlsx persists."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t8")

    # Monkeypatch check_size_guard inside reporter_run module to force False return
    with patch(
        "ga_crawler.runners.reporter_run.check_size_guard",
        return_value=(False, 99_999_999),
    ):
        result = run_reporter_phase(
            run_id=run_id, engine=engine, run_writer=run_writer,
            repo_root=repo_root, config=cfg,
        )
    assert result.status == "success", "size guard MUST NOT fail run (D-515)"
    assert result.size_guard_passed is False
    assert result.xlsx_size_bytes >= 0

    # xlsx persists on disk
    xlsx_abs = repo_root / cfg.output_dir / "2026-W19.xlsx"
    assert xlsx_abs.exists(), "xlsx must persist after size_guard=False (D-515)"

    # Stats flag false
    stats = run_writer.get_stats(run_id)
    assert stats["report.size_guard_passed"] is False


# ---------------------------------------------------------------------------
# D-405 KPI preservation
# ---------------------------------------------------------------------------


def test_d405_kpi_verbatim_in_summary(synthetic_report_run):
    """D-405: reporter cites runs.stats.match.rate verbatim (no recompute)."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t9")
    result = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    # Fixture set match.count=3, match.rate=60.0
    assert "Совпало: 3 (60.0%)" in result.summary_text


# ---------------------------------------------------------------------------
# Formula injection end-to-end (T-05-injection)
# ---------------------------------------------------------------------------


def test_formula_injection_sanitized_e2e(
    synthetic_report_run, openpyxl_workbook_reader
):
    """T-05-injection: malicious brand_norm '=cmd|...' sanitized in produced xlsx."""
    from sqlalchemy import text as _text
    engine, run_writer, run_id, repo_root = synthetic_report_run

    # Plant a malicious match row by updating brand_norm to formula trigger.
    # Per Pitfall 9 the matches sheet JOINs back to snapshots for URLs, so we
    # update BOTH matches and snapshots brand_norm to keep the JOIN consistent.
    with engine.begin() as conn:
        conn.execute(
            _text(
                "UPDATE matches SET brand_norm='=cmd|/c calc' "
                "WHERE viled_sku='v-givenchy-edp-50' AND run_id=:rid"
            ),
            {"rid": run_id},
        )
        conn.execute(
            _text(
                "UPDATE snapshots SET brand_norm='=cmd|/c calc' "
                "WHERE sku_id IN ('v-givenchy-edp-50','g-givenchy-edp-50') "
                "AND run_id=:rid"
            ),
            {"rid": run_id},
        )

    cfg = ReportConfig(output_dir="reports_t12")
    run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    xlsx_abs = repo_root / cfg.output_dir / "2026-W19.xlsx"
    wb = openpyxl_workbook_reader(xlsx_abs)
    ws = wb["Per-SKU deltas"]
    # Find the row with sanitized formula trigger — leading single quote.
    found_sanitized = False
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        if row and row[0] and isinstance(row[0], str) and row[0].startswith("'="):
            found_sanitized = True
            break
    assert found_sanitized, "Excel formula injection NOT sanitized in xlsx"


# ---------------------------------------------------------------------------
# Idempotency (D-510)
# ---------------------------------------------------------------------------


def test_idempotent_re_run_same_state(synthetic_report_run):
    """D-510 + REPORT-05: second call → same xlsx_path/sheet counts/summary."""
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t11")
    r1 = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    r2 = run_reporter_phase(
        run_id=run_id, engine=engine, run_writer=run_writer,
        repo_root=repo_root, config=cfg,
    )
    assert r1.xlsx_path == r2.xlsx_path
    assert r1.summary_text == r2.summary_text
    assert r1.sheet_row_counts == r2.sheet_row_counts
    # xlsx zip may differ by ~ms-level timestamps in zip metadata; sizes
    # equal or near-equal (xlsxwriter zip is deterministic for same bytes).
    assert abs(r1.xlsx_size_bytes - r2.xlsx_size_bytes) <= 200


# ---------------------------------------------------------------------------
# Defensive: NULL started_at on success row → loud raise
# ---------------------------------------------------------------------------


def test_raises_on_null_started_at(synthetic_report_run):
    """Defensive: status='success' but started_at NULL → ValueError (data integrity bug).

    The DB schema enforces NOT NULL on `started_at` so this corruption case
    can only happen via a query path returning None (test path). Mock
    `read_run_started_at` to simulate the integrity bug surface; the
    defensive raise in `run_reporter_phase` is the canary.
    """
    engine, run_writer, run_id, repo_root = synthetic_report_run
    cfg = ReportConfig(output_dir="reports_t_null")
    with patch(
        "ga_crawler.runners.reporter_run.read_run_started_at",
        return_value=None,
    ):
        with pytest.raises(ValueError, match="started_at"):
            run_reporter_phase(
                run_id=run_id, engine=engine, run_writer=run_writer,
                repo_root=repo_root, config=cfg,
            )


# ---------------------------------------------------------------------------
# Reporter does NOT catch its own exceptions (DATA-05 boundary)
# ---------------------------------------------------------------------------


def test_uncaught_exception_propagates(synthetic_report_run):
    """Plan 02-05 DATA-05 invariant: reporter_run does NOT catch-and-fail.
    main_run owns try/except. We simulate a builder crash and assert it
    bubbles up rather than being swallowed into status='failed'.
    """
    engine, run_writer, run_id, repo_root = synthetic_report_run

    cfg = ReportConfig(output_dir="reports_t_exc")
    with patch(
        "ga_crawler.runners.reporter_run.build_workbook",
        side_effect=RuntimeError("simulated xlsxwriter crash"),
    ):
        with pytest.raises(RuntimeError, match="simulated xlsxwriter crash"):
            run_reporter_phase(
                run_id=run_id, engine=engine, run_writer=run_writer,
                repo_root=repo_root, config=cfg,
            )
