"""Phase 3 orchestrator E2E tests with mocked Camoufox + Phase 2 protocol mocks.

Source plan: 03-06-PLAN.md Task 1 behavior (6 scenarios).

All tests inject:
  - sitemap_fetcher: pure-fn returning slug_map
  - fetcher_factory: callable returning FakeFetcher (mocks Camoufox lifecycle)
  - mock Phase 2 protocols (brand_alias, normalizer, snapshot_writer, run_writer)

Fake Camoufox: lifecycle is a no-op async context manager; fetch_one returns
canned smoke_records for the smoke probe phase, and run_loop returns
canned run_loop_records for the actual crawl.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ga_crawler.runners.goldapple_run import PhaseResult, run_goldapple_phase


# ---- Helpers ----


class FakeFetcher:
    """Mocks GoldappleFetcher: async context manager + run_loop returning canned records."""

    def __init__(self, run_id: int, *, headless: bool = True) -> None:
        self.run_id = run_id
        self.headless = headless
        self.profile_dir = Path("/tmp/fake-profile-" + str(run_id))
        self._page = MagicMock()
        self.smoke_records: list = []
        self.run_loop_records: list = []
        self.run_loop_stats_extras: dict = {}
        self._smoke_call_idx = 0

    async def __aenter__(self) -> "FakeFetcher":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def fetch_one(self, page, url):
        # Smoke probe iterates urls — return next canned smoke_record
        if self._smoke_call_idx < len(self.smoke_records):
            rec = dict(self.smoke_records[self._smoke_call_idx])
            self._smoke_call_idx += 1
            rec["url"] = url
            return rec
        return {"url": url, "status": 200, "block": False}

    async def run_loop(self, urls, stats, sleep_fn=None):
        # Return canned records; merge any extra stats
        stats.update(self.run_loop_stats_extras)
        stats["fetch_count"] = stats.get("fetch_count", 0) + len(urls)
        return self.run_loop_records[: len(urls)]


def make_fetcher_factory(fetcher: FakeFetcher):
    """Returns a callable that returns the same fetcher instance (one-shot, like tests)."""

    def factory(run_id: int, headless: bool = True):
        fetcher.run_id = run_id
        fetcher.headless = headless
        return fetcher

    return factory


def _real_pdp_smoke_record(html: str) -> dict:
    return {
        "status": 200,
        "html_size": len(html),
        "html": html,
        "title": "Givenchy ПАРФЮМЕРНАЯ ВОДА — купить ...",
        "block": False,
        "gate_cleared": True,
    }


def _gate_shell_smoke_record(html: str) -> dict:
    return {
        "status": 200,
        "html_size": len(html),
        "title": "Gold Apple — checking device",
        "block": True,
        "block_reason": "gate_shell_not_cleared",
        "gate_cleared": False,
    }


def _real_pdp_run_record(url: str, html: str) -> dict:
    return {
        "url": url,
        "status": 200,
        "html_size": len(html),
        "html": html,
        "title": "Givenchy ПАРФЮМЕРНАЯ ВОДА — купить ...",
        "block": False,
        "gate_cleared": True,
    }


# ---- Tests ----


@pytest.mark.asyncio
async def test_e2e_happy_path(
    tmp_path: Path,
    goldapple_pdp_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """All steps succeed: 2 URLs in matched, both parse, snapshot written, gate passes."""
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_real_pdp_smoke_record(goldapple_pdp_html)] * 3
    fetcher.run_loop_records = [
        _real_pdp_run_record("https://goldapple.kz/100-givenchy", goldapple_pdp_html),
        _real_pdp_run_record("https://goldapple.kz/200-givenchy", goldapple_pdp_html),
    ]

    def fake_sitemap():
        return {
            "givenchy": [
                "https://goldapple.kz/100-givenchy",
                "https://goldapple.kz/200-givenchy",
            ]
        }

    mock_brand_alias.lookup.side_effect = lambda b: ["Givenchy"] if b == "givenchy" else [b]

    result = await run_goldapple_phase(
        run_id=42,
        viled_brands=["givenchy"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=1,
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=fake_sitemap,
    )

    assert result.status == "success"
    assert result.goldapple_count == 2
    mock_snapshot_writer.append.assert_called_once()
    args = mock_snapshot_writer.append.call_args.args
    assert args[0] == 42  # run_id
    assert args[1] == "goldapple"  # retailer
    assert len(args[2]) == 2  # products
    mock_run_writer.fail.assert_not_called()
    mock_run_writer.patch_stats.assert_called_once()
    delta = mock_run_writer.patch_stats.call_args.args[1]
    assert delta["goldapple.fetch_count"] >= 2
    assert delta["goldapple.smoke_pass"] is True


@pytest.mark.asyncio
async def test_e2e_smoke_fail_aborts(
    tmp_path: Path,
    gate_shell_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """Smoke fails -> run_writer.fail called; snapshot not written."""
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_gate_shell_smoke_record(gate_shell_html)] * 3

    def fake_sitemap():
        return {"givenchy": ["https://goldapple.kz/100-givenchy"]}

    result = await run_goldapple_phase(
        run_id=42,
        viled_brands=["givenchy"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=1,
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=fake_sitemap,
    )

    assert result.status == "failed"
    assert result.reason == "smoke_probe_failed"
    mock_run_writer.fail.assert_called_once()
    fail_args = mock_run_writer.fail.call_args
    assert "smoke" in fail_args.args[1].lower()
    mock_snapshot_writer.append.assert_not_called()


@pytest.mark.asyncio
async def test_e2e_final_gate_fail_run_to_completion(
    tmp_path: Path,
    goldapple_pdp_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """Sitemap returns 1 URL; M=10; run-to-completion -> snapshot still written, run failed."""
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_real_pdp_smoke_record(goldapple_pdp_html)] * 3
    fetcher.run_loop_records = [
        _real_pdp_run_record("https://goldapple.kz/100-givenchy", goldapple_pdp_html),
    ]

    def fake_sitemap():
        return {"givenchy": ["https://goldapple.kz/100-givenchy"]}

    result = await run_goldapple_phase(
        run_id=42,
        viled_brands=["givenchy"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=10,  # 1 < 10 -> fails final gate
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=fake_sitemap,
    )

    assert result.status == "failed"
    assert "goldapple_count" in result.reason
    assert "M=10" in result.reason
    # D-309: run-to-completion -> snapshot append still happened
    mock_snapshot_writer.append.assert_called_once()
    mock_run_writer.fail.assert_called_once()
    mock_run_writer.patch_stats.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_norm06_forward_counts_unmatched(
    tmp_path: Path,
    goldapple_pdp_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """tom_ford brand absent from sitemap -> unmatched_viled_brands=1."""
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_real_pdp_smoke_record(goldapple_pdp_html)] * 3
    fetcher.run_loop_records = [
        _real_pdp_run_record("https://goldapple.kz/100-givenchy", goldapple_pdp_html),
    ]

    def fake_sitemap():
        return {"givenchy": ["https://goldapple.kz/100-givenchy"]}

    mock_brand_alias.lookup.side_effect = (
        lambda b: ["Givenchy"] if b == "givenchy" else ["Tom Ford"]
    )

    result = await run_goldapple_phase(
        run_id=42,
        viled_brands=["givenchy", "tom_ford"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=1,
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=fake_sitemap,
    )

    assert result.unmatched_viled_brands == ["tom_ford"]
    delta = mock_run_writer.patch_stats.call_args.args[1]
    assert delta["goldapple.unmatched_viled_brands"] == 1


@pytest.mark.asyncio
async def test_e2e_atomic_stats_merge_one_call(
    tmp_path: Path,
    goldapple_pdp_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """Pitfall 6: patch_stats called EXACTLY ONCE at end of phase (not per-fetch)."""
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_real_pdp_smoke_record(goldapple_pdp_html)] * 3
    fetcher.run_loop_records = [
        _real_pdp_run_record(f"https://goldapple.kz/{i}-givenchy", goldapple_pdp_html)
        for i in range(5)
    ]

    def fake_sitemap():
        return {
            "givenchy": [
                f"https://goldapple.kz/{i}-givenchy" for i in range(5)
            ]
        }

    await run_goldapple_phase(
        run_id=42,
        viled_brands=["givenchy"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=1,
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=fake_sitemap,
    )

    assert mock_run_writer.patch_stats.call_count == 1


@pytest.mark.asyncio
async def test_e2e_brand_intersect_against_realistic_sitemap_shape(
    tmp_path: Path,
    goldapple_pdp_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """Truth 1 closure regression — orchestrator level.

    Injects a 6-entry slug_map keyed by FULL product-slugs (mimics real 45,490-slug
    sitemap shape from live run-42). Asserts orchestrator's Step 3.5 builds a
    brand_bucket via index_by_brand_token + known_brand_tokens whitelist so that
    'givenchy', 'jo_malone_london', and 'tom_ford' all match — none of them
    appear in unmatched_viled_brands.
    """
    realistic_slug_map = {
        "givenchy-pour-homme-blue-label": ["https://goldapple.kz/100-givenchy-pour-homme-blue-label"],
        "givenchy-irresistible-eau-de-parfum": ["https://goldapple.kz/200-givenchy-irresistible-eau-de-parfum"],
        "jo-malone-london-wood-sage-and-sea-salt": ["https://goldapple.kz/300-jo-malone-london-wood-sage-and-sea-salt"],
        "tom-ford-noir": ["https://goldapple.kz/400-tom-ford-noir"],
        "category-listing-perfume": ["https://goldapple.kz/910-category-listing-perfume"],
        "estee-lauder-advanced-night-repair": ["https://goldapple.kz/500-estee-lauder-advanced-night-repair"],
    }
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_real_pdp_smoke_record(goldapple_pdp_html)] * 3
    # run_loop_records mirror the matched URLs (exact count is unimportant — we just
    # need at least one record to clear M=1 and reach final-gate success)
    fetcher.run_loop_records = [
        _real_pdp_run_record(
            "https://goldapple.kz/100-givenchy-pour-homme-blue-label", goldapple_pdp_html
        ),
        _real_pdp_run_record(
            "https://goldapple.kz/200-givenchy-irresistible-eau-de-parfum", goldapple_pdp_html
        ),
        _real_pdp_run_record(
            "https://goldapple.kz/300-jo-malone-london-wood-sage-and-sea-salt", goldapple_pdp_html
        ),
        _real_pdp_run_record(
            "https://goldapple.kz/400-tom-ford-noir", goldapple_pdp_html
        ),
    ]

    def alias_lookup(b: str) -> list[str]:
        return {
            "givenchy": ["Givenchy"],
            "jo_malone_london": ["Jo Malone London"],
            "tom_ford": ["Tom Ford"],
        }.get(b, [b])

    mock_brand_alias.lookup.side_effect = alias_lookup

    result = await run_goldapple_phase(
        run_id=99,
        viled_brands=["givenchy", "jo_malone_london", "tom_ford"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=1,
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=lambda: realistic_slug_map,
    )

    # Truth 1 closure: NONE of the 3 viled brands fell to unmatched
    assert "givenchy" not in result.unmatched_viled_brands
    assert "jo_malone_london" not in result.unmatched_viled_brands
    assert "tom_ford" not in result.unmatched_viled_brands
    # All 3 brands matched; unmatched count is 0
    delta = mock_run_writer.patch_stats.call_args.args[1]
    assert delta["goldapple.unmatched_viled_brands"] == 0
    # category-listing-perfume slug was orphaned (not viled-known) — proves orchestrator
    # only crawls operator-known brand prefixes
    assert result.status == "success"


@pytest.mark.asyncio
async def test_e2e_auto_suggest_when_history_present(
    tmp_path: Path,
    goldapple_pdp_html: str,
    mock_brand_alias,
    mock_normalizer,
    mock_snapshot_writer,
    mock_run_writer,
) -> None:
    """4+ prior runs in history -> auto_suggest_m emitted in delta."""
    fetcher = FakeFetcher(run_id=1)
    fetcher.smoke_records = [_real_pdp_smoke_record(goldapple_pdp_html)] * 3
    fetcher.run_loop_records = [
        _real_pdp_run_record("https://goldapple.kz/100-givenchy", goldapple_pdp_html),
    ]

    # Mock 4 prior runs returning fetch_count=2000 each. Override conftest default.
    def fake_get_stats(rid):
        return {"goldapple.fetch_count": 2000}

    mock_run_writer.get_stats.side_effect = fake_get_stats

    def fake_sitemap():
        return {"givenchy": ["https://goldapple.kz/100-givenchy"]}

    await run_goldapple_phase(
        run_id=42,
        viled_brands=["givenchy"],
        repo_root=tmp_path,
        brand_alias=mock_brand_alias,
        normalizer=mock_normalizer,
        snapshot_writer=mock_snapshot_writer,
        run_writer=mock_run_writer,
        M=1,
        fetcher_factory=make_fetcher_factory(fetcher),
        sitemap_fetcher=fake_sitemap,
    )

    delta = mock_run_writer.patch_stats.call_args.args[1]
    # 4 prior runs each fetch_count=2000; current=1; combined history
    # [2000,2000,2000,2000,1] last_4=[2000,2000,2000,1] median=2000 -> int(0.7*2000)=1400
    assert "goldapple.auto_suggest_m" in delta
    assert delta["goldapple.auto_suggest_m"] == 1400
