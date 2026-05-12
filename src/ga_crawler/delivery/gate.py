"""Phase 6 pre-send gate — composes 4 checks (D-604), first-fail-wins.

Pure DB-read decision function. NO I/O outside SQLite engine. NO network.
Reuses ``matcher.strict_key.read_run_status`` (D-411 helper) for check #1
— mirror of Plan 05-05 ``runners/reporter_run.py`` D-507 reuse pattern.

D-604 4 checks (independent, short-circuit on first fail):
  1. ``runs.status == 'success'`` — REUSE D-411 helper.
     Fail-reason: ``upstream_status_{status}`` (e.g. ``upstream_status_failed``,
     ``upstream_status_running``, ``upstream_status_None`` when row missing).
  2. ``report.xlsx_path`` non-empty.
     Fail-reason: ``no_xlsx_in_stats``.
  3. ``report.size_guard_passed == True`` (D-515 cascade — NOT NEGOTIABLE).
     Fail-reason: ``xlsx_oversize``.
  4. ``report.summary_text`` non-empty after ``.strip()``.
     Fail-reason: ``empty_summary_text``.

Source anchors: 06-CONTEXT.md D-604 + D-411 reuse; 06-PATTERNS.md
"src/ga_crawler/delivery/gate.py" section (lines 220-305); 06-RESEARCH.md
§Pattern 3 (gate composition + 5 fixture scenarios).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import structlog

from ga_crawler.matcher.strict_key import read_run_status

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GateDecision:
    """First-fail-wins composition result (D-604).

    Three fields, ordered to match PATTERNS.md skeleton:
      route: 'business' (all checks pass) or 'ops_only' (any check fails)
      gate_failed_check: short identifier of the failing check, or None on pass
      gate_failure_reason: machine-readable reason key (REASON_SHORT lookup), or None on pass
    """

    route: Literal["business", "ops_only"]
    gate_failed_check: Optional[str]
    gate_failure_reason: Optional[str]


def evaluate_gate(engine, run_writer, run_id: int) -> GateDecision:
    """4 independent checks; short-circuits at first fail (D-604).

    Args:
        engine: SQLAlchemy engine (used by check #1 ``read_run_status``).
        run_writer: ``SqliteRunWriter`` (provides ``.get_stats(run_id)`` for
            checks 2-4). Only consulted if check #1 passes — that is the
            short-circuit invariant the canary test pins.
        run_id: int.

    Returns:
        GateDecision with route in {"business", "ops_only"}. On 'business',
        both ``gate_failed_check`` and ``gate_failure_reason`` are ``None``.
    """
    # ---- Check 1: runs.status == 'success' (REUSE D-411 helper) ----
    status = read_run_status(engine, run_id)
    if status != "success":
        decision = GateDecision(
            route="ops_only",
            gate_failed_check="run_status",
            gate_failure_reason=f"upstream_status_{status}",
        )
        log.warning(
            "delivery_gate_decision",
            run_id=run_id,
            route=decision.route,
            gate_failed_check=decision.gate_failed_check,
            gate_failure_reason=decision.gate_failure_reason,
        )
        return decision

    stats = run_writer.get_stats(run_id) or {}

    # ---- Check 2: xlsx_path non-empty ----
    if not stats.get("report.xlsx_path"):
        decision = GateDecision(
            route="ops_only",
            gate_failed_check="xlsx_path",
            gate_failure_reason="no_xlsx_in_stats",
        )
        log.warning(
            "delivery_gate_decision",
            run_id=run_id,
            route=decision.route,
            gate_failed_check=decision.gate_failed_check,
            gate_failure_reason=decision.gate_failure_reason,
        )
        return decision

    # ---- Check 3: size_guard_passed (D-515 cascade) ----
    if not stats.get("report.size_guard_passed", False):
        decision = GateDecision(
            route="ops_only",
            gate_failed_check="size_guard",
            gate_failure_reason="xlsx_oversize",
        )
        log.warning(
            "delivery_gate_decision",
            run_id=run_id,
            route=decision.route,
            gate_failed_check=decision.gate_failed_check,
            gate_failure_reason=decision.gate_failure_reason,
        )
        return decision

    # ---- Check 4: summary_text non-empty after strip ----
    if not str(stats.get("report.summary_text", "")).strip():
        decision = GateDecision(
            route="ops_only",
            gate_failed_check="summary_text",
            gate_failure_reason="empty_summary_text",
        )
        log.warning(
            "delivery_gate_decision",
            run_id=run_id,
            route=decision.route,
            gate_failed_check=decision.gate_failed_check,
            gate_failure_reason=decision.gate_failure_reason,
        )
        return decision

    # ---- All checks pass ----
    decision = GateDecision(route="business", gate_failed_check=None, gate_failure_reason=None)
    log.info("delivery_gate_decision", run_id=run_id, route="business")
    return decision


__all__ = ["GateDecision", "evaluate_gate"]
