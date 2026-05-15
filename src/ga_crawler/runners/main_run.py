"""Phase 2 weekly orchestrator — `run_weekly()`.

Composes the full weekly pipeline:

    runs.create()
       → run_viled_phase()
       → run_goldapple_phase()             (Phase 3 frozen — async via asyncio.run)
       → Norm06Writer.persist()             (D-211 Phase 2 owns write-path)
       → run_writer.finalize("success")

DATA-05 lifecycle invariant: every code path closes the runs row. The body
runs inside try/except; any uncaught Exception triggers
`run_writer.fail(stack-trace)` (idempotent — safe to call after finalize).

D-221 brand-pool flow: viled brand list is read from
`v_current_snapshots WHERE retailer='viled'` AFTER the viled phase persists
its snapshots; the list is passed to `run_goldapple_phase` as `viled_brands`.

D-211 Norm06 ownership: Phase 2 owns the markdown ledger writer
(`storage/norm06_writer.py`). Phase 3's stub no longer writes review queue;
this orchestrator wires the canonical Norm06Writer.persist call AFTER both
retailer phases complete.

Source: 02-RESEARCH.md §System Architecture Diagram lines 145-242;
        02-CONTEXT.md D-211 / D-212 / D-218 / D-221.
"""

from __future__ import annotations

import asyncio
import dataclasses
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import text

from ga_crawler.alias.yaml_loader import YamlBrandAlias
from ga_crawler.config import ViledConfig
from ga_crawler.matcher.config import MatchConfig
from ga_crawler.normalizers.facade import Normalizer
from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
from ga_crawler.reporter.config import ReportConfig
from ga_crawler.runner.gates import parser_drift_null_rate_gate
from ga_crawler.runner.stats import GoldappleStatsBuilder
from ga_crawler.runners.delivery_run import run_delivery_phase
from ga_crawler.runners.matcher_run import run_matcher_phase
from ga_crawler.runners.reporter_run import run_reporter_phase
from ga_crawler.runners.viled_run import run_viled_phase
from ga_crawler.storage.norm06_writer import Norm06Writer
from ga_crawler.storage.sqlite import (
    SqliteRunWriter,
    SqliteSnapshotWriter,
    init_db,
    make_engine,
)

log = structlog.get_logger(__name__)


@dataclass
class MainRunResult:
    """Outcome of run_weekly."""

    status: str  # "success" | "failed"
    run_id: int
    viled_count: int = 0
    goldapple_count: int = 0
    match_count: int = 0  # Plan 04-05 — Phase 4 matcher count
    match_rate: float = 0.0  # Plan 04-05 — Phase 4 match-rate percent
    reason: Optional[str] = None
    norm06_path: Optional[Path] = None
    # ---- Plan 05-05 additions per D-514 (surface reporter outcome to CLI/caller) ----
    xlsx_path: Optional[str] = None
    xlsx_size_bytes: int = 0
    summary_text: str = ""
    size_guard_passed: bool = True
    # ---- Plan 06-05 additions per D-616 (Phase 7 Healthchecks cascade) ----
    delivery_status: str = "pending"
    delivery_route: str = ""
    # ---- keep stats_delta last (default_factory) ----
    stats_delta: dict = field(default_factory=dict)


def _derive_viled_brands_from_snapshots(engine, run_id: int) -> list[str]:
    """D-221: read DISTINCT brand_norm from this run's viled snapshots.

    Uses the `snapshots` table directly (not v_current_snapshots) because the
    VIEW filters on `runs.status='success'` and the run is still 'running' at
    this point — the viled phase has just persisted; the goldapple phase has
    not yet started.
    """
    sql = text(
        "SELECT DISTINCT brand_norm FROM snapshots "
        "WHERE retailer='viled' AND run_id=:rid "
        "AND brand_norm IS NOT NULL AND brand_norm <> ''"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"rid": run_id}).fetchall()
    return sorted({row[0] for row in rows if row[0]})


def _config_with_overrides(
    config: ViledConfig,
    *,
    sanity_gate_n: Optional[int],
) -> ViledConfig:
    """Apply CLI/test overrides via dataclasses.replace (frozen-safe)."""
    if sanity_gate_n is None:
        return config
    return dataclasses.replace(config, sanity_gate_n=sanity_gate_n)


