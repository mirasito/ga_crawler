"""Phase 4 matcher orchestrator -- `run_matcher_phase()`.

Sync 7-step pipeline mirroring `runners/viled_run.py` shape minus the
fetch/parse/normalize layers (matcher is pure SQL derivation over already-
persisted snapshots). Composes Plan 04-01 (Match table + MatchConfig),
Plan 04-02 (MatchStatsBuilder), Plan 04-03 (strict_key SQL primitives), and
the existing `runner/gates.py` retailer-agnostic helpers.

Steps:
  1. Read run status (D-411 skip-if-failed-or-running protocol)
  2. Compute counts: viled_comparable, goldapple_comparable, brand_overlap, denominator
  3. Build matches (DELETE+INSERT in single TX, D-410)
  4. Compute match.rate (zero-denominator guard per Claude's Discretion)
  5. Sanity-gate P (D-409) + auto-suggest P (D-407)
  6. Atomic single-call patch_stats (Pitfall 6)
  7. Return MatcherPhaseResult; on gate-fail call run_writer.fail (matches persist -- audit invariant)

Source: 04-CONTEXT.md D-409..D-414; 04-PATTERNS.md "NEW src/ga_crawler/runners/matcher_run.py".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

from ga_crawler.interfaces import RunWriterProtocol
from ga_crawler.matcher.stats import MatchStatsBuilder
from ga_crawler.matcher.strict_key import (
    build_matches_for_run,
    compute_brand_overlap,
    compute_comparable_counts,
    compute_denominator,
    read_run_status,
)
from ga_crawler.runner.gates import auto_suggest_threshold, final_threshold_gate

log = structlog.get_logger(__name__)


@dataclass
class MatcherPhaseResult:
    """Outcome of run_matcher_phase."""

    status: str  # "success" | "failed" | "skipped"
    match_count: int = 0
    match_rate: float = 0.0
    reason: Optional[str] = None
    stats_delta: dict = field(default_factory=dict)


# ---- Helpers ----


def _gather_prior_match_counts(
    run_writer: RunWriterProtocol, current_run_id: int, *, lookback: int = 4
) -> list[int]:
    """Read match.count from prior runs for D-407 auto-suggest median.

    Mirror of viled_run._gather_prior_counts / goldapple_run._gather_prior_counts
    but reads the match.* namespace. Best-effort -- any error returns [].
    """
    counts: list[int] = []
    for prior in range(max(1, current_run_id - lookback), current_run_id):
        try:
            stats = run_writer.get_stats(prior)
        except Exception:  # noqa: BLE001
            continue
        if not stats:
            continue
        c = stats.get("match.count")
        if isinstance(c, int) and c > 0:
            counts.append(c)
    return counts


# ---- Main entry point ----


def run_matcher_phase(
    *,
    run_id: int,
    engine,
    run_writer: RunWriterProtocol,
    threshold_p: int = 20,
    p_auto_suggest_factor: float = 0.7,
    p_auto_suggest_after_runs: int = 4,
) -> MatcherPhaseResult:
    """Execute the full Phase 4 matcher.

    Args:
      run_id: existing runs row id (created by caller; matcher does NOT create).
      engine: SQLAlchemy engine -- direct SQL access required for DELETE+INSERT.
      run_writer: RunWriterProtocol implementer (Phase 2 SqliteRunWriter in prod).
      threshold_p: D-408 sanity-gate seed (loaded from pyproject.toml in callers).
      p_auto_suggest_factor: D-407 (default 0.7).
      p_auto_suggest_after_runs: D-407 (default 4).

    Returns:
      MatcherPhaseResult -- status / match_count / match_rate / reason / stats_delta.
    """
    started = time.perf_counter()
    builder = MatchStatsBuilder()
    builder.set("threshold_p", threshold_p)

    # ---- Step 1: D-411 skip-if-upstream-failed ----
    status = read_run_status(engine, run_id)
    if status in (None, "failed", "running"):
        reason = (
            "failed_upstream" if status == "failed"
            else "in_progress_upstream" if status == "running"
            else "missing_run_row"
        )
        builder.set("skipped_reason", reason)
        builder.set("gate_passed", False)
        # Match-* keys that are still meaningful in the skipped path:
        builder.set("count", 0)
        builder.set("numerator", 0)
        builder.set("denominator", 0)
        builder.set("rate", 0.0)
        builder.set("brand_overlap_count", 0)
        builder.set("viled_comparable_count", 0)
        builder.set("goldapple_comparable_count", 0)
        run_writer.patch_stats(run_id, dict(builder.delta))
        log.warning(
            "match_skipped_failed_run",
            run_id=run_id,
            upstream_status=status,
            reason=reason,
        )
        return MatcherPhaseResult(
            status="skipped",
            match_count=0,
            match_rate=0.0,
            reason=reason,
            stats_delta=dict(builder.delta),
        )

    # ---- Step 2: Compute counts ----
    viled_comparable = compute_comparable_counts(engine, run_id, "viled")
    goldapple_comparable = compute_comparable_counts(engine, run_id, "goldapple")
    brand_overlap = compute_brand_overlap(engine, run_id)
    denominator = compute_denominator(engine, run_id)
    builder.set("viled_comparable_count", viled_comparable)
    builder.set("goldapple_comparable_count", goldapple_comparable)
    builder.set("brand_overlap_count", brand_overlap)
    builder.set("denominator", denominator)

    # ---- Step 3: Build matches (D-410 -- DELETE+INSERT in one TX inside primitive) ----
    match_count = build_matches_for_run(engine, run_id)
    builder.set("count", match_count)
    builder.set("numerator", match_count)

    # ---- Step 4: Compute match.rate (zero-denominator guard) ----
    if denominator > 0:
        rate = round(match_count * 100.0 / denominator, 2)
    else:
        rate = 0.0
        log.warning(
            "match_zero_denominator",
            run_id=run_id,
            match_count=match_count,
            note="no brand-overlap between viled and goldapple this run",
        )
    builder.set("rate", rate)
    # skipped_reason is null/empty on the non-skipped path (CONTEXT D-414 line 126:
    # "str OR null"; builder accepts ""). Use empty-string sentinel because
    # SqliteRunWriter.patch_stats rejects None values (Pitfall 4).
    builder.set("skipped_reason", "")

    # ---- Step 5: Sanity-gate P (D-409) + auto-suggest P (D-407) ----
    gate_passed = final_threshold_gate(match_count, threshold_p)
    builder.set("gate_passed", gate_passed)

    # Auto-suggest BEFORE patch_stats so the audit trail is single-call atomic.
    # NOTE: MATCH_STATS_KEYS does NOT include an `auto_suggest_p` key per D-414
    # (intentional -- operator workflow consumes the log line, not the stats column).
    history = _gather_prior_match_counts(
        run_writer, run_id, lookback=p_auto_suggest_after_runs
    )
    suggested = auto_suggest_threshold(
        history,
        factor=p_auto_suggest_factor,
        min_runs=p_auto_suggest_after_runs,
    )
    if suggested is not None:
        log.info(
            "match_auto_suggest_p",
            run_id=run_id,
            suggested=suggested,
            history_runs=len(history),
            factor=p_auto_suggest_factor,
        )

    # ---- Step 6: Atomic single-call patch_stats (Pitfall 6) ----
    run_writer.patch_stats(run_id, dict(builder.delta))

    elapsed = time.perf_counter() - started

    # ---- Step 7: Gate-fail branch (D-409 -- audit-trail invariant: matches PERSIST) ----
    if not gate_passed:
        reason = f"match_count_below_threshold:{match_count}<{threshold_p}"
        log.error(
            "match_sanity_gate_failed",
            run_id=run_id,
            match_count=match_count,
            threshold_p=threshold_p,
            reason=reason,
        )
        run_writer.fail(run_id, reason)
        return MatcherPhaseResult(
            status="failed",
            match_count=match_count,
            match_rate=rate,
            reason=reason,
            stats_delta=dict(builder.delta),
        )

    log.info(
        "matcher_phase_complete",
        run_id=run_id,
        match_count=match_count,
        match_rate=rate,
        denominator=denominator,
        brand_overlap=brand_overlap,
        duration_s=round(elapsed, 3),
    )
    return MatcherPhaseResult(
        status="success",
        match_count=match_count,
        match_rate=rate,
        stats_delta=dict(builder.delta),
    )


__all__ = ["MatcherPhaseResult", "run_matcher_phase"]
