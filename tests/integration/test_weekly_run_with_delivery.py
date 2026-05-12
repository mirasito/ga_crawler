"""Plan 06-05 (Wave 4) -- E2E weekly_run amended with delivery step.

Tests SC#1 (business route happy path) + SC#2 (deliberate-failure -> ops_only)
+ D-605 invariant (Telegram unreachable preserves ``runs.status='success'``)
+ delivery skip when reporter skipped + 5-namespace integrity.

Uses mocked fetchers (mirror of ``test_main_run_with_reporter.py`` pattern) +
mocked aiogram Bot via ``mock_aiogram_bot`` (conftest fixture) +
``patched_open_bot`` local fixture to swap ``runners.delivery_run.open_bot``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage
from sqlalchemy import text as _text

from ga_crawler.runners.main_run import run_weekly
from ga_crawler.runners.reporter_run import ReporterPhaseResult
from ga_crawler.storage.sqlite import make_engine

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------- #
# Local fixtures + synthetic fetcher mocks (mirror of test_main_run_with_reporter)
# ---------------------------------------------------------------------------- #


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
                    {"price": 10000, "realPrice": 10000, "currency": "T"}
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
    """Mirror of tests/integration/test_main_run_with_reporter.py::_FakeFetcher.

    Module-scoped so we can patch ViledFetcher with it. Returns a synthetic
    PDP per URL so the viled phase sanity_gate (n>=N) trips for the success
    threshold configured in setup_repo.
    """

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
    """Mirror of test_main_run_with_reporter::setup_repo with delivery defaults."""
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


@pytest.fixture
def patched_open_bot(mock_aiogram_bot, mocker):
    """Swap ``ga_crawler.runners.delivery_run.open_bot`` for a stub returning
    the mock_aiogram_bot. Bypasses aiogram token validator + zero network I/O.
    """

    async def _stub_open_bot(token, parse_mode="HTML"):
        return mock_aiogram_bot

    mocker.patch(
        "ga_crawler.runners.delivery_run.open_bot",
        _stub_open_bot,
    )
    return mock_aiogram_bot


# ---------------------------------------------------------------------------- #
# Test 1: SC#1 happy path -- business route receives summary + xlsx            #
# ---------------------------------------------------------------------------- #


def test_sc1_happy_path_business_route(
    setup_repo, mock_tg_env, patched_open_bot, mock_aiogram_bot,
):
    """SC#1: gate-pass business route -> business chat receives caption+xlsx;
    ops chat receives nothing. ``MainRunResult.delivery_status='delivered_business'``,
    ``delivery_route='business'``.
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
            sanity_gate_p=1,
        )

    assert result.status == "success", result.reason
    # D-616 delivery fields populated by delivery composition step.
    assert result.delivery_status == "delivered_business", (
        f"expected delivered_business, got {result.delivery_status!r}; "
        f"reason={result.reason!r}"
    )
    assert result.delivery_route == "business"

    # Business chat receives EXACTLY 1 document upload (xlsx + short caption when
    # summary <= 1024 chars, else send_message + send_document).
    assert mock_aiogram_bot.send_document.call_count == 1
    # In the happy path, ops chat receives nothing.
    # (send_message may have been called if summary > 1024 chars; assert by chat_id.)
    for call in mock_aiogram_bot.send_message.call_args_list:
        chat_id = call.kwargs.get("chat_id") or (call.args[0] if call.args else None)
        assert str(chat_id) != mock_tg_env["ops_chat_id"], (
            f"ops chat received an unexpected message on the happy path: {call}"
        )
    # send_document MUST target the business chat.
    doc_call = mock_aiogram_bot.send_document.call_args
    doc_chat_id = doc_call.kwargs.get("chat_id") or (doc_call.args[0] if doc_call.args else None)
    assert str(doc_chat_id) == mock_tg_env["business_chat_id"]

    # Stats reflect delivery namespace (verified separately in Test 5).
    assert any(k.startswith("deliver.") for k in result.stats_delta), (
        f"stats_delta missing deliver.* keys: {sorted(result.stats_delta.keys())}"
    )


# ---------------------------------------------------------------------------- #
# Test 2: SC#2 variant -- viled phase below sanity_gate -> delivery NOT invoked
# ---------------------------------------------------------------------------- #


