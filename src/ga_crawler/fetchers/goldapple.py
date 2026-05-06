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

    async def __aenter__(self) -> "GoldappleFetcher":
        """Boot Camoufox with locked kwargs (D-311 fresh profile + SKILL operational constants)."""
        from camoufox.async_api import AsyncCamoufox

        self._cm = AsyncCamoufox(
            headless=self.headless,
            geoip=True,                              # SKILL operational constant
            locale=["ru-RU", "kk-KZ", "en-US"],      # SKILL
            humanize=True,                           # SKILL
            persistent_context=True,                 # D-04 / SKILL
            user_data_dir=str(self.profile_dir),     # D-311 fresh tmp profile
        )
        try:
            self._browser = await self._cm.__aenter__()
            self._page = (
                self._browser.pages[0]
                if getattr(self._browser, "pages", None)
                else await self._browser.new_page()
            )
        except Exception:
            # Camoufox failed to boot — clean up profile dir before re-raising
            shutil.rmtree(self.profile_dir, ignore_errors=True)
            raise
        log.info(
            "camoufox_booted",
            run_id=self.run_id,
            profile_dir=str(self.profile_dir),
            headless=self.headless,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Always cleanup profile dir, even on failure (Pitfall 7)."""
        try:
            if self._cm is not None:
                await self._cm.__aexit__(exc_type, exc, tb)
        finally:
            shutil.rmtree(self.profile_dir, ignore_errors=True)
            log.info("camoufox_torn_down", run_id=self.run_id)

    async def fetch_one(self, page: Any, url: str) -> dict:
        """Returns spike-style dict per RESEARCH §"Code Examples" lines 858-902.

        Calls _goto_with_retry under the hood (CRAWL-04). Exception handling
        is deliberately broad — any error sets block=True so caller per-SKU
        isolation logic (fetch_one_isolated) can record without bubbling.
        """
        started = time.perf_counter()
        rec: dict = {
            "url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": None,
            "timing_ms": None,
            "html_size": None,
            "title": None,
            "gate_cleared": False,
            "gate_cleared_after_ms": None,
            "block": False,
            "block_reason": None,
            "error": None,
        }
        try:
            response = await _goto_with_retry(page, url, timeout_ms=PAGE_TIMEOUT_MS)
            rec["status"] = response.status if response else None

            # Best-effort networkidle (Camoufox / playwright may raise; ignore)
            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass

            # Poll title for gate clearance — spike notebook.py L161-168
            elapsed = 0
            last_title = ""
            while elapsed < GATE_POLL_DEADLINE_MS:
                last_title = await page.title()
                if GATE_TITLE_MARKER not in last_title.lower():
                    rec["gate_cleared"] = True
                    rec["gate_cleared_after_ms"] = elapsed
                    break
                await page.wait_for_timeout(GATE_POLL_STEP_MS)
                elapsed += GATE_POLL_STEP_MS
            rec["title"] = last_title

            html = await page.content()
            rec["html_size"] = len(html)

            # State classification (mirrors detect_state thresholds; record-style fields).
            # NOTE: keep field-names back-compatible with spike notebook.py for log replay.
            if not rec["gate_cleared"] and rec["html_size"] < GATE_SHELL_MAX_BYTES:
                rec["block"] = True
                rec["block_reason"] = "gate_shell_not_cleared"
            elif rec["status"] not in (200, 304):
                rec["block"] = True
                rec["block_reason"] = f"http_{rec['status']}"
            else:
                rec["html"] = html  # caller passes to parse_pdp
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {repr(e)[:200]}"
            rec["block"] = True
            rec["block_reason"] = "exception"
        rec["timing_ms"] = int((time.perf_counter() - started) * 1000)
        return rec

    async def fetch_one_isolated(self, url: str, stats: dict) -> Optional[dict]:
        """Per-SKU isolation wrapper (CRAWL-03). Exposed as instance method
        for orchestrator convenience; delegates to module-level fetch_one_isolated.
        """
        return await fetch_one_isolated(self.fetch_one, self._page, url, stats)

    async def run_loop(
        self,
        urls: list[str],
        stats: dict,
        sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> list[dict]:
        """Sequential fetch loop with random.uniform(3, 5) pacing per CRAWL-06.

        Args:
          urls: list of product URLs to fetch (matched_urls from intersect_brand_pool)
          stats: mutable dict accumulating fetch_failures / fetch_count / etc.
          sleep_fn: optional override for asyncio.sleep (test injection)

        Returns:
          list of fetch records (one per URL; None entries replaced with the
          partial record from fetch_one if it has block=True; truly-isolated
          exceptions are logged + counter-incremented and not appended).

        Source: spike notebook.py L217-257 (refactored for class method + injectable sleep).
        """
        if sleep_fn is None:
            sleep_fn = asyncio.sleep

        records: list[dict] = []
        for i, url in enumerate(urls, 1):
            rec = await fetch_one_isolated(self.fetch_one, self._page, url, stats)
            stats["fetch_count"] = stats.get("fetch_count", 0) + 1
            if rec is not None:
                records.append(rec)
                # Track gate-shell + stale via block_reason for runs.stats audit
                br = rec.get("block_reason")
                if br == "gate_shell_not_cleared":
                    stats["gate_shell_count"] = stats.get("gate_shell_count", 0) + 1
            log.info(
                "fetch_progress",
                run_id=self.run_id,
                idx=i,
                total=len(urls),
                url=url,
                block=(rec is None) or rec.get("block", False),
            )
            if i < len(urls):
                await sleep_fn(random.uniform(*PAUSE_RANGE))
        return records


__all__ = [
    "PAUSE_RANGE",
    "PAGE_TIMEOUT_MS",
    "GATE_POLL_DEADLINE_MS",
    "GATE_POLL_STEP_MS",
    "RETRY_MAX_ATTEMPTS",
    "RETRY_WAIT_INITIAL",
    "RETRY_WAIT_MAX",
    "TransientFetchError",
    "GoldappleFetcher",
    "fetch_one_isolated",
    "_goto_with_retry",
]
