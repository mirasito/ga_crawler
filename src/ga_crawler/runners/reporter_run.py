"""Phase 5 reporter orchestrator -- `run_reporter_phase()`.

Sync 7-step pipeline mirroring `runners/matcher_run.py` shape minus the
SQL-side derivation layers (reporter is pure derivation over already-
persisted matches + snapshots + runs.stats). Composes Plan 05-01
(ReportConfig + ReportStatsBuilder), Plan 05-02 (queries + excel_builder +
summary_builder), and Plan 05-03 (archive primitives).

Steps:
  1. D-507 status-gate (REUSE matcher.strict_key.read_run_status, no re-impl)
  2. Read upstream stats (viled.* + goldapple.* + match.* -- flat dot-keyed per Pitfall 6)
  3. Read matches DataFrame (queries.read_matches_for_run -- JOIN-back for URLs per Pitfall 9)
  4. Read gaps DataFrame + promos DataFrame + top-3 + started_at
  5. Pure builders: summary_builder.build_summary + excel_builder.build_workbook
  6. archive.derive_filename + archive.write_atomic + archive.check_size_guard
  7. SINGLE atomic patch_stats with all 7 D-514 keys (Pitfall 6); return ReporterPhaseResult

DATA-05 lifecycle: reporter_run does NOT catch its own exceptions. main_run
(Plan 05-05) owns try/except. Uncaught reporter exception -> run_writer.fail
via outer block -- keeps reporter testable and contract-clean.

Source: 05-CONTEXT.md D-507, D-510, D-511, D-514, D-515; 05-RESEARCH.md
reporter_run.py code block; 05-PATTERNS.md "runners/reporter_run.py" section.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from ga_crawler.interfaces import RunWriterProtocol
from ga_crawler.matcher.strict_key import read_run_status  # D-507 REUSE of D-411 helper
from ga_crawler.reporter.archive import (
    check_size_guard,
    derive_filename,
    write_atomic,
)
from ga_crawler.reporter.config import ReportConfig
from ga_crawler.reporter.excel_builder import build_workbook
from ga_crawler.reporter.queries import (
    read_gaps_for_run,
    read_matches_for_run,
    read_promos_for_run,
    read_run_started_at,
    read_top_n_deltas,
)
from ga_crawler.reporter.stats import ReportStatsBuilder
from ga_crawler.reporter.summary_builder import build_summary

log = structlog.get_logger(__name__)


@dataclass
class ReporterPhaseResult:
    """Outcome of run_reporter_phase."""

    status: str  # "success" | "skipped"
    xlsx_path: Optional[str] = None
    xlsx_size_bytes: int = 0
    summary_text: str = ""
    sheet_row_counts: dict = field(default_factory=dict)
    size_guard_passed: bool = True
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)


def _skip_path(
    *,
    run_id: int,
    upstream_status: Optional[str],
    run_writer: RunWriterProtocol,
) -> ReporterPhaseResult:
    """D-507 skip-gate body. All 7 D-514 keys patched with skip-values.

    Single `patch_stats` call (Pitfall 6) -- no read-modify-write.
    """
    builder = ReportStatsBuilder()
    if upstream_status == "failed":
        reason = "failed_upstream"
    elif upstream_status == "running":
        reason = "in_progress_upstream"
    elif upstream_status is None:
        reason = "missing_run_row"
    else:
        reason = f"unexpected_upstream:{upstream_status}"

    builder.set("xlsx_path", "")
    builder.set("xlsx_size_bytes", 0)
    builder.set("summary_text", "")
    builder.set("sheet_row_counts", {})
    builder.set("skipped_reason", reason)
    builder.set("size_guard_passed", False)  # trivially false on skip (no xlsx)
    builder.set("generated_at", datetime.now(timezone.utc).isoformat())

    # Pitfall 6: single atomic patch_stats -- D-507 path still patches once.
    run_writer.patch_stats(run_id, dict(builder.delta))

    log.warning(
        "report_skipped_failed_run",
        run_id=run_id,
        upstream_status=upstream_status,
        reason=reason,
    )
    return ReporterPhaseResult(
        status="skipped",
        reason=reason,
        stats_delta=dict(builder.delta),
    )


def run_reporter_phase(
    *,
    run_id: int,
    engine,
    run_writer: RunWriterProtocol,
    repo_root: Path,
    config: ReportConfig,
) -> ReporterPhaseResult:
    """Execute the full Phase 5 reporter.

    Args:
      run_id: existing runs row id (created by caller; reporter does NOT create).
      engine: SQLAlchemy engine -- direct SQL access for matches/snapshots reads.
      run_writer: RunWriterProtocol -- Phase 2 SqliteRunWriter in prod.
      repo_root: Path to repo root -- used to anchor `output_dir` relative path.
      config: ReportConfig -- output_dir, size_limit_mb, top_n_deltas, timezone (D-516).

    Returns:
      ReporterPhaseResult -- status='success' or 'skipped'. Never 'failed' from
      this function directly (DATA-05 boundary -- main_run catches exceptions).

    Source-locked invariants:
      - D-507 status-gate via matcher.strict_key.read_run_status (REUSED)
      - D-405 KPI: summary_builder reads stats['match.rate'] verbatim (no recompute)
      - Pitfall 6: single patch_stats call carrying all 7 D-514 keys
      - D-515: size-exceed sets flag, does NOT raise; xlsx persists
    """
    started = time.perf_counter()
    builder = ReportStatsBuilder()

    # ---- Step 1: D-507 status-gate (REUSED from D-411 matcher) ----
    status = read_run_status(engine, run_id)
    if status != "success":
        return _skip_path(
            run_id=run_id, upstream_status=status, run_writer=run_writer
        )

    log.info("reporter_phase_start", run_id=run_id, output_dir=config.output_dir)

    # ---- Step 2: read upstream stats for summary (Pitfall 6 flat keys) ----
    upstream_stats = run_writer.get_stats(run_id) or {}

    # ---- Step 3: read matches DataFrame (Pitfall 9 JOIN-back for URLs) ----
    matches_df = read_matches_for_run(engine, run_id)

    # ---- Step 4: read gaps + promos + top-3 + started_at ----
    gaps_df = read_gaps_for_run(engine, run_id)
    promos_df = read_promos_for_run(engine, run_id)
    top3 = read_top_n_deltas(engine, run_id, n=config.top_n_deltas)
    started_at = read_run_started_at(engine, run_id)
    if started_at is None:
        # Defensive: D-507 status-gate already confirmed run row exists; this
        # branch shouldn't fire in practice but raises a clear error if started_at
        # is somehow NULL (data integrity bug, not a reporter contract issue).
        raise ValueError(
            f"runs.started_at is NULL for run_id={run_id}; "
            "cannot derive ISO-week filename (DATA-05 invariant)"
        )

    # ---- Step 5: pure builders (no I/O) ----
    iso_week_stem = derive_filename(started_at, tz_name=config.timezone).removesuffix(".xlsx")
    summary_text = build_summary(
        stats=upstream_stats,
        top3=top3,
        gaps_count=len(gaps_df),
        promo_count=len(promos_df),
        iso_week=iso_week_stem,
    )
    xlsx_bytes = build_workbook(matches_df, gaps_df, promos_df, summary_text)

    # ---- Step 6: archive (filename -> atomic write -> size guard) ----
    filename = derive_filename(started_at, tz_name=config.timezone)
    output_dir = Path(config.output_dir)
    target_path = (repo_root / output_dir / filename).resolve()

    # Defense-in-depth path containment check (T-05-path-traversal):
    repo_root_resolved = repo_root.resolve()
    try:
        target_path.relative_to(repo_root_resolved)
    except ValueError as e:
        raise ValueError(
            f"target_path {target_path} escapes repo_root {repo_root_resolved}; "
            f"reject malformed config.output_dir={config.output_dir!r}"
        ) from e

    size_bytes = write_atomic(xlsx_bytes, target_path)
    passed, _ = check_size_guard(target_path, config.size_limit_mb)
    if not passed:
        log.warning(
            "report_size_exceeded",
            run_id=run_id,
            size_bytes=size_bytes,
            size_limit_mb=config.size_limit_mb,
        )

    # ---- Step 7: atomic single-call patch_stats (Pitfall 6) ----
    rel_path = str(target_path.relative_to(repo_root_resolved)).replace("\\", "/")
    sheet_row_counts = {
        "summary": 1,
        "per_sku_deltas": int(len(matches_df)),
        "assortment_gaps": int(len(gaps_df)),
        "goldapple_promos": int(len(promos_df)),
    }
    builder.set("xlsx_path", rel_path)
    builder.set("xlsx_size_bytes", int(size_bytes))
    builder.set("summary_text", summary_text)
    builder.set("sheet_row_counts", sheet_row_counts)
    builder.set("skipped_reason", "")  # sentinel for non-skip path (Pitfall 4)
    builder.set("size_guard_passed", bool(passed))
    builder.set("generated_at", datetime.now(timezone.utc).isoformat())

    run_writer.patch_stats(run_id, dict(builder.delta))

    elapsed = time.perf_counter() - started
    log.info(
        "reporter_phase_complete",
        run_id=run_id,
        xlsx_path=rel_path,
        xlsx_size_bytes=size_bytes,
        size_guard_passed=passed,
        sheet_row_counts=sheet_row_counts,
        duration_s=round(elapsed, 3),
    )
    return ReporterPhaseResult(
        status="success",
        xlsx_path=rel_path,
        xlsx_size_bytes=int(size_bytes),
        summary_text=summary_text,
        sheet_row_counts=sheet_row_counts,
        size_guard_passed=bool(passed),
        stats_delta=dict(builder.delta),
    )


__all__ = ["ReporterPhaseResult", "run_reporter_phase"]