def test_sc2_viled_below_sanity_no_delivery_invoked(
    setup_repo, mock_tg_env, patched_open_bot, mock_aiogram_bot,
):
    """SC#2 variant: viled fetch returns 0 SKUs -> sanity gate trips ->
    run_writer.fail -> goldapple/matcher/reporter all skipped -> delivery
    NOT invoked. Business + ops chats both get 0 calls.

    ``MainRunResult.delivery_status='pending'`` (pre-init default never
    overwritten because the delivery composition block is gated on
    ``m_result.status == 'success' and r_result.status == 'success'``).
    """

    class _EmptyFetcher:
        def __init__(self, *, run_id=1, pause_seconds=0):
            pass

        def run_loop(self, urls, stats, sleep_fn=None):
            # Return zero records -> sanity_gate_n=5 trips on viled phase.
            return []

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _EmptyFetcher):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
        )

    assert result.status == "failed"
    # Pre-init defaults preserved -- delivery composition block was never reached.
    assert result.delivery_status == "pending", (
        f"expected pending (delivery not invoked), got {result.delivery_status!r}"
    )
    assert result.delivery_route == ""
    # ZERO Telegram interactions.
    assert mock_aiogram_bot.send_message.call_count == 0
    assert mock_aiogram_bot.send_document.call_count == 0


# ---------------------------------------------------------------------------- #
# Test 3: SC#2 canonical -- size_guard trips -> ops alert sent                 #
# ---------------------------------------------------------------------------- #


