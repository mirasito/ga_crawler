"""Phase 6 message builder — pure transforms; no I/O.

Two public callables:
  build_ops_alert(...) -> str
      D-610 single-template ops alert with a reason-field placeholder.
      Used for all 4 pre-send gate-fail reasons + the
      ``delivery_exception`` fallback (one template, not per-reason
      templates — DRY + golden-file source-locked).

  business_caption(summary_text, max_chars=1024) -> tuple[str, bool]
      Pure helper for Plan 06-04 ``delivery_run``: passes the
      D-514-source-of-truth ``summary_text`` through verbatim when it
      fits inside Telegram's 1024-char document caption budget;
      otherwise returns a sentinel caption (``См. сводку выше``) plus a
      flag telling the orchestrator to send the summary as a separate
      pre-document message.

Notes
-----
* HTML escaping uses ``html.escape(value, quote=False)`` from stdlib per
  RESEARCH caveat #3 (Telegram HTML mode only escapes ``< > &``; quotes
  must stay literal so allowed tags like ``<a href="...">`` work).
  Pitfall A: every dynamic str field is wrapped in ``_esc(...)``.
* Pitfall E + W1 fix: the Almaty timestamp uses ``strftime("%Y-%m-%d %H:%M %z")``
  — lowercase ``%z`` yields a numeric ``+0500`` offset that renders
  identically on Linux / macOS / Windows. Uppercase ``%Z`` (named zone
  abbreviation) is *not* portable across platforms and would drift
  the golden file between OSes.

Source anchors: 06-CONTEXT.md D-609 + D-610; 06-RESEARCH.md Pattern 4 +
Pitfall A + Pitfall E + caveat #3; 06-PATTERNS.md
"src/ga_crawler/delivery/message_builder.py".
"""

from __future__ import annotations

import html as stdlib_html  # RESEARCH caveat #3 — stdlib over aiogram.html
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo  # Pitfall E — Almaty TZ formatting


# D-610 reason-key → short human-readable phrase. Source-locked: any new
# gate-failure reason must be added here AND covered by
# tests/test_message_builder.py::test_reason_short_dict_complete.
REASON_SHORT: dict[str, str] = {
    "upstream_status_failed":          "upstream pipeline failed",
    "upstream_status_running":         "upstream pipeline still running",
    "upstream_status_None":            "run row missing",
    "no_xlsx_in_stats":                "xlsx file missing",
    "xlsx_oversize":                   "xlsx too large for Telegram",
    "empty_summary_text":              "missing report summary",
    "missing_env_TG_BUSINESS_CHAT_ID": "TG_BUSINESS_CHAT_ID env missing",
    "delivery_exception":              "delivery layer crashed",
}


def _format_almaty(started_at_utc: datetime) -> str:
    """Pitfall E: format a datetime in ``Asia/Almaty`` with numeric offset.

    * Naive datetimes are treated as UTC (DATA-05 lifecycle invariant —
      every persisted timestamp is UTC; only display goes Almaty).
    * Format string is ``"%Y-%m-%d %H:%M %z"`` (W1 fix): lowercase
      ``%z`` gives the numeric offset (e.g. ``+0500``) which is stable
      across platforms; uppercase ``%Z`` returns a platform-dependent
      named abbreviation and would drift the golden file on Windows.
    """
    if started_at_utc.tzinfo is None:
        started_at_utc = started_at_utc.replace(tzinfo=timezone.utc)
    return started_at_utc.astimezone(ZoneInfo("Asia/Almaty")).strftime(
        "%Y-%m-%d %H:%M %z"
    )


def _esc(value: str) -> str:
    """HTML-escape per Telegram HTML parse_mode rules (Pitfall A, caveat #3).

    Telegram HTML mode allows ``<b>``, ``<i>``, ``<u>``, ``<s>``,
    ``<code>``, ``<pre>``, ``<a href>``. We only need to escape
    ``< > &`` — quotes stay literal so href attributes work.
    """
    return stdlib_html.escape(value, quote=False)


def build_ops_alert(
    *,
    run_id: int,
    reason_key: str,
    started_at_utc: datetime,
    run_status: str,
    gate_failed_check: Optional[str],
    viled_count: int,
    goldapple_count: int,
    match_count: int,
    match_rate: float,
    size_guard_failed: bool,
    xlsx_size_mb: float,
    size_limit_mb: int,
    error_short: Optional[str],
    truncate_chars: int = 3500,
) -> str:
    """D-610 single ops-alert template (HTML parse_mode).

    All dynamic str fields pass through ``_esc`` (Pitfall A). The error
    block is omitted entirely when ``error_short`` is falsy
    ("" / None). The ``xlsx size`` line is emitted only when
    ``size_guard_failed=True``.

    The output is deterministic — same inputs → byte-identical output —
    so the golden file
    ``tests/fixtures/delivery/ops-alert-templates.txt`` can pin it.
    """
    reason_short = REASON_SHORT.get(reason_key, reason_key)
    parts: list[str] = [
        f"🚨 <b>Weekly run #{run_id}</b> — {_esc(reason_short)}",
        "",
        f"<i>Run started:</i> {_esc(_format_almaty(started_at_utc))}",
        f"<i>Run status:</i> <code>{_esc(run_status)}</code>",
        f"<i>Gate failure:</i> <code>{_esc(gate_failed_check or '')}</code>",
        "",
        "<i>Snapshot stats:</i>",
        f"  viled: {viled_count} • goldapple: {goldapple_count}",
        f"  matches: {match_count} ({match_rate}%)",
    ]
    if size_guard_failed:
        parts.append(
            f"  xlsx size: {xlsx_size_mb} MB (limit: {size_limit_mb} MB)"
        )
    parts.append("")
    if error_short:
        truncated = error_short[:truncate_chars]
        parts.append(f"<i>Error:</i> <pre>{_esc(truncated)}</pre>")
        parts.append("")
    parts.append(
        f"<i>Manual recovery:</i> "
        f"<code>python -m ga_crawler deliver-run --run-id {run_id}</code>"
    )
    return "\n".join(parts)


def business_caption(summary_text: str, max_chars: int = 1024) -> tuple[str, bool]:
    """Pure helper for ``delivery_run``: caption-fit decision (D-514 cascade).

    Returns ``(caption, is_split_path)``:
      * ``len(summary_text) <= max_chars`` → ``(summary_text, False)`` —
        attach summary as the document's caption directly.
      * otherwise → ``("См. сводку выше", True)`` — orchestrator must
        send the full summary as a *separate* ``send_message`` before
        the ``send_document`` call so the caption stays under Telegram's
        1024-char limit.
    """
    if len(summary_text) <= max_chars:
        return summary_text, False
    return "См. сводку выше", True


__all__ = ["REASON_SHORT", "build_ops_alert", "business_caption"]
