"""CRAWL-06 + D-225 rate-limit + ViledConfig.from_pyproject() verification.

Plan 02-04 / Wave 3 GREEN. ViledFetcher.run_loop calls `sleep_fn(pause_seconds)`
exactly N-1 times for N URLs (no sleep after the last URL). ViledConfig loads
the `[tool.ga_crawler.crawl.viled]` namespace from pyproject.toml.

Source: 02-CONTEXT.md D-225, D-227; 02-RESEARCH.md §Validation Architecture row 17.
"""

from __future__ import annotations

from pathlib import Path

from ga_crawler.config import ViledConfig
from ga_crawler.fetchers.viled import ViledFetcher


# ---------- Rate limit: sleep called between fetches only ----------


def test_run_loop_sleeps_pause_seconds_between_each_pair_of_fetches():
    sleep_calls: list[float] = []

    def fake_sleep(s):
        sleep_calls.append(s)

    fetcher = ViledFetcher(run_id=1, pause_seconds=2.0)
    fetcher.fetch_one = lambda url: {"status": 200, "url": url, "html": "<html></html>"}
    stats: dict = {}
    fetcher.run_loop(["u1", "u2", "u3"], stats, sleep_fn=fake_sleep)
    # 3 URLs → 2 inter-fetch sleeps, both with the configured pause.
    assert sleep_calls == [2.0, 2.0]


def test_run_loop_no_sleep_for_single_url():
    sleep_calls: list[float] = []

    def fake_sleep(s):
        sleep_calls.append(s)

    fetcher = ViledFetcher(run_id=1, pause_seconds=2.0)
    fetcher.fetch_one = lambda url: {"status": 200, "url": url, "html": ""}
    fetcher.run_loop(["u1"], {}, sleep_fn=fake_sleep)
    assert sleep_calls == []  # single URL → zero sleeps


def test_run_loop_increments_fetch_count():
    fetcher = ViledFetcher(run_id=1)
    fetcher.fetch_one = lambda url: {"status": 200, "url": url, "html": ""}
    stats: dict = {}
    fetcher.run_loop(["u1", "u2"], stats, sleep_fn=lambda s: None)
    assert stats["fetch_count"] == 2


def test_run_loop_pauses_with_custom_pause_seconds():
    """Pause value comes from the constructor, not a hardcoded constant."""
    sleep_calls: list[float] = []
    fetcher = ViledFetcher(run_id=1, pause_seconds=0.5)
    fetcher.fetch_one = lambda url: {"status": 200, "url": url, "html": ""}
    fetcher.run_loop(
        ["u1", "u2", "u3"],
        {},
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    assert sleep_calls == [0.5, 0.5]


# ---------- ViledConfig loader ----------


def test_viled_config_from_real_pyproject():
    """Loads from the project's actual pyproject.toml — the operator-edited
    [tool.ga_crawler.crawl.viled] namespace.
    """
    cfg = ViledConfig.from_pyproject("pyproject.toml")
    assert cfg.sanity_gate_n == 100
    assert cfg.pause_seconds == 2.0
    assert cfg.concurrency == 1
    assert cfg.retry_attempts == 3
    assert len(cfg.catalog_urls) == 2
    assert cfg.catalog_urls == (
        "https://viled.kz/men/catalog/1310",
        "https://viled.kz/women/catalog/1310",
    )
    assert cfg.n_auto_suggest_factor == 0.7
    assert cfg.n_auto_suggest_after_runs == 4


def test_viled_config_defaults_when_file_missing(tmp_path: Path):
    cfg = ViledConfig.from_pyproject(tmp_path / "no_such.toml")
    assert cfg.sanity_gate_n == 100
    assert cfg.pause_seconds == 2.0
    assert cfg.concurrency == 1
    assert cfg.retry_attempts == 3
    assert len(cfg.catalog_urls) == 2  # falls back to dataclass defaults


def test_viled_config_partial_overrides(tmp_path: Path):
    """Operator-supplied subset of keys overrides defaults; the rest fall back."""
    toml = (
        "[tool.ga_crawler.crawl.viled]\n"
        "sanity_gate_n = 250\n"
        "pause_seconds = 3.5\n"
    )
    p = tmp_path / "pyproject.toml"
    p.write_text(toml, encoding="utf-8")
    cfg = ViledConfig.from_pyproject(p)
    assert cfg.sanity_gate_n == 250
    assert cfg.pause_seconds == 3.5
    assert cfg.concurrency == 1  # default
    assert cfg.retry_attempts == 3  # default


def test_viled_config_dataclass_is_frozen():
    """ViledConfig is frozen — accidental mutation should error."""
    import dataclasses

    cfg = ViledConfig()
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        cfg.sanity_gate_n = 999  # type: ignore[misc]
