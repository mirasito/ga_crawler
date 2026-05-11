"""End-to-end fetcher tests with mocked Camoufox (no live network).

Mocks AsyncCamoufox via monkeypatch: replace camoufox.async_api.AsyncCamoufox
with a fake context manager that yields a mock browser whose .pages[0] is a
mock page. Tests inject canned responses for page.goto/title/content.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ga_crawler.fetchers.goldapple import (
    GoldappleFetcher,
    PAUSE_RANGE,
    WARMUP_NETWORKIDLE_TIMEOUT_MS,
    WARMUP_URL,
)


class FakePage:
    """Minimal Camoufox-like page; tests configure its responses."""

    def __init__(self):
        self.goto = AsyncMock()
        self.title = AsyncMock(return_value="")
        self.content = AsyncMock(return_value="")
        self.wait_for_load_state = AsyncMock()
        self.wait_for_timeout = AsyncMock()


class FakeBrowser:
    def __init__(self, page: FakePage):
        self.pages = [page]

    async def new_page(self):
        return self.pages[0]


class FakeCamoufoxCM:
    """Replaces AsyncCamoufox(...) — async context manager returning FakeBrowser."""

    def __init__(self, *args, **kwargs):
        self._page = FakePage()
        self._browser = FakeBrowser(self._page)
        self.kwargs = kwargs  # tests inspect to verify locked kwargs passed

    async def __aenter__(self):
        return self._browser

    async def __aexit__(self, *exc):
        return None


@pytest.fixture
def fake_camoufox(monkeypatch):
    """Patch AsyncCamoufox in fetchers.goldapple namespace.

    Returns the CM class so tests can grab its instance via .last_instance after enter.
    """
    instances: list[FakeCamoufoxCM] = []

    def factory(*args, **kwargs):
        cm = FakeCamoufoxCM(*args, **kwargs)
        instances.append(cm)
        return cm

    # Camoufox is imported lazily inside __aenter__; patch at the import site.
    import camoufox.async_api as cam
    monkeypatch.setattr(cam, "AsyncCamoufox", factory)
    return instances


@pytest.mark.asyncio
async def test_lifecycle_creates_and_cleans_profile_dir(fake_camoufox) -> None:
    """D-311 + Pitfall 7: profile dir exists after __init__, gone after __aexit__."""
    fetcher = GoldappleFetcher(run_id=42, headless=True)
    profile_path = fetcher.profile_dir
    assert profile_path.exists()
    assert profile_path.name.startswith("camoufox-run-42-")

    async with fetcher:
        # Inside context manager — profile dir still exists
        assert profile_path.exists()

    # After __aexit__ — gone
    assert not profile_path.exists()


@pytest.mark.asyncio
async def test_lifecycle_cleans_profile_dir_on_exception(fake_camoufox) -> None:
    """Pitfall 7: profile dir cleaned even when caller raises inside async with."""
    fetcher = GoldappleFetcher(run_id=99)
    profile_path = fetcher.profile_dir
    assert profile_path.exists()

    with pytest.raises(RuntimeError, match="caller boom"):
        async with fetcher:
            raise RuntimeError("caller boom")

    assert not profile_path.exists()


@pytest.mark.asyncio
async def test_locked_camoufox_kwargs(fake_camoufox) -> None:
    """SKILL operational constants: geoip=True, locale=[ru-RU,kk-KZ,en-US], humanize=True, persistent_context=True."""
    async with GoldappleFetcher(run_id=1) as fetcher:
        cm = fake_camoufox[-1]
        assert cm.kwargs["geoip"] is True
        assert cm.kwargs["locale"] == ["ru-RU", "kk-KZ", "en-US"]
        assert cm.kwargs["humanize"] is True
        assert cm.kwargs["persistent_context"] is True
        assert cm.kwargs["user_data_dir"] == str(fetcher.profile_dir)


@pytest.mark.asyncio
async def test_fetch_one_happy_path(fake_camoufox, goldapple_pdp_html: str) -> None:
    """Real PDP HTML returned → block=False, html captured, title set, gate_cleared=True."""
    async with GoldappleFetcher(run_id=1) as fetcher:
        page: FakePage = fetcher._page
        resp = MagicMock(status=200)
        page.goto = AsyncMock(return_value=resp)
        page.title = AsyncMock(return_value="Givenchy ПАРФЮМЕРНАЯ ВОДА — купить ...")
        page.content = AsyncMock(return_value=goldapple_pdp_html)

        rec = await fetcher.fetch_one(page, "https://goldapple.kz/100-test")

    assert rec["status"] == 200
    assert rec["block"] is False
    assert rec["gate_cleared"] is True
    assert rec["html_size"] == len(goldapple_pdp_html)
    assert rec["html"] == goldapple_pdp_html
    assert "Givenchy" in rec["title"]


@pytest.mark.asyncio
async def test_fetch_one_gate_shell(fake_camoufox, gate_shell_html: str) -> None:
    """Gate-shell: title='checking device' + size<30KB → block=True, reason=gate_shell_not_cleared."""
    async with GoldappleFetcher(run_id=1) as fetcher:
        page = fetcher._page
        resp = MagicMock(status=200)
        page.goto = AsyncMock(return_value=resp)
        page.title = AsyncMock(return_value="Gold Apple — checking device")
        page.content = AsyncMock(return_value=gate_shell_html)

        rec = await fetcher.fetch_one(page, "https://goldapple.kz/100-test")

    assert rec["block"] is True
    assert rec["block_reason"] == "gate_shell_not_cleared"
    assert rec["gate_cleared"] is False
    assert rec["html_size"] < 30_000
    assert "html" not in rec


@pytest.mark.asyncio
async def test_fetch_one_http_404(fake_camoufox) -> None:
    """404 → block=True, reason='http_404'."""
    async with GoldappleFetcher(run_id=1) as fetcher:
        page = fetcher._page
        resp = MagicMock(status=404)
        page.goto = AsyncMock(return_value=resp)
        page.title = AsyncMock(return_value="Page not found")
        page.content = AsyncMock(return_value="<html><body>404</body></html>")

        rec = await fetcher.fetch_one(page, "https://goldapple.kz/100-deleted")

    assert rec["status"] == 404
    assert rec["block"] is True
    assert rec["block_reason"] == "http_404"


@pytest.mark.asyncio
async def test_fetch_one_exception_caught(fake_camoufox) -> None:
    """Uncaught error during page.title → block=True, reason='exception', error captured."""
    async with GoldappleFetcher(run_id=1) as fetcher:
        page = fetcher._page
        resp = MagicMock(status=200)
        page.goto = AsyncMock(return_value=resp)
        page.title = AsyncMock(side_effect=RuntimeError("page.title broke"))
        page.content = AsyncMock(return_value="<html></html>")

        rec = await fetcher.fetch_one(page, "https://goldapple.kz/100-x")

    assert rec["block"] is True
    assert rec["block_reason"] == "exception"
    assert rec["error"] is not None
    assert "RuntimeError" in rec["error"]


@pytest.mark.asyncio
async def test_run_loop_sequential_pacing(fake_camoufox, goldapple_pdp_html: str) -> None:
    """3 URLs: 2 sleep calls in [3.0, 5.0); records returned in order."""
    sleep_calls: list[float] = []

    async def fake_sleep(t: float):
        sleep_calls.append(t)

    async with GoldappleFetcher(run_id=1) as fetcher:
        page = fetcher._page
        resp = MagicMock(status=200)
        page.goto = AsyncMock(return_value=resp)
        page.title = AsyncMock(return_value="Givenchy")
        page.content = AsyncMock(return_value=goldapple_pdp_html)

        urls = [f"https://goldapple.kz/{i}-x" for i in range(3)]
        stats: dict = {}
        records = await fetcher.run_loop(urls, stats, sleep_fn=fake_sleep)

    assert len(records) == 3
    assert len(sleep_calls) == 2  # between fetches; not after last
    for t in sleep_calls:
        assert PAUSE_RANGE[0] <= t < PAUSE_RANGE[1]
    assert stats["fetch_count"] == 3
    assert stats.get("fetch_failures", 0) == 0


@pytest.mark.asyncio
async def test_run_loop_isolation_keeps_running(fake_camoufox, goldapple_pdp_html: str) -> None:
    """One fetch_one raises uncaught → captured by isolation; remaining 4 succeed."""
    call_count = {"i": 0}

    async def flaky_goto(*args, **kwargs):
        call_count["i"] += 1
        if call_count["i"] == 3:
            raise ValueError("transient")
        return MagicMock(status=200)

    async def no_sleep(t):
        pass

    async with GoldappleFetcher(run_id=1) as fetcher:
        page = fetcher._page
        page.goto = AsyncMock(side_effect=flaky_goto)
        page.title = AsyncMock(return_value="Givenchy")
        page.content = AsyncMock(return_value=goldapple_pdp_html)

        urls = [f"https://goldapple.kz/{i}-x" for i in range(5)]
        stats: dict = {}
        records = await fetcher.run_loop(urls, stats, sleep_fn=no_sleep)

    # All 5 fetch_one calls return a record (either healthy or block=True);
    # fetch_one_isolated returns the record, not None, because fetch_one
    # itself catches the error and packages into block=True. tenacity already
    # tried 3x — call_count for that one URL grew. Net: stats has fetch_failures
    # only when fetch_callable RAISES, not when it sets block=True.
    assert stats["fetch_count"] == 5
    # tenacity reraised after 3 attempts → fetch_one wraps in block=True; not in fetch_failures.
    assert len(records) == 5


@pytest.mark.asyncio
async def test_warmup_navigation_called_once_in_aenter(fake_camoufox) -> None:
    """Operational Finding #1 fix: __aenter__ navigates to WARMUP_URL exactly
    once with networkidle + WARMUP_NETWORKIDLE_TIMEOUT_MS before returning."""
    async with GoldappleFetcher(run_id=1) as fetcher:
        # Inspect goto call history during __aenter__ (no fetch_one yet)
        calls = fetcher._page.goto.call_args_list
        assert len(calls) == 1, f"expected exactly 1 goto in __aenter__, got {len(calls)}"
        # First positional arg is WARMUP_URL
        assert calls[0].args[0] == WARMUP_URL
        # Verify kwargs
        assert calls[0].kwargs.get("wait_until") == "networkidle"
        assert calls[0].kwargs.get("timeout") == WARMUP_NETWORKIDLE_TIMEOUT_MS


@pytest.mark.asyncio
async def test_camoufox_boot_failure_cleans_profile_dir() -> None:
    """Pitfall 7 + D-311: Camoufox-BOOT failure (before page capture) must
    still clean up tmp profile dir before re-raising.

    Warm-up goto failure is handled separately in
    test_warmup_goto_failure_does_not_abort_boot (warm-up is best-effort
    by design — D-314).
    """
    fetcher = GoldappleFetcher(run_id=77)
    profile_path = fetcher.profile_dir
    assert profile_path.exists()

    import camoufox.async_api as cam

    class FailingBootCM:
        """Camoufox CM whose __aenter__ raises BEFORE the page is captured."""

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise RuntimeError("camoufox boot boom")

        async def __aexit__(self, *exc):
            return None

    import pytest as _pytest

    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr(cam, "AsyncCamoufox", FailingBootCM)
    try:
        with _pytest.raises(RuntimeError, match="camoufox boot boom"):
            async with fetcher:
                pass  # unreachable — CM's __aenter__ raises

        # After exception: profile dir must be cleaned up (Pitfall 7).
        assert not profile_path.exists(), (
            "Camoufox-boot failure must trigger shutil.rmtree on profile_dir "
            "(Pitfall 7 / D-311 invariant)"
        )
    finally:
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_warmup_goto_failure_does_not_abort_boot() -> None:
    """D-314: warm-up `goto` is best-effort. A networkidle stall (or any
    Exception from goto) MUST NOT abort __aenter__ — the unconditional
    WARMUP_SETTLE_SECONDS sleep still runs, the boot completes, and the
    profile dir is NOT cleaned up by warm-up failure (cleanup happens
    only on Camoufox-boot failure OR on normal __aexit__).
    """
    from unittest.mock import AsyncMock as _AM

    import camoufox.async_api as cam

    sleep_calls: list[float] = []

    class StallingPage:
        def __init__(self):
            self.goto = _AM(side_effect=RuntimeError("networkidle stall"))
            self.title = _AM(return_value="")
            self.content = _AM(return_value="")
            self.wait_for_load_state = _AM()
            self.wait_for_timeout = _AM()

    class StallingBrowser:
        def __init__(self, page):
            self.pages = [page]

        async def new_page(self):
            return self.pages[0]

    class StallingCM:
        def __init__(self, *args, **kwargs):
            self._page = StallingPage()
            self._browser = StallingBrowser(self._page)

        async def __aenter__(self):
            return self._browser

        async def __aexit__(self, *exc):
            return None

    import pytest as _pytest

    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr(cam, "AsyncCamoufox", StallingCM)

    # Record asyncio.sleep calls inside the fetcher module so we can verify
    # the unconditional WARMUP_SETTLE_SECONDS sleep ran AFTER the failing goto.
    import asyncio as _asyncio

    import ga_crawler.fetchers.goldapple as fetcher_mod

    real_sleep = _asyncio.sleep

    async def recording_sleep(dt):
        sleep_calls.append(dt)
        await real_sleep(0)

    monkeypatch.setattr(fetcher_mod.asyncio, "sleep", recording_sleep)

    try:
        fetcher = GoldappleFetcher(run_id=314)
        profile_path = fetcher.profile_dir
        assert profile_path.exists()

        # __aenter__ must NOT raise — warm-up failure is best-effort.
        async with fetcher:
            # Inside the block: profile dir still exists (warm-up failure did
            # NOT trigger cleanup; cleanup only happens on Camoufox-boot fail
            # or on normal __aexit__).
            assert profile_path.exists(), (
                "profile dir cleaned up despite best-effort warm-up — regression"
            )

        # After clean __aexit__, profile dir gets cleaned up normally.
        assert not profile_path.exists(), "__aexit__ should have cleaned up profile_dir"

        # Settle sleep STILL ran with WARMUP_SETTLE_SECONDS even though goto raised.
        from ga_crawler.fetchers.goldapple import WARMUP_SETTLE_SECONDS

        assert WARMUP_SETTLE_SECONDS in sleep_calls, (
            f"warm-up settle sleep (WARMUP_SETTLE_SECONDS={WARMUP_SETTLE_SECONDS}) "
            f"was NOT called after the failing goto; recorded sleeps: {sleep_calls}"
        )
    finally:
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_run_loop_gate_shell_count(fake_camoufox, gate_shell_html: str) -> None:
    """Gate-shell records → stats['gate_shell_count'] increments."""
    async def no_sleep(t):
        pass

    async with GoldappleFetcher(run_id=1) as fetcher:
        page = fetcher._page
        resp = MagicMock(status=200)
        page.goto = AsyncMock(return_value=resp)
        page.title = AsyncMock(return_value="Gold Apple — checking device")
        page.content = AsyncMock(return_value=gate_shell_html)

        urls = [f"https://goldapple.kz/{i}-x" for i in range(2)]
        stats: dict = {}
        await fetcher.run_loop(urls, stats, sleep_fn=no_sleep)

    assert stats["gate_shell_count"] == 2
