"""CRAWL-03 — per-SKU exception isolation in `ViledFetcher`.

Plan 02-04 / Wave 3 GREEN. A single fetch raising MUST NOT abort the run
loop; the failure is logged + counted in `stats["fetch_failures"]` and the
loop proceeds to the next URL.

Source: 02-RESEARCH.md §Validation Architecture row 15;
        02-PATTERNS.md §"Pattern: Per-SKU Isolation".
"""

from __future__ import annotations

from ga_crawler.fetchers.viled import ViledFetcher, fetch_one_isolated


# ---------- fetch_one_isolated wrapper ----------


def test_exception_is_isolated_and_counted():
    stats: dict = {}

    def boom(url):
        raise RuntimeError("kaboom")

    result = fetch_one_isolated(boom, "https://viled.kz/item/1", stats)
    assert result is None
    assert stats["fetch_failures"] == 1


def test_no_exception_passthrough():
    stats: dict = {}

    def ok(url):
        return {"status": 200, "url": url, "html": "<html></html>"}

    result = fetch_one_isolated(ok, "https://viled.kz/item/1", stats)
    assert result == {"status": 200, "url": "https://viled.kz/item/1", "html": "<html></html>"}
    assert "fetch_failures" not in stats  # success doesn't touch the counter


def test_multiple_failures_accumulate():
    stats: dict = {}

    def boom(url):
        raise ValueError("nope")

    fetch_one_isolated(boom, "u1", stats)
    fetch_one_isolated(boom, "u2", stats)
    fetch_one_isolated(boom, "u3", stats)
    assert stats["fetch_failures"] == 3


def test_mixed_success_and_failure():
    stats: dict = {}

    def maybe(url):
        if url.endswith("bad"):
            raise IOError("network")
        return {"status": 200, "url": url, "html": ""}

    r1 = fetch_one_isolated(maybe, "https://viled.kz/item/1", stats)
    r2 = fetch_one_isolated(maybe, "https://viled.kz/item/bad", stats)
    r3 = fetch_one_isolated(maybe, "https://viled.kz/item/3", stats)
    assert r1 is not None
    assert r2 is None
    assert r3 is not None
    assert stats["fetch_failures"] == 1


# ---------- Run-loop continues past a bad SKU ----------


def test_run_loop_continues_after_one_failure():
    """If SKU#2 raises, SKU#3 still gets fetched and recorded."""
    fetcher = ViledFetcher(run_id=1, pause_seconds=0)

    call_log: list[str] = []

    def fake_fetch(url):
        call_log.append(url)
        if url.endswith("/2"):
            raise RuntimeError("transient")
        return {"status": 200, "url": url, "html": "<html></html>"}

    fetcher.fetch_one = fake_fetch
    stats: dict = {}
    records = fetcher.run_loop(
        ["https://viled.kz/item/1", "https://viled.kz/item/2", "https://viled.kz/item/3"],
        stats,
        sleep_fn=lambda s: None,
    )
    # All 3 calls happened (no early abort).
    assert len(call_log) == 3
    # Two records (SKU 1 and 3); SKU 2 was lost.
    assert len(records) == 2
    assert stats["fetch_failures"] == 1
    assert stats["fetch_count"] == 3
