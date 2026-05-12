"""Plan 06-03 (Wave 2) — unit tests for delivery/telegram_client.py.

Per CONTEXT D-601 + D-603, RESEARCH §5 + §11, Pitfall A + B, caveat #2.

Coverage axes:
  - 6-way exception classification (2 retry + 4 fail-fast + 1 retry-after)
  - tenacity wait_chain(5, 15, 45) — NOT wait_exponential (caveat #2)
  - TelegramRetryAfter handled OUTSIDE tenacity via asyncio.sleep loop
  - B3 FIX — precise attempt counting via closure-shared attempt_tracker
    + before_sleep callback (cumulative across retries, no leak between calls)
  - open_bot ParseMode enum validation
  - Structural canaries (source-lock: wait_chain, before_sleep, attempt_tracker,
    _RETRY_TYPES tuple shape, no wait_exponential)

Tests deliberately avoid real time-passing (~75s tenacity budget) by patching
``_build_retry_decorator`` to use ``wait_fixed(0)`` while preserving
``before_sleep`` callback semantics (so attempt_tracker still increments).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.methods import SendDocument, SendMessage

from ga_crawler.delivery.telegram_client import (
    SendOutcome,
    _RETRY_TYPES,
    open_bot,
    send_document_with_policy,
    send_message_with_policy,
)


# ---- helpers --------------------------------------------------------------


def _send_message_method() -> SendMessage:
    """Aiogram exception constructors require a method= arg; build a stub."""
    return SendMessage(chat_id="c", text="t")


def _send_document_method() -> SendDocument:
    return SendDocument(chat_id="c", document="x")


def _network_error(msg: str = "connection reset") -> TelegramNetworkError:
    return TelegramNetworkError(method=_send_message_method(), message=msg)


def _server_error(msg: str = "500 internal") -> TelegramServerError:
    return TelegramServerError(method=_send_message_method(), message=msg)


def _bad_request(msg: str = "chat not found") -> TelegramBadRequest:
    return TelegramBadRequest(method=_send_message_method(), message=msg)


def _forbidden(msg: str = "bot kicked") -> TelegramForbiddenError:
    return TelegramForbiddenError(method=_send_message_method(), message=msg)


def _not_found(msg: str = "chat does not exist") -> TelegramNotFound:
    return TelegramNotFound(method=_send_message_method(), message=msg)


def _unauthorized(msg: str = "token revoked") -> TelegramUnauthorizedError:
    return TelegramUnauthorizedError(method=_send_message_method(), message=msg)


def _retry_after(seconds: int = 2) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=_send_message_method(),
        message=f"flood control: wait {seconds}",
        retry_after=seconds,
    )


@pytest.fixture
def fast_retry(monkeypatch):
    """B3 FIX: patch wait_chain(5,15,45) → wait_chain(0,0,0); preserve before_sleep.

    Replaces ``_build_retry_decorator`` so tests do not wait the real
    5/15/45 second sequence, but keep the closure-shared attempt_tracker
    + before_sleep callback semantics intact.
    """
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_chain,
        wait_fixed,
    )

    from ga_crawler.delivery import telegram_client as tc

    def fast_builder(max_attempts, attempt_tracker):
        return retry(
            retry=retry_if_exception_type(tc._RETRY_TYPES),
            stop=stop_after_attempt(max_attempts),
            wait=wait_chain(wait_fixed(0), wait_fixed(0), wait_fixed(0)),
            before_sleep=tc._make_before_sleep(attempt_tracker),
            reraise=True,
        )

    monkeypatch.setattr(
        "ga_crawler.delivery.telegram_client._build_retry_decorator",
        fast_builder,
    )


@pytest.fixture
def fast_sleep(monkeypatch):
    """Skip real asyncio.sleep in retry-after loops; record durations."""
    import asyncio

    recorded = []

    async def _fake_sleep(seconds):
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    return recorded


# ---- open_bot -------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_bot_with_html_parse_mode():
    from aiogram.enums import ParseMode

    bot = await open_bot("123456789:test-token-stub-ABCDEFG", parse_mode="HTML")
    try:
        assert bot.default is not None
        assert bot.default.parse_mode == ParseMode.HTML
    finally:
        # Clean up session to avoid unclosed-session warning on teardown.
        await bot.session.close()


@pytest.mark.asyncio
async def test_open_bot_with_markdown_v2_parse_mode():
    from aiogram.enums import ParseMode

    bot = await open_bot("123456789:test-token-stub-ABCDEFG", parse_mode="MarkdownV2")
    try:
        assert bot.default.parse_mode == ParseMode.MARKDOWN_V2
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_open_bot_raises_on_invalid_parse_mode():
    with pytest.raises(ValueError):
        await open_bot("123456789:test-token-stub-ABCDEFG", parse_mode="FOO_BAD_VALUE")


# ---- send_message_with_policy --------------------------------------------


@pytest.mark.asyncio
async def test_send_message_success_attempts_eq_1(mock_aiogram_bot):
    """1st-call success: attempts == 1 exactly (B3 FIX)."""
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hello")
    assert outcome.message_id == 10001
    assert outcome.attempts == 1, f"expected exactly 1 attempt, got {outcome.attempts}"
    assert outcome.error is None
    assert mock_aiogram_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_send_message_network_error_exhausts_attempts_eq_3(
    mock_aiogram_bot, fast_retry
):
    """3 tenacity retries on TelegramNetworkError → attempts == 3 (B3 FIX precise)."""
    mock_aiogram_bot.send_message = AsyncMock(
        side_effect=[_network_error(), _network_error(), _network_error()]
    )
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.message_id == -1
    assert outcome.attempts == 3, f"expected exactly 3 attempts, got {outcome.attempts}"
    assert outcome.error is not None
    assert outcome.error.startswith("TelegramNetworkError")
    assert mock_aiogram_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_send_message_server_error_then_success_attempts_eq_2(
    mock_aiogram_bot, fast_retry
):
    """ServerError once → retry succeeds on 2nd attempt; attempts == 2 (B3 FIX)."""
    mock_aiogram_bot.send_message = AsyncMock(
        side_effect=[_server_error(), MagicMock(message_id=10001)]
    )
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.message_id == 10001
    assert outcome.attempts == 2, f"expected exactly 2 attempts, got {outcome.attempts}"
    assert outcome.error is None
    assert mock_aiogram_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_send_message_bad_request_no_retry_attempts_eq_1(mock_aiogram_bot):
    """TelegramBadRequest → NO retry (Pitfall A); attempts == 1."""
    mock_aiogram_bot.send_message = AsyncMock(side_effect=_bad_request())
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.message_id == -1
    assert outcome.attempts == 1
    assert outcome.error is not None
    assert outcome.error.startswith("TelegramBadRequest")
    assert mock_aiogram_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_send_message_forbidden_no_retry(mock_aiogram_bot):
    """TelegramForbiddenError → NO retry (Pitfall A); attempts == 1."""
    mock_aiogram_bot.send_message = AsyncMock(side_effect=_forbidden())
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.attempts == 1
    assert outcome.error.startswith("TelegramForbiddenError")
    assert mock_aiogram_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_send_message_not_found_no_retry(mock_aiogram_bot):
    """TelegramNotFound → NO retry (Pitfall A); attempts == 1."""
    mock_aiogram_bot.send_message = AsyncMock(side_effect=_not_found())
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.attempts == 1
    assert outcome.error.startswith("TelegramNotFound")


@pytest.mark.asyncio
async def test_send_message_unauthorized_no_retry(mock_aiogram_bot):
    """TelegramUnauthorizedError → NO retry (Pitfall A); attempts == 1."""
    mock_aiogram_bot.send_message = AsyncMock(side_effect=_unauthorized())
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.attempts == 1
    assert outcome.error.startswith("TelegramUnauthorizedError")


@pytest.mark.asyncio
async def test_retry_after_honored_attempts_eq_2(mock_aiogram_bot, fast_sleep):
    """TelegramRetryAfter once → asyncio.sleep(retry_after) → re-attempt → success.

    attempts == 2 (B3 FIX: 1 retry-after raise + 1 successful retry).
    """
    mock_aiogram_bot.send_message = AsyncMock(
        side_effect=[_retry_after(seconds=2), MagicMock(message_id=10001)]
    )
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.message_id == 10001
    assert outcome.attempts == 2, f"expected 2 attempts, got {outcome.attempts}"
    assert outcome.error is None
    assert mock_aiogram_bot.send_message.call_count == 2
    # asyncio.sleep was called with retry_after=2 (Pitfall: seconds, not ms)
    assert 2 in fast_sleep, f"asyncio.sleep not called with 2, recorded={fast_sleep}"


@pytest.mark.asyncio
async def test_retry_after_exhausted_attempts_eq_3(mock_aiogram_bot, fast_sleep):
    """TelegramRetryAfter on every call → 3 iterations exhausted; attempts == 3."""
    mock_aiogram_bot.send_message = AsyncMock(
        side_effect=[_retry_after(seconds=1)] * 5
    )
    outcome = await send_message_with_policy(mock_aiogram_bot, "chat-123", "hi")
    assert outcome.message_id == -1
    assert outcome.attempts == 3, f"expected exactly 3 attempts, got {outcome.attempts}"
    assert outcome.error is not None
    assert "TelegramRetryAfter" in outcome.error


# ---- send_document_with_policy -------------------------------------------


@pytest.mark.asyncio
async def test_send_document_accepts_path_attempts_eq_1(tmp_path, mock_aiogram_bot):
    """FSInputFile(pathlib.Path) accepted; on success attempts == 1."""
    fake_xlsx = tmp_path / "weekly.xlsx"
    fake_xlsx.write_bytes(b"PK\x03\x04stub")
    outcome = await send_document_with_policy(
        mock_aiogram_bot, "chat-123", fake_xlsx, "caption text"
    )
    assert outcome.message_id == 10002
    assert outcome.attempts == 1
    assert outcome.error is None
    assert mock_aiogram_bot.send_document.call_count == 1


@pytest.mark.asyncio
async def test_send_document_network_error_exhausts_attempts_eq_3(
    tmp_path, mock_aiogram_bot, fast_retry
):
    """send_document tenacity retry path mirrors send_message."""
    fake_xlsx = tmp_path / "weekly.xlsx"
    fake_xlsx.write_bytes(b"PK\x03\x04stub")
    net_err = TelegramNetworkError(method=_send_document_method(), message="boom")
    mock_aiogram_bot.send_document = AsyncMock(side_effect=[net_err, net_err, net_err])
    outcome = await send_document_with_policy(
        mock_aiogram_bot, "chat-123", fake_xlsx, "caption"
    )
    assert outcome.message_id == -1
    assert outcome.attempts == 3
    assert outcome.error.startswith("TelegramNetworkError")
    assert mock_aiogram_bot.send_document.call_count == 3


# ---- Structural canaries -------------------------------------------------


def test_wait_chain_used_not_exponential():
    """Source-lock: wait_chain(5,15,45) per caveat #2 — NOT wait_exponential."""
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ga_crawler"
        / "delivery"
        / "telegram_client.py"
    ).read_text(encoding="utf-8")
    assert "wait_chain" in src
    assert "wait_exponential" not in src, (
        "wait_exponential is forbidden — caveat #2 mandates explicit wait_chain"
    )
    assert "before_sleep" in src, "before_sleep callback hook is required (B3 FIX)"
    assert "attempt_tracker" in src, (
        "attempt_tracker dict is required (B3 FIX — precise attempt counting)"
    )


