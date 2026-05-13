"""Phase 8 PARSE-FIX-04 synthetic-regression integration test (Success Criteria #5).

Mirrors tests/integration/test_matcher_run.py engine/run setup style and uses
the same snapshot-planting shape as conftest.py `synthetic_report_run`.

Wires parser_drift_null_rate_gate into an in-memory pipeline: 10 goldapple
snapshots planted with 60% NULL volume_norm → orchestrator finalizes run with
status='failed' + parser_drift_failure_reason='parser_drift_null_volume_rate'.

Source: 08-CONTEXT.md D-815; 08-RESEARCH.md §"Synthetic Regression Test" lines
643-710; 08-PATTERNS.md lines 686-783.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text as _text

from ga_crawler.runner.gates import parser_drift_null_rate_gate
from ga_crawler.runner.stats import GoldappleStatsBuilder
from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "phase8_drift.db"
    init_db(db)
    return make_engine(db)


def _gold_snap(
    sku_id: str,
    *,
    volume_norm: str | None,
    brand: str = "Givenchy",
) -> dict:
    """Snapshot row builder mirroring conftest synthetic_report_run shape.

    `volume_norm=None` plants a NULL row (the regression mode); a non-None
    sentinel string like "(50, ml, 1)" plants a valid row.
    """
    return dict(
        sku_id=sku_id,
        url=f"https://goldapple.kz/{sku_id}",
        name="Test Product",
        brand=brand,
        brand_norm=brand.lower() if brand else "",
        name_norm="test product",
        volume_raw="50 мл" if volume_norm else None,
        volume_norm=volume_norm,
        multipack_flag=False,
        parse_error_flag=False,
        current_price=10000,
        was_price=None,
        currency="KZT",
        stock_state="IN_STOCK",
        scraped_at=datetime(2026, 5, 13, 14, 0, 0, tzinfo=timezone.utc),
    )


def test_synthetic_60pct_null_volume_triggers_drift_gate(engine) -> None:
    """Plant 10 goldapple snapshots — 6 with volume_norm=NULL, 4 valid.
    Compute null_rate via SQL; assert gate fails with volume-reason; assert
    end-state (run.status=='failed' AND stats reason populated). Success Criteria #5.
    """
    rw = SqliteRunWriter(engine)
    sw = SqliteSnapshotWriter(engine, batch_size=20)
    run_id = rw.create()

    snaps = [
        _gold_snap(f"g-{i:02d}", volume_norm=None) for i in range(6)  # 6 NULLs
    ] + [
        _gold_snap(f"g-{i:02d}", volume_norm="(50, ml, 1)") for i in range(6, 10)
    ]
    sw.append(run_id, "goldapple", snaps)

    # Compute null rates via SQL (mirrors RESEARCH.md §"Null-Rate Computation")
    with engine.begin() as conn:
        row = conn.execute(
            _text(
                "SELECT "
                "  AVG(CASE WHEN volume_norm IS NULL THEN 1.0 ELSE 0.0 END) AS v_null, "
                "  AVG(CASE WHEN brand IS NULL OR brand = '' THEN 1.0 ELSE 0.0 END) AS b_null "
                "FROM snapshots WHERE run_id = :rid AND retailer = 'goldapple'"
            ),
            {"rid": run_id},
        ).first()
    volume_null_rate = float(row.v_null or 0.0)
    brand_null_rate = float(row.b_null or 0.0)

    assert volume_null_rate == 0.6
    assert brand_null_rate == 0.0

    drift = parser_drift_null_rate_gate(
        volume_null_rate=volume_null_rate,
        brand_null_rate=brand_null_rate,
        threshold=0.5,
    )
    assert not drift.passed
    assert drift.failure_reason == "parser_drift_null_volume_rate"

    # Wire into stats + finalize (mirrors RESEARCH.md §"Orchestrator Wiring").
    # Pitfall 4: patch_stats rejects None — use "" sentinel for missing reason.
    builder = GoldappleStatsBuilder()
    builder.set("volume_null_rate", drift.volume_null_rate)
    builder.set("brand_null_rate", drift.brand_null_rate)
    builder.set(
        "parser_drift_failure_reason",
        drift.failure_reason if drift.failure_reason is not None else "",
    )
    rw.patch_stats(run_id, builder.delta)
    rw.fail(run_id, drift.failure_reason or "parser_drift_unknown")

    # Assert end-state: status=failed + reason in stats
    stats = rw.get_stats(run_id)
    assert stats["goldapple.parser_drift_failure_reason"] == (
        "parser_drift_null_volume_rate"
    )
    assert stats["goldapple.volume_null_rate"] == 0.6
    assert stats["goldapple.brand_null_rate"] == 0.0

    # Verify runs.status flipped to 'failed' via fail() path
    with engine.begin() as conn:
        run_status = conn.execute(
            _text("SELECT status, fail_reason FROM runs WHERE run_id = :rid"),
            {"rid": run_id},
        ).first()
    assert run_status.status == "failed"
    assert run_status.fail_reason == "parser_drift_null_volume_rate"
