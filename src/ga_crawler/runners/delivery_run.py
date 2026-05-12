"""Phase 6 delivery orchestrator -- ``run_delivery_phase()``.

Sync 7-step pipeline mirroring ``runners/reporter_run.py`` shape. Composes
Plan 06-02 + 06-03 ``delivery/*`` modules: ``config`` (D-611/D-614),
``gate`` (D-604), ``message_builder`` (D-610), ``telegram_client``
(D-601/D-603), ``stats`` (D-607).

Steps:
  0. Pre-flight: TG_BOT_TOKEN required (D-611 asymmetric handling).
  1. Idempotency dispatch (D-606 enum check; D-608 ``--force``).
  2. D-604 gate evaluation (REUSE ``matcher.strict_key.read_run_status``).
  3. Read ops-alert facts from stats (viled/goldapple counts, match.*).
  4. Build messages (pure transforms via ``message_builder``).
  5. dry-run early exit OR Pitfall C defense-in-depth xlsx-path containment.
  6. ``asyncio.run(_send_async(...))`` mirror of ``main_run.py:224``
     ``run_goldapple_phase`` pattern (D-602).
  7. SINGLE atomic ``patch_stats`` with all 8 D-607 keys (Pitfall 6);
     return ``DeliveryPhaseResult``.

DATA-05 lifecycle: ``run_delivery_phase`` does NOT raise on Telegram
failure (D-605). Only programmer bugs (AttributeError, TypeError) reach
the defensive outer try/except and are mapped to
``delivery_status='undelivered_telegram_unreachable'``.

Source: 06-CONTEXT.md D-601..D-616; 06-RESEARCH.md §Integration Patterns +
Pitfall A/B/C/D; 06-PATTERNS.md
"src/ga_crawler/runners/delivery_run.py" section.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from aiogram.exceptions import (  # noqa: F401  -- re-exported for caller catch-all
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from sqlalchemy import text as _sql

from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
from ga_crawler.delivery.gate import GateDecision, evaluate_gate
from ga_crawler.delivery.message_builder import (
    REASON_SHORT,  # noqa: F401  -- re-export for downstream callers / canary
    build_ops_alert,
    business_caption,
)
from ga_crawler.delivery.stats import DeliverStatsBuilder
from ga_crawler.delivery.telegram_client import (
    SendOutcome,
    open_bot,
    send_document_with_policy,
    send_message_with_policy,
)
from ga_crawler.matcher.strict_key import read_run_status  # D-411 reuse

log = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Result dataclasses                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class DeliveryPhaseResult:
    """Outcome of :func:`run_delivery_phase`.

    Fields mirror the 8 ``deliver.*`` stats keys (D-607) plus a
    ``stats_delta`` echo (the dict actually patched into runs.stats).
    """

    delivery_status: str  # D-606 enum (6 values)
    route: str            # "business" | "ops_only" | "skipped"
    business_caption_message_id: int = -1
    business_document_message_id: int = -1
    ops_message_id: int = -1
    attempt_count: int = 0
    last_error: str = ""
    delivered_at: str = ""
    stats_delta: dict = field(default_factory=dict)


@dataclass
class _AsyncSendResult:
    """Internal bundle returned by :func:`_send_async`."""

    business_caption_message_id: int = -1
    business_document_message_id: int = -1
    ops_message_id: int = -1
    attempt_count: int = 0
    last_error: str = ""
    delivery_status: str = "pending"  # promoted to delivered_* / undelivered_*


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _truncate(value: str, max_chars: int) -> str:
    """Defensive string truncation; ``None`` / empty pass through."""
    if not value:
        return ""
    return value[:max_chars]


def _coerce_started_at(value) -> datetime:
    """Coerce a value read from ``runs.started_at`` into an aware UTC datetime.

    Python 3.12 deprecated the default sqlite3 datetime adapter so the value
    comes back as an ISO 8601 string (e.g. ``"2026-05-10 14:00:00+00:00"``).
    ``datetime.fromisoformat`` parses both the new ``"+00:00"`` and the older
    ``"Z"`` suffixes; naive datetimes are treated as UTC per DATA-05.
    """
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text_val = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text_val)
        except ValueError:
            return datetime.now(timezone.utc)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _resolve_xlsx_safely(xlsx_path: str, repo_root: Path) -> Path:
    """Pitfall C: defense-in-depth path containment check.

    Phase 5 Plan 05-04 already validates path on the write side; this
    function re-validates on the read side so even a tampered
    ``runs.stats.report.xlsx_path`` cannot cause ``FSInputFile`` to open
    a file outside ``repo_root``.

    Raises:
      * ``ValueError`` -- path escapes ``repo_root`` (``..`` segments,
        absolute path outside repo, etc.).
      * ``FileNotFoundError`` -- resolved path does not exist on disk.
    """
    candidate = (repo_root / xlsx_path).resolve()
    repo_resolved = repo_root.resolve()
    try:
        candidate.relative_to(repo_resolved)
    except ValueError as e:
        raise ValueError(f"xlsx_path_escapes_repo:{xlsx_path}") from e
    if not candidate.is_file():
        raise FileNotFoundError(f"xlsx_path_not_found:{xlsx_path}")
    return candidate


def _build_stats_skip_path(
    *,
    run_id: int,
    run_writer,
    delivery_status: str,
    route: str,
    last_error: str = "",
) -> DeliveryPhaseResult:
    """Single atomic ``patch_stats`` for skip / no-op / credentials-missing /
    pitfall-C / unexpected-crash branches (Pitfall 6 + Pitfall 4).

    All 8 D-607 keys patched with sentinel values so downstream consumers
    see a consistent shape regardless of how the orchestrator exited.
    """
    builder = DeliverStatsBuilder()
    builder.set("delivery_status", delivery_status)
    builder.set("route", route)
    builder.set("business_caption_message_id", -1)
    builder.set("business_document_message_id", -1)
    builder.set("ops_message_id", -1)
    builder.set("attempt_count", 0)
    builder.set("last_error", _truncate(last_error, 500))
    builder.set("delivered_at", "")
    run_writer.patch_stats(run_id, dict(builder.delta))
    return DeliveryPhaseResult(
        delivery_status=delivery_status,
        route=route,
        last_error=_truncate(last_error, 500),
        stats_delta=dict(builder.delta),
    )


# --------------------------------------------------------------------------- #
# Main sync entrypoint                                                        #
# --------------------------------------------------------------------------- #


def run_delivery_phase(
    *,
    run_id: int,
    engine,
    run_writer,
    repo_root: Path,
    config: DeliverConfig,
    env: DeliverEnvConfig,
    force: bool = False,
    dry_run: bool = False,
) -> DeliveryPhaseResult:
    """Execute Phase 6 delivery end-to-end. Never raises on Telegram failure.

    Args:
      run_id: existing ``runs.run_id`` (orchestrator does NOT create).
      engine: SQLAlchemy engine (passed through to ``evaluate_gate``).
      run_writer: ``SqliteRunWriter`` instance.
      repo_root: ``Path`` to repo root for Pitfall C containment.
      config: ``DeliverConfig`` (retry/truncate/caption tunables).
      env: ``DeliverEnvConfig`` (bot_token + 2 chat_ids).
      force: D-608 -- override idempotency on ``delivered_business``.
      dry_run: D-608 -- print preview JSON, skip Telegram + patch_stats.

    Returns:
      ``DeliveryPhaseResult`` with one of the 6 D-606 enum values.

    Source-locked invariants:
      * D-605 Telegram failure does NOT raise -- mapped to
        ``delivery_status='undelivered_telegram_unreachable'`` and the
        upstream ``runs.status`` is untouched.
      * Pitfall 6 single ``patch_stats`` call per non-dry-run invocation.
      * Pitfall C ``_resolve_xlsx_safely`` runs BEFORE ``send_document``.
    """
    started = time.perf_counter()
    log.info(
        "delivery_phase_start",
        run_id=run_id,
        force=force,
        dry_run=dry_run,
    )

    # ---- Step 0: Pre-flight (D-611 asymmetric ENV handling) ----
    if not env.bot_token:
        log.error(
            "delivery_skipped_no_credentials",
            run_id=run_id,
            missing_env="TG_BOT_TOKEN",
        )
        return _build_stats_skip_path(
            run_id=run_id,
            run_writer=run_writer,
            delivery_status="skipped_no_credentials",
            route="skipped",
            last_error="missing_env_TG_BOT_TOKEN",
        )

    # ---- Step 1: Idempotency dispatch (D-608) ----
    existing_stats = run_writer.get_stats(run_id) or {}
    existing_status = existing_stats.get("deliver.delivery_status", "")
    if existing_status == "delivered_business" and not force:
        log.info("delivery_skipped_already_delivered", run_id=run_id)
        return _build_stats_skip_path(
            run_id=run_id,
            run_writer=run_writer,
            delivery_status="skipped_already_delivered",
            route="skipped",
            last_error="",
        )

    # ---- Step 2: D-604 gate evaluation ----
    decision = evaluate_gate(engine, run_writer, run_id)

    # ---- Step 3: Read ops-alert facts from stats ----
    stats = existing_stats  # gate may have re-read but values are immutable here
    viled_count = int(stats.get("viled.fetch_count", 0) or 0)
    goldapple_count = int(stats.get("goldapple.fetch_count", 0) or 0)
    match_count = int(stats.get("match.count", 0) or 0)
    match_rate = float(stats.get("match.rate", 0.0) or 0.0)
    summary_text = str(stats.get("report.summary_text", "") or "")
    xlsx_path_rel = str(stats.get("report.xlsx_path", "") or "")
    xlsx_size_bytes = int(stats.get("report.xlsx_size_bytes", 0) or 0)
    xlsx_size_mb = round(xlsx_size_bytes / (1024 * 1024), 2)
    size_guard_passed = bool(stats.get("report.size_guard_passed", True))

    # Read runs.status + started_at separately (gate already touched status,
    # but we need both for the ops-alert template body).
    actual_run_status = read_run_status(engine, run_id) or "unknown"
    with engine.connect() as _conn:
        _row = _conn.execute(
            _sql("SELECT started_at FROM runs WHERE run_id=:rid"),
            {"rid": run_id},
        ).first()
    started_at_utc = _coerce_started_at(_row[0] if _row else None)

    # ---- Step 4: Build messages (no I/O yet) ----
    ops_alert_html: Optional[str]
    business_payload: Optional[dict]
    if decision.route == "ops_only":
        ops_alert_html = build_ops_alert(
            run_id=run_id,
            reason_key=decision.gate_failure_reason or "delivery_exception",
            started_at_utc=started_at_utc,
            run_status=actual_run_status,
            gate_failed_check=decision.gate_failed_check,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            match_count=match_count,
            match_rate=match_rate,
            size_guard_failed=not size_guard_passed,
            xlsx_size_mb=xlsx_size_mb,
            size_limit_mb=45,
            error_short="",
            truncate_chars=config.ops_message_truncate_chars,
        )
        business_payload = None
    else:
        ops_alert_html = None
        caption_text, is_split = business_caption(
            summary_text, max_chars=config.business_caption_max_chars,
        )
        business_payload = {
            "caption": caption_text,
            "is_split": is_split,
            "full_summary": summary_text,
        }

    # ---- Step 5: dry-run early exit (D-608 -- read-only preview) ----
    if dry_run:
        preview = {
            "route": decision.route,
            "gate_decision": {
                "failed_check": decision.gate_failed_check,
                "failure_reason": decision.gate_failure_reason,
            },
            "business_caption_preview": (
                business_payload["caption"][:200] if business_payload else None
            ),
            "ops_alert_preview": (
                ops_alert_html[:200] if ops_alert_html else None
            ),
        }
        payload = json.dumps(preview, ensure_ascii=False, indent=2)
        sys.stdout.buffer.write(payload.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        # Dry-run does NOT patch_stats (read-only by design).
        return DeliveryPhaseResult(
            delivery_status="pending",
            route=decision.route,
        )

    # ---- Step 6: Pitfall C defense-in-depth xlsx path containment ----
    xlsx_full_path: Optional[Path] = None
    if decision.route == "business":
        try:
            xlsx_full_path = _resolve_xlsx_safely(xlsx_path_rel, repo_root)
        except (ValueError, FileNotFoundError) as e:
            log.error(
                "delivery_xlsx_path_invalid",
                run_id=run_id,
                error=repr(e),
            )
            return _build_stats_skip_path(
                run_id=run_id,
                run_writer=run_writer,
                delivery_status="undelivered_telegram_unreachable",
                route=decision.route,
                last_error=repr(e)[:500],
            )

    # ---- Step 6b: ENV chat_id presence per route (D-611 asymmetric) ----
    # route=business + business_chat_id missing  -> degrade to ops_only.
    # route=business + ops_chat_id missing       -> warn + proceed (business ok).
    # route=ops_only + ops_chat_id missing       -> skipped_no_credentials.
    # route=ops_only + business_chat_id missing  -> no impact (not used).
    if decision.route == "business" and not env.business_chat_id:
        log.warning("delivery_business_chat_missing", run_id=run_id)
        decision = GateDecision(
            route="ops_only",
            gate_failed_check="missing_env_TG_BUSINESS_CHAT_ID",
            gate_failure_reason="missing_env_TG_BUSINESS_CHAT_ID",
        )
        # Re-build ops alert with new reason so the operator sees why business
        # send was suppressed.
        ops_alert_html = build_ops_alert(
            run_id=run_id,
            reason_key="missing_env_TG_BUSINESS_CHAT_ID",
            started_at_utc=started_at_utc,
            run_status=actual_run_status,
            gate_failed_check=decision.gate_failed_check,
            viled_count=viled_count,
            goldapple_count=goldapple_count,
            match_count=match_count,
            match_rate=match_rate,
            size_guard_failed=False,
            xlsx_size_mb=0.0,
            size_limit_mb=45,
            error_short="",
            truncate_chars=config.ops_message_truncate_chars,
        )
        business_payload = None
    if decision.route == "business" and not env.ops_chat_id:
        log.warning(
            "delivery_ops_chat_missing_acceptable_for_business_route",
            run_id=run_id,
            note=(
                "business send proceeds; if it later fails, manual recovery "
                "via deliver-run --run-id N"
            ),
        )
    if decision.route == "ops_only" and not env.ops_chat_id:
        log.error("delivery_ops_chat_missing", run_id=run_id)
        return _build_stats_skip_path(
            run_id=run_id,
            run_writer=run_writer,
            delivery_status="skipped_no_credentials",
            route="skipped",
            last_error="missing_env_TG_OPS_CHAT_ID",
        )

    # ---- Step 6c: asyncio.run sync→async glue (mirror main_run.py:224) ----
    try:
        async_result = asyncio.run(
            _send_async(
                token=env.bot_token,
                config=config,
                route=decision.route,
                business_chat_id=env.business_chat_id,
                ops_chat_id=env.ops_chat_id,
                business_payload=business_payload,
                ops_alert_html=ops_alert_html,
                xlsx_full_path=xlsx_full_path,
            )
        )
    except Exception as e:  # noqa: BLE001 -- Pitfall A defensive catch-all
        tb = traceback.format_exc()
        log.error(
            "delivery_unexpected_crash",
            run_id=run_id,
            error=repr(e),
            traceback=tb,
        )
        return _build_stats_skip_path(
            run_id=run_id,
            run_writer=run_writer,
            delivery_status="undelivered_telegram_unreachable",
            route=decision.route,
            last_error=repr(e)[:500],
        )

    # ---- Step 7: Single atomic patch_stats (Pitfall 6) ----
    builder = DeliverStatsBuilder()
    builder.set("delivery_status", async_result.delivery_status)
    builder.set("route", decision.route)
    builder.set("business_caption_message_id", async_result.business_caption_message_id)
    builder.set("business_document_message_id", async_result.business_document_message_id)
    builder.set("ops_message_id", async_result.ops_message_id)
    builder.set("attempt_count", async_result.attempt_count)
    builder.set("last_error", _truncate(async_result.last_error, 500))
    delivered_at = (
        datetime.now(timezone.utc).isoformat()
        if async_result.delivery_status.startswith("delivered_")
        else ""
    )
    builder.set("delivered_at", delivered_at)
    run_writer.patch_stats(run_id, dict(builder.delta))

    elapsed = time.perf_counter() - started
    log.info(
        "delivery_phase_complete",
        run_id=run_id,
        delivery_status=async_result.delivery_status,
        route=decision.route,
        duration_s=round(elapsed, 3),
    )

    return DeliveryPhaseResult(
        delivery_status=async_result.delivery_status,
        route=decision.route,
        business_caption_message_id=async_result.business_caption_message_id,
        business_document_message_id=async_result.business_document_message_id,
        ops_message_id=async_result.ops_message_id,
        attempt_count=async_result.attempt_count,
        last_error=_truncate(async_result.last_error, 500),
        delivered_at=delivered_at,
        stats_delta=dict(builder.delta),
    )


# --------------------------------------------------------------------------- #
# Async send block (single ``async with`` Bot lifecycle -- Pitfall B)         #
# --------------------------------------------------------------------------- #


async def _send_async(
    *,
    token: str,
    config: DeliverConfig,
    route: str,
    business_chat_id: Optional[str],
    ops_chat_id: Optional[str],
    business_payload: Optional[dict],
    ops_alert_html: Optional[str],
    xlsx_full_path: Optional[Path],
) -> _AsyncSendResult:
    """Single async block: ``async with Bot()`` + sequential sends + retry.

    Mirror of ``main_run.py::run_goldapple_phase`` asyncio.run target. The
    ``async with`` wrapper guarantees aiohttp session auto-close (D-602 /
    Pitfall B). Returns an ``_AsyncSendResult`` bundle for the sync caller
    to map onto stats.
    """
    result = _AsyncSendResult()
    bot = await open_bot(token, parse_mode=config.parse_mode)
    async with bot:  # Pitfall B -- auto-close aiohttp session
        if route == "business":
            assert business_payload is not None
            assert business_chat_id is not None
            assert xlsx_full_path is not None

            # Caption split path (Claude's Discretion): summary_text > 1024
            # chars -> send_message FIRST with full summary, then attach the
            # short fallback caption to the document.
            if business_payload["is_split"]:
                cap_msg: SendOutcome = await send_message_with_policy(
                    bot,
                    business_chat_id,
                    business_payload["full_summary"],
                    max_attempts=config.retry_max_attempts,
                )
                result.business_caption_message_id = cap_msg.message_id
                result.attempt_count += cap_msg.attempts
                if cap_msg.error:
                    result.last_error = cap_msg.error
                    result.delivery_status = "undelivered_telegram_unreachable"
                    return result

            # send_document is always called for the business route.
            doc_msg: SendOutcome = await send_document_with_policy(
                bot,
                business_chat_id,
                xlsx_full_path,
                business_payload["caption"],
                max_attempts=config.retry_max_attempts,
            )
            result.business_document_message_id = doc_msg.message_id
            result.attempt_count += doc_msg.attempts
            if doc_msg.error:
                result.last_error = doc_msg.error
                result.delivery_status = "undelivered_telegram_unreachable"
            else:
                # Pitfall D semantics: non-split path -- caption + document
                # ride on the same Telegram message -> message_id mirrors.
                if not business_payload["is_split"]:
                    result.business_caption_message_id = doc_msg.message_id
                result.delivery_status = "delivered_business"
        else:  # ops_only
            assert ops_alert_html is not None
            assert ops_chat_id is not None
            ops_msg: SendOutcome = await send_message_with_policy(
                bot,
                ops_chat_id,
                ops_alert_html,
                max_attempts=config.retry_max_attempts,
            )
            result.ops_message_id = ops_msg.message_id
            result.attempt_count += ops_msg.attempts
            if ops_msg.error:
                result.last_error = ops_msg.error
                result.delivery_status = "undelivered_telegram_unreachable"
            else:
                result.delivery_status = "delivered_ops_only"
    return result


__all__ = ["DeliveryPhaseResult", "run_delivery_phase"]
