---
phase: 06-telegram-delivery
verified: 2026-05-12T00:00:00Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
requirements_satisfied: 5/5
test_suite: 746 passed / 1 skipped / 0 failed
---

# Phase 6 Verification

**Phase Goal:** Successful runs deliver Excel + summary to the business chat; failed/incomplete runs alert only ops chat; pre-send sanity-gate guarantees a broken report cannot reach the pricing team.

**Verified:** 2026-05-12
**Status:** VERIFIED
**Re-verification:** No — initial verification

## Status

PASSED. Все 4 Success Criteria подтверждены кодом + тестами. Все 5 требований DELIVER-01..05 имеют рабочую реализацию и регрессионное покрытие. Все архитектурные инварианты (source-lock, 5-way namespace disjoint, load_dotenv isolation, aiogram isolation) подтверждены структурными канарейками. Тестовый набор: 746 passed / 1 skipped / 0 failed (единственный skip — pre-existing Phase 3 artificial mutation, не относится к Phase 6).

## Success Criteria

### SC#1 — On `runs.status='success'` AND gate-pass: business chat gets caption + xlsx; ops chat gets nothing

**Status:** VERIFIED

**Evidence:**

- **Composition wired in**: `src/ga_crawler/runners/main_run.py:381-404` — блок `if r_result.status == "success" and r_result.xlsx_path:` вызывает `run_delivery_phase` ПОСЛЕ reporter и ПЕРЕД final `run_writer.finalize` (D-615 invariant — Step 9 после reporter перед Step 11 finalize).
- **Async send (business route)**: `src/ga_crawler/runners/delivery_run.py:519-559` (`_send_async` функция, ветка `if route == "business"`) — выполняет `send_document_with_policy(bot, business_chat_id, xlsx_full_path, caption)` через `FSInputFile(Path)` (D-601). На < 1024 символов caption встроен в send_document; на > 1024 — preceded by separate `send_message`.
- **E2E test**: `tests/integration/test_weekly_run_with_delivery.py::test_sc1_happy_path_business_route` (строки 186-247) — patched_open_bot + mock_aiogram_bot; assertions:
  - `mock_aiogram_bot.send_document.call_count == 1`
  - `str(doc_chat_id) == mock_tg_env["business_chat_id"]`
  - Ops chat: `for call in send_message.call_args_list: assert str(chat_id) != mock_tg_env["ops_chat_id"]`
  - `result.delivery_status == "delivered_business"`
  - `result.delivery_route == "business"`

### SC#2 — On `runs.status != 'success'` OR gate-fail: ops chat gets alert with run_id + failed phase + error; business chat gets nothing

**Status:** VERIFIED

**Evidence:**

- **Gate composition (4-check first-fail-wins, D-604)**: `src/ga_crawler/delivery/gate.py:50-134` — `evaluate_gate(engine, run_writer, run_id)`:
  - Check 1: `read_run_status(engine, run_id) != "success"` → reason `upstream_status_<status>` (line 66-79). Reuses `matcher.strict_key.read_run_status` per D-411.
  - Check 2: `not stats.get("report.xlsx_path")` → reason `no_xlsx_in_stats` (line 84-97).
  - Check 3: `not stats.get("report.size_guard_passed", False)` → reason `xlsx_oversize` (line 100-113) — D-515 cascade from Phase 5.
  - Check 4: `not str(stats.get("report.summary_text", "")).strip()` → reason `empty_summary_text` (line 116-129).
  - On any fail: `GateDecision(route="ops_only", ...)` returned, short-circuits.
- **Ops alert template (D-610 single-template)**: `src/ga_crawler/delivery/message_builder.py:85-138` — `build_ops_alert(...)` принимает `run_id`, `reason_key`, `run_status`, `gate_failed_check`, `viled_count`, `goldapple_count`, `match_count`, `match_rate`, `error_short`. Тело шаблона включает `🚨 Weekly run #{run_id}`, `Run status: <code>{run_status}</code>`, `Gate failure: <code>{gate_failed_check}</code>`, `Error: <pre>{error_short}</pre>` (когда непустой).
- **E2E test (deliberate-failure)**: `tests/integration/test_weekly_run_with_delivery.py::test_sc2_deliberate_failure_size_guard_trips_ops_alert` (строки 301-404) — патчит reporter возвращать `size_guard_passed=False`. Assertions:
  - `result.delivery_status == "delivered_ops_only"`
  - `result.delivery_route == "ops_only"`
  - `send_message.call_count == 1` AND `send_document.call_count == 0`
  - `str(alert_chat_id) == mock_tg_env["ops_chat_id"]`
  - `str(result.run_id) in alert_text` — run_id присутствует в теле.
