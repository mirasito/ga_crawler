"""Full weekly run integration: viled → goldapple → Norm06 → finalize.

Plan 02-05 keystone test. Verifies run_weekly() composes the full pipeline
with a single `runs` row, both phase-stats merged atomically into the same
JSON column (Pitfall 6), the Norm06 ledger written exactly once, and DATA-05
lifecycle on every code path (success / phase-fail / crash).

The goldapple side is patched out at module-level (we only test the viled
phase + main_run lifecycle here; goldapple's own E2E lives in Phase 3).

Phase 4 amendments (Plan 04-05): 5 new tests pin the matcher composition step
that runs AFTER goldapple (or AFTER viled if goldapple was skipped). The
matcher's D-411 skip protocol means main_run does NOT pre-gate on upstream
status; it always invokes run_matcher_phase and lets the matcher decide
(skip / success / failed-by-P-gate).

Source: 02-RESEARCH.md §Validation Architecture row 23;
        02-CONTEXT.md D-211 Norm06 ownership; D-218 sequential gates;
        D-221 brand-pool flow; DATA-05 idempotent fail;
        04-CONTEXT.md D-411 (skip protocol), D-412 (CLI/composition shape).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session

from ga_crawler.runners.main_run import MainRunResult, run_weekly
from ga_crawler.runners.matcher_run import MatcherPhaseResult
from ga_crawler.storage.sqlite import Run, init_db, make_engine


# ---- Fixture: tmp_path repo-root with config + pyproject ----


@pytest.fixture
def setup_repo(tmp_path, brand_alias_yaml_fixture):
    """Plant a tmp_path/config/brand-aliases.yaml + pyproject.toml so
    run_weekly can find them. Returns the repo_root path + db_path."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "brand-aliases.yaml").write_text(
        Path(brand_alias_yaml_fixture).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """\
[project]
name = "ga-crawler-test"
version = "0.0.1"

[tool.ga_crawler.crawl.viled]
sanity_gate_n = 5
pause_seconds = 0.0
concurrency = 1
retry_attempts = 1
catalog_urls = [
    "https://viled.kz/men/catalog/1310",
    "https://viled.kz/women/catalog/1310",
]
n_auto_suggest_factor = 0.7
n_auto_suggest_after_runs = 4
""",
        encoding="utf-8",
    )
    return {
        "repo_root": tmp_path,
        "db_path": tmp_path / "prices.db",
        "pyproject_path": pyproject,
    }


# ---- Helpers ----


def _synthetic_pdp(*, sku_id: int = 1, brand: str = "Givenchy", name: str = "EDP 50ml"):
    payload = {
        "props": {
            "pageProps": {
                "item": {
                    "id": sku_id,
                    "name": name,
                    "brandName": brand,
                    "count": 5,
                    "purchaseType": "ONLINE",
                },
                "attributes": [
                    {"price": 10000, "realPrice": 10000, "currency": "₸"}
                ],
            }
        }
    }
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script></body></html>"
    )


def _sku_from_url(url: str) -> int:
    """Stable sku_id derivation from URL path so men/women catalogs don't collide."""
    # /item/men_3 → "men_3" → hash → positive int
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return abs(hash(tail)) % 10_000_000


class _FakeFetcher:
    def __init__(self, *, run_id=1, pause_seconds=0):
        self.run_id = run_id

    def run_loop(self, urls, stats, sleep_fn=None):
        records = []
        for i, url in enumerate(urls):
            stats["fetch_count"] = stats.get("fetch_count", 0) + 1
            records.append(
                {"status": 200, "url": url, "html": _synthetic_pdp(sku_id=_sku_from_url(url))}
            )
        return records


class _TooFewFetcher(_FakeFetcher):
    """Returns fewer records than N to force sanity-gate failure."""

    def run_loop(self, urls, stats, sleep_fn=None):
        # Only return 2 records regardless of input length.
        records = []
        for i, url in enumerate(urls[:2]):
            stats["fetch_count"] = stats.get("fetch_count", 0) + 1
            records.append(
                {"status": 200, "url": url, "html": _synthetic_pdp(sku_id=_sku_from_url(url))}
            )
        return records


