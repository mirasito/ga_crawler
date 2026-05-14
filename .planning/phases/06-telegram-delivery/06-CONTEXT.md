---
phase: 6
slug: telegram-delivery
status: archived
reconstructed: 2026-05-14
reconstructed_from: ".planning/milestones/v1.0-REQUIREMENTS.md + src/ga_crawler/delivery/message_builder.py docstring"
note: "Retroactive stub for Phase 10 AUDIT-DEBT-01..04 skill State-B precondition. v1.0 milestone closed 2026-05-13; original CONTEXT artifacts were not archived per-phase, only milestone-level."
---

# Phase 6 Context — Telegram Delivery

**Phase boundary:** Ships the Telegram delivery pipeline — message builder (business caption + ops alert), async bot client, pre-send gate (D-604), retry logic, and CLI composition wiring into `run_weekly`.

## Implementation Decisions (from v1.0-REQUIREMENTS.md evidence trail)

- **D-601** — aiogram 3.27 locked per CLAUDE.md §Telegram Delivery. `async with Bot()` lifecycle prevents unclosed-session warnings (Pitfall B, RESEARCH §2).
- **D-604** — 4-check first-fail-wins gate in `delivery/gate.py::evaluate_gate`: (1) `runs.status == 'success'`; (2) `report.xlsx_path` non-empty; (3) `report.size_guard_passed == True` (D-515 cascade from Phase 5); (4) `report.summary_text` non-empty after strip. `GateDecision` frozen dataclass with route + gate_failed_check + gate_failure_reason.
- **D-605** — Delivery-status decoupling: `runs.status='success'` even when Telegram fails (xlsx stays on disk for manual recovery via `deliver-run --run-id N`).
- **D-606** — `delivery_status='undelivered_telegram_unreachable'` on tenacity exhaustion.
- **D-608** — `deliver-run --run-id N` standalone CLI for manual recovery.
- **D-609** — `parse_mode=HTML` (not MarkdownV2). Only `< > &` need escaping — quotes stay literal so href attributes work.
- **D-610** — Single `build_ops_alert` template with reason-field placeholder (D-610). Pitfall A: every dynamic str field wrapped in `_esc()` (`stdlib_html.escape(value, quote=False)`).
- **D-611** — Asymmetric ENV handling: `TG_BOT_TOKEN` missing → `delivery_status='skipped_no_credentials'` (fail-loud exit 3); `TG_BUSINESS_CHAT_ID` missing → degrade to ops alert with reason `missing_env_TG_BUSINESS_CHAT_ID`.
- **D-612** — `.env.example` template + `.gitignore` audit confirms `.env` excluded.
- **D-614** — 3500-char traceback truncation in `build_ops_alert`.
- **D-615/D-616** — Composition gate wires delivery into `run_weekly`; `MainRunResult.delivery_status/delivery_route` surface delivery outcome.

## Phase Outcomes

5 DELIVER requirements closed (DELIVER-01..05). Phase 6 passed 4/4 verification truths; D-605 invariant holds (runs.status='success' even on Telegram network failure).
