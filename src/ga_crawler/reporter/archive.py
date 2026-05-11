"""Phase 5 reporter filesystem service — ISO-week filename + atomic write + size guard.

Pure-stdlib (no pandas/xlsxwriter). Module-level functions; no class state
required since output_dir is plumbed via ReportConfig (caller).

Three independent primitives consumed by the Plan 05-04 orchestrator:

  1. ``derive_filename(started_at, tz_name)`` — D-512 ISO-week filename derivation
     from a tz-aware ``runs.started_at`` value. Rejects naive datetime per
     DATA-05 invariant. Handles Pitfall 4 ISO 8601 Thursday-rule year boundaries.

  2. ``write_atomic(xlsx_bytes, target_path)`` — D-510 crash-safe disk write via
     ``*.xlsx.tmp`` sibling + ``os.replace``. Auto-creates parent directory.
     Returns final ``stat().st_size`` of the written file.

  3. ``check_size_guard(file_path, limit_mb)`` — D-515 / REPORT-06 size guard.
     Returns ``(passed, size_bytes)``; **never raises**. Caller logs warning
     and sets ``report.size_guard_passed=False`` flag. xlsx persists on disk
     regardless — ARCHITECTURE.md "reporter independent of delivery" invariant.

Source: 05-CONTEXT.md D-510 / D-512 / D-515; 05-RESEARCH.md Patterns 8 / 9 / 10
and Pitfalls 4, 5; 05-PATTERNS.md "src/ga_crawler/reporter/archive.py" section.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# D-512 — ISO-week filename derivation from tz-aware started_at.
# ---------------------------------------------------------------------------


def derive_filename(
    started_at: datetime,
    tz_name: str = "Asia/Almaty",
) -> str:
    """D-512 deterministic ISO-week filename from ``runs.started_at``.

    Args:
      started_at: MUST be timezone-aware (DATA-05 invariant). SQLModel
                  ``default_factory`` uses ``datetime.now(timezone.utc)`` so
                  production values are always tz-aware.
      tz_name:    IANA timezone name. Default ``"Asia/Almaty"`` per D-512;
                  matches Phase 7 cron ``CRON_TZ=Asia/Almaty`` invariant.

    Returns:
      Filename string ``"YYYY-WNN.xlsx"`` (e.g. ``"2026-W19.xlsx"``). Week is
      zero-padded to 2 digits per ISO 8601 conventions.

    Raises:
      ValueError: if ``started_at`` is naive (timezone-unaware). Helpful
                  message points at the DATA-05 invariant for ops debugging.

    Edge cases (Pitfall 4, ISO 8601 Thursday-rule):
      - ``2027-01-01`` UTC (Fri) → ``"2026-W53.xlsx"``
        (Thursday Dec 31 belongs to 2026-W53; Friday Jan 1 still in W53)
      - ``2025-12-29`` UTC (Mon) → ``"2026-W01.xlsx"``
        (first Thursday of 2026 is Jan 1, week starts Dec 29 2025)
      - ``2026-05-10`` 14:00 UTC → Almaty 19:00 Sun → ``"2026-W19.xlsx"``

    Source: 05-CONTEXT.md L81-88; 05-RESEARCH.md Pitfall 4 L712-724.
    """
    if started_at.tzinfo is None:
        raise ValueError(
            "started_at must be timezone-aware (DATA-05 invariant); "
            f"got naive datetime {started_at!r}"
        )
    local = started_at.astimezone(ZoneInfo(tz_name))
    iso_year, iso_week, _ = local.isocalendar()
    return f"{iso_year}-W{iso_week:02d}.xlsx"


# ---------------------------------------------------------------------------
# D-510 — atomic write via temp-file sibling + os.replace.
# ---------------------------------------------------------------------------


def write_atomic(xlsx_bytes: bytes, target_path: Path) -> int:
    """Atomic disk write via ``*.xlsx.tmp`` sibling + ``os.replace``.

    Crash-safe (Pitfall 5): if the process dies between
    ``tmp_path.write_bytes`` and ``os.replace``, ``target_path`` either does
    not exist or contains the *previous* run's full content — never partial.
    Orphan ``*.xlsx.tmp`` may remain on crash and is cleaned by the Phase 7
    ops playbook glob.

    Args:
      xlsx_bytes:  Complete xlsx file body (built in memory by
                   ``excel_builder.build_workbook``). May be empty (zero-byte
                   write is supported; produces an empty file).
      target_path: Final disk location (e.g. ``reports/2026-W19.xlsx``).
                   Parent directories are auto-created via ``mkdir(parents=True,
                   exist_ok=True)``.

    Returns:
      Final file size in bytes after rename. Equal to
      ``target_path.stat().st_size``.

    Notes:
      - ``os.replace`` is the atomic primitive: per CPython docs it is atomic
        on POSIX **and** Windows NTFS when source + target live on the same
        filesystem. Using a same-suffix-style ``*.xlsx.tmp`` sibling guarantees
        same-FS placement.
      - Logs a ``report_overwritten`` event when ``target_path`` already
        existed before the write (D-510 — second call within same ISO week
        overwrites without backup; structlog event is the audit trail).
      - The function does **not** clean up an orphan ``*.xlsx.tmp`` from a
        prior crash; the rename target uses the same ``.tmp`` name so a stale
        tmp is naturally overwritten by the new write.

    Source: 05-CONTEXT.md L66 (D-510 overwrite policy); 05-RESEARCH.md
    Pattern 9 atomic write L555-579 + Pitfall 5 L726-734.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        prev_size = target_path.stat().st_size
        log.info(
            "report_overwritten",
            path=str(target_path),
            previous_size_bytes=prev_size,
        )

    # Append .tmp suffix so tmp lives in the same parent dir (same FS).
    # `target.with_suffix('.xlsx.tmp')` would lose the .xlsx suffix; building
    # the sibling via `suffix + ".tmp"` keeps both in place.
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_bytes(xlsx_bytes)

    # os.replace is the atomic primitive. Path.replace wraps it.
    os.replace(tmp_path, target_path)

    return target_path.stat().st_size


