---
phase: 6
slug: telegram-delivery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already installed, mirrored Phase 2-5) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (existing) |
| **Quick run command** | `uv run pytest tests/test_delivery_*.py tests/test_gate.py tests/test_message_builder.py tests/test_telegram_client.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~5 seconds (delivery subset), ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_delivery_*.py tests/test_gate.py tests/test_message_builder.py tests/test_telegram_client.py -x`
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds (quick), 30 seconds (full)

---

## Per-Task Verification Map

> Filled in by gsd-planner during planning. Each plan's tasks must populate one row here with the test command from `<automated>` block in the task XML. The planner can append additional rows; see RESEARCH.md §Validation Architecture for the 25+ test cases.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-XX-XX | XX | 0 | DELIVER-05 | — | ENV-load via python-dotenv only at CLI entry | unit | `uv run pytest tests/test_delivery_config.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 0 | DELIVER-01 | — | aiogram Bot context-manager session close | unit | `uv run pytest tests/test_telegram_client.py::test_session_closed_on_exit -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 1 | DELIVER-03 | — | Gate composition first-fail-wins (4 checks) | unit | `uv run pytest tests/test_gate.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 1 | DELIVER-02 | — | Ops alert HTML template + escape + truncate | unit | `uv run pytest tests/test_message_builder.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 2 | DELIVER-04 | — | tenacity 3-retry + TelegramRetryAfter outside | unit | `uv run pytest tests/test_telegram_client.py::test_retry_policy -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 2 | DELIVER-01 | — | DeliverStatsBuilder 8-key atomic patch | unit | `uv run pytest tests/test_delivery_stats.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 3 | DELIVER-01..05 | — | delivery_run.py orchestration (gate + send + patch) | integration | `uv run pytest tests/integration/test_delivery_run.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 3 | DELIVER-04 | — | CLI `deliver-run --run-id N` idempotency + --force + --dry-run | integration | `uv run pytest tests/integration/test_cli_deliver.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 4 | DELIVER-01..05 | — | E2E weekly_run amend: gate-pass branch | integration | `uv run pytest tests/integration/test_weekly_run_with_delivery.py::test_business_route -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 4 | DELIVER-02 | — | E2E deliberate-failure: ops-only branch (SC#2) | integration | `uv run pytest tests/integration/test_weekly_run_with_delivery.py::test_ops_only_route -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 4 | cross-cutting | — | Source-lock canary: no summary_builder import in delivery/ | unit | `uv run pytest tests/test_delivery_source_lock.py -x` | ❌ W0 | ⬜ pending |
| 6-XX-XX | XX | 4 | cross-cutting | — | Namespace disjoint canary: 5-way (viled∩goldapple∩match∩report∩deliver=∅) | unit | `uv run pytest tests/test_stats_namespace.py::test_namespace_disjoint_invariant -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Per RESEARCH.md §Validation Architecture, 25+ test cases span 10 test files (8 new + 2 amended). Planner finalizes per-task mapping.*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — add fixtures: `mock_aiogram_bot` (stub Message/message_id), `mock_tg_env` (sets/unsets TG_* vars per test), `synthetic_delivered_run` (Run row with report.* stats populated for gate-pass + gate-fail scenarios)
- [ ] `tests/test_delivery_config.py` — DeliverConfig.from_env + from_pyproject (DELIVER-05)
- [ ] `tests/test_telegram_client.py` — Bot context-manager + tenacity retry + TelegramRetryAfter handling (DELIVER-01 + DELIVER-04)
- [ ] `tests/test_gate.py` — PreSendGate.evaluate_gate first-fail-wins composition (DELIVER-03)
- [ ] `tests/test_message_builder.py` — build_ops_alert HTML template + html.escape + truncate (DELIVER-02)
- [ ] `tests/test_delivery_stats.py` — DeliverStatsBuilder 8-key namespace + atomic patch_stats single call (DELIVER-01)
- [ ] `tests/test_delivery_source_lock.py` — structural canary: `grep -r "summary_builder" src/ga_crawler/delivery/` returns 0
- [ ] `tests/integration/test_delivery_run.py` — orchestrator end-to-end on real SQLite + mock Bot
- [ ] `tests/integration/test_cli_deliver.py` — argparse + idempotency + --force + --dry-run
- [ ] `tests/integration/test_weekly_run_with_delivery.py` — amended main_run.run_weekly: SC#1 (business route) + SC#2 (ops-only route, deliberate failure)
- [ ] `tests/test_stats_namespace.py` — AMEND existing: add `deliver.*` to disjoint-invariant assertion (5-way)
- [ ] `pyproject.toml` — add `aiogram>=3.27,<4.0` to dependencies (Wave 0 single new dep)
- [ ] `.env.example` — create at repo root with `TG_BOT_TOKEN=` / `TG_BUSINESS_CHAT_ID=` / `TG_OPS_CHAT_ID=` placeholders
- [ ] `.gitignore` — verify `.env` excluded (likely already via Phase 1 `.env.local` pattern; double-check)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Telegram bot setup via @BotFather | DELIVER-05 | External service interaction (creates real bot, requires Telegram account); off-CI; Phase 7 README documents | (1) Open Telegram → @BotFather → `/newbot` → name + username → save token to `.env`. (2) Create group chat, add bot, send `/get_id` to @userinfobot to get business_chat_id. (3) Repeat for ops chat. (4) Manual smoke: `uv run python -m ga_crawler deliver-run --run-id 1` against test-run. |
| Production smoke on first weekly cron-run | DELIVER-01..05 | First real-Telegram delivery happens in Phase 7 cron deployment | Phase 7 deliverable. Manual approval after first Sunday weekly run lands in business chat. |

*All other phase behaviors have automated verification via the per-task map.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
