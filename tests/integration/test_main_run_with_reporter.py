"""Integration tests for Plan 05-05 main_run composition with reporter.

Extends tests/integration/test_main_run_e2e.py precedent. Real engine,
mocked goldapple phase (Camoufox is expensive), real matcher + reporter.

Source: 05-VALIDATION.md Task 5-05-01 (composition) + 5-05-03 (DATA-05 reporter
exception path); 05-CONTEXT.md D-511 composition order.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text as _text
from sqlmodel import Session

from ga_crawler.runners.main_run import MainRunResult, run_weekly
from ga_crawler.runners.matcher_run import MatcherPhaseResult
from ga_crawler.storage.sqlite import Run, init_db, make_engine


# ---- Test helpers (mirror test_main_run_e2e patterns) ----


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
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return abs(hash(tail)) % 10_000_000


class _FakeFetcher:
    def __init__(self, *, run_id=1, pause_seconds=0):
        self.run_id = run_id

    def run_loop(self, urls, stats, sleep_fn=None):
        records = []
        for url in urls:
            stats["fetch_count"] = stats.get("fetch_count", 0) + 1
            records.append(
                {"status": 200, "url": url, "html": _synthetic_pdp(sku_id=_sku_from_url(url))}
            )
        return records


def _fake_catalog(catalog_base, *, pause_seconds=0):
    if "/women/" in catalog_base:
        return [f"https://viled.kz/item/women_{i}" for i in range(5)]
    if "/men/" in catalog_base:
        return [f"https://viled.kz/item/men_{i}" for i in range(5)]
    return [f"https://viled.kz/item/other_{i}" for i in range(5)]


def _plant_matched_snapshots(engine, run_id):
    """Plant 1 viled + 1 goldapple snapshot with identical strict-key so
    matcher computes match_count=1, denominator=1, rate=100.0.
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


@pytest.fixture
def setup_repo(tmp_path, brand_alias_yaml_fixture):
    """Plant tmp_path/config/brand-aliases.yaml + pyproject.toml so
    run_weekly can find them. Returns the repo_root path + db_path + pyproject.
    """
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

[tool.ga_crawler.report]
output_dir = "reports"
size_limit_mb = 45
top_n_deltas = 3
timezone = "Asia/Almaty"
""",
        encoding="utf-8",
    )
    return {
        "repo_root": tmp_path,
        "db_path": tmp_path / "prices.db",
        "pyproject_path": pyproject,
    }


# ---- Tests ----


def test_run_weekly_invokes_reporter_after_matcher(setup_repo):
    """Plan 05-05 Test 1: full pipeline → reporter step writes xlsx + MainRunResult
    fields populated with all 4 stats namespaces present (viled/goldapple/match/report).
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        return GoldappleRunResult(
            status="success",
            goldapple_count=1,
            stats_delta={"goldapple.count": 1},
            unmatched_viled_brands=[],
            new_goldapple_slugs=[],
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
    # Plan 05-05 D-514 new MainRunResult fields populated
    assert result.xlsx_path is not None
    assert result.xlsx_path.endswith(".xlsx")
    assert result.xlsx_size_bytes > 0
    assert result.summary_text != ""
    assert result.size_guard_passed is True

    # xlsx file exists on disk under repo_root
    xlsx_full = setup_repo["repo_root"] / result.xlsx_path
    assert xlsx_full.exists(), f"xlsx missing at {xlsx_full}"
    assert xlsx_full.stat().st_size == result.xlsx_size_bytes

    # All 4 stats namespaces coexist in MainRunResult.stats_delta (Pitfall 6 atomic merge)
    keys = result.stats_delta.keys()
    has_viled = any(k.startswith("viled.") for k in keys)
    has_gold = any(k.startswith("goldapple.") for k in keys)
    has_match = any(k.startswith("match.") for k in keys)
    has_report = any(k.startswith("report.") for k in keys)
    assert has_viled and has_gold and has_match and has_report, (
        f"missing namespaces: viled={has_viled} gold={has_gold} "
        f"match={has_match} report={has_report}; keys={sorted(keys)}"
    )


def test_run_weekly_viled_only_skips_reporter(setup_repo):
    """Plan 05-05 Test 2: viled_only=True → matcher + reporter NOT invoked → xlsx_path is None."""
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
    assert result.xlsx_path is None  # reporter NOT invoked
    assert result.xlsx_size_bytes == 0
    assert result.summary_text == ""
    assert result.size_guard_passed is True  # default for no-reporter path
    # No reports/ written
    reports_dir = setup_repo["repo_root"] / "reports"
    assert not reports_dir.exists() or not any(reports_dir.glob("*.xlsx"))
    # No report.* keys in stats_delta
    assert not any(
        k.startswith("report.") for k in result.stats_delta
    ), f"report.* keys should be absent: {sorted(result.stats_delta.keys())}"


def test_run_weekly_goldapple_only_skips_reporter(setup_repo):
    """Plan 05-05 Test 3: goldapple_only=True → matcher + reporter NOT invoked."""
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        return GoldappleRunResult(
            status="success",
            goldapple_count=0,
            stats_delta={"goldapple.count": 0},
            unmatched_viled_brands=[],
            new_goldapple_slugs=[],
        )

    with patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            goldapple_only=True,
            pyproject_path=setup_repo["pyproject_path"],
        )

    assert result.status == "success"
    assert result.xlsx_path is None  # reporter NOT invoked
    assert not any(k.startswith("report.") for k in result.stats_delta)