def _fake_catalog(catalog_base, *, pause_seconds=0):
    """Returns 5 URLs per call so two catalogs yield 10 total.

    NOTE: The substring 'men' is in 'women' too — match the FULL gender path
    segment to disambiguate: '/men/' vs '/women/'.
    """
    if "/women/" in catalog_base:
        return [f"https://viled.kz/item/women_{i}" for i in range(5)]
    if "/men/" in catalog_base:
        return [f"https://viled.kz/item/men_{i}" for i in range(5)]
    return [f"https://viled.kz/item/other_{i}" for i in range(5)]


# ---- Tests ----


def test_full_run_cycle_viled_only(setup_repo):
    """Happy path: viled-only mode → success; Norm06 ledger written; run finalized."""
    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            viled_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )

    assert result.status == "success"
    assert result.viled_count == 10  # 5 men + 5 women
    assert result.norm06_path is not None
    assert result.norm06_path.exists()

    # Run row finalized
    engine = make_engine(setup_repo["db_path"])
    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    assert run is not None
    assert run.status == "success"
    assert run.finished_at is not None


def test_viled_failure_blocks_goldapple(setup_repo):
    """Viled phase fails sanity-N → goldapple phase NOT invoked.

    Override sanity_gate_n=100 via CLI-style param; provide TooFewFetcher
    that only returns 2 records.
    """
    goldapple_called = {"yes": False}

    async def fake_goldapple(*args, **kwargs):
        goldapple_called["yes"] = True
        # Should never reach here.
        return None

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch(
        "ga_crawler.runners.viled_run.ViledFetcher", _TooFewFetcher
    ), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            sanity_gate_n=100,  # Force failure
            pyproject_path=setup_repo["pyproject_path"],
            viled_only=False,
        )

    assert result.status == "failed"
    assert result.reason is not None
    assert "sanity_gate_n" in result.reason or "100" in result.reason
    assert goldapple_called["yes"] is False


def test_crash_finalizes_run(setup_repo):
    """DATA-05 invariant: uncaught Exception → run_writer.fail with stack-trace."""

    def crashing_catalog(*args, **kwargs):
        raise RuntimeError("simulated crash")

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=crashing_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            viled_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )

    # The crashing catalog is caught by viled_run's per-catalog try/except,
    # so it logs and continues — both endpoints fail → 0 URLs → 0 fetches →
    # sanity-N gate fires (count 0 < N=5) → run.status=failed.
    assert result.status == "failed"
    assert result.reason is not None
    # Run row is closed (not stuck in 'running')
    engine = make_engine(setup_repo["db_path"])
    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.fail_reason is not None


def test_data05_uncaught_exception_finalizes(setup_repo):
    """DATA-05: an uncaught exception OUTSIDE viled_run's try/except still closes the row.

    Patch the snapshot_writer.append to raise — that's an unhandled exception
    inside viled_run that propagates to main_run's try/except → fail() called.
    """
    from ga_crawler.storage.sqlite import SqliteSnapshotWriter

    original_append = SqliteSnapshotWriter.append

    def boom(self, run_id, retailer, products):
        raise RuntimeError("storage layer simulated crash")

    with patch.object(SqliteSnapshotWriter, "append", boom), patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            viled_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )

    # Restore original (defensive — tests should be isolated, but patch.object
    # reverts automatically on exit).
    assert SqliteSnapshotWriter.append is original_append or SqliteSnapshotWriter.append is not boom

    assert result.status == "failed"
    assert "RuntimeError" in (result.reason or "") or "storage layer" in (
        result.reason or ""
    )
    engine = make_engine(setup_repo["db_path"])
    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.finished_at is not None  # finalize set this


