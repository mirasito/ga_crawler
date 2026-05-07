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
from ga_crawler.normalizers.facade import Normalizer
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
    reason: Optional[str] = None
    norm06_path: Optional[Path] = None
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
    aliases_path: Optional[Path | str] = None,
    pyproject_path: Path | str = "pyproject.toml",
) -> MainRunResult:
    """Execute the full weekly run.

    Args:
        repo_root:        project root for Norm06 ledger + week-over-week artifacts
        db_path:          SQLite DB file (auto-created via init_db)
        headless:         Camoufox headless flag for goldapple phase
        viled_only:       skip the goldapple phase
        goldapple_only:   skip the viled phase (reads brand list from previous run's view)
        sanity_gate_n:    override viled config N
        sanity_gate_m:    override goldapple gate M
        aliases_path:     override config/brand-aliases.yaml location
        pyproject_path:   path to pyproject.toml (for ViledConfig.from_pyproject)

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

    run_id = run_writer.create()
    log.info(
        "weekly_run_started",
        run_id=run_id,
        viled_only=viled_only,
        goldapple_only=goldapple_only,
        db_path=str(db_path),
    )

    stats_delta_acc: dict = {}
    viled_count = 0
    goldapple_count = 0
    viled_unmatched: list[str] = []
    goldapple_new_slugs: list[str] = []

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
                    stats_delta=dict(stats_delta_acc),
                )

        # ---- Norm06 review queue (D-211) ----
        norm06_path = Norm06Writer(repo_root).persist(
            run_id, viled_unmatched, goldapple_new_slugs
        )

        # ---- Finalize ----
        run_writer.finalize(run_id, status="success")
        log.info(
            "weekly_run_complete",
            run_id=run_id,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            norm06_path=str(norm06_path),
        )
        return MainRunResult(
            status="success",
            run_id=run_id,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            norm06_path=norm06_path,
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
            reason=reason,
            norm06_path=norm06_path,
            stats_delta=dict(stats_delta_acc),
        )


__all__ = ["MainRunResult", "run_weekly"]
