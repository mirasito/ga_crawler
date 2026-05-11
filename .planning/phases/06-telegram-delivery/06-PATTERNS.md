# Phase 6: Telegram Delivery + Ops/Business Split — Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 19 (8 NEW source + 4 AMEND source + 7 NEW tests + 1 AMEND conftest + 1 AMEND test_stats)
**Analogs found:** 19 / 19 (Phase 4/5 mirrors)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|-------------------|------|-----------|----------------|-------|
| `src/ga_crawler/delivery/__init__.py` | package-init | n/a | `src/ga_crawler/reporter/__init__.py` | exact |
| `src/ga_crawler/delivery/config.py` | config | file-I/O + env | `src/ga_crawler/reporter/config.py` | exact |
| `src/ga_crawler/delivery/telegram_client.py` | service | async network + retry | `src/ga_crawler/fetchers/viled.py` (tenacity); `src/ga_crawler/fetchers/goldapple.py` (async Bot lifecycle) | role-match |
| `src/ga_crawler/delivery/message_builder.py` | utility | pure transform | `src/ga_crawler/reporter/summary_builder.py` | role-match |
| `src/ga_crawler/delivery/gate.py` | service | DB read + pure decision | `src/ga_crawler/matcher/strict_key.py` (read_run_status) | role-match |
| `src/ga_crawler/delivery/stats.py` | model | namespace builder | `src/ga_crawler/reporter/stats.py` | exact |
| `src/ga_crawler/runners/delivery_run.py` | orchestrator | sync→async glue + CRUD | `src/ga_crawler/runners/reporter_run.py` | exact |
| `src/ga_crawler/runners/main_run.py` (AMEND) | orchestrator | composition | self (Plan 05-05 insertion point) | self-amend |
| `src/ga_crawler/cli.py` (AMEND) | controller | argparse subcommand | self `_cmd_report` | self-amend |
| `pyproject.toml` (AMEND) | config | toml | self `[tool.ga_crawler.report]` | self-amend |
| `.env.example` (NEW) | config | env template | (none — first in project) | no-analog |
| `.gitignore` (AMEND) | config | text | self (already lists `.env`) | self-amend |
| `tests/conftest.py` (AMEND) | test-fixtures | DB fixture | self `synthetic_report_run` | self-amend |
| `tests/test_delivery_config.py` (NEW) | test | unit | (no Phase 5 `test_report_config.py` — closest analog is `test_report_stats.py` style) | role-match |
| `tests/test_telegram_client.py` (NEW) | test | unit + async-mock | `tests/unit/test_viled_fetcher.py` (tenacity), `tests/integration/test_viled_fetcher_mocked.py` | role-match |
| `tests/test_gate.py` (NEW) | test | unit | (no exact analog — uses `synthetic_report_run` fixture) | partial |
| `tests/test_message_builder.py` (NEW) | test | unit + golden-file | `tests/unit/test_summary_builder.py` | role-match |
| `tests/test_delivery_stats.py` (NEW) | test | unit | `tests/unit/test_report_stats.py` | exact |
| `tests/test_delivery_source_lock.py` (NEW) | test | structural canary | `tests/test_stats_namespace.py` patterns | partial |
| `tests/integration/test_delivery_run.py` (NEW) | test | integration | `tests/integration/test_reporter_run.py` | exact |
| `tests/integration/test_cli_deliver.py` (NEW) | test | integration + subprocess | `tests/integration/test_cli_report_subcommand.py` | exact |
| `tests/integration/test_weekly_run_with_delivery.py` (NEW) | test | integration | `tests/integration/test_main_run_with_reporter.py` | exact |
| `tests/test_stats_namespace.py` (AMEND) | test | structural | self (5-way disjoint extension) | self-amend |

---

## Pattern Assignments

### `src/ga_crawler/delivery/__init__.py` (package-init)

**Analog:** `src/ga_crawler/reporter/__init__.py` (full file, 2 lines).

**Copy verbatim — single-line docstring:**
```python
"""Delivery (Phase 6): aiogram Telegram client + pre-send gate + ops/business routing."""
```

---

### `src/ga_crawler/delivery/config.py` (config, env + toml)

**Analog:** `src/ga_crawler/reporter/config.py` (full file, 59 lines).

**Class skeleton + `from_pyproject` pattern — mirror exactly (lines 11-56):**
```python
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DeliverConfig:
    """Operator-tunable runtime constants for the delivery layer.

    Defaults mirror `[tool.ga_crawler.deliver]` in pyproject.toml so that
    constructing `DeliverConfig()` directly (e.g. in tests) yields the same
    values as `DeliverConfig.from_pyproject()` against the production toml.

    Per D-614.
    """

    retry_max_attempts: int = 3
    retry_backoff_min_seconds: int = 5
    retry_backoff_max_seconds: int = 45
    ops_message_truncate_chars: int = 3500
    business_caption_max_chars: int = 1024
    parse_mode: str = "HTML"

    @classmethod
    def from_pyproject(cls, pyproject_path: Path | str = "pyproject.toml") -> "DeliverConfig":
        """Read [tool.ga_crawler.deliver] from the given pyproject.toml."""
        path = Path(pyproject_path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        deliver = (
            data.get("tool", {})
            .get("ga_crawler", {})
            .get("deliver", {})
        )
        return cls(
            retry_max_attempts=int(deliver.get("retry_max_attempts", cls.retry_max_attempts)),
            retry_backoff_min_seconds=int(deliver.get("retry_backoff_min_seconds", cls.retry_backoff_min_seconds)),
            retry_backoff_max_seconds=int(deliver.get("retry_backoff_max_seconds", cls.retry_backoff_max_seconds)),
            ops_message_truncate_chars=int(deliver.get("ops_message_truncate_chars", cls.ops_message_truncate_chars)),
            business_caption_max_chars=int(deliver.get("business_caption_max_chars", cls.business_caption_max_chars)),
            parse_mode=str(deliver.get("parse_mode", cls.parse_mode)),
        )
```

**NEW `from_env` API — first in project; pattern recommended in RESEARCH caveat #4** (D-611 + Pitfall A):
```python
@dataclass(frozen=True)
class DeliverEnvConfig:
    """ENV-loaded credentials (separated from from_pyproject — secrets NEVER in git)."""
    bot_token: Optional[str]
    business_chat_id: Optional[str]
    ops_chat_id: Optional[str]

    @classmethod
    def from_env(cls) -> "DeliverEnvConfig":
        """Read TG_* from os.environ.

        NOTE: load_dotenv() is NOT called here — CLI's _cmd_deliver calls it
        ONCE at startup. Tests use monkeypatch.setenv() to bypass file IO.
        Per RESEARCH caveat #4.
        """
        return cls(
            bot_token=os.getenv("TG_BOT_TOKEN") or None,
            business_chat_id=os.getenv("TG_BUSINESS_CHAT_ID") or None,
            ops_chat_id=os.getenv("TG_OPS_CHAT_ID") or None,
        )
```

**Export pattern (line 58):**
```python
__all__ = ["DeliverConfig", "DeliverEnvConfig"]
```

---

### `src/ga_crawler/delivery/stats.py` (model, namespace builder)

**Analog:** `src/ga_crawler/reporter/stats.py` (full file, 80 lines).