def test_norm06_ledger_written_on_success(setup_repo):
    """D-211: Norm06 ledger written exactly once on success path."""
    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            viled_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )

    assert result.status == "success"
    assert result.norm06_path is not None
    expected = (
        setup_repo["repo_root"]
        / ".planning"
        / "runs"
        / str(result.run_id)
        / "norm06-review.md"
    )
    assert result.norm06_path == expected
    assert expected.exists()
    content = expected.read_text(encoding="utf-8")
    assert f"Run {result.run_id}" in content
    # Empty unmatched lists → header written but no body rows
    assert "viled-unmatched" not in content
    assert "goldapple-new-slug" not in content


# ---- Phase 4 (Plan 04-05) — matcher composition ----


def _plant_matched_snapshots(engine, run_id):
    """Plant 1 viled + 1 goldapple snapshot with identical strict-key (brand/name/volume_norm)
    so the matcher computes match_count=1, denominator=1, rate=100.0.

    Bypasses the viled/goldapple fetchers — used by tests that stub out the
    crawler step and inject synthetic matched data directly so the matcher
    has something to JOIN on.
    """
    from ga_crawler.storage.sqlite import SqliteSnapshotWriter

    def _row(sku_id, retailer, price):
        return dict(
            sku_id=sku_id,
            url=f"https://{retailer}.kz/{sku_id}",
            name="EDP 50ml",
            brand="Givenchy",
            brand_norm="givenchy",
            name_norm="eau de parfum",
            volume_norm="(50, ml, 1)",
            volume_raw="50 ml",
            multipack_flag=False,
            parse_error_flag=False,
            current_price=price,
            was_price=None,
            currency="KZT",
            stock_state="IN_STOCK",
        )

    w = SqliteSnapshotWriter(engine, batch_size=10)
    w.append(run_id, "viled", [_row("V1", "viled", 10000)])
    w.append(run_id, "goldapple", [_row("G1", "goldapple", 12000)])


def test_run_weekly_composes_matcher_step(setup_repo):
    """Plan 04-05 Task 1, Test 1: matcher step is invoked AFTER goldapple phase
    and its stats are merged into runs.stats.

    Strategy: patch goldapple_run.run_goldapple_phase to a fake that plants
    matched snapshots (bypassing crawl) and returns a GoldappleRunResult-ish
    object with status='success'. Then matcher will compute count=1.
    """
    from ga_crawler.runners.goldapple_run import GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        # Plant matched snapshots so the matcher has overlapping rows to JOIN.
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        return GoldappleRunResult(
            status="success",
            run_id=run_id,
            goldapple_count=1,
            new_goldapple_slugs=[],
            unmatched_viled_brands=[],
            stats_delta={"goldapple.count": 1},
        )

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
            sanity_gate_p=1,  # accept any match_count >= 1
        )

    assert result.status == "success", result.reason
    assert result.match_count >= 1
    # stats_delta merged: viled.* + goldapple.* + match.* keys all present.
    assert any(k.startswith("match.") for k in result.stats_delta), (
        f"match.* keys missing from stats_delta: {sorted(result.stats_delta.keys())}"
    )
    assert "match.count" in result.stats_delta

    # runs.stats column contains match.count (proves patch_stats was called).
    engine = make_engine(setup_repo["db_path"])
    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    stats = json.loads(run.stats or "{}")
    assert "match.count" in stats
    assert stats["match.count"] == result.match_count


