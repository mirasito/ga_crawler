"""Goldapple fetcher (Camoufox Tier 2 + tenacity retry + per-SKU isolation).

Architecture (verified by spike 01-08 100-fetch run, 99/100 success):
  GoldappleFetcher (async context manager)
    ├── __aenter__: tempfile.mkdtemp profile dir → AsyncCamoufox boot (D-311 fresh profile per run)
    ├── fetch_one(url): page.goto + gate-poll + state classify (delegates to parsers.goldapple_microdata.detect_state)
    │   └── _goto_with_retry: tenacity exp+jitter on TransientFetchError + PWTimeout (CRAWL-04)
    ├── fetch_one_isolated(url, stats): wraps fetch_one in try/except (CRAWL-03)
    ├── run_loop(urls, stats, sleep_fn): sequential drive with random.uniform(3,5) pacing
    └── __aexit__: shutil.rmtree(profile_dir, ignore_errors=True) — always-cleanup (Pitfall 7)

Source: 03-RESEARCH.md §Pattern 3 lines 461-490 (Camoufox bootstrap),
        §Pattern 5 lines 675-712 (retry + isolation),
        §"Code Examples" lines 858-902 (full fetch_one with state classification),
        spike notebook.py L41-49 (constants), L128-191 (fetch_one), L207-214 (bootstrap),
        L217-257 (run_loop).
"""

from __future__ import annotations

import asyncio
import random
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import structlog

from ga_crawler.parsers.goldapple_microdata import (
    GATE_SHELL_MAX_BYTES,
    GATE_TITLE_MARKER,
)

# ---- Constants (mirror pyproject.toml [tool.ga_crawler.crawl.goldapple]) ----
# Hard-coded defaults for module-level usability; orchestrator (Wave 5) may
# override at fetcher construction time when it loads pyproject config.
PAUSE_RANGE: tuple[float, float] = (3.0, 5.0)            # D-04 + SKILL
PAGE_TIMEOUT_MS: int = 60_000
GATE_POLL_DEADLINE_MS: int = 25_000
GATE_POLL_STEP_MS: int = 500
RETRY_MAX_ATTEMPTS: int = 3                              # tenacity stop_after_attempt
RETRY_WAIT_INITIAL: float = 2.0
RETRY_WAIT_MAX: float = 30.0


log = structlog.get_logger(__name__)


# ---- Exceptions ----

class TransientFetchError(Exception):
    """Raised on retryable network failures: connection error, 5xx response,
    timeout, no-response. tenacity retries; non-transient errors (403/404)
    are NOT raised — caller decides parse outcome.
    """


# ---- Tenacity retry decorator (lazy import; tests can swap policy via monkeypatch) ----

def _make_retry_decorator():
    """Build the tenacity retry decorator. Factory so tests can override
    waits via monkeypatching this function before import in test setUp.
    """
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential_jitter,
    )
    try:
        from playwright.async_api import TimeoutError as PWTimeout
    except ImportError:
        # Camoufox is Firefox-based; playwright pkg may or may not expose this.
        # Fall back to a generic Exception subclass so tenacity-retry-by-type still works.
        class PWTimeout(Exception):  # type: ignore[no-redef]
            pass

    return retry(
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        wait=wait_exponential_jitter(initial=RETRY_WAIT_INITIAL, max=RETRY_WAIT_MAX),
        retry=retry_if_exception_type((TransientFetchError, PWTimeout)),
        reraise=True,
    )


_RETRY = _make_retry_decorator()


@_RETRY
async def _goto_with_retry(page: Any, url: str, timeout_ms: int = PAGE_TIMEOUT_MS) -> Any:
    """Per CRAWL-04. tenacity policy:
       - stop_after_attempt(3): max 3 tries
       - wait_exponential_jitter(initial=2, max=30): 2s + jitter, then exp grow capped at 30s
       - retry_if_exception_type(TransientFetchError, PWTimeout): retry on transient only
       - reraise=True: surfaces final failure to caller for per-SKU isolation

    Non-transient (403, 404, 410): returns response — caller's parse handles.

    Source: 03-RESEARCH.md §Pattern 5 lines 682-699 (verbatim).
    """
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as e:
        # If exception type is in retry set, tenacity will catch on next iteration;
        # else raise unchanged.
        msg = type(e).__name__
        if "Timeout" in msg or "Transient" in msg:
            raise
        # Re-raise other exceptions as TransientFetchError to enable retry on transient
        # network gunk (DNS hiccups, TCP RSTs). Non-transient parse-time issues
        # are caller's domain.
        raise TransientFetchError(f"{msg}: {e!r}") from e

    if response is None:
        raise TransientFetchError("no response (page.goto returned None)")
    if response.status >= 500:
        raise TransientFetchError(f"5xx: {response.status}")
    return response


# ---- fetch_one_isolated (CRAWL-03) — pure wrapper, can be unit-tested with mocks ----

async def fetch_one_isolated(
    fetch_callable: Callable[[Any, str], Awaitable[dict]],
    page: Any,
    url: str,
    stats: dict,
) -> Optional[dict]:
    """Per-SKU isolation per CRAWL-03. Any exception from fetch_callable is
    logged + counted but does NOT propagate. Source: RESEARCH §Pattern 5
    lines 701-711 (verbatim).

    Wave 5 orchestrator passes `GoldappleFetcher.fetch_one` as fetch_callable.
    Tests inject a mock callable.
    """
    try:
        return await fetch_callable(page, url)
    except Exception as e:
        log.error(
            "fetch_failed",
            url=url,
            error=str(e),
            error_type=type(e).__name__,
        )
        stats["fetch_failures"] = stats.get("fetch_failures", 0) + 1
        return None


# ---- GoldappleFetcher class scaffold (Task 2 fills out fetch_one + lifecycle) ----

class GoldappleFetcher:
    """CrawlerProtocol-conforming async context manager.

    Lifecycle:
      __aenter__:
        - tempfile.mkdtemp(prefix=f"camoufox-run-{run_id}-") → tmp profile dir (D-311)
        - AsyncCamoufox(...) boot with locked kwargs (geoip, locale, humanize, persistent_context)
        - capture browser + first page
      __aexit__:
        - close browser
        - shutil.rmtree(profile_dir, ignore_errors=True) — Pitfall 7

    Methods (Task 2 below):
      - fetch_one(page, url) -> dict
      - fetch_one_isolated(url, stats) -> Optional[dict]
      - run_loop(urls, stats, sleep_fn=None) -> list[dict]
    """

    site = "goldapple"

    def __init__(self, run_id: int, headless: bool = True):
        self.run_id = run_id
        self.headless = headless
        self.profile_dir = Path(tempfile.mkdtemp(prefix=f"camoufox-run-{run_id}-"))
        self._cm: Any = None
        self._browser: Any = None
        self._page: Any = None

    # __aenter__ / __aexit__ / fetch_one / run_loop in Task 2.