# ---------------------------------------------------------------------------
# D-515 — REPORT-06 size guard. Flag-only, never raises.
# ---------------------------------------------------------------------------


def check_size_guard(file_path: Path, limit_mb: int) -> tuple[bool, int]:
    """D-515 / REPORT-06 size guard. Read-only, flag-only — never raises.

    Args:
      file_path: Path to xlsx already written to disk (e.g. via
                 ``write_atomic``).
      limit_mb:  Megabyte threshold (default ``45`` per ``ReportConfig`` /
                 D-516 — 50 MB Telegram Bot API limit minus 5 MB safety).

    Returns:
      ``(passed, size_bytes)``:
        - ``passed=True`` if ``size_bytes <= limit_mb * 1024 * 1024``
          (**inclusive** boundary — a file exactly equal to the limit passes).
        - ``size_bytes`` is the file's logical ``stat().st_size`` in bytes.

    Notes:
      - **Never raises** on oversize. Caller (Plan 05-04 orchestrator) logs a
        ``report_size_exceeded`` warning and sets
        ``report.size_guard_passed=False`` flag in ``runs.stats``. xlsx remains
        on disk regardless — ARCHITECTURE.md "reporter independent of delivery"
        invariant + D-515 "xlsx ВСЕГДА пишется на диск" for manual recovery.
      - Run status remains ``'success'``. The size guard is a delivery-time
        concern surfaced via stats flag, not a reporter-time failure.

    Source: 05-CONTEXT.md L118-123 (D-515 size guard semantics);
    05-RESEARCH.md Pattern 10 size-guard L582-607.
    """
    size_bytes = file_path.stat().st_size
    limit_bytes = limit_mb * 1024 * 1024
    return (size_bytes <= limit_bytes, size_bytes)


__all__ = ["derive_filename", "write_atomic", "check_size_guard"]