**Mirror exactly — 8 keys (D-607) instead of 7:**
```python
"""Phase 6 delivery stats namespace builder.

Mirror of ReportStatsBuilder. Enforces `deliver.` prefix; reuses
`StatsNamespaceError` from runner/stats.py (no re-definition). All keys
listed below are write-able via bare-name or fully-namespaced; everything
else raises.

Source: 06-CONTEXT.md D-607 (8 keys, mirror D-514 pattern).
"""

from __future__ import annotations

from typing import Any, Iterable

from ga_crawler.runner.stats import StatsNamespaceError

# 8 deliver.* keys, D-607. Any new key MUST be added here AND the regression
# test tests/test_delivery_stats.py::test_delivery_stats_keys_count updated.
DELIVER_STATS_KEYS: tuple[str, ...] = (
    "deliver.delivery_status",              # str — enum D-606 (6 values)
    "deliver.route",                        # str — "business" | "ops_only" | "skipped" | ""
    "deliver.business_caption_message_id",  # int — Telegram message_id; -1 sentinel
    "deliver.business_document_message_id", # int — Telegram message_id; -1 sentinel
    "deliver.ops_message_id",               # int — Telegram message_id; -1 sentinel
    "deliver.attempt_count",                # int — cumulative across retries
    "deliver.last_error",                   # str — short truncated error; "" sentinel
    "deliver.delivered_at",                 # str — ISO 8601 UTC; "" sentinel
)


_DELIVER_BARE_TO_NAMESPACED: dict[str, str] = {
    k.split(".", 1)[1]: k for k in DELIVER_STATS_KEYS
}


class DeliverStatsBuilder:
    """Mirror of ReportStatsBuilder / MatchStatsBuilder / Viled / Goldapple."""
    def __init__(self) -> None:
        self.delta: dict[str, Any] = {}

    def _resolve(self, bare_key: str) -> str:
        if bare_key in _DELIVER_BARE_TO_NAMESPACED:
            return _DELIVER_BARE_TO_NAMESPACED[bare_key]
        if bare_key in DELIVER_STATS_KEYS:
            return bare_key
        raise StatsNamespaceError(
            f"key {bare_key!r} not in DELIVER_STATS_KEYS; "
            f"allowed: {sorted(DELIVER_STATS_KEYS)}"
        )

    def set(self, bare_key: str, value: Any) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = value

    def inc(self, bare_key: str, n: int = 1) -> None:
        full = self._resolve(bare_key)
        self.delta[full] = self.delta.get(full, 0) + n

    def get(self, bare_key: str, default: Any = None) -> Any:
        try:
            full = self._resolve(bare_key)
        except StatsNamespaceError:
            return default
        return self.delta.get(full, default)

    def keys(self) -> Iterable[str]:
        return self.delta.keys()

    def __len__(self) -> int:
        return len(self.delta)


__all__ = ["DELIVER_STATS_KEYS", "DeliverStatsBuilder"]
```

---

### `src/ga_crawler/delivery/gate.py` (service, DB-read + pure decision)

**Analog:** `src/ga_crawler/matcher/strict_key.py::read_run_status` (lines 199-207) for REUSE.

**Reused helper (D-604 step 1, lines 199-207):**
```python
def read_run_status(engine, run_id: int) -> Optional[str]:
    """D-411 input: returns the literal status column value or None.
    Caller interprets None / 'running' / 'failed' as skip-conditions; only
    'success' OR 'partial' allow matching to proceed.
    """
    with engine.connect() as conn:
        row = conn.execute(RUN_STATUS_SQL, {"rid": run_id}).first()
    return row[0] if row else None
```

**New gate composition pattern (D-604 4-check + short-circuit) — pure function returning a frozen dataclass:**
```python
"""Phase 6 pre-send gate — composes 4 checks (D-604), first-fail-wins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import structlog

from ga_crawler.interfaces import RunWriterProtocol
from ga_crawler.matcher.strict_key import read_run_status  # D-604 REUSE

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GateDecision:
    route: Literal["business", "ops_only"]
    gate_failed_check: Optional[str]    # None when route=business
    gate_failure_reason: Optional[str]  # human-readable fail-reason


def evaluate_gate(engine, run_writer: RunWriterProtocol, run_id: int) -> GateDecision:
    """4 independent checks; short-circuits at first fail (D-604)."""
    # Check 1: runs.status == 'success' (REUSE from matcher.strict_key)
    status = read_run_status(engine, run_id)
    if status != "success":
        return GateDecision(
            route="ops_only",
            gate_failed_check="run_status",
            gate_failure_reason=f"upstream_status_{status}",
        )
    # Check 2: xlsx_path non-empty (defends Plan 05-05 default size_guard_passed=True trap)
    stats = run_writer.get_stats(run_id) or {}
    if not stats.get("report.xlsx_path"):
        return GateDecision(
            route="ops_only",
            gate_failed_check="xlsx_path",
            gate_failure_reason="no_xlsx_in_stats",
        )
    # Check 3: size_guard_passed (D-515 cascade)
    if not stats.get("report.size_guard_passed", False):
        return GateDecision(
            route="ops_only",
            gate_failed_check="size_guard",
            gate_failure_reason="xlsx_oversize",
        )
    # Check 4: summary_text non-empty
    if not str(stats.get("report.summary_text", "")).strip():
        return GateDecision(
            route="ops_only",
            gate_failed_check="summary_text",
            gate_failure_reason="empty_summary_text",
        )
    return GateDecision(route="business", gate_failed_check=None, gate_failure_reason=None)
```

**Logging pattern (steal verbatim from `runners/reporter_run.py:103-108`):**
```python
log.warning(
    "delivery_gate_decision",
    run_id=run_id,
    route=decision.route,
    gate_failed_check=decision.gate_failed_check,
    gate_failure_reason=decision.gate_failure_reason,
)
```

---

### `src/ga_crawler/delivery/message_builder.py` (utility, pure transform)

**Analog:** `src/ga_crawler/reporter/summary_builder.py` (`build_summary` — pure function, no I/O, structlog log on entry).

**Pattern: pure function + golden-file-friendly output** (mirror `build_summary` signature shape):
```python
"""Phase 6 message builder — pure transforms; no I/O.

build_ops_alert(...) -> str: D-610 single-template ops alert with reason-field.
business_caption(summary_text) -> str: pass-through (D-514 source-of-truth verbatim).
"""

from __future__ import annotations

import html as stdlib_html  # caveat #3 — stdlib over aiogram.html
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo  # Pitfall E — Almaty TZ formatting


REASON_SHORT: dict[str, str] = {
    "upstream_status_failed":   "upstream pipeline failed",
    "upstream_status_running":  "upstream pipeline still running",
    "upstream_status_None":     "run row missing",
    "no_xlsx_in_stats":         "xlsx file missing",
    "xlsx_oversize":            "xlsx too large for Telegram",
    "empty_summary_text":       "missing report summary",
    "missing_env_TG_BUSINESS_CHAT_ID": "TG_BUSINESS_CHAT_ID env missing",
    "delivery_exception":       "delivery layer crashed",
}


def _format_almaty(started_at_utc: datetime) -> str:
    """Pitfall E: Phase 5 uses Asia/Almaty for ISO-week; mirror for ops alert."""
    if started_at_utc.tzinfo is None:
        started_at_utc = started_at_utc.replace(tzinfo=timezone.utc)
    return started_at_utc.astimezone(ZoneInfo("Asia/Almaty")).strftime("%Y-%m-%d %H:%M %Z")


def _esc(value: str) -> str:
    """HTML-escape per Telegram HTML parse_mode rules (caveat #3, Pitfall A).
    Telegram allows: <b><i><u><s><code><pre><a href>.
    """
    return stdlib_html.escape(value, quote=False)


def build_ops_alert(
    *,
    run_id: int,
    reason_key: str,           # e.g. "xlsx_oversize" → looked up in REASON_SHORT
    started_at_utc: datetime,  # runs.started_at (DATA-05: tz-aware)
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
    truncate_chars: int = 3500,  # D-614 ops_message_truncate_chars
) -> str:
    """D-610 single ops-alert template with reason-field. HTML parse_mode."""
    reason_short = REASON_SHORT.get(reason_key, reason_key)
    parts = [
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
        parts.append(f"  xlsx size: {xlsx_size_mb} MB (limit: {size_limit_mb} MB)")
    parts.append("")
    if error_short:
        truncated = error_short[:truncate_chars]
        parts.append(f"<i>Error:</i> <pre>{_esc(truncated)}</pre>")
        parts.append("")
    parts.append(
        f"<i>Manual recovery:</i> <code>python -m ga_crawler deliver-run --run-id {run_id}</code>"
    )
    return "\n".join(parts)


__all__ = ["REASON_SHORT", "build_ops_alert"]
```