def test_retry_types_excludes_fail_fast_classes():
    """_RETRY_TYPES tuple must be exactly (TelegramNetworkError, TelegramServerError)."""
    assert _RETRY_TYPES == (TelegramNetworkError, TelegramServerError)
    assert TelegramBadRequest not in _RETRY_TYPES, "Pitfall A: BadRequest must fail-fast"
    assert TelegramForbiddenError not in _RETRY_TYPES, "Pitfall A: Forbidden must fail-fast"
    assert TelegramNotFound not in _RETRY_TYPES, "Pitfall A: NotFound must fail-fast"
    assert (
        TelegramUnauthorizedError not in _RETRY_TYPES
    ), "Pitfall A: Unauthorized must fail-fast"


def test_send_outcome_has_3_fields():
    """SendOutcome dataclass shape: message_id, attempts, error."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(SendOutcome)}
    assert fields == {"message_id", "attempts", "error"}


def test_module_only_aiogram_import_site():
    """Isolation canary: aiogram imported ONLY from telegram_client.py.

    Verifies delivery package isolation per architectural decision:
    config.py / stats.py / message_builder.py / gate.py / __init__.py
    must NOT touch aiogram.
    """
    delivery_pkg = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ga_crawler"
        / "delivery"
    )
    for py in delivery_pkg.glob("*.py"):
        if py.name == "telegram_client.py":
            continue
        text = py.read_text(encoding="utf-8")
        assert "import aiogram" not in text, f"{py.name} must not import aiogram"
        assert "from aiogram" not in text, f"{py.name} must not import aiogram"


# ---- B3 FIX — tracker isolation -----------------------------------------


@pytest.mark.asyncio
async def test_send_message_no_tracker_leak(mock_aiogram_bot, fast_retry):
    """Two consecutive calls on same bot — each gets own attempt_tracker.

    First call exhausts (attempts==3); second succeeds first try (attempts==1).
    Tracker leak would show second call as attempts==4 — B3 FIX rejects.
    """
    # Call 1 — exhausts retries
    mock_aiogram_bot.send_message = AsyncMock(
        side_effect=[_network_error(), _network_error(), _network_error()]
    )
    r1 = await send_message_with_policy(mock_aiogram_bot, "chat-1", "text1")
    assert r1.attempts == 3
    # Call 2 — fresh tracker; first-try success
    mock_aiogram_bot.send_message = AsyncMock(return_value=MagicMock(message_id=10002))
    r2 = await send_message_with_policy(mock_aiogram_bot, "chat-2", "text2")
    assert r2.attempts == 1, (
        f"Tracker leaked between invocations — expected 1, got {r2.attempts}. "
        "B3 FIX requires per-invocation tracker isolation."
    )
    assert r2.message_id == 10002
