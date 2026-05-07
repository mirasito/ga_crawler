"""CRAWL-04 — tenacity retry policy on viled fetch.

Plan 02-04 / Wave 3 GREEN. Verifies:
  - 5xx raises TransientFetchError → retry up to 3 attempts; succeed on 3rd
  - 4xx (e.g. 404) returns naturally → 1 attempt
  - 3 sequential failures → re-raise (reraise=True)
  - exception classes import from `curl_cffi.requests.exceptions` (A10 REVISED)

Source: 02-RESEARCH.md §Pattern 9; 02-WAVE0-PROBE.md §A10 REVISED.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ga_crawler.fetchers.viled import _fetch_html, TransientFetchError


class _StubResp:
    """Minimal stand-in for curl_cffi.requests.Response — the two attrs
    `_fetch_html` reads.
    """

    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


# ---------- 5xx triggers TransientFetchError → retried ----------


def test_retry_on_transient_5xx_then_success():
    state = {"calls": 0}

    def flaky(*_, **__):
        state["calls"] += 1
        if state["calls"] < 3:
            return _StubResp(503, "")
        return _StubResp(200, "<html>ok</html>")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=flaky):
        status, body = _fetch_html("https://viled.kz/x")
    assert status == 200
    assert state["calls"] == 3


def test_max_3_attempts_then_reraise_on_persistent_5xx():
    state = {"calls": 0}

    def always_503(*_, **__):
        state["calls"] += 1
        return _StubResp(503, "")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=always_503):
        with pytest.raises(TransientFetchError):
            _fetch_html("https://viled.kz/x")
    assert state["calls"] == 3


# ---------- 4xx is NOT retried ----------


def test_no_retry_on_404():
    state = {"calls": 0}

    def respond_404(*_, **__):
        state["calls"] += 1
        return _StubResp(404, "")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=respond_404):
        status, body = _fetch_html("https://viled.kz/x")
    assert status == 404
    assert state["calls"] == 1


def test_no_retry_on_410():
    """410 Gone is also a non-retryable terminal state (DELISTED route)."""
    state = {"calls": 0}

    def respond_410(*_, **__):
        state["calls"] += 1
        return _StubResp(410, "")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=respond_410):
        status, _ = _fetch_html("https://viled.kz/x")
    assert status == 410
    assert state["calls"] == 1


def test_no_retry_on_403():
    """403 surfaces immediately — Pitfall 8 fallback is the caller's domain."""
    state = {"calls": 0}

    def respond_403(*_, **__):
        state["calls"] += 1
        return _StubResp(403, "")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=respond_403):
        status, _ = _fetch_html("https://viled.kz/x")
    assert status == 403
    assert state["calls"] == 1


# ---------- curl_cffi exception types are in retry-set (A10 REVISED) ----------


def test_curl_cffi_timeout_is_retried():
    """`curl_cffi.requests.exceptions.Timeout` MUST be in the retry-set."""
    from curl_cffi.requests.exceptions import Timeout

    state = {"calls": 0}

    def flaky(*_, **__):
        state["calls"] += 1
        if state["calls"] < 3:
            raise Timeout("test timeout")
        return _StubResp(200, "<html>ok</html>")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=flaky):
        status, _ = _fetch_html("https://viled.kz/x")
    assert status == 200
    assert state["calls"] == 3


def test_curl_cffi_connection_error_is_retried():
    from curl_cffi.requests.exceptions import ConnectionError as CCConnectionError

    state = {"calls": 0}

    def flaky(*_, **__):
        state["calls"] += 1
        if state["calls"] < 3:
            raise CCConnectionError("test conn err")
        return _StubResp(200, "")

    with patch("ga_crawler.fetchers.viled.requests.get", side_effect=flaky):
        status, _ = _fetch_html("https://viled.kz/x")
    assert status == 200
    assert state["calls"] == 3


def test_a10_import_path_correct():
    """Sanity: A10 REVISED — exceptions live at `curl_cffi.requests.exceptions`,
    NOT `curl_cffi.requests.errors`. Failing this is a Wave 0 cascade regression.
    """
    from curl_cffi.requests.exceptions import (  # noqa: F401
        ConnectTimeout,
        ConnectionError as _CCConnectionError,
        HTTPError,
        ReadTimeout,
        RequestException,
        Timeout,
    )
    # Also verify .errors does NOT export these (negative assertion).
    from curl_cffi.requests import errors as _errors_mod
    assert not hasattr(_errors_mod, "Timeout"), (
        "If curl_cffi adds Timeout to .errors, update WAVE0-PROBE A10 + this assertion"
    )