def test_run_weekly_matcher_failed_skips_reporter(setup_repo):
    """Plan 05-05 Test 4: matcher gate-fail (status='failed') → reporter NOT invoked.

    Plant 1 match, set sanity_gate_p=10 → matcher.fail; main_run returns
    status='failed'; xlsx_path is None.
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        return GoldappleRunResult(
            status="success",
            goldapple_count=1,
            stats_delta={"goldapple.count": 1},
            unmatched_viled_brands=[],
            new_goldapple_slugs=[],
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
    assert result.xlsx_path is None  # reporter NOT invoked on matcher-fail early-return
    assert result.xlsx_size_bytes == 0
    # match.* keys present (matcher ran before failing), report.* absent
    assert any(k.startswith("match.") for k in result.stats_delta)
    assert not any(k.startswith("report.") for k in result.stats_delta), (
        f"report.* keys MUST be absent on matcher-fail path: "
        f"{sorted(result.stats_delta.keys())}"
    )


def test_run_weekly_matcher_skipped_path_does_not_invoke_reporter(setup_repo):
    """Plan 05-05 Test 5: matcher 'skipped' → reporter NOT invoked (gated explicitly
    on m_result.status == 'success'); run still finalizes as success.
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        return GoldappleRunResult(
            status="success",
            goldapple_count=0,
            stats_delta={"goldapple.count": 0},
            unmatched_viled_brands=[],
            new_goldapple_slugs=[],
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

    assert result.status == "success"
    assert result.xlsx_path is None  # reporter NOT invoked when matcher skipped
    assert not any(k.startswith("report.") for k in result.stats_delta), (
        f"report.* MUST be absent when matcher skipped: "
        f"{sorted(result.stats_delta.keys())}"
    )


def test_data05_reporter_exception_finalizes(setup_repo):
    """Plan 05-05 Test 6 — DATA-05 invariant: uncaught reporter exception →
    run_writer.fail + status='failed' in DB.

    Plan 02-05 outer try/except in run_weekly catches; reporter does NOT own
    its try/except (Plan 05-04 invariant).
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        return GoldappleRunResult(
            status="success",
            goldapple_count=1,
            stats_delta={"goldapple.count": 1},
            unmatched_viled_brands=[],
            new_goldapple_slugs=[],
        )

    def _explode(**kw):
        raise RuntimeError("synthetic_reporter_explosion")

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ), patch(
        "ga_crawler.runners.main_run.run_reporter_phase",
        side_effect=_explode,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
            sanity_gate_p=1,
        )

    # DATA-05: outer try/except catches → run_writer.fail → status='failed'
    assert result.status == "failed"
    assert "synthetic_reporter_explosion" in (result.reason or "")
    # xlsx_path defaults (None / 0 / "" / True) since reporter never returned
    assert result.xlsx_path is None
    assert result.xlsx_size_bytes == 0
    assert result.summary_text == ""
    assert result.size_guard_passed is True

    # DB confirms runs.status='failed' (DATA-05 canary)
    engine = make_engine(setup_repo["db_path"])
    with engine.connect() as conn:
        row = conn.execute(
            _text("SELECT status FROM runs WHERE run_id=:rid"),
            {"rid": result.run_id},
        ).first()
    assert row is not None
    assert row[0] == "failed", f"DATA-05 violation: status={row[0]!r}"


def test_main_run_result_has_reporter_fields():
    """Plan 05-05 Test 7: MainRunResult dataclass exposes the 4 new D-514 reporter fields
    with correct default values.
    """
    r = MainRunResult(status="success", run_id=1)
    assert r.xlsx_path is None
    assert r.xlsx_size_bytes == 0
    assert r.summary_text == ""
    assert r.size_guard_passed is True
    # Explicit construction with reporter fields:
    r2 = MainRunResult(
        status="success",
        run_id=2,
        xlsx_path="reports/2026-W19.xlsx",
        xlsx_size_bytes=12345,
        summary_text="hello",
        size_guard_passed=False,
    )
    assert r2.xlsx_path == "reports/2026-W19.xlsx"
    assert r2.xlsx_size_bytes == 12345
    assert r2.summary_text == "hello"
    assert r2.size_guard_passed is False


def test_pre_finalize_pattern_preserved(setup_repo):
    """Plan 05-05 Test 8: Plan 04-05 pre-finalize-before-matcher pattern preserved.

    run_writer.finalize is called twice on a successful end-to-end run:
    once BEFORE matcher (pre-finalize so D-411 read_run_status sees 'success')
    and once at the end (idempotent via WHERE status='running' guard, no-op).
    Adding the reporter step does NOT add extra finalize calls.
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult
    from ga_crawler.storage.sqlite import SqliteRunWriter

    finalize_calls = {"n": 0}
    original_finalize = SqliteRunWriter.finalize

    def _spy_finalize(self, run_id, status="success"):
        finalize_calls["n"] += 1
        return original_finalize(self, run_id, status)

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        return GoldappleRunResult(
            status="success",
            goldapple_count=1,
            stats_delta={"goldapple.count": 1},
            unmatched_viled_brands=[],
            new_goldapple_slugs=[],
        )

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ), patch.object(SqliteRunWriter, "finalize", _spy_finalize):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
            sanity_gate_p=1,
        )

    assert result.status == "success"
    # Plan 04-05 pattern: 2 finalize calls — 1 pre-matcher + 1 final-idempotent.
    assert finalize_calls["n"] == 2, (
        f"expected 2 finalize() calls (pre-matcher + final), got {finalize_calls['n']}"
    )

    # Run row should be finalized exactly once (idempotent guard via WHERE status='running')
    engine = make_engine(setup_repo["db_path"])
    with Session(engine) as s:
        run = s.get(Run, result.run_id)
    assert run is not None
    assert run.status == "success"
    assert run.finished_at is not None