---

### `src/ga_crawler/delivery/telegram_client.py` (service, async network + retry)

**Analog 1 (tenacity wrap):** `src/ga_crawler/fetchers/viled.py` lines 87-92 (RESEARCH cited).

```python
@retry(
    stop=stop_after_attempt(VILED_RETRY_MAX_ATTEMPTS),
    wait=wait_exponential_jitter(initial=VILED_RETRY_WAIT_INITIAL, max=VILED_RETRY_WAIT_MAX),
    retry=retry_if_exception_type(_RETRY_TYPES),
    reraise=True,
)
def _fetch_html(url: str, timeout_s: int = VILED_TIMEOUT_S) -> tuple[int, str]:
    ...
```

**New telegram_client pattern (D-601 + D-603 + RESEARCH §Pattern 1 + caveats #2, #6, Pitfall A, B):**
```python
"""Phase 6 Telegram client — aiogram Bot wrapper + tenacity retry policy.

D-601: aiogram 3.27.x async-native.
D-602: async-with Bot lifecycle (auto-close session — Pitfall B).
D-603: tenacity 3-retry on (TelegramNetworkError, TelegramServerError);
       TelegramRetryAfter handled OUTSIDE tenacity per RESEARCH §11.
Pitfall A: TelegramBadRequest / TelegramForbiddenError / TelegramNotFound
       → NO retry; caller's outer try/except maps to undelivered_telegram_unreachable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.types import FSInputFile, Message
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
)

log = structlog.get_logger(__name__)


_RETRY_TYPES = (TelegramNetworkError, TelegramServerError)


@dataclass
class SendOutcome:
    """One send call result — caller patches stats accordingly."""
    message_id: int            # -1 on failure
    attempts: int              # cumulative
    error: Optional[str] = None  # "" on success


# Per RESEARCH caveat #2: explicit 5/15/45 via wait_chain (NOT wait_exponential).
def _build_retry_decorator(max_attempts: int = 3):
    return retry(
        retry=retry_if_exception_type(_RETRY_TYPES),
        stop=stop_after_attempt(max_attempts),
        wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45)),
        reraise=True,
    )


async def _send_with_retry_after_loop(
    send_callable,
    *,
    max_retry_after_iterations: int = 3,
) -> Message:
    """Wraps a tenacity-decorated coroutine; handles TelegramRetryAfter outside
    tenacity (RESEARCH §11). retry_after value is integer SECONDS.
    """
    for i in range(max_retry_after_iterations):
        try:
            return await send_callable()
        except TelegramRetryAfter as e:
            log.warning("telegram_retry_after", seconds=e.retry_after, iteration=i)
            await asyncio.sleep(e.retry_after)
    # Exhausted retry-after loop — re-raise as a final attempt
    return await send_callable()


async def send_message_with_policy(
    bot: Bot, chat_id: str, text: str, *, max_attempts: int = 3
) -> SendOutcome:
    """send_message wrapped with tenacity + retry-after loop (D-603)."""
    decorated = _build_retry_decorator(max_attempts)

    @decorated
    async def _do() -> Message:
        return await bot.send_message(chat_id=chat_id, text=text)

    try:
        msg = await _send_with_retry_after_loop(_do)
        return SendOutcome(message_id=msg.message_id, attempts=max_attempts, error=None)
    except (TelegramBadRequest, TelegramForbiddenError, TelegramNotFound,
            TelegramUnauthorizedError) as e:
        # Pitfall A: fail-fast classes — do NOT retry; mark undelivered.
        return SendOutcome(
            message_id=-1,
            attempts=1,
            error=f"{type(e).__name__}: {e.message[:200]}",
        )
    except (TelegramNetworkError, TelegramServerError) as e:
        # Retries exhausted
        return SendOutcome(
            message_id=-1,
            attempts=max_attempts,
            error=f"{type(e).__name__}: {str(e)[:200]}",
        )


async def send_document_with_policy(
    bot: Bot, chat_id: str, document_path: Path, caption: str,
    *, max_attempts: int = 3,
) -> SendOutcome:
    """send_document with FSInputFile + retry policy.

    D-601: FSInputFile(Path) accepted (RESEARCH §3 — verified pathlib support).
    Caption truncated to ≤ 1024 chars by caller (D-614 business_caption_max_chars).
    """
    decorated = _build_retry_decorator(max_attempts)

    @decorated
    async def _do() -> Message:
        return await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(document_path),
            caption=caption,
        )

    try:
        msg = await _send_with_retry_after_loop(_do)
        return SendOutcome(message_id=msg.message_id, attempts=max_attempts, error=None)
    except (TelegramBadRequest, TelegramForbiddenError, TelegramNotFound,
            TelegramUnauthorizedError) as e:
        return SendOutcome(message_id=-1, attempts=1,
                           error=f"{type(e).__name__}: {e.message[:200]}")
    except (TelegramNetworkError, TelegramServerError) as e:
        return SendOutcome(message_id=-1, attempts=max_attempts,
                           error=f"{type(e).__name__}: {str(e)[:200]}")


async def open_bot(token: str, parse_mode: str = "HTML") -> Bot:
    """Construct Bot. Caller MUST use `async with` (D-602; Pitfall B).
    Use ParseMode enum internally for type safety (RESEARCH Open Q2).
    """
    pm = ParseMode(parse_mode)  # "HTML" → ParseMode.HTML; fail-fast on bad TOML
    return Bot(token=token, default=DefaultBotProperties(parse_mode=pm))


__all__ = [
    "SendOutcome",
    "open_bot",
    "send_message_with_policy",
    "send_document_with_policy",
]
```

---

### `src/ga_crawler/runners/delivery_run.py` (orchestrator, sync→async glue)

**Analog:** `src/ga_crawler/runners/reporter_run.py` (full file, 250 lines).

**Mirror exactly — module docstring + dataclass + sync entry + skip-path + main flow:**

**Module header (mirror reporter_run.py:1-24 shape):**
```python
"""Phase 6 delivery orchestrator -- `run_delivery_phase()`.

Sync 7-step pipeline mirroring `runners/reporter_run.py` shape. Composes
Plan 06-XX delivery/* modules: config (D-611/D-614), gate (D-604),
message_builder (D-610), telegram_client (D-601/D-603), stats (D-607).

Steps:
  1. D-604 gate evaluation (REUSE matcher.strict_key.read_run_status)
  2. Idempotency check via existing deliver.delivery_status enum (D-606/D-608)
  3. Read ops-alert facts from stats (viled/goldapple counts, match.*)
  4. Build messages (pure transforms)
  5. Resolve xlsx path safely (Pitfall C — defense-in-depth)
  6. asyncio.run(_send_async(...)) — mirror main_run.py:224 goldapple pattern (D-602)
  7. SINGLE atomic patch_stats with all 8 D-607 keys (Pitfall 6); return result

DATA-05 lifecycle: delivery_run does NOT raise on Telegram failure (D-605).
Only programmer bugs (AttributeError, TypeError) propagate to main_run.

Source: 06-CONTEXT.md D-601..D-616; 06-RESEARCH.md §Integration Patterns.
"""
```

**Result dataclass (mirror `ReporterPhaseResult` reporter_run.py:58-69 + Plan 06 D-616 fields):**
```python
@dataclass
class DeliveryPhaseResult:
    """Outcome of run_delivery_phase."""
    delivery_status: str   # D-606 enum: pending / delivered_business / delivered_ops_only / undelivered_* / skipped_*
    route: str             # "business" | "ops_only" | "skipped" | ""
    business_caption_message_id: int = -1
    business_document_message_id: int = -1
    ops_message_id: int = -1
    attempt_count: int = 0
    last_error: str = ""
    delivered_at: str = ""
    stats_delta: dict = field(default_factory=dict)
```

**Skip-path pattern — mirror reporter_run.py:72-113 `_skip_path` exactly:**
```python
def _skip_path(
    *,
    run_id: int,
    delivery_status: str,
    route: str,
    last_error: str,
    run_writer: RunWriterProtocol,
) -> DeliveryPhaseResult:
    """Single atomic patch_stats (Pitfall 6) for skip/no-op/credentials-missing paths.
    All 8 D-607 keys patched with sentinels per Pitfall 4.
    """
    builder = DeliverStatsBuilder()
    builder.set("delivery_status", delivery_status)
    builder.set("route", route)
    builder.set("business_caption_message_id", -1)
    builder.set("business_document_message_id", -1)
    builder.set("ops_message_id", -1)
    builder.set("attempt_count", 0)
    builder.set("last_error", last_error[:500])
    builder.set("delivered_at", "")
    run_writer.patch_stats(run_id, dict(builder.delta))
    return DeliveryPhaseResult(
        delivery_status=delivery_status, route=route,
        last_error=last_error, stats_delta=dict(builder.delta),
    )
```

**Main flow — mirror reporter_run.py:116-250 shape:**

```python
def run_delivery_phase(
    *,
    run_id: int,
    engine,
    run_writer: RunWriterProtocol,
    repo_root: Path,
    config: DeliverConfig,
    env: DeliverEnvConfig,
    force: bool = False,    # D-608 --force flag
    dry_run: bool = False,  # D-608 --dry-run flag
) -> DeliveryPhaseResult:
    """Execute full Phase 6 delivery. Never raises on Telegram failure (D-605)."""
    started = time.perf_counter()

    # ---- Pre-flight: TG_BOT_TOKEN required (D-611 asymmetric handling) ----
    if not env.bot_token:
        return _skip_path(
            run_id=run_id, delivery_status="skipped_no_credentials",
            route="skipped", last_error="missing_env_TG_BOT_TOKEN",
            run_writer=run_writer,
        )

    # ---- Step 1: D-608 idempotency dispatch ----
    existing = (run_writer.get_stats(run_id) or {}).get("deliver.delivery_status", "")
    if existing == "delivered_business" and not force:
        return _skip_path(
            run_id=run_id, delivery_status="skipped_already_delivered",
            route="skipped", last_error="", run_writer=run_writer,
        )

    # ---- Step 2: D-604 gate evaluation ----
    decision = evaluate_gate(engine, run_writer, run_id)
    log.info("delivery_gate_decision", run_id=run_id, route=decision.route,
             gate_failed_check=decision.gate_failed_check)

    # ---- Step 3: build messages (pure transforms; no I/O yet) ----
    # ... read stats for ops alert; build business caption from summary_text verbatim (D-514) ...

    # ---- Step 4: dry-run early exit (D-608) ----
    if dry_run:
        # Print preview JSON; do NOT call Telegram or patch_stats
        ...

    # ---- Step 5: Pitfall C — defense-in-depth xlsx path containment ----
    if decision.route == "business":
        xlsx_rel = (run_writer.get_stats(run_id) or {}).get("report.xlsx_path", "")
        candidate = (repo_root / xlsx_rel).resolve()
        try:
            candidate.relative_to(repo_root.resolve())
        except ValueError:
            return _skip_path(
                run_id=run_id, delivery_status="undelivered_telegram_unreachable",
                route="ops_only", last_error=f"xlsx_path_escapes_repo:{xlsx_rel}",
                run_writer=run_writer,
            )

    # ---- Step 6: asyncio.run sync→async glue (D-602 mirror main_run.py:224) ----
    builder = DeliverStatsBuilder()
    try:
        send_result = asyncio.run(_send_async(
            token=env.bot_token,
            route=decision.route,
            business_chat_id=env.business_chat_id,
            ops_chat_id=env.ops_chat_id,
            # ... caption, ops_alert_html, xlsx_path ...
            config=config,
        ))
    except Exception as e:  # Pitfall A defensive — only programmer bugs reach here
        log.error("delivery_unexpected_crash", run_id=run_id, error=repr(e))
        return _skip_path(
            run_id=run_id, delivery_status="undelivered_telegram_unreachable",
            route=decision.route, last_error=repr(e)[:500],
            run_writer=run_writer,
        )

    # ---- Step 7: single atomic patch_stats (Pitfall 6) ----
    builder.set("delivery_status", send_result.delivery_status)
    builder.set("route", decision.route)
    builder.set("business_caption_message_id", send_result.business_caption_message_id)
    builder.set("business_document_message_id", send_result.business_document_message_id)
    builder.set("ops_message_id", send_result.ops_message_id)
    builder.set("attempt_count", send_result.attempt_count)
    builder.set("last_error", send_result.last_error[:500])
    builder.set("delivered_at", datetime.now(timezone.utc).isoformat())
    run_writer.patch_stats(run_id, dict(builder.delta))

    elapsed = time.perf_counter() - started
    log.info("delivery_phase_complete", run_id=run_id,
             delivery_status=send_result.delivery_status, route=decision.route,
             duration_s=round(elapsed, 3))
    return DeliveryPhaseResult(
        delivery_status=send_result.delivery_status, route=decision.route,
        # ... fill all fields from send_result + builder.delta ...
        stats_delta=dict(builder.delta),
    )


async def _send_async(*, token, route, business_chat_id, ops_chat_id, ..., config) -> _AsyncSendResult:
    """Single async block — Bot context manager + sequential sends + retry policy."""
    bot = await open_bot(token, parse_mode=config.parse_mode)
    async with bot:  # D-602 / Pitfall B — auto-close session
        if route == "business":
            # caption split if > 1024 chars (Claude's Discretion)
            ...
        else:  # ops_only
            ...
        return _AsyncSendResult(...)
```

**Critical: the `asyncio.run` call mirror — verbatim from `main_run.py:224-236`:**
```python
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
```

---

### `src/ga_crawler/runners/main_run.py` (AMEND — composition point)

**Self-amend at insertion point (Plan 05-05 reporter step block, lines 320-358):**

**Existing reporter step that Phase 6 hooks AFTER (verbatim, lines 320-358):**
```python
            # ---- Reporter phase (Plan 05-05; D-507 skip-if-not-success handled inside) ----
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
                    log.warning(
                        "weekly_run_reporter_skipped",
                        run_id=run_id,
                        reason=r_result.reason,
                    )
```

**Phase 6 AMEND — insert IMMEDIATELY AFTER `r_result.status == "skipped"` warning, INSIDE the `if m_result.status == "success":` block (D-615):**
```python
                # ---- Delivery phase (Plan 06-XX; D-604 gate + D-605 never-fails-run) ----
                # Composition rule (D-615): delivery needs reporter output (xlsx + summary).
                # We invoke delivery ONLY when reporter returned 'success' AND xlsx_path
                # is non-empty (defense for D-507 skip-path leaking through to here).
                # Telegram unreachable → delivery_status=undelivered, runs.status stays
                # 'success', xlsx persists on disk — D-605 invariant. Outer DATA-05
                # try/except catches only programmer bugs (D-605 exception clause).
                if r_result.status == "success" and r_result.xlsx_path:
                    deliver_config = DeliverConfig.from_pyproject(pyproject_path)
                    deliver_env = DeliverEnvConfig.from_env()
                    log.info(
                        "weekly_run_delivery_starting",
                        run_id=run_id,
                        route="pending_gate",
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
```

**Pre-init outcome vars amendment (insert in pre-try block lines 176-179, D-616):**
```python
    # Plan 06-XX (D-616) — delivery outcome scoped above try for failure-return paths.
    delivery_status: str = "pending"
    delivery_route: str = ""
```

**MainRunResult amendment (lines 60-78, D-616) — 2 new fields:**
```python
@dataclass
class MainRunResult:
    """Outcome of run_weekly."""
    status: str
    run_id: int
    viled_count: int = 0
    goldapple_count: int = 0
    match_count: int = 0
    match_rate: float = 0.0
    reason: Optional[str] = None
    norm06_path: Optional[Path] = None
    xlsx_path: Optional[str] = None
    xlsx_size_bytes: int = 0
    summary_text: str = ""
    size_guard_passed: bool = True
    # ---- Plan 06-XX additions (D-616) ----
    delivery_status: str = "pending"
    delivery_route: str = ""
    # ---- keep stats_delta last (default_factory) ----
    stats_delta: dict = field(default_factory=dict)
```

**Return-statement amendment (all 5 return paths must include the 2 new fields — match the pattern at lines 384-397, 202-209, 250-258, 301-311, 426-436).**

**Import amendments (insert after line 47):**
```python
from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
from ga_crawler.runners.delivery_run import run_delivery_phase
```

---

### `src/ga_crawler/cli.py` (AMEND — add `deliver-run` subcommand)

**Self-amend mirror of `_cmd_report` (lines 159-222) + subparser registration (lines 336-367).**

**`_cmd_deliver` handler — mirror `_cmd_report` exactly:**
```python
def _cmd_deliver(args) -> int:
    """ADDED Plan 06-XX (D-608): standalone deliver-run for recovery.

    Idempotency dispatch per D-606 enum (D-608):
      pending → run full delivery
      delivered_business → no-op (--force overrides)
      delivered_ops_only → re-send to ops
      undelivered_telegram_unreachable → re-attempt full
      skipped_no_credentials → re-validate ENV
      skipped_already_delivered → no-op (--force overrides)

    Exit codes:
      0 -> delivered_business OR delivered_ops_only
      2 -> undelivered_telegram_unreachable (retryable)
      3 -> skipped_no_credentials (config error)
    """
    from dotenv import load_dotenv

    from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
    from ga_crawler.runners.delivery_run import run_delivery_phase
    from ga_crawler.storage.sqlite import (
        SqliteRunWriter,
        init_db,
        make_engine,
    )

    # RESEARCH caveat #4: load_dotenv() ONLY here, never in from_env() — tests
    # bypass via monkeypatch.setenv.
    load_dotenv(override=False)

    init_db(args.db_path)
    engine = make_engine(args.db_path)
    run_writer = SqliteRunWriter(engine)
    repo_root = Path(args.repo_root).resolve()

    cfg = DeliverConfig.from_pyproject(args.pyproject)
    env = DeliverEnvConfig.from_env()

    result = run_delivery_phase(
        run_id=args.run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=cfg,
        env=env,
        force=args.force,
        dry_run=args.dry_run,
    )
    payload = json.dumps(
        {
            "delivery_status": result.delivery_status,
            "route": result.route,
            "run_id": args.run_id,
            "business_caption_message_id": result.business_caption_message_id,
            "business_document_message_id": result.business_document_message_id,
            "ops_message_id": result.ops_message_id,
            "attempt_count": result.attempt_count,
            "last_error": result.last_error,
            "stats_delta_keys": sorted(result.stats_delta.keys()),
        },
        ensure_ascii=False,
        indent=2,
    )
    # Plan 05-05 Unicode-stdout pattern — emoji-safe Windows output (D-608 dry-run preview)
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()

    # D-608 exit code mapping
    if result.delivery_status in ("delivered_business", "delivered_ops_only",
                                  "skipped_already_delivered"):
        return 0
    if result.delivery_status == "skipped_no_credentials":
        return 3
    return 2  # undelivered_* / skipped_no_xlsx
```

**Subparser registration — mirror `report` subparser (lines 336-367) + add `--force` + `--dry-run`:**
```python
    # ADDED Plan 06-XX (D-608) — deliver-run standalone recovery tool.
    deliver = sub.add_parser(
        "deliver-run",
        help="Send Telegram delivery against an existing run_id "
             "(idempotent per D-606 enum, D-608)",
    )
    deliver.add_argument(
        "--run-id", type=int, required=True,
        help="runs.run_id of an existing run to deliver report for",
    )
    deliver.add_argument(
        "--db-path", default="prices.db",
        help="SQLite database file path",
    )
    deliver.add_argument(
        "--pyproject", default="pyproject.toml",
        help="Path to pyproject.toml for [tool.ga_crawler.deliver] config",
    )
    deliver.add_argument(
        "--repo-root", default=".",
        help="Repo root for resolving xlsx_path + Pitfall C containment check",
    )
    deliver.add_argument(
        "--force", action="store_true",
        help="Override idempotency for delivered_business/delivered_ops_only state (D-608)",
    )
    deliver.add_argument(
        "--dry-run", action="store_true",
        help="Build messages + gate decision, print JSON to stdout, skip Telegram API (D-608)",
    )
```

**Dispatch table amendment (lines 369-378):**
```python
    if args.cmd == "deliver-run":
        return _cmd_deliver(args)
```

**Module docstring amendment (lines 1-37) — add 5th subcommand and Plan 06-XX section.**

---

### `pyproject.toml` (AMEND)

**Self-amend mirror of `[tool.ga_crawler.report]` (lines 102-108).**

**New dep (insert after line 14, before `curl-cffi`, alphabetical sort):**
```toml
    "aiogram>=3.27,<4.0",
```

**New namespace (append after line 108, the `[tool.ga_crawler.report]` block — mirror that block's shape):**
```toml

[tool.ga_crawler.deliver]
# Phase 6 operational constants. Type-locked; operator edits via git PR.
# Source anchors: 06-CONTEXT.md (D-603, D-609, D-610, D-614).
retry_max_attempts = 3                  # D-603 tenacity stop_after_attempt
retry_backoff_min_seconds = 5           # D-603 wait_chain(5, 15, 45) — first wait
retry_backoff_max_seconds = 45          # D-603 wait_chain(5, 15, 45) — last wait
ops_message_truncate_chars = 3500       # D-610 traceback truncation (safe under 4096 TG limit)
business_caption_max_chars = 1024       # Telegram document caption hard-limit
parse_mode = "HTML"                     # D-609 — escape only <>&
```

---

### `.env.example` (NEW at repo root)

**No existing analog** — first env-file in project. Per D-612 verbatim:
```env
# Telegram delivery (Phase 6 — DELIVER-05)
# Create bot: @BotFather → /newbot
# Get chat_id: add @userinfobot to chat → it prints the chat_id

TG_BOT_TOKEN=
TG_BUSINESS_CHAT_ID=
TG_OPS_CHAT_ID=
```

---

### `.gitignore` (AMEND)

**Verify `.env` already present at line 25 — D-612 audit only (no edit needed):**
```
# Secrets (D-08: IPRoyal credentials)
.env
.env.local
.env.*.local
```

Phase 6 may optionally append a clarifying comment but `.env` is **already** ignored.

---

### `tests/conftest.py` (AMEND — 3 new fixtures)

**Analog (existing in same file):** `synthetic_report_run` (lines 315-594) — the Phase 5 fixture that planted Run + matches + report.* stats.

**NEW fixture 1: `synthetic_delivered_run` — superset of `synthetic_report_run` (Pitfall F)**

Pattern: build on top of `synthetic_report_run` and additionally patch `report.*` and `runs.status` to be gate-pass; provide variants for the 4 gate-fail cases via `request.param` parametrization.

```python
@pytest.fixture
def synthetic_delivered_run(synthetic_report_run):
    """Pitfall F superset: gate-pass + ops-alert facts populated.

    Returns: (engine, run_writer, run_id, repo_root) — same shape as synthetic_report_run.

    Populates report.* (xlsx_path + summary_text + size_guard_passed=True)
    AND match.*/viled.*/goldapple.* for D-610 ops-alert builder.
    """
    engine, run_writer, run_id, repo_root = synthetic_report_run
    # Plant a fake xlsx file so FSInputFile would succeed if test reaches it
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)
    fake_xlsx = reports_dir / "2026-W19.xlsx"
    fake_xlsx.write_bytes(b"PK\x03\x04fake-xlsx")
    # Patch report.* to gate-pass state
    run_writer.patch_stats(run_id, {
        "report.xlsx_path": "reports/2026-W19.xlsx",
        "report.xlsx_size_bytes": fake_xlsx.stat().st_size,
        "report.summary_text": "📊 Weekly report 2026-W19\nmatch_count: 3 (60.0%)",
        "report.sheet_row_counts": {"summary": 1, "per_sku_deltas": 3},
        "report.skipped_reason": "",
        "report.size_guard_passed": True,
        "report.generated_at": "2026-05-10T14:30:00+00:00",
    })
    return engine, run_writer, run_id, repo_root
```

**NEW fixture 2: `mock_aiogram_bot` (Claude's Discretion fixture spec)**

```python
@pytest.fixture
def mock_aiogram_bot(mocker):
    """Mock aiogram Bot with send_message/send_document → returns Message with stub message_id.

    Mocks at class level to avoid aiogram aiohttp session instantiation.
    """
    from unittest.mock import AsyncMock, MagicMock
    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=None)
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=10001))
    bot.send_document = AsyncMock(return_value=MagicMock(message_id=10002))
    return bot
```

**NEW fixture 3: `mock_tg_env` (Claude's Discretion fixture spec)**

```python
@pytest.fixture
def mock_tg_env(monkeypatch):
    """Set TG_* env vars for delivery tests; clear via monkeypatch teardown.

    Per RESEARCH caveat #4: tests use monkeypatch.setenv, NOT .env file loading.
    """
    monkeypatch.setenv("TG_BOT_TOKEN", "test-token-12345")
    monkeypatch.setenv("TG_BUSINESS_CHAT_ID", "-100000001")
    monkeypatch.setenv("TG_OPS_CHAT_ID", "-100000002")
    yield {
        "bot_token": "test-token-12345",
        "business_chat_id": "-100000001",
        "ops_chat_id": "-100000002",
    }
```

---

### `tests/test_delivery_stats.py` (NEW — unit)

**Analog:** `tests/unit/test_report_stats.py` (lines 1-114) — mirror exactly.

**Five-way disjoint canary (D-607 + Pitfall 7) — extend the four-way at test_report_stats.py:82-94:**
```python
def test_five_way_namespaces_disjoint():
    """D-607 + Pitfall 7: deliver.* disjoint from viled.*/goldapple.*/match.*/report.*."""
    viled_set = set(VILED_STATS_KEYS)
    gold_set = set(GOLDAPPLE_STATS_KEYS)
    match_set = set(MATCH_STATS_KEYS)
    report_set = set(REPORT_STATS_KEYS)
    deliver_set = set(DELIVER_STATS_KEYS)
    assert viled_set.isdisjoint(deliver_set), "viled.* ∩ deliver.* must be empty"
    assert gold_set.isdisjoint(deliver_set), "goldapple.* ∩ deliver.* must be empty"
    assert match_set.isdisjoint(deliver_set), "match.* ∩ deliver.* must be empty"
    assert report_set.isdisjoint(deliver_set), "report.* ∩ deliver.* must be empty"
    # Re-assert four-way (Phase 5 invariant)
    assert viled_set.isdisjoint(gold_set)
    assert viled_set.isdisjoint(match_set)
    assert viled_set.isdisjoint(report_set)
    assert gold_set.isdisjoint(match_set)
    assert gold_set.isdisjoint(report_set)
    assert match_set.isdisjoint(report_set)


def test_delivery_stats_keys_count():
    """D-607: 8-tuple namespace."""
    assert len(DELIVER_STATS_KEYS) == 8


def test_all_keys_have_deliver_prefix():
    for k in DELIVER_STATS_KEYS:
        assert k.startswith("deliver."), f"{k!r} missing deliver. prefix"
```

---

### `tests/integration/test_delivery_run.py` (NEW)

**Analog:** `tests/integration/test_reporter_run.py` (full file). Use `synthetic_delivered_run` (NEW) + `mock_aiogram_bot` + `mock_tg_env` from conftest amend.

**Header + import block mirror:**
```python
"""Integration tests for run_delivery_phase — Phase 6 orchestrator.

Real on-disk SQLite (via synthetic_delivered_run conftest fixture) + mock
aiogram Bot (no real Telegram API) + tmp_path-rooted repo_root with fake xlsx.
Covers all D-606 enum transitions + D-604 gate composition + D-605 invariant +
Pitfall 6 single patch_stats + Pitfall C path containment.

Source: 06-VALIDATION.md (to be authored); 06-CONTEXT.md D-604/605/606/607.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
from ga_crawler.runners.delivery_run import DeliveryPhaseResult, run_delivery_phase


pytestmark = pytest.mark.integration
```

**Gate-fail test mirror (reporter_run.py:49-83 `test_d507_skip_on_failed_run` shape):**
```python
def test_d604_gate_trips_on_failed_run(synthetic_delivered_run, mock_tg_env):
    """Failed upstream → delivery routes to ops_only with reason='upstream_status_failed'."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    # Flip runs.status back to running, then call fail()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE runs SET status='running', finished_at=NULL WHERE run_id=:rid"),
            {"rid": run_id},
        )
    run_writer.fail(run_id, "goldapple_sanity_gate_failed")

    cfg = DeliverConfig()
    env = DeliverEnvConfig.from_env()
    with patch("ga_crawler.delivery.telegram_client.Bot") as MockBot:
        # Wire mock Bot
        ...
        result = run_delivery_phase(
            run_id=run_id, engine=engine, run_writer=run_writer,
            repo_root=repo_root, config=cfg, env=env,
        )
    assert result.route == "ops_only"
    assert "upstream_status_failed" in (result.last_error or "")

    # All 8 D-607 keys present in stats
    stats = run_writer.get_stats(run_id)
    for k in (
        "deliver.delivery_status", "deliver.route",
        "deliver.business_caption_message_id", "deliver.business_document_message_id",
        "deliver.ops_message_id", "deliver.attempt_count",
        "deliver.last_error", "deliver.delivered_at",
    ):
        assert k in stats, f"{k} missing after gate-fail path"
```

---

### `tests/integration/test_cli_deliver.py` (NEW)

**Analog:** `tests/integration/test_cli_report_subcommand.py` (lines 1-90 helpers + subprocess pattern).

**Helpers mirror exactly (lines 37-77 `_viled`, `_goldapple`, `_write_pyproject` shape):**
```python
def _write_pyproject(tmp_path: Path) -> Path:
    pyp = tmp_path / "pyproject.toml"
    pyp.write_text(
        "[tool.ga_crawler.deliver]\n"
        "retry_max_attempts = 3\n"
        "retry_backoff_min_seconds = 5\n"
        "retry_backoff_max_seconds = 45\n"
        "ops_message_truncate_chars = 3500\n"
        "business_caption_max_chars = 1024\n"
        'parse_mode = "HTML"\n',
        encoding="utf-8",
    )
    return pyp
```

**Subprocess invocation pattern (mirror test_cli_report_subcommand.py general shape — exit code + JSON stdout assertion):**
```python
def test_deliver_run_missing_token_exits_3(tmp_path, monkeypatch):
    """D-611: TG_BOT_TOKEN missing → exit code 3, delivery_status=skipped_no_credentials."""
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    db_path = tmp_path / "p.db"
    # ... plant db with one successful run ...
    pyproject = _write_pyproject(tmp_path)

    proc = subprocess.run(
        [sys.executable, "-m", "ga_crawler", "deliver-run",
         "--run-id", "1", "--db-path", str(db_path),
         "--pyproject", str(pyproject), "--repo-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 3
    payload = json.loads(proc.stdout)
    assert payload["delivery_status"] == "skipped_no_credentials"
```

---

### `tests/integration/test_weekly_run_with_delivery.py` (NEW)

**Analog:** `tests/integration/test_main_run_with_reporter.py` (lines 1-60 helpers + `_FakeFetcher` + `run_weekly` invocation patterns).

Mirror exactly — extend its scenarios with delivery assertions:
- `result.delivery_status == "delivered_business"` after happy-path weekly run
- `runs.stats["deliver.delivery_status"]` matches result field
- `MainRunResult.delivery_status` + `delivery_route` D-616 fields populated

---

### `tests/test_stats_namespace.py` (AMEND-or-NEW)

**Note:** File does NOT exist yet (Grep confirmed). Phase 6 may create it OR amend `tests/unit/test_report_stats.py::test_four_way_namespaces_disjoint` (lines 82-94) by adding the deliver-set assertion. CONTEXT.md §"Action Items" lists this as AMEND — confirm with planner.

If creating new — mirror the disjoint test from `test_report_stats.py:82-94` exactly.

---

## Shared Patterns

### Pattern S1: Single atomic `patch_stats` invariant (Pitfall 6)

**Source:** `src/ga_crawler/storage/sqlite.py` (lines 232-251) — REUSED, never reimplemented.

```python
def patch_stats(self, run_id: int, delta: dict) -> None:
    """Atomic JSON-merge into runs.stats (Pitfall 6 RFC-7396 MergePatch).
    Pitfall 4: delta MUST NOT contain None/null values (would DELETE keys).
    """
    if any(v is None for v in delta.values()):
        raise ValueError(
            "Pitfall 4: delta contains None — RFC-7396 MergePatch DELETES the key. "
            "Use sentinels (-1, '', []) or omit the key."
        )
    delta_json = json.dumps(delta, ensure_ascii=False, default=str)
    with Session(self.engine) as s:
        s.exec(
            text("UPDATE runs SET stats = json_patch(stats, :delta) WHERE run_id = :rid"),
            params={"delta": delta_json, "rid": run_id},
        )
        s.commit()
```

**Apply to:** `delivery/stats.py` (single emit point), `runners/delivery_run.py` (call exactly once per invocation — both happy and skip paths). Test canary `test_single_patch_stats_call` (spy on call_count).

### Pattern S2: `StatsNamespaceError` reuse (no re-definition)

**Source:** `src/ga_crawler/runner/stats.py:41-42`:
```python
class StatsNamespaceError(KeyError):
    """Raised when a caller tries to set a key outside GOLDAPPLE_STATS_KEYS."""
```

**Apply to:** `delivery/stats.py` — `from ga_crawler.runner.stats import StatsNamespaceError` (mirror `matcher/stats.py:16` and `reporter/stats.py:16`).

### Pattern S3: `read_run_status` REUSE (D-411 helper)

**Source:** `src/ga_crawler/matcher/strict_key.py:199-207` (already verbatim above).

**Apply to:** `delivery/gate.py::evaluate_gate` step 1 — `from ga_crawler.matcher.strict_key import read_run_status`. Mirror `runners/reporter_run.py:37 + 147`.

### Pattern S4: `from_pyproject` config loader

**Source:** `src/ga_crawler/reporter/config.py:34-55` (full method, already verbatim above).

**Apply to:** `delivery/config.py::DeliverConfig.from_pyproject`. Identical shape: `tomllib.load` + nested `.get("tool",{}).get("ga_crawler",{}).get("deliver",{})` + fallback to dataclass defaults.

### Pattern S5: `asyncio.run` sync→async glue

**Source:** `src/ga_crawler/runners/main_run.py:224-236`:
```python
g_result = asyncio.run(
    run_goldapple_phase(
        run_id=run_id,
        # ... 8 kwargs ...
    )
)
```

**Apply to:** `runners/delivery_run.py::run_delivery_phase` — wrap `_send_async(...)` exactly the same way. Two `asyncio.run` calls in one `run_weekly` invocation is fine (RESEARCH caveat #5 verified).

### Pattern S6: structlog event names + JSON renderer

**Source:** `src/ga_crawler/cli.py:225-232`:
```python
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
```

**Apply to:** All `delivery/*.py` modules. Event names per CONTEXT.md §code_context: `delivery_phase_start` / `delivery_gate_decision` / `telegram_send_attempt` / `telegram_retry_after` / `delivery_complete` / `delivery_undelivered`. Plus structural: `delivery_unexpected_crash` (Pitfall A path).

### Pattern S7: DATA-05 outer try/except in main_run

**Source:** `src/ga_crawler/runners/main_run.py:399-436`:
```python
except Exception as e:  # noqa: BLE001
    # DATA-05 invariant: every code path closes the runs row.
    tb = traceback.format_exc()
    reason = f"{type(e).__name__}: {e}"
    log.error("weekly_run_crashed", run_id=run_id, error=reason, traceback=tb)
    try:
        run_writer.fail(run_id, reason)
    except Exception as fail_exc:
        log.error("weekly_run_fail_failed", run_id=run_id, error=str(fail_exc))
    # ... return MainRunResult(status="failed", ...)
```

**Apply to:** Phase 6 inherits unchanged — `run_delivery_phase` MUST NOT raise on Telegram failure (D-605); only programmer bugs reach this outer block. Update the failure-path `MainRunResult` construction to include the 2 new D-616 fields (`delivery_status="pending"`, `delivery_route=""`).

### Pattern S8: Pre-init outcome vars above try (Plan 05-05)

**Source:** `src/ga_crawler/runners/main_run.py:170-179`:
```python
# Plan 04-05 — matcher counters scoped above try so the except branch can read them.
match_count = 0
match_rate = 0.0
viled_unmatched: list[str] = []
goldapple_new_slugs: list[str] = []
# Plan 05-05 — reporter outcome scoped above try so the except branch returns
# valid MainRunResult with sane defaults (None / 0 / "" / True).
xlsx_path: Optional[str] = None
xlsx_size_bytes: int = 0
summary_text: str = ""
size_guard_passed: bool = True
```

**Apply to:** Phase 6 adds 2 lines (D-616):
```python
delivery_status: str = "pending"
delivery_route: str = ""
```

### Pattern S9: Unicode-safe stdout (Windows emoji)

**Source:** `src/ga_crawler/cli.py:213-222`:
```python
# Plan 05-05 Rule 1 deviation: summary_text contains Cyrillic + emoji
# (📊 from D-504 template). On Windows the default stdout encoding is
# cp1252 which cannot encode \U0001f4ca → UnicodeEncodeError. Write the
# UTF-8 bytes directly to sys.stdout.buffer to bypass the locale codec.
sys.stdout.buffer.write(payload.encode("utf-8"))
sys.stdout.buffer.write(b"\n")
sys.stdout.buffer.flush()
```

**Apply to:** `cli.py::_cmd_deliver` payload print AND `delivery_run.py` dry-run preview (D-608). Ops alerts contain 🚨 emoji per D-610.

### Pattern S10: Frozen dataclass results

**Source:** `src/ga_crawler/runners/reporter_run.py:58-69` (`ReporterPhaseResult`).

**Apply to:** `DeliveryPhaseResult` (frozen=False because builder mutates; mirror reporter_run.py's mutable @dataclass not frozen) AND `GateDecision` (frozen=True — pure value object).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.env.example` | config | env-template | First env-template in project; D-612 spec is verbatim from CONTEXT.md (no pattern needed beyond 3 placeholder lines). |
| `delivery/config.py::DeliverEnvConfig.from_env` | config | env-read | First `from_env` pattern in project. RESEARCH caveat #4 supplies the recommended split (no `load_dotenv` inside; only in `cli.py::_cmd_deliver`). |
| `delivery/telegram_client.py` (aiogram Bot wrapper) | service | async + retry | No prior aiogram code in project. Pattern composed from: viled fetcher tenacity wrap (analog), goldapple async fetcher `async with` (analog), RESEARCH §Integration Patterns 1-5 (verified). |
| `tests/fixtures/delivery/ops-alert-templates.txt` | test-fixture | golden-file | No prior golden-file fixtures in project. RESEARCH §Validation Architecture specifies 5-scenario coverage. |

---

## Metadata

**Analog search scope:**
- `src/ga_crawler/reporter/` (Phase 5 mirror — primary analog)
- `src/ga_crawler/matcher/` (Phase 4 mirror — REUSED helpers)
- `src/ga_crawler/runners/` (orchestrator patterns)
- `src/ga_crawler/runner/stats.py` (StatsNamespaceError shared)
- `src/ga_crawler/fetchers/viled.py` (tenacity precedent)
- `src/ga_crawler/cli.py` (`_cmd_report` analog)
- `src/ga_crawler/storage/sqlite.py` (`patch_stats` / `get_stats` REUSED)
- `tests/conftest.py` (`synthetic_report_run` analog)
- `tests/integration/test_reporter_run.py` (integration test shape)
- `tests/integration/test_cli_report_subcommand.py` (subprocess CLI test shape)
- `tests/unit/test_report_stats.py` (5-way disjoint extension target)
- `pyproject.toml` (`[tool.ga_crawler.report]` namespace shape)

**Files scanned:** 19 source files + 8 test files = 27 analogs read.

**Pattern extraction date:** 2026-05-12

---

## PATTERN MAPPING COMPLETE

**Phase:** 6 - telegram-delivery
**Files classified:** 23 (8 NEW source + 4 AMEND source + 9 NEW tests + 2 AMEND test/conftest)
**Analogs found:** 23 / 23 (Phase 4/5 mirrors + 2 self-amend + 4 no-analog with synthesized patterns)

### Coverage
- Files with exact analog: 14
- Files with role-match analog: 5
- Files with self-amend (existing code): 4
- Files with no analog (synthesized from RESEARCH): 4

### Key Patterns Identified
- **5-domain symmetry locked:** `delivery/` package mirrors `reporter/` exactly (config + stats + orchestrator + `runners/*_run.py` + CLI subcommand). Phase 6 is the fifth domain in the established `{viled, goldapple, matcher, reporter, deliver}` pattern.
- **Reuse over reimplementation:** `matcher.strict_key.read_run_status` (D-411 helper) REUSED in `delivery/gate.py` step 1; `runner.stats.StatsNamespaceError` REUSED in `DeliverStatsBuilder`; `storage.sqlite.patch_stats` + `get_stats` REUSED unchanged. No new SQL primitives, no new exception classes.
- **`asyncio.run` sync→async glue is project-wide pattern:** main_run.py:224 (goldapple) → delivery_run.py adopts identical shape. Two `asyncio.run` calls in one `run_weekly` is verified safe (RESEARCH caveat #5).
- **Single `patch_stats` per invocation (Pitfall 6) extends to Phase 6:** all 8 `deliver.*` keys patched in one atomic call (both happy path and skip path). Mirror of `_skip_path` in `reporter_run.py:72-113`.
- **`from_pyproject` + new `from_env`** — `DeliverConfig.from_pyproject` exact mirror of `ReportConfig.from_pyproject`; `DeliverEnvConfig.from_env` is new pattern (first env-reader in project) with RESEARCH-verified separation: `load_dotenv` lives only in `cli.py::_cmd_deliver`, never in `from_env`.
- **Tenacity wrap pattern:** RESEARCH caveat #2 confirms `wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))` (explicit) over `wait_exponential` (math gives different sequence). aiogram-specific exception classification per Pitfall A: 2 retry classes vs 4 fail-fast classes.

### File Created
`C:\Users\gstorepc\projects\ga_crawler\.planning\phases\06-telegram-delivery\06-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in `06-PLAN-NN.md` files. Every NEW source file has a concrete analog with line-anchored code excerpt; every AMEND point in `main_run.py`, `cli.py`, `pyproject.toml`, `.gitignore` has the existing code shown so the diff is trivial to author.
