"""Wave 0 / Plan 06-01 — Task 2 RED-gate test.

Asserts the 3 new conftest fixtures + golden-file ops-alert-templates.txt:
- synthetic_delivered_run: 4-tuple + report.* keys + fake xlsx on disk
- mock_aiogram_bot: AsyncMock send_message returns Message(message_id=10001),
                    send_document returns Message(message_id=10002)
- mock_tg_env: monkeypatch sets 3 TG_* env vars + yields dict
- tests/fixtures/delivery/ops-alert-templates.txt: 5 section headers

Permanent canary — survives into Phase 7 (D-607/D-610 source-lock).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_delivered_run_shape_and_xlsx_persisted(synthetic_delivered_run):
    engine, run_writer, run_id, repo_root = synthetic_delivered_run
    # Run row is success (inherited from synthetic_report_run.finalize)
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM runs WHERE run_id = :rid"), {"rid": run_id}
        ).scalar()
    assert status == "success"

    # report.* keys all 7 planted by fixture
    stats = run_writer.get_stats(run_id)
    assert stats["report.xlsx_path"] == "reports/2026-W19.xlsx"
    assert stats["report.xlsx_size_bytes"] > 0
    assert "2026-W19" in stats["report.summary_text"]
    assert stats["report.size_guard_passed"] is True
    assert stats["report.skipped_reason"] == ""
    assert stats["report.generated_at"] == "2026-05-10T14:30:00+00:00"
    assert stats["report.sheet_row_counts"] == {"summary": 1, "per_sku_deltas": 3}

    # Fake xlsx file on disk so FSInputFile would succeed in Wave 2+
    xlsx_path = repo_root / "reports" / "2026-W19.xlsx"
    assert xlsx_path.exists()
    assert xlsx_path.read_bytes().startswith(b"PK\x03\x04")  # zip magic — xlsx-shaped


def test_mock_aiogram_bot_is_async_context_manager(mock_aiogram_bot):
    # Sync test — verify Mock attributes shape only.
    assert hasattr(mock_aiogram_bot, "__aenter__")
    assert hasattr(mock_aiogram_bot, "__aexit__")
    assert hasattr(mock_aiogram_bot, "send_message")
    assert hasattr(mock_aiogram_bot, "send_document")


@pytest.mark.asyncio
async def test_mock_aiogram_bot_send_message_returns_message_id_10001(mock_aiogram_bot):
    msg = await mock_aiogram_bot.send_message(chat_id=-1, text="hi")
    assert msg.message_id == 10001


@pytest.mark.asyncio
async def test_mock_aiogram_bot_send_document_returns_message_id_10002(mock_aiogram_bot):
    doc = await mock_aiogram_bot.send_document(chat_id=-1, document=None)
    assert doc.message_id == 10002


def test_mock_tg_env_sets_three_env_vars(mock_tg_env):
    assert os.environ["TG_BOT_TOKEN"] == "test-token-12345"
    assert os.environ["TG_BUSINESS_CHAT_ID"] == "-100000001"
    assert os.environ["TG_OPS_CHAT_ID"] == "-100000002"
    assert mock_tg_env["bot_token"] == "test-token-12345"
    assert mock_tg_env["business_chat_id"] == "-100000001"
    assert mock_tg_env["ops_chat_id"] == "-100000002"


def test_ops_alert_templates_golden_file_has_five_sections():
    path = REPO_ROOT / "tests" / "fixtures" / "delivery" / "ops-alert-templates.txt"
    assert path.exists(), f"missing golden file at {path}"
    content = path.read_text(encoding="utf-8")
    expected_sections = (
        "upstream_status_failed",
        "xlsx_oversize",
        "empty_summary_text",
        "no_xlsx_in_stats",
        "delivery_exception",
    )
    for section in expected_sections:
        assert f"=== {section} ===" in content, f"missing section header: {section}"
    # Exactly 5 section headers (drift detection — refuse stealth additions).
    assert content.count("=== ") == 5


def test_ops_alert_templates_contains_no_real_chat_ids():
    # T-6-08 mitigation canary: synthetic chat_ids only.
    path = REPO_ROOT / "tests" / "fixtures" / "delivery" / "ops-alert-templates.txt"
    content = path.read_text(encoding="utf-8")
    # The synthetic mock_tg_env chat_ids are -100000001 / -100000002.
    # Real Telegram chat_ids could be in -1001234567890 range; reject any 13-digit negative.
    import re
    real_chat_pattern = re.compile(r"-1001\d{9,}")
    matches = real_chat_pattern.findall(content)
    assert not matches, f"real-looking chat_ids in golden file: {matches} — T-6-08 violation"
