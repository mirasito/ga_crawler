"""Plan 06-04 (Wave 3) -- integration tests for runners/delivery_run.py.

Tests use real on-disk SQLite (synthetic_delivered_run fixture) +
mock aiogram Bot patched at the ``runners.delivery_run.open_bot`` site
(so the orchestrator never instantiates a real Bot and never hits the
aiogram token validator).

Coverage axes:
  * 6 D-606 enum transitions (pending(dry-run) / delivered_business /
    delivered_ops_only / undelivered_telegram_unreachable /
    skipped_no_credentials / skipped_already_delivered).
  * D-604 gate-fail -> ops route happy path.
  * D-605 invariant: Telegram failure does NOT call run_writer.fail();
    xlsx stays on disk; runs.status untouched.
  * D-608 idempotency dispatch + --force override + --dry-run.
  * D-611 asymmetric ENV handling (TG_BOT_TOKEN required;
    TG_BUSINESS_CHAT_ID missing degrades to ops; TG_OPS_CHAT_ID missing
    on business route logs warning + proceeds).
  * Pitfall 6 single ``patch_stats`` call per non-dry-run invocation.
  * Pitfall A: TelegramBadRequest fail-fast (no retry, attempts == 1).
  * Pitfall C: ``_resolve_xlsx_safely`` defense-in-depth.
  * Pitfall D: business_*_message_id sentinel semantics (-1 on ops route;
    caption_id == document_id on non-split; distinct on split).
  * 8 D-607 stats keys persisted atomically.

The ``fast_retry`` fixture from Plan 06-03 unit tests is intentionally
not reused here -- mock_aiogram_bot resolves synchronously, so even the
retry-exhaustion test completes in <1s without tenacity sleeps.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import SendMessage

from ga_crawler.delivery.config import DeliverConfig, DeliverEnvConfig
from ga_crawler.runners.delivery_run import (
    DeliveryPhaseResult,
    run_delivery_phase,
)

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------- #
# Local fixtures                                                              #
# --------------------------------------------------------------------------- #


@pytest.fixture
def patched_bot(mock_aiogram_bot, mocker):
    """Replace ``runners.delivery_run.open_bot`` with a stub that returns the
    mock aiogram Bot.

    Bypasses the aiogram token validator (mock_tg_env's token does not match
    ``digits:string`` regex) and prevents any real network I/O.
    """

    async def _stub_open_bot(token, parse_mode="HTML"):
        return mock_aiogram_bot

    mocker.patch(
        "ga_crawler.runners.delivery_run.open_bot",
        _stub_open_bot,
    )
    return mock_aiogram_bot


@pytest.fixture
def fast_retry(monkeypatch):
    """Mirror of tests/test_telegram_client.py::fast_retry.

    Flattens tenacity wait_chain(5,15,45) -> wait_chain(0,0,0) so
    retry-exhaustion tests do not wait the real 75s budget. Preserves
    before_sleep callback so attempt_tracker still increments correctly.
    """
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_chain,
        wait_fixed,
    )

    from ga_crawler.delivery import telegram_client as tc

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


def _make_cfg() -> DeliverConfig:
    """Test-default DeliverConfig (mirrors pyproject defaults)."""
    return DeliverConfig()


# --------------------------------------------------------------------------- #
# Test 1: D-611 asymmetric ENV -- TG_BOT_TOKEN absent -> skipped_no_credentials
# --------------------------------------------------------------------------- #


def test_skip_when_token_missing(
    synthetic_delivered_run, mock_tg_env, mock_aiogram_bot, monkeypatch,
):
    """No TG_BOT_TOKEN -> delivery_status=skipped_no_credentials; no Bot ctor."""
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    engine, run_writer, run_id, repo_root = synthetic_delivered_run

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "skipped_no_credentials"
    assert result.route == "skipped"
    assert "missing_env_TG_BOT_TOKEN" in result.last_error
    # No aiogram Bot was instantiated -- mock has zero call.
    assert mock_aiogram_bot.send_message.call_count == 0
    assert mock_aiogram_bot.send_document.call_count == 0
    # Stats patched with the skip sentinel.
    stats = run_writer.get_stats(run_id) or {}
    assert stats.get("deliver.delivery_status") == "skipped_no_credentials"
    assert stats.get("deliver.route") == "skipped"


# --------------------------------------------------------------------------- #
# Test 2: D-608 idempotency -- already delivered, no --force                  #
# --------------------------------------------------------------------------- #


def test_idempotency_skip_when_already_delivered(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """Pre-planted delivered_business + force=False -> skipped_already_delivered."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    run_writer.patch_stats(run_id, {"deliver.delivery_status": "delivered_business"})

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
        force=False,
    )
    assert result.delivery_status == "skipped_already_delivered"
    assert result.route == "skipped"
    assert patched_bot.send_message.call_count == 0
    assert patched_bot.send_document.call_count == 0