def test_sc2_deliberate_failure_size_guard_trips_ops_alert(
    setup_repo, mock_tg_env, patched_open_bot, mock_aiogram_bot,
):
    """SC#2 canonical (ROADMAP wording): upstream pipeline succeeds but reporter
    flags ``size_guard_passed=False`` -> delivery gate check #3 trips ->
    ops alert sent to ops chat; business chat gets nothing.

    ``MainRunResult.delivery_status='delivered_ops_only'``,
    ``delivery_route='ops_only'``.

    Implementation: patch ``run_reporter_phase`` to return a
    ``ReporterPhaseResult`` with ``size_guard_passed=False`` and a synthetic
    xlsx on disk. Real reporter logic is bypassed but the contract is honored.
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

    # Plant a synthetic xlsx so report.xlsx_path is non-empty (D-615 gate trips
    # on r_result.xlsx_path; size_guard_passed=False does NOT prevent delivery
    # composition entry -- it trips the delivery's INTERNAL gate check #3
    # (D-604) which routes to ops_only).
    reports_dir = setup_repo["repo_root"] / "reports"
    reports_dir.mkdir(exist_ok=True)
    xlsx_file = reports_dir / "2026-W19.xlsx"
    xlsx_file.write_bytes(b"PK\x03\x04fake-xlsx-size-guard-fail")

    def fake_reporter(*, run_id, engine, run_writer, repo_root, config):
        # Mirror Plan 05-05 ReporterPhaseResult shape; populate stats via
        # run_writer.patch_stats so the delivery phase sees the upstream
        # report.* values when it reads runs.stats. size_guard_passed=False
        # is the critical bit -- it routes the delivery gate to ops_only.
        run_writer.patch_stats(run_id, {
            "report.xlsx_path": "reports/2026-W19.xlsx",
            "report.xlsx_size_bytes": xlsx_file.stat().st_size,
            "report.summary_text": "synthetic summary for SC#2",
            "report.size_guard_passed": False,
            "report.skipped_reason": "",
            "report.generated_at": "2026-05-10T14:30:00+00:00",
            "report.sheet_row_counts": {"summary": 1},
        })
        return ReporterPhaseResult(
            status="success",
            xlsx_path="reports/2026-W19.xlsx",
            xlsx_size_bytes=xlsx_file.stat().st_size,
            summary_text="synthetic summary for SC#2",
            size_guard_passed=False,
            sheet_row_counts={"summary": 1},
            stats_delta={
                "report.xlsx_path": "reports/2026-W19.xlsx",
                "report.size_guard_passed": False,
            },
        )

    with patch(
        "ga_crawler.runners.viled_run._default_fetch_catalog",
        side_effect=_fake_catalog,
    ), patch("ga_crawler.runners.viled_run.ViledFetcher", _FakeFetcher), patch(
        "ga_crawler.runners.goldapple_run.run_goldapple_phase",
        side_effect=fake_goldapple_phase,
    ), patch(
        "ga_crawler.runners.main_run.run_reporter_phase",
        side_effect=fake_reporter,
    ):
        result = run_weekly(
            repo_root=setup_repo["repo_root"],
            db_path=setup_repo["db_path"],
            pyproject_path=setup_repo["pyproject_path"],
            sanity_gate_p=1,
        )

    # runs.status MUST still be 'success' (D-605 + D-515: size-guard does not
    # fail the run; it routes delivery to ops_only).
    assert result.status == "success", result.reason
    assert result.delivery_status == "delivered_ops_only", (
        f"expected delivered_ops_only, got {result.delivery_status!r}"
    )
    assert result.delivery_route == "ops_only"

    # Ops chat received EXACTLY one alert; business chat got 0.
    assert mock_aiogram_bot.send_message.call_count == 1
    assert mock_aiogram_bot.send_document.call_count == 0
    alert_call = mock_aiogram_bot.send_message.call_args
    alert_chat_id = alert_call.kwargs.get("chat_id") or (
        alert_call.args[0] if alert_call.args else None
    )
    assert str(alert_chat_id) == mock_tg_env["ops_chat_id"], (
        f"alert routed to wrong chat: {alert_chat_id}"
    )
    # Alert body contains run_id (per build_ops_alert template).
    alert_text = alert_call.kwargs.get("text", "")
    assert str(result.run_id) in alert_text, (
        f"ops alert body missing run_id={result.run_id}: {alert_text[:200]}"
    )


# ---------------------------------------------------------------------------- #
# Test 4: D-605 invariant -- Telegram unreachable does NOT fail the run        #
# ---------------------------------------------------------------------------- #


def test_d605_telegram_unreachable_run_status_unchanged(
    setup_repo, mock_tg_env, patched_open_bot, mock_aiogram_bot, monkeypatch,
):
    """D-605: happy upstream pipeline -> reporter writes xlsx -> delivery_run
    invoked -> Telegram send raises ``TelegramNetworkError`` repeatedly ->
    tenacity exhausts -> ``delivery_status='undelivered_telegram_unreachable'``.

    ``MainRunResult.status='success'`` (D-605); runs.status in DB == 'success';
    xlsx file STILL on disk for manual recovery via ``deliver-run --run-id N``.
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult
    from ga_crawler.delivery import telegram_client as tc

    # Flatten tenacity wait_chain so the test does not wait 75s.
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_chain,
        wait_fixed,
    )

    def _fast_builder(max_attempts, attempt_tracker):
        return retry(
            retry=retry_if_exception_type(tc._RETRY_TYPES),
            stop=stop_after_attempt(max_attempts),
            wait=wait_chain(wait_fixed(0), wait_fixed(0), wait_fixed(0)),
            before_sleep=tc._make_before_sleep(attempt_tracker),
            reraise=True,
        )

    monkeypatch.setattr(
        "ga_crawler.delivery.telegram_client._build_retry_decorator",
        _fast_builder,
    )

    # Force send_document to fail with TelegramNetworkError 3x.
    network_err = TelegramNetworkError(
        method=SendMessage(chat_id="c", text="t"), message="ECONNRESET",
    )
    mock_aiogram_bot.send_document = AsyncMock(side_effect=network_err)

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
            sanity_gate_p=1,
        )

    # D-605 core invariant: Telegram failure does NOT fail the run.
    assert result.status == "success", (
        f"D-605 VIOLATION: Telegram unreachable flipped run to failed: {result.reason!r}"
    )
    assert result.delivery_status == "undelivered_telegram_unreachable", (
        f"expected undelivered_telegram_unreachable, got {result.delivery_status!r}"
    )
    assert result.delivery_route == "business"

    # DB runs.status must also be 'success' (D-605 storage-side invariant).
    engine = make_engine(setup_repo["db_path"])
    with engine.connect() as conn:
        row = conn.execute(
            _text("SELECT status FROM runs WHERE run_id=:rid"),
            {"rid": result.run_id},
        ).first()
    assert row is not None and row[0] == "success", (
        f"D-605 storage VIOLATION: runs.status={row[0] if row else None!r}"
    )

    # xlsx file MUST still be on disk (no cleanup on send failure ->
    # operator can run deliver-run --run-id N for recovery).
    assert result.xlsx_path is not None
    xlsx_full = setup_repo["repo_root"] / result.xlsx_path
    assert xlsx_full.exists(), (
        f"xlsx evaporated after Telegram failure -- manual recovery broken: {xlsx_full}"
    )


# ---------------------------------------------------------------------------- #
# Test 5: delivery NOT invoked when reporter is skipped                        #
# ---------------------------------------------------------------------------- #