def run_weekly(
    repo_root: Path | str,
    *,
    db_path: str | Path = "prices.db",
    headless: bool = True,
    viled_only: bool = False,
    goldapple_only: bool = False,
    sanity_gate_n: Optional[int] = None,
    sanity_gate_m: Optional[int] = None,
    sanity_gate_p: Optional[int] = None,
    aliases_path: Optional[Path | str] = None,
    pyproject_path: Path | str = "pyproject.toml",
    existing_run_id: Optional[int] = None,
) -> MainRunResult:
    """Execute the full weekly run.

    Args:
        repo_root:        project root for Norm06 ledger + week-over-week artifacts
        db_path:          SQLite DB file (auto-created via init_db)
        headless:         Camoufox headless flag for goldapple phase
        viled_only:       skip the goldapple phase (matcher also skipped — needs both retailers)
        goldapple_only:   skip the viled phase (reads brand list from previous run's view;
                          matcher also skipped — needs both retailers)
        sanity_gate_n:    override viled config N
        sanity_gate_m:    override goldapple gate M
        sanity_gate_p:    Plan 04-05 — override matcher sanity-P threshold
                          (default: MatchConfig.from_pyproject().sanity_gate_p)
        aliases_path:     override config/brand-aliases.yaml location
        pyproject_path:   path to pyproject.toml (for ViledConfig.from_pyproject / MatchConfig)

    Returns:
        MainRunResult — status / run_id / counts / reason / norm06_path / stats_delta.
    """
    repo_root = Path(repo_root)
    if aliases_path is None:
        aliases_path = repo_root / "config" / "brand-aliases.yaml"

    init_db(db_path)
    engine = make_engine(db_path)

    run_writer = SqliteRunWriter(engine)
    snapshot_writer = SqliteSnapshotWriter(engine)
    brand_alias = YamlBrandAlias(aliases_path)
    normalizer = Normalizer(brand_alias)
    base_config = ViledConfig.from_pyproject(pyproject_path)
    config = _config_with_overrides(base_config, sanity_gate_n=sanity_gate_n)

    if existing_run_id is not None:
        run_id = existing_run_id
        log.info("weekly_run_continuing_existing_run", run_id=run_id, source="operator chain-mode (e.g. bin/viled_fast_crawl.py)")
    else:
        run_id = run_writer.create()
    log.info(
        "weekly_run_started",
        run_id=run_id,
        viled_only=viled_only,
        goldapple_only=goldapple_only,
        existing_run_id=existing_run_id,
        db_path=str(db_path),
    )

    stats_delta_acc: dict = {}
    viled_count = 0
    goldapple_count = 0
    # Plan 04-05 — matcher counters scoped above try so the except branch can read them.
    match_count = 0
    match_rate = 0.0
    viled_unmatched: list[str] = []
    goldapple_new_slugs: list[str] = []
    # Plan 05-05 — reporter outcome scoped above try so the except branch returns
    # valid MainRunResult with sane defaults (None / 0 / "" / True). Phase 6
    # DELIVER-03 sanity-gate reads size_guard_passed only when xlsx_path is non-empty,
    # so the default True is semantically "no xlsx produced → no size violation".
    xlsx_path: Optional[str] = None
    xlsx_size_bytes: int = 0
    summary_text: str = ""
    size_guard_passed: bool = True
    # Plan 06-05 — delivery outcome scoped above try so the except branch returns
    # valid MainRunResult with sane defaults. D-616 + Phase 7 health-probe.
    delivery_status: str = "pending"
    delivery_route: str = ""

    try:
        # ---- Viled phase ----
        if not goldapple_only:
            v_result = run_viled_phase(
                run_id=run_id,
                config=config,
                brand_alias=brand_alias,
                normalizer=normalizer,
                snapshot_writer=snapshot_writer,
                run_writer=run_writer,
            )
            viled_count = v_result.viled_count
            stats_delta_acc.update(v_result.stats_delta)
            if v_result.status == "failed":
                # Persist Norm06 with what we have (likely empty for both lists).
                norm06_path = Norm06Writer(repo_root).persist(run_id, [], [])
                log.error(
                    "weekly_run_viled_failed",
                    run_id=run_id,
                    reason=v_result.reason,
                )
                return MainRunResult(
                    status="failed",
                    run_id=run_id,
                    viled_count=viled_count,
                    reason=v_result.reason,
                    norm06_path=norm06_path,
                    delivery_status=delivery_status,
                    delivery_route=delivery_route,
                    stats_delta=dict(stats_delta_acc),
                )

        # ---- Goldapple phase ----
        if not viled_only:
            from ga_crawler.runners.goldapple_run import run_goldapple_phase

            viled_brands = _derive_viled_brands_from_snapshots(engine, run_id)
            log.info(
                "goldapple_phase_starting",
                run_id=run_id,
                viled_brand_count=len(viled_brands),
            )
            kwargs: dict = {}
            if sanity_gate_m is not None:
                kwargs["M"] = sanity_gate_m
            g_result = asyncio.run(
                run_goldapple_phase(
                    run_id=run_id,
                    viled_brands=viled_brands,
                    repo_root=repo_root,
                    brand_alias=brand_alias,
                    normalizer=normalizer,
                    snapshot_writer=snapshot_writer,
                    run_writer=run_writer,
                    headless=headless,
                    **kwargs,
                )
            )
            goldapple_count = g_result.goldapple_count
            stats_delta_acc.update(g_result.stats_delta)
            viled_unmatched = list(g_result.unmatched_viled_brands)
            goldapple_new_slugs = list(g_result.new_goldapple_slugs)
            if g_result.status == "failed":
                norm06_path = Norm06Writer(repo_root).persist(
                    run_id, viled_unmatched, goldapple_new_slugs
                )
                log.error(
                    "weekly_run_goldapple_failed",
                    run_id=run_id,
                    reason=g_result.reason,
                )
                return MainRunResult(
                    status="failed",
                    run_id=run_id,
                    viled_count=viled_count,
                    goldapple_count=goldapple_count,
                    reason=g_result.reason,
                    norm06_path=norm06_path,
                    delivery_status=delivery_status,
                    delivery_route=delivery_route,
                    stats_delta=dict(stats_delta_acc),
                )

            # ---- PARSE-FIX-04 parser-drift null-rate sanity gate (Plan 08-05 D-817) ----
            # Sits AFTER goldapple persist + AFTER parse_quality_gate (inside
            # goldapple_run) and BEFORE matcher invocation. Catches the run-#13
            # silent failure mode where goldapple parser drifts back to >50%
            # NULL volume_norm or brand — prevents matcher running over empty
            # comparable set and producing a blank Excel.
            #
            # Pitfall 6 (RESEARCH.md): if goldapple crawl was empty
            # (goldapple_count == 0), skip the gate — the SQL AVG over zero
            # rows returns NULL and would false-positive on `> 0.5`. Existing
            # final_threshold_gate (M-gate) handles the zero-crawl failure
            # mode independently.
            #
            # Pitfall 4 (storage.sqlite): patch_stats DELETES keys on None
            # value. failure_reason MUST be persisted as "" sentinel when
            # the gate passes, NOT as None.
            #
            # Source: 08-CONTEXT.md D-815/D-817; 08-RESEARCH.md §"Orchestrator
            # Wiring (pseudo-code)" lines 613-641 + §"Pitfall 6" lines 1126-1137.
            if goldapple_count > 0:
                with engine.begin() as conn:
                    drift_row = conn.execute(
                        text(
                            "SELECT "
                            "  AVG(CASE WHEN volume_norm IS NULL THEN 1.0 ELSE 0.0 END) AS v_null, "
                            "  AVG(CASE WHEN brand IS NULL OR brand = '' THEN 1.0 ELSE 0.0 END) AS b_null "
                            "FROM snapshots WHERE run_id = :rid AND retailer = 'goldapple'"
                        ),
                        {"rid": run_id},
                    ).first()
                volume_null_rate = float(drift_row.v_null or 0.0)
                brand_null_rate = float(drift_row.b_null or 0.0)

                drift = parser_drift_null_rate_gate(
                    volume_null_rate=volume_null_rate,
                    brand_null_rate=brand_null_rate,
                    threshold=0.5,
                )

                drift_builder = GoldappleStatsBuilder()
                drift_builder.set("volume_null_rate", drift.volume_null_rate)
                drift_builder.set("brand_null_rate", drift.brand_null_rate)
                drift_builder.set(
                    "parser_drift_failure_reason",
                    # Pitfall 4: "" sentinel on pass instead of None
                    drift.failure_reason if drift.failure_reason is not None else "",
                )
                run_writer.patch_stats(run_id, drift_builder.delta)
                stats_delta_acc.update(drift_builder.delta)

                if not drift.passed:
                    log.error(
                        "phase8_parser_drift_gate_failed",
                        run_id=run_id,
                        volume_null_rate=drift.volume_null_rate,
                        brand_null_rate=drift.brand_null_rate,
                        reason=drift.failure_reason,
                    )
                    run_writer.fail(
                        run_id,
                        drift.failure_reason or "parser_drift_unknown",
                    )
                    norm06_path = Norm06Writer(repo_root).persist(
                        run_id, viled_unmatched, goldapple_new_slugs
                    )
                    return MainRunResult(
                        status="failed",
                        run_id=run_id,
                        viled_count=viled_count,
                        goldapple_count=goldapple_count,
                        reason=drift.failure_reason,
                        norm06_path=norm06_path,
                        delivery_status=delivery_status,
                        delivery_route=delivery_route,
                        stats_delta=dict(stats_delta_acc),
                    )
            else:
                log.warning(
                    "phase8_drift_gate_skipped_no_snapshots",
                    run_id=run_id,
                )

        # ---- Matcher phase (Plan 04-05; D-411 skip-if-failed handled inside) ----
        # Composition rule: matcher needs BOTH retailer datasets. *_only modes skip it.
        # D-411 makes this fire-and-let-it-handle: matcher reads runs.status itself
        # and decides skip vs run. We do NOT pre-gate on upstream status here.
        #
        # Pre-finalize the runs row to status='success' BEFORE invoking the matcher
        # so D-411's read_run_status returns 'success' (matcher proceeds) instead
        # of 'running' (matcher skips). D-409 gate-fail path then calls
        # run_writer.fail(...) which flips status back to 'failed' — fail() has no
        # `WHERE status='running'` guard (DATA-05 idempotency).
        if not viled_only and not goldapple_only:
            run_writer.finalize(run_id, status="success")
            match_config = MatchConfig.from_pyproject(pyproject_path)
            effective_p = (
                sanity_gate_p
                if sanity_gate_p is not None
                else match_config.sanity_gate_p
            )
            m_result = run_matcher_phase(
                run_id=run_id,
                engine=engine,
                run_writer=run_writer,
                threshold_p=effective_p,
                p_auto_suggest_factor=match_config.p_auto_suggest_factor,
                p_auto_suggest_after_runs=match_config.p_auto_suggest_after_runs,
            )
            match_count = m_result.match_count
            match_rate = m_result.match_rate
            stats_delta_acc.update(m_result.stats_delta)
            if m_result.status == "failed":
                # D-409: matcher already called run_writer.fail; matches rows persisted.
                # Norm06 ledger still written below for the audit artifact.
                norm06_path = Norm06Writer(repo_root).persist(
                    run_id, viled_unmatched, goldapple_new_slugs
                )
                log.error(
                    "weekly_run_matcher_failed",
                    run_id=run_id,
                    reason=m_result.reason,
                    match_count=match_count,
                )
                return MainRunResult(
                    status="failed",
                    run_id=run_id,
                    viled_count=viled_count,
                    goldapple_count=goldapple_count,
                    match_count=match_count,
                    match_rate=match_rate,
                    reason=m_result.reason,
                    norm06_path=norm06_path,
                    delivery_status=delivery_status,
                    delivery_route=delivery_route,
                    stats_delta=dict(stats_delta_acc),
                )
            elif m_result.status == "skipped":
                log.warning(
                    "weekly_run_matcher_skipped",
                    run_id=run_id,
                    reason=m_result.reason,
                )
                # Skip is NOT a run-failure — fall through to Norm06 + finalize.

            # ---- Reporter phase (Plan 05-05; D-507 skip-if-not-success handled inside) ----
            # Composition rule (D-511): reporter needs matcher output (matches table).
            # *_only modes skip both matcher and reporter. We invoke reporter ONLY when
            # matcher returned 'success' — explicit gate, even though D-507 inside
            # reporter_run would also skip on other statuses. Explicit > implicit.
            # The 'failed' branch already early-returned above; the 'skipped' branch
            # falls through here but we gate on '== "success"' to keep stats coherent
            # (no report.* keys when there were no matches to report on).
            if m_result.status == "success":
                report_config = ReportConfig.from_pyproject(pyproject_path)
                log.info(
                    "weekly_run_reporter_starting",
                    run_id=run_id,
                    output_dir=report_config.output_dir,
                )
                r_result = run_reporter_phase(
                    run_id=run_id,
                    engine=engine,
                    run_writer=run_writer,
                    repo_root=repo_root,
                    config=report_config,
                )
                xlsx_path = r_result.xlsx_path
                xlsx_size_bytes = r_result.xlsx_size_bytes
                summary_text = r_result.summary_text
                size_guard_passed = r_result.size_guard_passed
                stats_delta_acc.update(r_result.stats_delta)

                if r_result.status == "skipped":
                    # Defensive — should not fire if matcher.status was 'success'
                    # moments ago (pre-finalize set runs.status='success'). But
                    # D-507 inside reporter could trip if the row was tampered
                    # with between. Reporter skip is NOT a run-failure — fall
                    # through to Norm06 + final idempotent finalize.
                    log.warning(
                        "weekly_run_reporter_skipped",
                        run_id=run_id,
                        reason=r_result.reason,
                    )

                # ---- Delivery phase (Plan 06-05; D-604 gate + D-605 never-fails-run) ----
                # Composition rule (D-615): delivery needs reporter output (xlsx + summary).
                # Explicit gate above D-507/D-604 (Plan 05-05 pattern preserved).
                # On Telegram unreachable: delivery_status='undelivered_*' but runs.status
                # remains 'success' (D-605 invariant) and xlsx persists on disk.
                # Outer DATA-05 try/except catches only programmer bugs.
                if r_result.status == "success" and r_result.xlsx_path:
                    deliver_config = DeliverConfig.from_pyproject(pyproject_path)
                    deliver_env = DeliverEnvConfig.from_env()
                    log.info(
                        "weekly_run_delivery_starting",
                        run_id=run_id,
                    )
                    d_result = run_delivery_phase(
                        run_id=run_id,
                        engine=engine,
                        run_writer=run_writer,
                        repo_root=repo_root,
                        config=deliver_config,
                        env=deliver_env,
                    )
                    delivery_status = d_result.delivery_status
                    delivery_route = d_result.route
                    stats_delta_acc.update(d_result.stats_delta)
                    log.info(
                        "weekly_run_delivery_complete",
                        run_id=run_id,
                        status=delivery_status,
                        route=delivery_route,
                    )

        # ---- Norm06 review queue (D-211) ----
        norm06_path = Norm06Writer(repo_root).persist(
            run_id, viled_unmatched, goldapple_new_slugs
        )

        # ---- Finalize ----
        # If matcher ran (viled+goldapple both invoked), the run was already
        # pre-finalized to 'success' before matcher; finalize() is idempotent
        # (guard `WHERE status='running'`) so a second call is a no-op when
        # matcher succeeded or was skipped. *_only modes did NOT pre-finalize,
        # so this is the canonical close.
        run_writer.finalize(run_id, status="success")
        log.info(
            "weekly_run_complete",
            run_id=run_id,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            match_count=match_count,
            match_rate=match_rate,
            xlsx_path=xlsx_path,
            xlsx_size_bytes=xlsx_size_bytes,
            size_guard_passed=size_guard_passed,
            norm06_path=str(norm06_path),
        )
        return MainRunResult(
            status="success",
            run_id=run_id,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            match_count=match_count,
            match_rate=match_rate,
            norm06_path=norm06_path,
            xlsx_path=xlsx_path,
            xlsx_size_bytes=xlsx_size_bytes,
            summary_text=summary_text,
            size_guard_passed=size_guard_passed,
            delivery_status=delivery_status,
            delivery_route=delivery_route,
            stats_delta=dict(stats_delta_acc),
        )

    except Exception as e:  # noqa: BLE001
        # DATA-05 invariant: every code path closes the runs row.
        tb = traceback.format_exc()
        reason = f"{type(e).__name__}: {e}"
        log.error(
            "weekly_run_crashed",
            run_id=run_id,
            error=reason,
            traceback=tb,
        )
        # Idempotent fail() — safe even if a phase already called fail() earlier.
        try:
            run_writer.fail(run_id, reason)
        except Exception as fail_exc:  # noqa: BLE001
            log.error(
                "weekly_run_fail_failed",
                run_id=run_id,
                error=str(fail_exc),
            )
        # Best-effort Norm06 audit artifact even on crash.
        norm06_path: Optional[Path] = None
        try:
            norm06_path = Norm06Writer(repo_root).persist(
                run_id, viled_unmatched, goldapple_new_slugs
            )
        except Exception:  # noqa: BLE001
            pass
        return MainRunResult(
            status="failed",
            run_id=run_id,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            match_count=match_count,
            match_rate=match_rate,
            reason=reason,
            norm06_path=norm06_path,
            delivery_status=delivery_status,
            delivery_route=delivery_route,
            stats_delta=dict(stats_delta_acc),
        )


__all__ = ["MainRunResult", "run_weekly"]
