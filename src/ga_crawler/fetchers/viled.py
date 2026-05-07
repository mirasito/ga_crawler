"""viled fetcher — curl_cffi Tier 0, sync sequential, 2 s rate-limit, per-SKU isolated.

D-225: NOT async. Single-thread `for` loop with `time.sleep(pause_seconds)`
between fetches. Spike 01-07 confirmed 15/15 success at 2 s pause via
`curl_cffi.requests.get(impersonate="chrome")`; Wave 0 PROBE re-confirmed
8/8 (5 PDPs + 3 catalog pages, all HTTP 200 first try).

CRAWL-04 retry policy uses tenacity exp+jitter (initial=2 s, max=30 s, max
3 attempts); retried exception types are imported from
`curl_cffi.requests.exceptions` (NOT `.errors` — see 02-WAVE0-PROBE.md §A10
REVISED: `.errors` only exports CookieConflict/CurlError/RequestsError/
SessionClosed; the full Timeout / ConnectTimeout / ReadTimeout / ConnectionError
/ HTTPError stack lives in `.exceptions`).

CRAWL-03 per-SKU isolation: `fetch_one_isolated` swallows + counts any
exception so a single bad SKU does not abort the run-loop.

Source:
  - 02-RESEARCH.md §Pattern 9 (tenacity for curl_cffi); §Per-SKU Isolation
  - 02-PATTERNS.md (lines 51-153) — fetcher analog of fetchers/goldapple.py
    with async stripped per D-225
  - 02-WAVE0-PROBE.md §A10 — verified curl_cffi exception import paths
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import structlog
from curl_cffi import requests
from curl_cffi.requests.exceptions import (
    ConnectionError as CCConnectionError,
    HTTPError,
    ReadTimeout,
    RequestException,
    Timeout,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = structlog.get_logger(__name__)


# --- Constants (mirror [tool.ga_crawler.crawl.viled]; orchestrator overrides at construction) ---

VILED_TIMEOUT_S: int = 30
VILED_PAUSE_S: float = 2.0
VILED_RETRY_MAX_ATTEMPTS: int = 3
VILED_RETRY_WAIT_INITIAL: float = 2.0
VILED_RETRY_WAIT_MAX: float = 30.0


# --- Exceptions ----

class TransientFetchError(RuntimeError):
    """Raised on retryable network failures (5xx response, network error, timeout).

    tenacity retries this; non-transient outcomes (4xx) return naturally so the
    caller can decide parse outcome (404/410 → DELISTED at Plan 05 normalizer).
    """


# --- Tenacity retry decorator (CRAWL-04) ---
#
# A10 import path: `curl_cffi.requests.exceptions`. Adding the curl_cffi
# native types to the retry-set means any timeout / connection-reset surfacing
# from curl_cffi BEFORE we get a chance to map it to TransientFetchError will
# still be retried. Bare `except Exception` in `_fetch_html` then re-raises
# the broader category as TransientFetchError so the test-friendly type is
# observed by callers.

_RETRY_TYPES = (
    TransientFetchError,
    Timeout,
    ReadTimeout,
    CCConnectionError,
    HTTPError,
    RequestException,
)


@retry(
    stop=stop_after_attempt(VILED_RETRY_MAX_ATTEMPTS),
    wait=wait_exponential_jitter(initial=VILED_RETRY_WAIT_INITIAL, max=VILED_RETRY_WAIT_MAX),
    retry=retry_if_exception_type(_RETRY_TYPES),
    reraise=True,
)
def _fetch_html(url: str, timeout_s: int = VILED_TIMEOUT_S) -> tuple[int, str]:
    """Fetch HTML with curl_cffi `impersonate="chrome"`.

    Returns (status_code, body). Raises TransientFetchError on 5xx or any
    underlying network exception (curl_cffi `Timeout`, `ConnectionError`,
    `HTTPError` subclasses of `RequestException`); tenacity wraps & retries
    up to 3 attempts with exponential jitter.

    4xx returns naturally — the caller (Plan 05 orchestrator) maps 404/410
    to StockState.DELISTED.
    """
    try:
        resp = requests.get(url, impersonate="chrome", timeout=timeout_s)
    except RequestException:
        # curl_cffi-native exception; let tenacity see and retry it directly.
        raise
    except Exception as e:
        # Anything else (DNS, OS errors): rewrap so tenacity retries.
        raise TransientFetchError(f"connection error fetching {url}: {e}") from e
    if 500 <= resp.status_code < 600:
        raise TransientFetchError(f"http {resp.status_code} for {url}")
    return resp.status_code, resp.text


# --- fetch_one_isolated (CRAWL-03) — pure wrapper, sync, mockable ---

def fetch_one_isolated(
    fetch_callable: Callable[[str], dict],
    url: str,
    stats: dict,
) -> Optional[dict]:
    """Per-SKU isolation per CRAWL-03. Any exception from `fetch_callable` is
    logged + counted but does NOT propagate. Returns None on exception so the
    run-loop can continue to the next URL.

    Source: 02-PATTERNS.md §"Pattern: Per-SKU Isolation" (sync adaptation of
    Phase 3 async equivalent in fetchers/goldapple.py).
    """
    try:
        return fetch_callable(url)
    except Exception as e:
        log.error(
            "fetch_failed",
            url=url,
            error=str(e),
            error_type=type(e).__name__,
        )
        stats["fetch_failures"] = stats.get("fetch_failures", 0) + 1
        return None


# --- ViledFetcher class (sync sequential with 2 s pacing) ---

class ViledFetcher:
    """Sync curl_cffi fetcher. concurrency=1 + 2 s pause between fetches (D-225).

    Mirrors GoldappleFetcher's class shape (run_id init, fetch_one, run_loop)
    minus the async/Camoufox lifecycle — viled needs no browser, no profile,
    no `__aenter__`/`__aexit__`.
    """

    site = "viled"

    def __init__(self, *, run_id: int, pause_seconds: float = VILED_PAUSE_S) -> None:
        self.run_id = run_id
        self.pause_seconds = pause_seconds

    def fetch_one(self, url: str) -> dict:
        """Fetch one URL; return spike-style dict {status, url, html}.

        Raises TransientFetchError if all 3 retries fail; the caller is
        responsible for wrapping with `fetch_one_isolated` to keep the
        run-loop alive.
        """
        status, html = _fetch_html(url)
        return {"status": status, "url": url, "html": html}

    def run_loop(
        self,
        urls: list[str],
        stats: dict,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> list[dict]:
        """Sequential fetch loop with `pause_seconds` pacing between fetches.

        Args:
          urls:     list of product URLs (catalog enumeration output).
          stats:    mutable dict; accumulates `fetch_count`, `fetch_failures`.
          sleep_fn: optional override for `time.sleep` (test injection).

        CRAWL-06 + D-225: sleep only between fetches (N URLs → N-1 sleeps);
        the loop does NOT pause after the last fetch.
        """
        records: list[dict] = []
        n = len(urls)
        for i, url in enumerate(urls, 1):
            rec = fetch_one_isolated(self.fetch_one, url, stats)
            stats["fetch_count"] = stats.get("fetch_count", 0) + 1
            if rec is not None:
                records.append(rec)
            log.info(
                "fetch_progress",
                run_id=self.run_id,
                idx=i,
                total=n,
                url=url,
            )
            if i < n:
                sleep_fn(self.pause_seconds)
        return records


__all__ = [
    "VILED_TIMEOUT_S",
    "VILED_PAUSE_S",
    "VILED_RETRY_MAX_ATTEMPTS",
    "VILED_RETRY_WAIT_INITIAL",
    "VILED_RETRY_WAIT_MAX",
    "TransientFetchError",
    "ViledFetcher",
    "fetch_one_isolated",
    "_fetch_html",
]
