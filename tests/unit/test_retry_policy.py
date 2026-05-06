"""tenacity retry policy tests (CRAWL-04)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ga_crawler.fetchers.goldapple import (
    RETRY_MAX_ATTEMPTS,
    TransientFetchError,
    _goto_with_retry,
)


@pytest.mark.asyncio
async def test_retry_succeeds_on_third_attempt() -> None:
    """First 2 attempts raise transient, 3rd returns 200."""
    response_200 = MagicMock()
    response_200.status = 200
    page = MagicMock()
    page.goto = AsyncMock(
        side_effect=[
            TransientFetchError("flaky"),
            TransientFetchError("flaky"),
            response_200,
        ]
    )
    result = await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert result is response_200
    assert page.goto.call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausts_after_3_attempts() -> None:
    """All 3 attempts fail → reraise the TransientFetchError."""
    page = MagicMock()
    page.goto = AsyncMock(side_effect=TransientFetchError("persistent"))
    with pytest.raises(TransientFetchError, match="persistent"):
        await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert page.goto.call_count == RETRY_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_retry_5xx_raises_after_3_attempts() -> None:
    """503 response → raised as TransientFetchError; tenacity retries 3x then reraises."""
    response_503 = MagicMock()
    response_503.status = 503
    page = MagicMock()
    page.goto = AsyncMock(return_value=response_503)
    with pytest.raises(TransientFetchError, match="5xx: 503"):
        await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert page.goto.call_count == RETRY_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_retry_403_NOT_retried() -> None:
    """Non-transient 403 → response returned, NO retry."""
    response_403 = MagicMock()
    response_403.status = 403
    page = MagicMock()
    page.goto = AsyncMock(return_value=response_403)
    result = await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert result is response_403
    assert page.goto.call_count == 1


@pytest.mark.asyncio
async def test_retry_404_NOT_retried() -> None:
    """Non-transient 404 → response returned, NO retry. PARSE-05 will count as missing."""
    response_404 = MagicMock()
    response_404.status = 404
    page = MagicMock()
    page.goto = AsyncMock(return_value=response_404)
    result = await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert result is response_404
    assert page.goto.call_count == 1


@pytest.mark.asyncio
async def test_retry_no_response_raises_after_3_attempts() -> None:
    """page.goto returns None → TransientFetchError; retried 3x then reraises."""
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    with pytest.raises(TransientFetchError, match="no response"):
        await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert page.goto.call_count == RETRY_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_retry_unknown_exception_wrapped_as_transient() -> None:
    """A random ConnectionError wraps as TransientFetchError → retried."""
    page = MagicMock()
    page.goto = AsyncMock(side_effect=ConnectionError("boom"))
    with pytest.raises(TransientFetchError):
        await _goto_with_retry(page, "https://goldapple.kz/100-test", timeout_ms=1000)
    assert page.goto.call_count == RETRY_MAX_ATTEMPTS