def test_run_weekly_matcher_gate_fail_returns_failed(setup_repo):
    """Plan 04-05 Task 1, Test 2: matcher P-gate trip → MainRunResult(status='failed').

    Plant snapshots that yield match_count=1; override sanity_gate_p=10
    via CLI param; expect status='failed' with reason starting with
    'match_count_below_threshold:'. matches table still has 1 row
    (audit-trail invariant — D-409).
    """
    from ga_crawler.runners.goldapple_run import GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        return GoldappleRunResult(
            status="success",
            run_id=run_id,
            goldapple_count=1,
            new_goldapple_slugs=[],
            unmatched_viled_brands=[],
            stats_delta={"goldapple.count": 1},
        )

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
            sanity_gate_p=10,  # 1 match < 10 → gate trips
        )

    assert result.status == "failed"
    assert result.reason is not None
    assert result.reason.startswith("match_count_below_threshold:"), result.reason
    assert result.match_count == 1  # matcher still computed before gate-fail

    # Audit-trail invariant — matches row persisted even though run failed.
    engine = make_engine(setup_repo["db_path"])
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            f"SELECT COUNT(*) FROM matches WHERE run_id={int(result.run_id)}"
        ).first()
    assert row[0] == 1, "matches row must persist on gate-fail (D-409)"

    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    assert run.status == "failed"


def test_run_weekly_matcher_skip_still_finalizes_success(setup_repo):
    """Plan 04-05 Task 1, Test 3: matcher status='skipped' → continue to
    Norm06 + finalize as success (skip is NOT a run-failure per D-411 + plan truths).

    Patch run_matcher_phase directly to return skipped — the actual upstream
    can succeed; we just exercise the composition-layer skip handling.
    """
    from ga_crawler.runners.goldapple_run import GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        # Don't plant — goldapple "succeeded" but matcher will be stubbed-skipped.
        return GoldappleRunResult(
            status="success",
            run_id=run_id,
            goldapple_count=0,
            new_goldapple_slugs=[],
            unmatched_viled_brands=[],
            stats_delta={"goldapple.count": 0},
        )

    def fake_matcher(*, run_id, engine, run_writer, threshold_p,
                     p_auto_suggest_factor, p_auto_suggest_after_runs):
        return MatcherPhaseResult(
            status="skipped",
            match_count=0,
            match_rate=0.0,
            reason="in_progress_upstream",
            stats_delta={"match.skipped_reason": "in_progress_upstream"},
        )

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ), patch(
        "ga_crawler.runners.main_run.run_matcher_phase",
        side_effect=fake_matcher,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
        )

    # Skip is NOT a run-failure; composition continues to Norm06 + finalize success.
    assert result.status == "success", result.reason
    assert result.match_count == 0
    # match.* keys present from stub matcher delta.
    assert "match.skipped_reason" in result.stats_delta
    assert result.norm06_path is not None
    assert result.norm06_path.exists()

    engine = make_engine(setup_repo["db_path"])
    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    assert run.status == "success"


def test_run_weekly_only_flag_skips_matcher(setup_repo):
    """Plan 04-05 Task 1, Test 4: viled_only OR goldapple_only → matcher NOT invoked.

    Matcher needs both retailer datasets; if either is skipped at the
    composition layer, matcher is bypassed (NOT just D-411 skip — actually
    not called at all). result.match_count=0; match.* keys NOT in stats.
    """
    matcher_called = {"yes": False}

    def fake_matcher(*args, **kwargs):
        matcher_called["yes"] = True
        return MatcherPhaseResult(status="success", match_count=99)

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.main_run.run_matcher_phase",
        side_effect=fake_matcher,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            viled_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )

    assert result.status == "success"
    assert result.match_count == 0
    assert matcher_called["yes"] is False, "matcher must not run in *_only mode"
    # match.* keys NOT in stats — matcher never ran.
    assert not any(
        k.startswith("match.") for k in result.stats_delta
    ), f"match.* keys should be absent: {sorted(result.stats_delta.keys())}"


def test_main_run_result_has_match_count_field():
    """Plan 04-05 Task 1, Test 5: MainRunResult dataclass exposes match_count + match_rate."""
    r = MainRunResult(status="success", run_id=1)
    assert r.match_count == 0
    assert r.match_rate == 0.0
    # Explicit construction with matcher fields:
    r2 = MainRunResult(status="success", run_id=2, match_count=42, match_rate=87.5)
    assert r2.match_count == 42
    assert r2.match_rate == 87.5
