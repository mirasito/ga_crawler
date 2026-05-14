---
phase: 6
slug: telegram-delivery
status: complete
completed: 2026-05-12
requirements-completed: [DELIVER-01, DELIVER-02, DELIVER-03, DELIVER-04, DELIVER-05]
test-count-at-close: 120
reconstructed: 2026-05-14
---

# Phase 6 Summary — Telegram Delivery

## Goal

Ship the Telegram delivery pipeline: business caption + ops alert message builder, async aiogram 3.27 bot client, pre-send gate (D-604 4-check first-fail-wins), retry logic with tenacity `wait_chain(5, 15, 45)`, and CLI composition into `run_weekly`. Passed 4/4 verification truths; D-605 delivery-status decoupling invariant confirmed end-to-end.

## Files Changed

### Production code

- `src/ga_crawler/delivery/message_builder.py` — `build_ops_alert` (D-610 single-template; Pitfall A: `_esc()` wraps `stdlib_html.escape(value, quote=False)` at lines 75-82, applied to every dynamic str field: `reason_short` line 115, `_format_almaty(started_at_utc)` line 117, `run_status` line 118, `gate_failed_check` line 119, truncated error line 132); `business_caption` (D-514 verbatim `summary_text` passthrough with 1024-char budget + sentinel fallback). Golden-file `tests/fixtures/delivery/ops-alert-templates.txt` source-locks 5 scenarios.
- `src/ga_crawler/delivery/config.py` — `DeliverEnvConfig.from_env` reading `TG_BOT_TOKEN` / `TG_BUSINESS_CHAT_ID` / `TG_OPS_CHAT_ID` via `os.getenv` only (RESEARCH caveat #4 — `load_dotenv` ONLY in `cli.py::_cmd_deliver`). Bot token at `config.py:97`.
- `src/ga_crawler/delivery/gate.py` — `evaluate_gate` composing 4 checks (D-604); REUSES `matcher.strict_key.read_run_status` (D-411 helper).
- `src/ga_crawler/delivery/telegram_client.py` — `send_document_with_policy` with `FSInputFile(Path)`; tenacity 3-retry on `(TelegramNetworkError, TelegramServerError)` via `wait_chain(5, 15, 45)`; `_send_with_retry_after_loop` for `TelegramRetryAfter`; fail-fast exclusions for `TelegramBadRequest` / `TelegramForbiddenError` / `TelegramNotFound` / `TelegramUnauthorizedError`.
- `src/ga_crawler/runners/delivery_run.py` — Phase 6 orchestrator; D-611 asymmetric ENV routing; D-606 `delivery_status='undelivered_telegram_unreachable'` on exhaustion; D-605 `runs.status` preserved as `'success'`.

## Threat Flags

- none — retroactive reconstruction