def test_delivery_skipped_when_reporter_skipped(
    setup_repo, mock_tg_env, patched_open_bot, mock_aiogram_bot,
):
    """When matcher returns 'skipped' (D-411), reporter is NOT invoked (D-507
    cascade) -> the delivery composition gate (``r_result.xlsx_path``) is also
    not entered -> delivery_status stays at pre-init default 'pending'.

    Triggers the upstream cascade by patching run_matcher_phase to return
    a 'skipped' result; reporter then falls through unexecuted.
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult
    from ga_crawler.runners.matcher_run import MatcherPhaseResult

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
    # delivery composition block guarded on m_result.status == 'success' -> NOT entered.
    assert result.delivery_status == "pending"
    assert result.delivery_route == ""
    # ZERO Telegram interactions.
    assert mock_aiogram_bot.send_message.call_count == 0
    assert mock_aiogram_bot.send_document.call_count == 0
    # No deliver.* keys in stats_delta because run_delivery_phase never ran.
    assert not any(k.startswith("deliver.") for k in result.stats_delta), (
        f"deliver.* keys leaked into stats_delta: "
        f"{sorted(k for k in result.stats_delta if k.startswith('deliver.'))}"
    )


# ---------------------------------------------------------------------------- #
# Test 6: 5-namespace integrity end-to-end                                     #
# ---------------------------------------------------------------------------- #


def test_five_namespace_integrity_after_e2e(
    setup_repo, mock_tg_env, patched_open_bot, mock_aiogram_bot,
):
    """After a successful end-to-end happy run, ``runs.stats`` JSON in DB
    contains keys from all 5 namespaces: viled.* / goldapple.* / match.* /
    report.* / deliver.*. Sets disjoint (no key belongs to two namespaces).

    The fake goldapple phase here MUST call ``run_writer.patch_stats`` itself
    (mirroring the real ``run_goldapple_phase`` Step 14) so the goldapple.*
    keys land in the DB row, not only in the orchestrator's local accumulator.
    """
    from ga_crawler.runners.goldapple_run import PhaseResult as GoldappleRunResult

    async def fake_goldapple_phase(*, run_id, viled_brands, repo_root,
                                   brand_alias, normalizer, snapshot_writer,
                                   run_writer, headless, **kwargs):
        _plant_matched_snapshots(snapshot_writer.engine, run_id)
        # Mirror real run_goldapple_phase Step 14 -- patch_stats so the
        # goldapple.* namespace persists into runs.stats in DB.
        run_writer.patch_stats(run_id, {
            "goldapple.fetch_count": 1,
            "goldapple.fetch_failures": 0,
            "goldapple.parse_failures": 0,
        })
        return GoldappleRunResult(
            status="success",
            goldapple_count=1,
            stats_delta={"goldapple.fetch_count": 1},
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
            sanity_gate_p=1,
        )

    assert result.status == "success"
    assert result.delivery_status == "delivered_business"

    # Read stats from DB (authoritative -- result.stats_delta is a snapshot of
    # the orchestrator's accumulator, but runs.stats is what Phase 7 reads).
    engine = make_engine(setup_repo["db_path"])
    with engine.connect() as conn:
        row = conn.execute(
            _text("SELECT stats FROM runs WHERE run_id=:rid"),
            {"rid": result.run_id},
        ).first()
    assert row is not None
    stats_json = row[0]
    db_stats = json.loads(stats_json) if isinstance(stats_json, str) else (stats_json or {})

    keys = set(db_stats.keys())
    has_viled = any(k.startswith("viled.") for k in keys)
    has_gold = any(k.startswith("goldapple.") for k in keys)
    has_match = any(k.startswith("match.") for k in keys)
    has_report = any(k.startswith("report.") for k in keys)
    has_deliver = any(k.startswith("deliver.") for k in keys)
    assert has_viled and has_gold and has_match and has_report and has_deliver, (
        f"5-namespace integrity VIOLATION; missing: "
        f"viled={not has_viled} gold={not has_gold} match={not has_match} "
        f"report={not has_report} deliver={not has_deliver}; keys={sorted(keys)}"
    )

    # Disjointness: each key has exactly one namespace prefix.
    namespaces = ("viled.", "goldapple.", "match.", "report.", "deliver.")
    for k in keys:
        hits = sum(1 for ns in namespaces if k.startswith(ns))
        assert hits == 1, (
            f"key {k!r} matches {hits} namespace prefixes "
            f"(must match exactly 1 -- disjoint canary)"
        )
