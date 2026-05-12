"""Phase 6 Telegram client — aiogram 3.27 wrapper + tenacity retry policy.

Single isolation point for aiogram dependency. All other delivery/* modules
(config.py, stats.py, message_builder.py, gate.py) are pure-Python — verified
by ``test_module_only_aiogram_import_site`` canary.

Decisions:
  - D-601: aiogram 3.27.x async-native; pinned in pyproject.toml.
  - D-602: ``async with Bot(...)`` lifecycle — auto-close aiohttp session
    (Pitfall B). Caller MUST wrap ``open_bot(...)`` invocation under
    ``async with`` to avoid unclosed-session warning.
  - D-603: tenacity 3-retry on ``(TelegramNetworkError, TelegramServerError)``
    with ``wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))`` —
    explicit 5/15/45 sequence per RESEARCH caveat #2.

Pitfall A (fail-fast classification — RESEARCH §5):
  ``TelegramBadRequest``, ``TelegramForbiddenError``, ``TelegramNotFound``,
  ``TelegramUnauthorizedError`` are NOT retried — tenacity's
  ``retry_if_exception_type`` filter does not include them. They propagate
  out of tenacity's wrapped coroutine and are caught by the outer
  try/except, which maps them to ``message_id=-1``.

Retry-after handling (RESEARCH §11): ``TelegramRetryAfter`` is handled
OUTSIDE tenacity in ``_send_with_retry_after_loop`` — caught explicitly,
``asyncio.sleep(retry_after)`` is awaited, then the inner tenacity-wrapped
callable is re-invoked. After ``max_retry_after_iterations`` iterations
(default 3), the exception propagates.

Attempt counting (D-607 + B3 revision fix):
-----------------------------------------
``SendOutcome.attempts`` reflects the EXACT cumulative count of send-method
invocations across all retries (including the initial call). Implementation:
a closure-shared ``attempt_tracker = {"count": 0}`` is incremented at the
start of every ``_do()`` body BEFORE the ``bot.send_*`` call. This guarantees:
  - 1st-call success:           attempts == 1
  - retry-then-success (N=2):   attempts == 2
  - full retry exhaustion:      attempts == max_attempts (= 3 default)
  - fail-fast (e.g. 400):       attempts == 1 (one invocation, no retry)
  - retry-after exhaustion:     attempts == max_retry_after_iterations (= 3 default)

Each call to ``send_message_with_policy`` / ``send_document_with_policy``
creates a NEW tracker — no cross-call leak (verified by
``test_send_message_no_tracker_leak``).

The ``before_sleep`` callback hook (``_make_before_sleep``) emits a
structlog ``telegram_retry_scheduled`` event — its main responsibility is
observability. The tracker increment happens INSIDE ``_do()`` rather than
``before_sleep`` because that's where the actual invocation occurs.

Source anchors: 06-PATTERNS.md "src/ga_crawler/delivery/telegram_client.py"
section; 06-RESEARCH.md §5 + §11 + Pitfall A/B + caveat #2; 06-CONTEXT.md
D-601 + D-603 + D-607 (B3 revision).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

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
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
)

log = structlog.get_logger(__name__)


# Pitfall A: ONLY transient transport / server errors are retried.
# Fail-fast classes (TelegramBadRequest / TelegramForbiddenError /
# TelegramNotFound / TelegramUnauthorizedError) are deliberately excluded.
_RETRY_TYPES: tuple[type[BaseException], ...] = (
    TelegramNetworkError,
    TelegramServerError,
)


@dataclass
class SendOutcome:
    """One send-call result. Caller patches ``runs.stats.deliver.*`` accordingly.

    Fields:
      message_id: int — Telegram-returned id on success; ``-1`` on failure.
      attempts:   int — EXACT cumulative count of send invocations (B3 FIX).
      error:      Optional[str] — short truncated error string, ``None`` on success.
    """

    message_id: int
    attempts: int
    error: Optional[str] = None


def _make_before_sleep(attempt_tracker: dict) -> Callable[[RetryCallState], None]:
    """Returns a tenacity before_sleep callback.

    The callback fires AFTER a failed attempt and BEFORE the wait. Its
    primary responsibility is structlog observability — the tracker
    increment itself happens INSIDE ``_do()`` body (that's where the
    invocation actually occurs).
    """

    def _cb(retry_state: RetryCallState) -> None:
        next_wait = 0.0
        if retry_state.next_action is not None:
            next_wait = float(getattr(retry_state.next_action, "sleep", 0) or 0)
        log.info(
            "telegram_retry_scheduled",
            attempt=retry_state.attempt_number,
            next_wait_s=next_wait,
        )

    return _cb


def _build_retry_decorator(max_attempts: int, attempt_tracker: dict):
    """B3 FIX: attempt counter via closure-shared dict.

    Returns a tenacity ``@retry`` decorator with:
      - ``retry_if_exception_type(_RETRY_TYPES)`` — only transient errors retry
      - ``stop_after_attempt(max_attempts)`` — default 3 attempts
      - ``wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))`` —
        explicit 5/15/45 sequence per RESEARCH caveat #2 (formula-based
        alternatives are deliberately avoided)
      - ``before_sleep`` callback for observability (closure-shared tracker)
      - ``reraise=True`` — propagate last exception (outer try/except maps)
    """
    return retry(
        retry=retry_if_exception_type(_RETRY_TYPES),
        stop=stop_after_attempt(max_attempts),
        wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45)),
        before_sleep=_make_before_sleep(attempt_tracker),
        reraise=True,
    )


async def _send_with_retry_after_loop(
    send_callable: Callable[[], "asyncio.Future[Message] | object"],
    attempt_tracker: dict,
    max_retry_after_iterations: int = 3,
) -> Message:
    """Handle ``TelegramRetryAfter`` OUTSIDE tenacity (RESEARCH §11).

    Each iteration:
      1. invoke ``send_callable()`` (tenacity-wrapped — handles
         NetworkError / ServerError internally)
      2. on TelegramRetryAfter: await ``asyncio.sleep(retry_after)``,
         then loop
      3. on success or any non-RetryAfter exception: propagate

    After ``max_retry_after_iterations`` iterations, the last
    ``TelegramRetryAfter`` is re-raised so the outer try/except can map
    it to ``SendOutcome(message_id=-1, error="TelegramRetryAfter: ...")``.

    The ``attempt_tracker`` is shared with the wrapped ``_do()`` body —
    each retry-after iteration adds one ``_do()`` invocation, which
    increments the tracker on entry. So tracker["count"] equals the
    cumulative invocation count across both tenacity retries AND
    retry-after iterations.
    """
    last_exc: Optional[TelegramRetryAfter] = None
    for iteration in range(max_retry_after_iterations):
        try:
            return await send_callable()  # type: ignore[no-any-return,misc]
        except TelegramRetryAfter as e:
            last_exc = e
            log.warning(
                "telegram_retry_after",
                seconds=e.retry_after,
                iteration=iteration,
                tracker_count=attempt_tracker.get("count", 0),
            )
            if iteration == max_retry_after_iterations - 1:
                # Exhausted — let outer try/except handle.
                break
            await asyncio.sleep(e.retry_after)
    assert last_exc is not None  # defensive — loop guarantees this on exit
    raise last_exc


async def send_message_with_policy(
    bot: Bot, chat_id: str, text: str, *, max_attempts: int = 3
) -> SendOutcome:
    """``bot.send_message`` wrapped with tenacity + retry-after loop (D-603).

    Returns a ``SendOutcome`` regardless of outcome — exceptions are mapped
    to ``message_id=-1`` + ``error="<ClassName>: <truncated message>"``.
    The caller never has to catch aiogram exceptions directly.
    """
    # B3 FIX: per-invocation tracker — NO cross-call leak.
    attempt_tracker: dict = {"count": 0}
    decorated = _build_retry_decorator(max_attempts, attempt_tracker)

    @decorated
    async def _do() -> Message:
        # B3 FIX: increment BEFORE the network call so a raise still counts.
        attempt_tracker["count"] += 1
        log.info(
            "telegram_send_attempt",
            method="send_message",
            attempt=attempt_tracker["count"],
        )
        return await bot.send_message(chat_id=chat_id, text=text)

    try:
        msg = await _send_with_retry_after_loop(_do, attempt_tracker)
        return SendOutcome(
            message_id=msg.message_id,
            attempts=attempt_tracker["count"],
            error=None,
        )
    except (
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramNotFound,
        TelegramUnauthorizedError,
    ) as e:
        # Pitfall A: fail-fast classes — tracker == 1 (one invocation, no retry).
        err_msg = getattr(e, "message", str(e))[:200]
        return SendOutcome(
            message_id=-1,
            attempts=attempt_tracker["count"],
            error=f"{type(e).__name__}: {err_msg}",
        )
    except TelegramRetryAfter as e:
        # Retry-after iterations exhausted — tracker reflects iterations.
        return SendOutcome(
            message_id=-1,
            attempts=attempt_tracker["count"],
            error=f"TelegramRetryAfter: {e.retry_after}s exhausted",
        )
    except (TelegramNetworkError, TelegramServerError) as e:
        # Tenacity retries exhausted — tracker["count"] == max_attempts.
        err_msg = getattr(e, "message", str(e))[:200]
        return SendOutcome(
            message_id=-1,
            attempts=attempt_tracker["count"],
            error=f"{type(e).__name__}: {err_msg}",
        )


async def send_document_with_policy(
    bot: Bot,
    chat_id: str,
    document_path: Path,
    caption: str,
    *,
    max_attempts: int = 3,
) -> SendOutcome:
    """``bot.send_document`` with FSInputFile + retry policy.

    D-601: ``FSInputFile(Path)`` accepted (RESEARCH §3 — verified pathlib
    support). Caption is expected to be ``≤ D-614.business_caption_max_chars``
    (1024) — the caller (delivery_run) is responsible for truncation.

    Same retry/error mapping semantics as ``send_message_with_policy``.
    """
    attempt_tracker: dict = {"count": 0}
    decorated = _build_retry_decorator(max_attempts, attempt_tracker)

    @decorated
    async def _do() -> Message:
        attempt_tracker["count"] += 1
        log.info(
            "telegram_send_attempt",
            method="send_document",
            attempt=attempt_tracker["count"],
        )
        return await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(document_path),
            caption=caption,
        )

    try:
        msg = await _send_with_retry_after_loop(_do, attempt_tracker)
        return SendOutcome(
            message_id=msg.message_id,
            attempts=attempt_tracker["count"],
            error=None,
        )
    except (
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramNotFound,
        TelegramUnauthorizedError,
    ) as e:
        err_msg = getattr(e, "message", str(e))[:200]
        return SendOutcome(
            message_id=-1,
            attempts=attempt_tracker["count"],
            error=f"{type(e).__name__}: {err_msg}",
        )
    except TelegramRetryAfter as e:
        return SendOutcome(
            message_id=-1,
            attempts=attempt_tracker["count"],
            error=f"TelegramRetryAfter: {e.retry_after}s exhausted",
        )
    except (TelegramNetworkError, TelegramServerError) as e:
        err_msg = getattr(e, "message", str(e))[:200]
        return SendOutcome(
            message_id=-1,
            attempts=attempt_tracker["count"],
            error=f"{type(e).__name__}: {err_msg}",
        )


async def open_bot(token: str, parse_mode: str = "HTML") -> Bot:
    """Construct an aiogram Bot. Caller MUST use ``async with`` (D-602; Pitfall B).

    Uses ``ParseMode`` enum internally for type safety (RESEARCH Open Q2):
    invalid TOML strings (e.g. ``"FOO_BAD_VALUE"``) raise ``ValueError`` at
    construction time, NOT mid-send.
    """
    pm = ParseMode(parse_mode)  # fail-fast on invalid string
    return Bot(token=token, default=DefaultBotProperties(parse_mode=pm))


__all__ = [
    "SendOutcome",
    "_RETRY_TYPES",  # exported for canary tests
    "_make_before_sleep",  # exported so fast_retry fixture can preserve callback
    "open_bot",
    "send_message_with_policy",
    "send_document_with_policy",
]
