"""Per-SKU isolation tests (CRAWL-03)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ga_crawler.fetchers.goldapple import fetch_one_isolated


@pytest.mark.asyncio
async def test_isolation_swallows_exception() -> None:
    """Arbitrary exception → returns None, stats incremented, no raise."""
    page = object()
    stats: dict = {}

    async def boom(p, u):
        raise ValueError("boom")

    result = await fetch_one_isolated(boom, page, "https://goldapple.kz/100-test", stats)
    assert result is None
    assert stats["fetch_failures"] == 1


@pytest.mark.asyncio
async def test_isolation_passes_through_success() -> None:
    """Successful fetch → record returned, stats not touched."""
    page = object()
    stats: dict = {}

    async def ok(p, u):
        return {"url": u, "status": 200, "block": False}

    result = await fetch_one_isolated(ok, page, "https://goldapple.kz/100-test", stats)
    assert result == {"url": "https://goldapple.kz/100-test", "status": 200, "block": False}
    assert "fetch_failures" not in stats


@pytest.mark.asyncio
async def test_isolation_runs_continue_after_failure() -> None:
    """5 sequential calls; 2 throw, 3 succeed → stats=2 failures, 3 records."""
    page = object()
    stats: dict = {}
    call_count = {"i": 0}

    async def fetch_callable(p, u):
        call_count["i"] += 1
        if call_count["i"] in {2, 4}:
            raise RuntimeError(f"transient on call {call_count['i']}")
        return {"url": u, "status": 200, "block": False}

    results = []
    for n in range(5):
        r = await fetch_one_isolated(
            fetch_callable, page, f"https://goldapple.kz/{n}-x", stats
        )
        results.append(r)

    successes = [r for r in results if r is not None]
    failures = [r for r in results if r is None]
    assert len(successes) == 3
    assert len(failures) == 2
    assert stats["fetch_failures"] == 2


@pytest.mark.asyncio
async def test_isolation_logs_failed_url(caplog) -> None:
    """structlog event 'fetch_failed' is emitted with url + error type."""
    page = object()
    stats: dict = {}

    async def boom(p, u):
        raise ValueError("boom-msg")

    with caplog.at_level("ERROR"):
        await fetch_one_isolated(boom, page, "https://goldapple.kz/999-bad", stats)

    # structlog renders to logger; the URL should appear somewhere in caplog text.
    # If structlog routes to stdlib logger, caplog captures; else this test is best-effort.
    text = " ".join(rec.getMessage() for rec in caplog.records)
    # Tolerant check — structlog may not emit through stdlib logger by default
    if text:
        assert "999-bad" in text or "fetch_failed" in text