# --------------------------------------------------------------------------- #
# Test 3: D-608 idempotency -- already delivered + --force                    #
# --------------------------------------------------------------------------- #


def test_force_overrides_idempotency(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """delivered_business + force=True -> full delivery proceeds again."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    run_writer.patch_stats(run_id, {"deliver.delivery_status": "delivered_business"})

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
        force=True,
    )
    assert result.delivery_status == "delivered_business"
    assert result.route == "business"
    # send_document was called (business route always sends document).
    assert patched_bot.send_document.call_count == 1


# --------------------------------------------------------------------------- #
# Test 4: D-604 gate-fail -> ops_only route                                   #
# --------------------------------------------------------------------------- #


def test_gate_fail_routes_to_ops_only(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """run_writer.fail() -> gate check #1 trips -> ops alert sent."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    run_writer.fail(run_id, reason="simulated upstream failure")

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "delivered_ops_only"
    assert result.route == "ops_only"
    assert result.ops_message_id == 10001  # send_message stub returns 10001
    # business message_ids are sentinels per Pitfall D.
    assert result.business_caption_message_id == -1
    assert result.business_document_message_id == -1
    # Only ops_alert sent -- no document upload.
    assert patched_bot.send_message.call_count == 1
    assert patched_bot.send_document.call_count == 0


# --------------------------------------------------------------------------- #
# Test 5a: D-604 gate-pass non-split (W2 FIX)                                 #
# --------------------------------------------------------------------------- #


def test_gate_pass_non_split_path_5a(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """summary_text <= 1024 -> only send_document; caption_id == document_id."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    # synthetic_delivered_run plants a ~50-char summary_text by default.
    summary = (run_writer.get_stats(run_id) or {}).get("report.summary_text", "")
    assert len(summary) <= 1024, "fixture summary must fit non-split path"

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "delivered_business"
    assert result.route == "business"
    # Pitfall D: non-split -> caption_id == document_id == 10002.
    assert result.business_document_message_id == 10002
    assert result.business_caption_message_id == 10002
    assert patched_bot.send_message.call_count == 0  # NO separate send_message
    assert patched_bot.send_document.call_count == 1


# --------------------------------------------------------------------------- #
# Test 5b: D-604 gate-pass split path (W2 FIX)                                #
# --------------------------------------------------------------------------- #


def test_gate_pass_split_path_5b(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """summary_text > 1024 -> send_message FIRST, then send_document; ids distinct."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    # Plant a long summary to force split path.
    long_summary = "X" * 2000
    run_writer.patch_stats(run_id, {"report.summary_text": long_summary})

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "delivered_business"
    assert result.route == "business"
    # Distinct message_ids per Pitfall D (split path).
    assert result.business_caption_message_id == 10001
    assert result.business_document_message_id == 10002
    assert patched_bot.send_message.call_count == 1
    assert patched_bot.send_document.call_count == 1
    # send_message received the FULL summary, not the fallback string.
    sent_text = patched_bot.send_message.call_args.kwargs.get("text")
    assert sent_text == long_summary
    # send_document caption is the short fallback.
    sent_caption = patched_bot.send_document.call_args.kwargs.get("caption")
    assert sent_caption == "См. сводку выше"


# --------------------------------------------------------------------------- #
# Test 5c: D-611 asymmetric -- route=business + TG_OPS_CHAT_ID missing (W3)   #
# --------------------------------------------------------------------------- #


def test_business_route_with_missing_ops_chat_proceeds_5c(
    synthetic_delivered_run, mock_tg_env, patched_bot, monkeypatch, capsys,
):
    """ops_chat_id missing on business route -> warn + proceed (D-611 asymmetric).

    structlog logs go to stdout via PrintLogger -- caplog (stdlib logging) does
    NOT capture them in this project's setup. Assert against capsys instead.
    """
    monkeypatch.delenv("TG_OPS_CHAT_ID", raising=False)
    engine, run_writer, run_id, repo_root = synthetic_delivered_run

    env = DeliverEnvConfig.from_env()
    assert env.ops_chat_id is None  # confirm the delenv took effect.

    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "delivered_business"
    assert result.route == "business"
    captured = capsys.readouterr()
    assert "delivery_ops_chat_missing_acceptable_for_business_route" in captured.out, (
        "expected D-611 asymmetric-handling warning event in stdout; "
        f"got out={captured.out!r}"
    )


# --------------------------------------------------------------------------- #
# Test 6: Pitfall 6 single patch_stats per invocation                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "scenario",
    ["gate_pass_business", "gate_fail_ops", "skip_token_missing", "skip_idempotent"],
)
def test_single_patch_stats_per_invocation(
    synthetic_delivered_run, mock_tg_env, patched_bot, mocker, monkeypatch, scenario,
):
    """patch_stats is called EXACTLY ONCE per non-dry-run invocation."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    # Set up scenario-specific pre-state.
    if scenario == "gate_fail_ops":
        run_writer.fail(run_id, reason="simulated upstream failure")
    elif scenario == "skip_token_missing":
        monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    elif scenario == "skip_idempotent":
        run_writer.patch_stats(
            run_id, {"deliver.delivery_status": "delivered_business"},
        )
    # Spy AFTER any pre-state planting so only the orchestrator call counts.
    spy = mocker.spy(run_writer, "patch_stats")

    env = DeliverEnvConfig.from_env()
    run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert spy.call_count == 1, (
        f"expected exactly 1 patch_stats call for scenario {scenario!r}, "
        f"got {spy.call_count}"
    )


# --------------------------------------------------------------------------- #
# Test 7: D-605 -- TelegramNetworkError does NOT fail the run                 #
# --------------------------------------------------------------------------- #


def test_telegram_network_error_does_not_fail_run(
    synthetic_delivered_run, mock_tg_env, patched_bot, fast_retry,
):
    """Network error 3x -> undelivered_telegram_unreachable; runs.status unchanged."""
    network_err = TelegramNetworkError(
        method=SendMessage(chat_id="c", text="t"), message="ECONNRESET",
    )
    # Force the document send to repeatedly fail (business route).
    patched_bot.send_document = AsyncMock(side_effect=network_err)

    engine, run_writer, run_id, repo_root = synthetic_delivered_run

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "undelivered_telegram_unreachable"
    assert result.route == "business"
    assert "TelegramNetworkError" in result.last_error
    # runs.status untouched (D-605 invariant).
    from ga_crawler.matcher.strict_key import read_run_status
    assert read_run_status(engine, run_id) == "success"
    # xlsx file STILL on disk (no cleanup on send failure).
    xlsx_path = (run_writer.get_stats(run_id) or {}).get("report.xlsx_path", "")
    assert (repo_root / xlsx_path).is_file()


# --------------------------------------------------------------------------- #
# Test 8: Pitfall A -- TelegramBadRequest fail-fast                           #
# --------------------------------------------------------------------------- #


def test_telegram_bad_request_no_retry(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """TelegramBadRequest -> attempts==1, no retry, undelivered_*."""
    bad_req = TelegramBadRequest(
        method=SendMessage(chat_id="c", text="t"), message="bad chat",
    )
    patched_bot.send_document = AsyncMock(side_effect=bad_req)

    engine, run_writer, run_id, repo_root = synthetic_delivered_run

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "undelivered_telegram_unreachable"
    assert "TelegramBadRequest" in result.last_error
    # Fail-fast: exactly 1 invocation (no retries for BadRequest).
    assert patched_bot.send_document.call_count == 1
    # runs.status still success.
    from ga_crawler.matcher.strict_key import read_run_status
    assert read_run_status(engine, run_id) == "success"


# --------------------------------------------------------------------------- #
# Test 9: Pitfall C -- xlsx path traversal blocked                            #
# --------------------------------------------------------------------------- #


def test_xlsx_path_traversal_blocked(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """xlsx_path with ../ escape -> undelivered_telegram_unreachable; no send."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    # Tamper xlsx_path to escape repo_root.
    run_writer.patch_stats(
        run_id, {"report.xlsx_path": "../../etc/passwd"},
    )

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "undelivered_telegram_unreachable"
    assert "xlsx_path_escapes_repo" in result.last_error
    assert patched_bot.send_document.call_count == 0
    assert patched_bot.send_message.call_count == 0


# --------------------------------------------------------------------------- #
# Test 10: Caption split (Claude's Discretion)                                #
# --------------------------------------------------------------------------- #


def test_caption_split_when_long(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """summary > 1024 -> send_message(full) + send_document(short caption)."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    long_text = "Y" * 1500
    run_writer.patch_stats(run_id, {"report.summary_text": long_text})

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.delivery_status == "delivered_business"
    assert patched_bot.send_message.call_count == 1
    assert patched_bot.send_document.call_count == 1
    # business_caption_message_id reflects the send_message stub id (10001).
    assert result.business_caption_message_id == 10001
    assert result.business_document_message_id == 10002


# --------------------------------------------------------------------------- #
# Test 11: --dry-run                                                          #
# --------------------------------------------------------------------------- #


def test_dry_run_no_telegram_calls(
    synthetic_delivered_run, mock_tg_env, patched_bot, mocker, capsys,
):
    """dry_run=True -> no Telegram calls; no patch_stats; preview JSON to stdout."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    spy = mocker.spy(run_writer, "patch_stats")

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
        dry_run=True,
    )
    assert result.delivery_status == "pending"
    assert result.route == "business"  # gate-pass on the fixture
    assert patched_bot.send_message.call_count == 0
    assert patched_bot.send_document.call_count == 0
    assert spy.call_count == 0, "dry_run must be read-only"
    # Preview JSON is written to sys.stdout.buffer; capsys captures it.
    captured = capsys.readouterr()
    assert '"route"' in captured.out


# --------------------------------------------------------------------------- #
# Test 12: 8 D-607 keys present after business send                           #
# --------------------------------------------------------------------------- #


def test_all_8_d607_keys_present_after_business_send(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """After a successful business send, all 8 deliver.* keys are present."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run

    env = DeliverEnvConfig.from_env()
    run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    stats = run_writer.get_stats(run_id) or {}
    expected_keys = {
        "deliver.delivery_status",
        "deliver.route",
        "deliver.business_caption_message_id",
        "deliver.business_document_message_id",
        "deliver.ops_message_id",
        "deliver.attempt_count",
        "deliver.last_error",
        "deliver.delivered_at",
    }
    missing = expected_keys - set(stats.keys())
    assert not missing, f"missing deliver.* keys: {missing}"
    # Spot-check sentinel semantics: ops_message_id == -1 on business route.
    assert stats["deliver.ops_message_id"] == -1
    # Non-split business -> caption_id == document_id (both 10002).
    assert stats["deliver.business_caption_message_id"] == 10002
    assert stats["deliver.business_document_message_id"] == 10002
    # delivered_at is non-empty ISO timestamp.
    assert stats["deliver.delivered_at"]


# --------------------------------------------------------------------------- #
# Test 13: Pitfall D -- message_id sentinels for ops_only route               #
# --------------------------------------------------------------------------- #


def test_message_id_sentinels_for_ops_only(
    synthetic_delivered_run, mock_tg_env, patched_bot,
):
    """Ops-only route -> business_*_id == -1; ops_id == 10001."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    run_writer.fail(run_id, reason="trigger ops route")

    env = DeliverEnvConfig.from_env()
    result = run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    assert result.business_caption_message_id == -1
    assert result.business_document_message_id == -1
    assert result.ops_message_id == 10001


# --------------------------------------------------------------------------- #
# Test 14: Pitfall B -- no unclosed-session warning                           #
# --------------------------------------------------------------------------- #


def test_no_unclosed_session_warning(
    synthetic_delivered_run, mock_tg_env, patched_bot, recwarn,
):
    """Successful business send triggers async with bot enter/exit; no warnings."""
    engine, run_writer, run_id, repo_root = synthetic_delivered_run

    env = DeliverEnvConfig.from_env()
    run_delivery_phase(
        run_id=run_id,
        engine=engine,
        run_writer=run_writer,
        repo_root=repo_root,
        config=_make_cfg(),
        env=env,
    )
    # mock_aiogram_bot.__aenter__ / __aexit__ MUST have been awaited.
    assert patched_bot.__aenter__.await_count == 1
    assert patched_bot.__aexit__.await_count == 1
    # No "Unclosed client session" RuntimeWarning during this run.
    for w in recwarn.list:
        msg = str(w.message)
        assert "Unclosed client session" not in msg, (
            f"unexpected unclosed-session warning: {msg}"
        )