- **Bonus test**: `test_sc2_viled_below_sanity_no_delivery_invoked` (строки 255-293) — при viled-sanity-fail доставка вовсе не вызывается, оба чата получают 0 сообщений.

### SC#3 — Bot config loaded from ENV; missing vars → ops alert OR fail-loud crash

**Status:** VERIFIED

**Evidence:**

- **ENV-only loading (D-611)**: `src/ga_crawler/delivery/config.py:74-100` — `DeliverEnvConfig.from_env()` использует ТОЛЬКО `os.getenv("TG_BOT_TOKEN")`, `os.getenv("TG_BUSINESS_CHAT_ID")`, `os.getenv("TG_OPS_CHAT_ID")`. Empty-string normalized to None.
- **load_dotenv() isolation (RESEARCH caveat #4)**: подтверждено grep — единственное вхождение `load_dotenv` в `src/ga_crawler/` это `cli.py:257` (внутри `_cmd_deliver`). В `delivery/` модулях вхождений 0. Канарейка `tests/test_delivery_source_lock.py::test_load_dotenv_not_in_delivery_module` (строки 95-109) ловит регрессии.
- **Asymmetric handling (D-611)**: `src/ga_crawler/runners/delivery_run.py`:
  - **TG_BOT_TOKEN missing** (line 246-258): exit без I/O, `_build_stats_skip_path(delivery_status="skipped_no_credentials", last_error="missing_env_TG_BOT_TOKEN")`. CLI exit code 3 (cli.py:321-322).
  - **TG_BUSINESS_CHAT_ID missing on business route** (line 379-404): degrade route to ops_only + переcборка alert с `reason_key="missing_env_TG_BUSINESS_CHAT_ID"`.
  - **TG_OPS_CHAT_ID missing on business route** (line 405-413): warn + proceed (business send ok).
  - **TG_OPS_CHAT_ID missing on ops route** (line 414-422): `skipped_no_credentials` (последняя баррикада).
- **Tests**:
  - `tests/integration/test_delivery_run.py` (Test 5c per Plan 06-04) — 4 degradation scenarios на отсутствие chat_id.
  - `tests/integration/test_cli_deliver.py` — CLI exit code 3 на отсутствие TG_BOT_TOKEN.
  - `tests/test_delivery_config.py` (12 tests) — все 4 поля + дефолты + empty-string normalization.

### SC#4 — Telegram rate-limit / retry-after honored; if unreachable after retries → report on disk + marked undelivered

**Status:** VERIFIED

**Evidence:**

- **wait_chain (NOT wait_exponential)**: `src/ga_crawler/delivery/telegram_client.py:140-152` — `wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))` — точно по RESEARCH caveat #2. Grep подтверждает `wait_exponential` в файле = 0 вхождений.
- **TelegramRetryAfter OUTSIDE tenacity**: `src/ga_crawler/delivery/telegram_client.py:155-196` — `_send_with_retry_after_loop` ловит `TelegramRetryAfter`, делает `asyncio.sleep(e.retry_after)`, повторяет до `max_retry_after_iterations=3`.
- **Fail-fast classes excluded (Pitfall A)**: `_RETRY_TYPES = (TelegramNetworkError, TelegramServerError)` (line 91-94). `TelegramBadRequest`, `TelegramForbiddenError`, `TelegramNotFound`, `TelegramUnauthorizedError` каждый имеет outer `except` отдельно и НЕ ретраит (lines 230-242 + 300-311).
- **D-605 invariant — report remains on disk**: `src/ga_crawler/runners/delivery_run.py:438-452` — defensive outer try/except на `asyncio.run(_send_async(...))` мапит любой Exception в `delivery_status="undelivered_telegram_unreachable"`, НЕ raise. `_send_async` сам ловит aiogram exceptions и возвращает `_AsyncSendResult(delivery_status="undelivered_telegram_unreachable", ...)`.
- **D-605 E2E test**: `tests/integration/test_weekly_run_with_delivery.py::test_d605_telegram_unreachable_run_status_unchanged` (строки 412-506):
  - Подменяет `send_document` на 3x raising `TelegramNetworkError`
  - Подменяет `_build_retry_decorator` на fast variant (0/0/0)
  - Assert: `result.status == "success"` (D-605 КЛЮЧЕВАЯ инварианта)
  - Assert: `result.delivery_status == "undelivered_telegram_unreachable"`
  - Assert: DB `runs.status == "success"` (storage-side)
  - Assert: `xlsx_full.exists()` — xlsx остался на диске для manual recovery через `deliver-run --run-id N`
- **CLI recovery**: `python -m ga_crawler deliver-run --run-id N` — D-608 идемпотентный standalone subcommand (cli.py:241-325).

## Requirement Coverage

| Requirement | Source Plan | Implementation File | Test |
|-------------|-------------|---------------------|------|
| DELIVER-01 (Telegram delivery: send xlsx + summary on success) | 06-02, 06-03, 06-04, 06-05 | `delivery/telegram_client.py` (FSInputFile + send_document); `delivery/message_builder.py:141-154` (business_caption split); `runners/delivery_run.py:519-559` (business branch); `runners/main_run.py:381-404` (composition) | `test_weekly_run_with_delivery.py::test_sc1_happy_path_business_route` |
| DELIVER-02 (Ops alert on failure: run_id + phase + error) | 06-02 | `delivery/message_builder.py:85-138` (build_ops_alert D-610 single-template + Pitfall A html.escape + Pitfall E Asia/Almaty tz); golden file `tests/fixtures/delivery/ops-alert-templates.txt` | `test_message_builder.py` (22 tests); `test_weekly_run_with_delivery.py::test_sc2_deliberate_failure_size_guard_trips_ops_alert` |
| DELIVER-03 (Pre-send sanity-gate: 4-check first-fail-wins) | 06-03 | `delivery/gate.py:50-134` (evaluate_gate REUSES `matcher.strict_key.read_run_status` D-411 + D-515 size_guard cascade) | `test_gate.py` (10 tests covering 4 fail reasons + happy path) |
| DELIVER-04 (Retry/backoff + undelivered marking) | 06-03, 06-04, 06-05 | `delivery/telegram_client.py:140-152` (wait_chain 5/15/45); `:155-196` (TelegramRetryAfter outside-tenacity); `runners/delivery_run.py:438-452` (D-605 mapping to undelivered_telegram_unreachable) | `test_telegram_client.py` (19 tests covering retry/fail-fast/retry-after); `test_weekly_run_with_delivery.py::test_d605_telegram_unreachable_run_status_unchanged` |
| DELIVER-05 (ENV-based bot config + asymmetric handling) | 06-01, 06-02, 06-04 | `.env.example` (3 TG_* keys); `delivery/config.py:74-100` (DeliverEnvConfig.from_env pure os.getenv); `runners/delivery_run.py:246-258` (TG_BOT_TOKEN fail-loud); `:379-422` (chat_id asymmetric degradation); `cli.py:257-271` (load_dotenv ONLY here) | `test_delivery_config.py` (12 tests); `test_cli_deliver.py` (8 tests); `test_delivery_source_lock.py::test_load_dotenv_not_in_delivery_module` |

**Все 5 требований Done.** REQUIREMENTS.md строки 174-178 содержат закрывающие аннотации с per-plan citations.

## Architectural Invariants

| Invariant | Mechanism | Status | Evidence |
|-----------|-----------|--------|----------|
| **Source-lock**: delivery/ does NOT import reporter builders (D-514 inverted) | Structural canary | VERIFIED | `tests/test_delivery_source_lock.py::test_no_summary_builder_import_in_delivery`; grep on `summary_builder|excel_builder|reporter\.queries|reporter\.archive` in `src/ga_crawler/delivery/` returns 0 hits |
| **5-way namespace disjoint** (viled ∩ goldapple ∩ match ∩ report ∩ deliver = ∅) | DELIVER_STATS_KEYS frozen 8-tuple + 5-way test | VERIFIED | `delivery/stats.py:23-32` (8 keys all prefixed `deliver.`); `tests/unit/test_stats_namespace_five_way.py::test_five_way_namespaces_disjoint` |
| **aiogram isolation**: imports ONLY in `delivery/telegram_client.py` | Structural canary line-by-line scan | VERIFIED | Grep on `^from aiogram\|^import aiogram` in `src/ga_crawler/delivery/` returns 5 hits ALL on `telegram_client.py:63-75`; `test_delivery_source_lock.py::test_aiogram_imports_only_in_telegram_client` (strips inline comments) |
| **load_dotenv ONLY in `cli.py::_cmd_deliver`** (RESEARCH caveat #4) | Grep canary | VERIFIED | `load_dotenv` runtime call appears at `cli.py:271` only; 0 hits in `src/ga_crawler/delivery/`; `test_delivery_source_lock.py::test_load_dotenv_not_in_delivery_module` |
| **D-616 5 return-sites with delivery fields** | Grep canary | VERIFIED | `grep delivery_status=delivery_status` returns 5; `grep delivery_route=delivery_route` returns 5 (lines 217-218, 268-269, 323-324, 442-443, 483-484 in main_run.py) |
| **D-607 Pitfall 6 single patch_stats** in delivery_run | Static call-site count | VERIFIED | `grep patch_stats(run_id,` in `runners/delivery_run.py` returns exactly 2 (1 in `_build_stats_skip_path` for skip paths, 1 in main flow Step 7) |
| **D-615 composition order**: `run_delivery_phase` AFTER reporter, BEFORE final finalize | Code review of main_run.py | VERIFIED | `main_run.py:343-404` — reporter at line 350, delivery composition at line 381-404, final `run_writer.finalize(run_id, status="success")` at line 417 |
| **D-603 wait_chain (NOT wait_exponential)** per RESEARCH caveat #2 | Source code | VERIFIED | `telegram_client.py:149` `wait=wait_chain(wait_fixed(5), wait_fixed(15), wait_fixed(45))`; grep on `wait_exponential` in telegram_client.py = 0 hits |
| **Phase boundary respect**: no edits to reporter/matcher/fetchers/normalizers/parsers/alias/enumeration | git diff of frozen packages | VERIFIED | `git diff --name-only 5396317..HEAD` shows changes ONLY in `delivery/`, `runners/main_run.py` (composition), `runners/delivery_run.py` (new), `cli.py` (subcommand), `pyproject.toml` (aiogram + namespace), `.env.example`, tests/ |
| **No schema/alembic changes** (D-220 preserved — delivery only appends `deliver.*` via patch_stats) | git diff | VERIFIED | No changes to `storage/` package; no alembic migration in diff |

## Test Suite Health

```
746 passed, 1 skipped, 181 warnings in 127.42s
```

- **Total collected:** 747 tests (`uv run pytest --co`)
- **Passed:** 746
- **Skipped:** 1 (Phase 3 pre-existing artificial-mutation skip — not Phase 6 related, confirmed in 06-05-SUMMARY.md)
- **Failed:** 0
- **Phase 6-specific suites:** 106 tests across 8 files (test_weekly_run_with_delivery.py 6, test_delivery_run.py 19, test_delivery_source_lock.py 4, test_gate.py 10, test_telegram_client.py 19, test_message_builder.py 22, test_delivery_stats.py 14, test_delivery_config.py 12) — all GREEN

Phase 2-5 frozen suites pass unchanged. No regressions in viled/goldapple/matcher/reporter test suites after Phase 6 wiring.

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 6 unit + integration test suites | `uv run pytest tests/integration/test_weekly_run_with_delivery.py tests/integration/test_delivery_run.py tests/test_delivery_source_lock.py tests/test_gate.py tests/test_telegram_client.py tests/test_message_builder.py tests/test_delivery_stats.py tests/test_delivery_config.py` | 106 passed | PASS |
| Full test suite regression | `uv run pytest -q` | 746 passed, 1 skipped | PASS |
| Test collection (no import errors) | `uv run pytest --co` | 747 tests collected | PASS |
| aiogram isolation grep | `grep "^from aiogram\|^import aiogram" src/ga_crawler/delivery/*.py` | 5 hits, all in telegram_client.py | PASS |
| load_dotenv isolation grep | `grep "load_dotenv" src/ga_crawler/delivery/*.py` | 0 hits | PASS |
| source-lock grep | `grep "summary_builder\|excel_builder" src/ga_crawler/delivery/*.py` | 0 hits | PASS |
| D-616 invariant | `grep "delivery_status=delivery_status" main_run.py` | 5 hits | PASS |
| D-607 single patch_stats | `grep "patch_stats(run_id," delivery_run.py` | 2 hits (per Plan 06-04 documented) | PASS |

## Findings

Нет блокеров. Нет gaps. Phase 6 — clean close.

Минорные наблюдения (информационные, НЕ влияют на проходимость):

1. **DeprecationWarning** про SQLite datetime adapter из SQLAlchemy (Python 3.12) — 181 warnings в общем прогоне. Уже обработано в `delivery_run.py:121-140` через `_coerce_started_at` helper. Полная миграция на explicit adapters не относится к Phase 6 scope — Phase 2-5 наследуют те же warnings.

2. **B5 fix в `06-CONTEXT.md` D-603** (commit 45e327d): `wait_exponential` → `wait_chain` в документации синхронизировано с production code per RESEARCH caveat #2. История документа теперь согласуется с реализацией.

## VERIFICATION PASSED

Phase goal achieved. Successful runs route `xlsx + summary` to business chat; failed/gate-fail runs route `ops alert` to ops chat; pre-send 4-check gate (D-604) enforces the boundary; D-605 invariant guarantees `runs.status='success'` even on Telegram unreachable so xlsx stays on disk for manual recovery via `deliver-run --run-id N`. All 5 DELIVER-* requirements Done. All architectural invariants (source-lock, 5-way namespace, aiogram isolation, load_dotenv isolation, D-616 5 return-sites, D-607 single patch_stats, D-615 composition order) verified by structural canaries. Phase boundary respected — zero edits to frozen Phase 2-5 packages, no schema migrations.

Phase 7 (Scheduler + Observability Hardening) unblocked.

---

_Verified: 2026-05-12_
_Verifier: Claude (gsd-verifier, Opus 4.7)_
